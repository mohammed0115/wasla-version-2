# Production Commerce Quick Reference

## 🏃 Quick Start

### 1. Reserve Stock (at checkout)
```python
from apps.orders.services.stock_management_service import StockManagementService

reservation = StockManagementService.reserve_order_items(order_item)
# Status: "reserved", expires in 30 mins
```

### 2. Confirm Stock (at payment success)
```python
StockManagementService.confirm_reservation(reservation)
# Status: "confirmed", expires in 30 days (extended)
```

### 3. Generate Invoice
```python
from apps.orders.services.invoice_service import InvoiceService

invoice = InvoiceService.generate_invoice(order)
# Creates: INV-TENANT-2026-0001 with PDF
```

### 4. Create Partial Shipment
```python
from apps.shipping.services import ShippingService
from apps.orders.models import ShipmentLineItem

shipment = ShippingService.create_shipment(order, carrier="dhl")
ShipmentLineItem.objects.create(
    shipment=shipment,
    order_item=order_item,
    quantity_shipped=5  # Can ship 5 out of 10
)
```

### 5. Create Return (RMA)
```python
from apps.orders.models import ReturnMerchandiseAuthorization as RMA
from apps.orders.models import ReturnItem

rma = RMA.objects.create(
    order=order,
    rma_number="RMA-2026-001",
    reason="defective"
)
ReturnItem.objects.create(
    rma=rma,
    order_item=order_item,
    quantity_returned=1,
    condition="defective"
)
```

### 6. Process Refund
```python
from apps.orders.services.refund_service import RefundService

# For individual refund
refund = RefundService.initiate_refund(order, amount=Decimal("50.00"))
RefundService.process_refund(refund)

# For RMA (processes all approved items)
refunds = RefundService.process_rma_refund(rma)
```

---

## 📊 State Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ORDER LIFECYCLE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│     pending ──────────────────┐                            │
│       │                       │ (cancel)                   │
│       ├─ (pay)                │                            │
│       └──────> paid ────────┐ │                            │
│                  │          │ │                            │
│                  ├─ (process)   │                          │
│                  └─> processing ─┤                         │
│                       │          │                         │
│                       ├─ (ship)  │                         │
│                       └─> shipped ─┤                       │
│                            │       │                       │
│                            ├─ (deliver)                    │
│                            ├─> delivered ──────┐           │
│                            │                   │           │
│                            │               ┌───┤           │
│                            │               │   │ (return)  │
│                            └─> completed   │   │           │
│                                            │   │           │
│                                            └──>└> returned │
│                                                 │          │
│                                          ┌──────┤          │
│                                          │ (partial refund)
│                                          │      │          │
│                                    ┌─────┘      │          │
│                                    │    partially_refunded │
│                                    │            │          │
│                              ┌─────┤            │ (full)   │
│                              │    refunded ◇    │          │
│                              └──────────────────┘          │
│                                                             │
│          cancelled ◇                                        │
│          (from pending/paid)                               │
│                                                             │
│  ◇ = Terminal state                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 Stock Reservation States

```
┌─────────────┐
│  reserved   │ ◄──────────── StockMgmt.reserve_order_items()
│ (30 mins)   │              (At: checkout)
└─────────────┘
      │
      │ StockMgmt.confirm_reservation()
      │ (At: payment success)
      │
┌─────────────┐
│ confirmed   │ ◄──────────── Extended to 30 days
│ (30 days)   │              (At: payment success)
└─────────────┘
      │
      │ StockMgmt.release_reservation()
      │ (At: order cancel OR payment timeout)
      │
┌─────────────┐
│  released   │ ◄──────────── Stock freed
│ (terminal)  │ (At: Any time after release requested)
└─────────────┘
```

---

## 💰 Refund Flow

```
Order Placed
    │
    ├─ StockMgmt.reserve() ─────────────┐
    │                                    │
    └─ Payment → Order.status = "paid"   │
              └─ StockMgmt.confirm() ◄──┘
              └─ Invoice.generate()
    
[Customer wants to return]
    │
    ├─ RMA.create(reason="defective")
    └─ ReturnItem.create(qty=1)
    
[Admin approves return]
    │
    └─ RefundService.process_rma_refund(rma)
            │
            ├─ RefundService.initiate_refund()
            │       └─ RefundTransaction.create()
            │
            ├─ RefundService.process_refund()
            │       └─ PaymentOrchestrator.refund_payment()
            │           ├─ Tap.refund() OR
            │           └─ Stripe.refund()
            │
            ├─ Order.refunded_amount += amount
            │
            └─ Order.status = "partially_refunded" OR "refunded"
```

---

## 📦 Models at a Glance

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **StockReservation** | Prevents overselling | product, quantity, status, expires_at |
| **ShipmentLineItem** | Partial shipments | shipment, order_item, quantity_shipped |
| **RMA** | Return tracking | order, rma_number, reason, status |
| **ReturnItem** | Items in RMA | rma, order_item, quantity_returned |
| **Invoice** | ZATCA invoices | invoice_number, subtotal, tax_amount, total |
| **RefundTransaction** | Refund audit | order, amount, status, provider_refund_id |

---

## 🔐 Tenant Isolation

