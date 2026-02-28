# Production Commerce Upgrade - Implementation Guide

## Overview

Complete implementation of production-grade order lifecycle with:
- **Stock Reservation System**: 15-min TTL checkout reservations, auto-release on expiry
- **Invoice Management**: ZATCA-compliant Saudi Arabia e-invoices with QR codes
- **Returns & Exchanges**: Complete RMA workflow with condition assessment and partial refunds
- **Refund Processing**: Payment gateway integration with audit trail
- **Extended Order States**: New states for returned, partially_refunded, refunded

## Architecture

### Models

All new models in `apps/orders/models_extended.py`:

```
StockReservation
├─ Reservation created at checkout
├─ 15-min TTL, extends to 30-min after payment
├─ Auto-releases on expiry via Celery task
└─ Prevents overselling by reserving inventory capacity

Invoice
├─ Generated from Order after payment
├─ Sequential numbering per tenant/store (INV-<T>-<S>-<SEQ>)
├─ ZATCA compliance with QR codes and SHA256 hashing
├─ Supports partial invoice for split shipments
└─ PDF generation with reportlab

InvoiceLineItem
├─ Line items from OrderItems
├─ Tax calculation (15% Saudi VAT default)
└─ Supports partial refunds per line item

RMA (Return Merchandise Authorization)
├─ Complete workflow: requested→approved→in_transit→received→inspected→completed
├─ Support for exchanges (is_exchange + exchange_product)
├─ Return tracking with carrier/tracking_number
└─ Integration with RefundTransaction

ReturnItem
├─ Individual items in RMA
├─ Condition assessment (as_new, used, damaged, defective)
└─ Per-item refund amount for partial refunds

RefundTransaction
├─ Refund request tracking with audit trail
├─ Payment gateway integration (gateway_response JSON)
├─ Status flow: initiated→processing→completed/failed
└─ Links to Order and RMA for context
```

### Services

#### StockReservationService (`stock_reservation_service.py`)

```python
# Reserve stock at checkout (15-min TTL)
reservation = service.reserve_stock(order_item, qty, tenant_id, store_id)

# Confirm after payment (extends TTL to 30-min)
confirmed = service.confirm_reservation(reservation)

# Release when order cancels
released = service.release_reservation(reservation, reason="order_cancelled")

# Release when order ships
released = service.release_on_shipment(order_item, shipped_qty)

# Auto-release expired (background task)
result = service.auto_release_expired()
```

#### InvoiceService (`invoice_service.py`)

```python
# Create invoice from paid order
invoice = service.create_invoice_from_order(order)

# Get next sequential number
number = service.get_next_invoice_number(tenant_id, store_id)
# Returns: INV-<TENANT>-<STORE>-<SEQUENCE>

# Issue invoice and generate ZATCA hash
issued = service.issue_invoice(invoice, previous_hash=None)

# Generate PDF
pdf_bytes = service.generate_pdf(invoice)

# Generate ZATCA QR code with compliance data
qr_code_base64 = service.generate_zatca_qr_code(invoice)
```

#### ReturnsService (`returns_service.py`)

```python
# Request RMA
rma = service.request_rma(
    order=order,
    items=[{'order_item': oi, 'quantity': 2, 'reason': 'defective'}],
    reason='defective',
    description='Product not working',
    is_exchange=False,
)

# Approve RMA
approved = service.approve_rma(rma, comment="Approved")

# Track return shipment
in_transit = service.track_return_shipment(rma, carrier='FedEx', tracking='1234567')

# Mark as received at warehouse
received = service.receive_return(rma)

# Inspect and assess condition
inspected = service.inspect_return(rma, inspections=[
    {
        'return_item_id': 123,
        'condition': 'damaged',
        'refund_amount': Decimal('80.00'),
    }
])

# Complete RMA and process refund
completed = service.complete_rma(rma, refund_method='original')
```

#### RefundsService (`returns_service.py`)

```python
# Request refund (creates RefundTransaction)
refund = service.request_refund(
    order=order,
    amount=Decimal('100.00'),
    reason='customer_request',
    rma=rma,  # Optional, for return context
)

# Process refund via payment gateway
refund = service.process_refund(refund, gateway_client)

# Mark as completed
completed = service.complete_refund(refund)

# Handle failed refunds
failed = service.fail_refund(refund, error_msg='Declined by gateway')
```

#### OrderLifecycleService (Extensions)

```python
# New state transitions enabled:
order.status = 'delivered'
service.transition(order, 'returned')  # ← NEW

order.status = 'returned'
service.transition(order, 'partially_refunded')  # ← NEW
service.transition(order, 'refunded')  # ← NEW

order.status = 'partially_refunded'
service.transition(order, 'refunded')  # ← NEW

# State diagram:
# pending → paid → processing → shipped → delivered → completed
#                                                   ↘ returned → partially_refunded → refunded
# cancelled (from pending/paid)
```

## Integration Steps

### 1. Run Migration

```bash
python manage.py migrate orders
```

This creates:
- StockReservation table
- Invoice + InvoiceLineItem tables
- RMA + ReturnItem tables
- RefundTransaction table
- Updates Order model with shipping_charge field

### 2. Update Django Admin

Register new models by adding to `apps/orders/admin.py`:

```python
from wasla.apps.orders.admin_commerce import (
    InvoiceAdmin,
    RMAAdmin,
    ReturnItemAdmin,
    RefundTransactionAdmin,
    StockReservationAdmin,
)
```

Or copy implementations from `admin_commerce.py` into your existing `admin.py`.

### 3. Add API Endpoints

Register viewsets in `config/urls.py`:

```python
from rest_framework.routers import DefaultRouter
from wasla.apps.orders.views.commerce import (
    InvoiceViewSet,
    RMAViewSet,
    RefundTransactionViewSet,
    StockReservationViewSet,
)

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'rmas', RMAViewSet, basename='rma')
router.register(r'refunds', RefundTransactionViewSet, basename='refund')
router.register(r'stock-reservations', StockReservationViewSet, basename='stock_reservation')

urlpatterns = [
    path('api/v1/orders/', include(router.urls)),
]
```

### 4. Configure Celery Tasks

Add to `config/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Release expired stock reservations every 5 minutes
    'auto-release-expired-reservations': {
        'task': 'wasla.apps.orders.tasks.auto_release_expired_stock_reservations',
        'schedule': crontab(minute='*/5'),
    },
    
    # Cleanup very old abandoned reservations daily at 3 AM
    'cleanup-abandoned-reservations': {
        'task': 'wasla.apps.orders.tasks.cleanup_abandoned_reservations',
        'schedule': crontab(hour=3, minute=0),
    },
}
```

### 5. Install Dependencies

```bash
pip install reportlab qrcode[pil] Pillow
```

- `reportlab`: PDF generation
- `qrcode`: QR code generation for ZATCA
- `Pillow`: Image processing for QR codes

### 6. Merchant Checkout Flow with Stock Reservation