All models include `tenant_id`:
```python
Order.objects.filter(tenant_id=1)  # Automatic scoping
StockReservation.objects.filter(tenant_id=1)
Invoice.objects.filter(tenant_id=1)
RMA.objects.filter(tenant_id=1)
RefundTransaction.objects.filter(tenant_id=1)
```

---

## 📋 Service Methods

### StockManagementService
```python
.reserve_order_items(order_item, timeout_minutes=30)
.confirm_reservation(reservation)
.release_reservation(reservation, reason="")
.auto_release_expired_reservations()  # Celery task
._get_available_stock(product, variant)
._count_reserved(product, variant)
```

### InvoiceService
```python
.generate_invoice(order, save_pdf=True)
.mark_as_issued(invoice)
.mark_as_paid(invoice)
._generate_invoice_number(tenant_id, tenant_slug)
._generate_pdf(invoice)  # reportlab
```

### RefundService
```python
.initiate_refund(order, amount, rma, reason)
.process_refund(refund_tx)
.process_rma_refund(rma)
.calculate_refundable_amount(order)
```

### OrderLifecycleService
```python
.transition(order, new_status)
.allowed_transitions(current_status)
```

---

## 🧪 Testing

```bash
# Run all tests
python manage.py test apps.orders.tests.test_production_commerce

# Run specific test class
python manage.py test apps.orders.tests.test_production_commerce.StockReservationTests

# Run specific test
python manage.py test apps.orders.tests.test_production_commerce.StockReservationTests.test_reserve_stock

# Verbose output
python manage.py test apps.orders.tests.test_production_commerce -v 2
```

---

## 📊 Database Queries

### Check Stock Reservations
```python
from apps.orders.models import StockReservation
from django.utils import timezone

# Active (non-released) reservations
active = StockReservation.objects.filter(status__in=["reserved", "confirmed"])

# Expired (should be cleaned up)
expired = StockReservation.objects.filter(
    status="reserved",
    expires_at__lt=timezone.now()
)

# For a specific product
product_reserved = StockReservation.objects.filter(
    product_id=1,
    status__in=["reserved", "confirmed"]
).aggregate(total=Sum('quantity'))
```

### Check Invoices
```python
from apps.orders.models import Invoice

# All to-issue invoices for a tenant
pending = Invoice.objects.filter(
    tenant_id=1,
    status="draft"
).order_by("-issue_date")

# Late-paid invoices
overdue = Invoice.objects.filter(
    tenant_id=1,
    status="issued",
    due_date__lt=date.today()
)
```

### Check Refunds
```python
from apps.orders.models import RefundTransaction

# Failed refunds (need retry)
failed = RefundTransaction.objects.filter(
    tenant_id=1,
    status="failed"
).order_by("-created_at")

# Processing (check status)
processing = RefundTransaction.objects.filter(
    status="processing"
)
```

---

## ⚠️ Common Errors & Fixes

### Error: "Insufficient stock"
```python
# Check available stock
from apps.orders.services.stock_management_service import StockManagementService

available = StockManagementService._get_available_stock(product, variant)
# Returns: stock - reserved - sold

# Solution: Release old reservations
StockManagementService.auto_release_expired_reservations()
```

### Error: "Cannot mark delivered without shipment"
```python
# Need to create shipment first
shipment = Shipment.objects.create(order=order, carrier="dhl")

# Then transition
OrderLifecycleService.transition(order=order, new_status="delivered")
```

### Error: "Refund amount exceeds refundable"
```python
# Check remaining refundable
remaining = RefundService.calculate_refundable_amount(order)

# Try with smaller amount
RefundService.initiate_refund(order, amount=remaining)
```

---

## 🎯 Key Constraints

| Constraint | Reason | Example |
|-----------|--------|---------|
| StockReservation unique per OrderItem | Prevent double-reserve | Can't reserve same item twice |
| Invoice number unique per tenant | Prevent duplicate invoices | INV-001 scoped to tenant |
| RMA number unique | Track individual returns | RMA-2026-001 unique globally |
| Refund ≤ (total - already_refunded) | Prevent over-refunding | Can't refund $150 if order was $100 |
| Shipped items must map to OrderItems | Proper inventory | Each shipment item must come from an order item |

---

## 📈 Performance Tips

1. **Use select_for_update()** when updating critical fields:
```python
order = Order.objects.select_for_update().get(id=order_id)
```

2. **Prefetch related data** to avoid N+1:
```python
orders = Order.objects.prefetch_related('items', 'shipments').all()
```

3. **Use indexes** for common filters:
```python
# Already indexed:
Order.objects.filter(tenant_id=1, status="paid")
StockReservation.objects.filter(expires_at__lt=now)
Invoice.objects.filter(tenant_id=1, issue_date__year=2026)
```

---

## 📞 Quick Links

- **Full Docs:** `docs/PRODUCTION_COMMERCE_ORDER_LIFECYCLE.md`
- **Implementation:** `docs/PRODUCTION_COMMERCE_IMPLEMENTATION.md`
- **Models:** `apps/orders/models.py`
- **Tests:** `apps/orders/tests/test_production_commerce.py`
- **Services:** `apps/orders/services/`

---

**Last Updated:** 2026-02-28  
**Version:** 2.0  
**Status:** Production Ready ✅