```python
from wasla.apps.orders.services.order_service import OrderService
from wasla.apps.orders.services.stock_reservation_service import StockReservationService

# 1. Create order at start of checkout
order = OrderService().create_order(
    store=store,
    customer_email='customer@example.com',
)

# 2. Add items to order
for item_data in checkout_items:
    order_item = OrderItem.objects.create(
        order=order,
        product=product,
        quantity=qty,
        unit_price=price,
    )

# 3. Reserve stock (15-min TTL)
reservation_service = StockReservationService()
for order_item in order.items.all():
    try:
        reservation = reservation_service.reserve_stock(
            order_item=order_item,
            quantity=order_item.quantity,
            tenant_id=order.tenant_id,
            store_id=order.store_id,
        )
    except ValueError:
        # Out of stock - reject order
        return Response({'error': 'Item out of stock'}, status=400)

# 4. Process payment
payment_result = payment_gateway.charge(
    amount=order.total_amount,
    currency='SAR',
    customer=order.customer_email,
    order_id=order.id,
)

if payment_result['success']:
    # 5. Confirm reservations (extends to 30-min)
    for order_item in order.items.all():
        try:
            reservation = order_item.stock_reservation
            reservation_service.confirm_reservation(reservation)
        except StockReservation.DoesNotExist:
            pass  # Already released
    
    # 6. Mark order as paid
    order.status = 'paid'
    order.save()
    
    # 7. Generate invoice
    invoice_service = InvoiceService()
    invoice = invoice_service.create_invoice_from_order(order)
    issued_invoice = invoice_service.issue_invoice(invoice)
    
    return Response({
        'order_id': order.id,
        'invoice_number': issued_invoice.invoice_number,
    })
else:
    # Payment failed - release reservations
    for order_item in order.items.all():
        try:
            reservation = order_item.stock_reservation
            reservation_service.release_reservation(
                reservation,
                reason='payment_failed'
            )
        except StockReservation.DoesNotExist:
            pass
    
    raise PaymentException(f"Payment failed: {payment_result['error']}")
```

## Fulfillment Flow

```python
# 1. When preparing to ship, create shipment
shipment = Shipment.objects.create(
    order=order,
    status='pending',
)

# Add items to shipment (can be partial)
for item in items_to_ship:
    ShipmentItem.objects.create(
        shipment=shipment,
        order_item=item['order_item'],
        quantity=item['quantity'],
    )

# 2. Release stock reservations for shipped items
reservation_service = StockReservationService()
for shipment_item in shipment.items.all():
    order_item = shipment_item.order_item
    try:
        reservation_service.release_on_shipment(
            order_item,
            shipment_item.quantity,
        )
    except StockReservation.DoesNotExist:
        pass  # Already released elsewhere

# 3. Update shipment status
shipment.status = 'shipped'
shipment.tracking_number = tracking_num
shipment.carrier = carrier_name
shipment.save()

# 4. Update order status (can be partial)
if all_items_shipped:
    OrderLifecycleService().transition(order, 'shipped')

# 5. Send notification to customer
from wasla.apps.orders.tasks import send_order_notification
send_order_notification.delay(
    order.id,
    'order_shipped',
    tracking_number=tracking_num,
)
```

## Returns Flow

```python
# 1. Customer requests return
returns_service = ReturnsService()
rma = returns_service.request_rma(
    order=order,
    items=[
        {
            'order_item': order.items.get(id=item_id),
            'quantity': qty,
            'reason': 'defective',
        }
    ],
    reason='defective',
    description='Product is broken',
)

# 2. Admin reviews and approves RMA
rma = returns_service.approve_rma(rma, comment="Approved")

# 3. Customer ships return
rma = returns_service.track_return_shipment(
    rma,
    carrier='FedEx',
    tracking_number='1234567890',
)

# 4. Warehouse receives return
rma = returns_service.receive_return(rma)

# 5. Warehouse inspects items
rma = returns_service.inspect_return(
    rma,
    inspections=[
        {
            'return_item_id': return_item.id,
            'condition': 'damaged',
            'refund_amount': Decimal('80.00'),  # Partial refund due to damage
        }
    ],
)

# 6. Complete RMA and process refund
rma = returns_service.complete_rma(rma, refund_method='original')

# 7. Check refund status
refund = rma.refunds.first()
if refund.status == 'completed':
    customer_refunded = True
elif refund.status == 'failed':
    # Retry refund
    from wasla.apps.orders.tasks import process_refund
    process_refund.delay(refund.id)
```

## Testing

Run integration tests:

```bash
python manage.py test wasla.apps.orders.tests.test_commerce_upgrade
```

Coverage includes:
- Stock reservation and expiry
- Invoice generation and numbering
- ZATCA QR code compliance
- Complete RMA workflows
- Refund processing
- Tenant isolation verification

## Configuration

### ZATCA Compliance (Saudi Arabia)

Default tax rate: 15% (configurable per invoice)

For compliance, ensure:
- Seller VAT ID is set on Store model
- Invoice has seller address and bank details
- Tax amount is calculated as subtotal × 15%

### Stock Reservation TTL

- **Checkout**: 15 minutes from order creation
- **After Payment**: Extends to 30 minutes for fulfillment
- **Auto-release**: Every 5 minutes via Celery beat

Customize in `StockReservationService.reserve_stock()`:
```python
expires_at = timezone.now() + timedelta(minutes=15)  # Change this
```

### Refund Processing

Implement payment gateway client in `wasla.apps.payments.gateway.PaymentGatewayClient`:

```python
class PaymentGatewayClient:
    def request_refund(self, refund_id, amount, reason):
        """Submit refund request to gateway"""
        # Implementation specific to your gateway
        return {
            'gateway_refund_id': '...',
            'status': 'processing',
        }
```

Then update `RefundsService.process_refund()` to use your client.

## Monitoring & Observability

### Celery Tasks

Monitor task queue:
```bash
celery -A wasla.config inspect active
celery -A wasla.config inspect scheduled
```

### Stock Reservations Dashboard

Django admin shows:
- Real-time expiry countdowns
- Total reserved vs available inventory
- Failed/expired reservations for cleanup

### Invoice Audit Trail

All invoices logged with:
- ZATCA hash chain for compliance
- QR code generation timestamp
- PDF generation status
- Payment receipt date

### RMA Metrics

Track in admin:
- Approval rate (approved/requested)
- Resolution time (requested → completed)
- Refund amount distribution
- Return reason breakdown

## Troubleshooting

### Stock Reservation Issues

**Problem**: Inventory reserved_quantity not decreasing
**Solution**: 
1. Check Celery beat is running: `celery -A wasla.config beat`
2. Check expired reservations: Django admin → Stock Reservations → Expired
3. Manually release in admin or via API

**Problem**: Reservation expires before payment confirmation
**Solution**: Extend TTL in StockReservationService (currently 15 min)

### Invoice Generation Errors

**Problem**: "No module named reportlab"
**Solution**: `pip install reportlab qrcode[pil] Pillow`

**Problem**: ZATCA QR code not generating
**Solution**: Verify seller_vat_id and seller_name are set on Store

### RMA Workflow Stuck

**Problem**: RMA won't transition to next state
**Solution**: Check status field against allowed transitions in ReturnsService

**Problem**: Refund not processing
**Solution**: Check payment gateway client implementation and gateway_response JSON in RefundTransaction

## Performance Optimization

### Database Indexes

All models include optimized indexes:
- StockReservation: (store_id, status), (tenant_id, expires_at)
- Invoice: (store_id, -issue_date), (tenant_id, status)
- RMA: (store_id, status), (order_id)

### Batch Operations

For bulk operations, use Django admin actions:
- Release expired reservations
- Issue multiple invoices
- Approve RMAs in bulk
- Retry failed refunds

### Async Processing

Use Celery tasks for slow operations:
- PDF generation: `generate_invoice_pdf.delay(invoice_id)`
- Refund processing: `process_refund.delay(refund_id)`
- Notifications: `send_order_notification.delay(order_id, event)`

## Next Steps

1. ✅ Models created (StockReservation, Invoice, RMA, RefundTransaction)
2. ✅ Services implemented (StockReservation, Invoice, Returns/Refunds)
3. ✅ Migration created (0003_production_commerce_upgrade.py)
4. ✅ Integration tests written (test_commerce_upgrade.py)
5. ✅ API endpoints defined (views/commerce.py)
6. ✅ Serializers created (serializers_commerce.py)
7. ✅ Admin interfaces registered (admin_commerce.py)
8. ✅ Celery tasks configured (tasks.py)
9. **To Do**: Create payment gateway integration examples
10. **To Do**: Create email notification templates
11. **To Do**: Add frontend UI for customer RMA portal

## Support

For issues or questions:
1. Check Django admin for data state
2. Review integration tests for usage patterns
3. Check Celery task logs for async errors
4. Verify tenant_id and store_id on all models (tenant isolation)
