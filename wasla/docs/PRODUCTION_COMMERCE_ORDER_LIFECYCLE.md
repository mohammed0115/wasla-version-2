# Production Commerce Order Lifecycle

**Status:** Complete implementation  
**Version:** 2.0  
**Date:** 2026-02-28

## Overview

Wasla's production-grade order management system supports complex commerce workflows:

- **Stock Reservation** - Prevents overselling with automatic timeout-based release
- **Partial Shipments** - Split orders into multiple shipments with independent tracking
- **Returns & RMA** - Full return authorization flow with refund processing
- **Invoice Management** - ZATCA-compliant invoices with PDF generation
- **Refund Processing** - Integrated with payment orchestrator for secure refunds

---

## Architecture

### Core Models

#### Order (Enhanced)
```python
Order(
    # Core fields
    order_number: str,
    customer: FK,
    status: str,  # See state diagram
    payment_status: str,
    total_amount: Decimal,
    currency: str = "SAR",
    
    # VAT structure (ZATCA compatible)
    subtotal: Decimal,
    tax_amount: Decimal,
    tax_rate: Decimal = 0.15,
    
    # Refund tracking
    refunded_amount: Decimal,
    
    # Tenant isolation
    tenant_id: int,
    store_id: int,
)
```

**Status Diagram:**
```
pending → paid → processing → shipped → delivered → completed
                                                ↘ returned → partially_refunded/refunded
  ↓
cancelled
```

#### StockReservation
Reserves stock during checkout with automatic TTL-based release.

```python
StockReservation(
    order_item: FK,
    product: FK,
    variant: FK,
    quantity: int,
    status: str,  # "reserved", "confirmed", "released"
    expires_at: datetime,  # TTL default 30 mins
)
```

**Workflow:**
1. `reserve()` - Called at checkout creation (30-minute window)
2. `confirm()` - Called when payment succeeds (extends to 30 days)
3. `release()` - Called on cancellation or timeout
4. `auto_release_expired()` - Celery task runs every 5 minutes

#### ShipmentLineItem
Maps OrderItem to Shipment with quantity breakdown, enabling partial shipments.

```python
ShipmentLineItem(
    shipment: FK,
    order_item: FK,
    quantity_shipped: int,
)
```

**Use case:** Order 10 items → Ship 5 now, 5 later

#### RMA (Return Merchandise Authorization)
```python
RMA(
    order: FK,
    rma_number: str,
    reason: str,  # "defective", "damaged_in_transit", etc.
    status: str,  # "requested", "approved", "received", "processed"
    items: FK[ReturnItem],  # One-to-many
)
```

#### ReturnItem
```python
ReturnItem(
    rma: FK,
    order_item: FK,
    quantity_returned: int,
    condition: str,  # "new", "good", "defective"
)
```

#### Invoice
ZATCA-compliant invoice with PDF generation.

```python
Invoice(
    order: FK,
    invoice_number: str,  # INV-TENANT-YYYY-0001
    status: str,  # "draft", "issued", "paid"
    subtotal: Decimal,
    tax_amount: Decimal,
    tax_rate: Decimal = 0.15,  # Saudi VAT
    total_amount: Decimal,
    pdf_file: FileField,
    seller_vat_number: str,  # Seller VAT ID
    buyer_vat_number: str,   # Buyer VAT ID
)
```

#### RefundTransaction
Audit trail for refunds processed through payment provider.

```python
RefundTransaction(
    order: FK,
    rma: FK,
    amount: Decimal,
    provider: str,  # "tap", "stripe"
    provider_refund_id: str,
    status: str,  # "initiated", "processing", "completed", "failed"
)
```

---

## Services

### StockManagementService

**Prevents overselling** via reservations with automatic cleanup.

```python
# Reserve stock at checkout (30-minute window)
reservation = StockManagementService.reserve_order_items(order_item)

# Confirm when payment succeeds (extends to 30 days)
StockManagementService.confirm_reservation(reservation)

# Release on timeout/cancellation
StockManagementService.release_reservation(reservation, reason="timeout")

# Celery: Auto-release expired (run every 5 min)
StockManagementService.auto_release_expired_reservations()
```

**Constraints:**
- Prevents duplicate reservations (unique_together: order_item)
- Calculates available stock as: total - reserved - sold
- Auto-release on timeout (default 30 mins for unpaid, 30 days for paid)

---

### InvoiceService

**Generates ZATCA-compliant invoices** with sequential numbering.

```python
# Generate invoice from order
invoice = InvoiceService.generate_invoice(order, save_pdf=True)

# Mark as issued
InvoiceService.mark_as_issued(invoice)

# Mark as paid
InvoiceService.mark_as_paid(invoice)
```

**Features:**
- Sequential numbering per tenant: `INV-TENANT-YYYY-0001`
- PDF generation with reportlab
- VAT calculation (15% for Saudi Arabia)
- ZATCA-ready structure with QR field

**Invoice PDF generates:**
- Header with invoice number and dates
- Line items (product, qty, price)
- Summary (subtotal, tax, total)
- VAT compliance info

---

### RefundService

**Integrates refunds with payment orchestrator.**

```python
# Initiate refund
refund_tx = RefundService.initiate_refund(
    order=order,
    amount=Decimal("50.00"),
    rma=rma,
    reason="Customer return"
)

# Process refund through payment provider
RefundService.process_refund(refund_tx)

# Process all refunds for RMA
refunds = RefundService.process_rma_refund(rma)

# Calculate refundable amount
remaining = RefundService.calculate_refundable_amount(order)
```

**Validation:**
- Prevents over-refunding (refund ≤ original amount - already refunded)
- Links to original PaymentAttempt
- Calls PaymentOrchestrator.refund_payment()
- Updates order.refunded_amount on completion
- Sets order.status to "refunded" (100%) or "partially_refunded" (partial)

---

### OrderLifecycleService (Extended)

**Handles full order lifecycle including returns.**

```python
# Transition to new status
OrderLifecycleService.transition(order=order, new_status="returned")
```

**Valid transitions:**
- pending → paid, cancelled
- paid → processing
- processing → shipped
- shipped → delivered
- delivered → completed, returned
- returned → partially_refunded, refunded
- partially_refunded → refunded

**State-specific logic:**
- `delivered` → Moves wallet pending to available
- `completed` → Finalizes order
- `returned` → Holds wallet funds pending refund approval
- `partially_refunded`/`refunded` → Reverses wallet entries
- `cancelled` → Releases stock reservations

---

## Integration Flows

### Order Placement → Payment → Shipment

```
1. Checkout
   └─> StockManagementService.reserve_order_items(order_item)
       Status: reserved (30-min TTL)

2. Payment Confirmed
   └─> StockManagementService.confirm_reservation(reservation)
       Status: confirmed (30-day TTL)
   └─> InvoiceService.generate_invoice(order)
   └─> OrderLifecycleService.transition("paid")

3. Fulfillment
   └─> OrderLifecycleService.transition("processing")
   └─> ShippingService.create_shipment(order)
       └─> ShipmentLineItem created for each product
   └─> OrderLifecycleService.transition("shipped")

4. Delivery
   └─> UpdateShipmentAPI.update("delivered")
   └─> OrderLifecycleService.transition("delivered")
   └─> WalletService.on_order_delivered() (move pending to available)

5. Completion
   └─> OrderLifecycleService.transition("completed")
```

### Return Flow (RMA)

```
1. Request Return
   └─> RMA.create(order=order, reason="defective")
   └─> ReturnItem.create(rma=rma, order_item=item, qty=1)
   └─> RMA.status = "requested"

2. Approve RMA
   └─> RMA.status = "approved"

3. Customer Returns Item
   └─> Provide return label/info
   └─> RMA.status = "received"

4. Inspect & Approve Refund
   └─> ReturnItem.condition = "defective" (and approve)
   └─> RefundService.process_rma_refund(rma)
       └─> For each approved item:
           ├─> RefundService.initiate_refund()
           ├─> RefundService.process_refund()
           │   └─> PaymentOrchestrator.refund_payment()
           └─> ReturnItem.status = "refunded"

5. Finalize
   └─> RMA.status = "processed"
   └─> OrderLifecycleService.transition("partially_refunded" or "refunded")
```

---

## API Examples

### Stock Reservation
```bash
# Auto-reserved at checkout (no explicit API call)
POST /checkouts/{id}/confirm
```

### Invoice Generation
```bash
GET /orders/{id}/invoice/pdf
# Downloads: invoices/<tenant>/<invoice_number>.pdf

GET /orders/{id}/invoice
# Returns: {invoice_number, status, total_amount, ...}
```

### RMA Creation
```bash
POST /orders/{id}/returns
Body: {
  "reason": "defective",
  "items": [
    {"order_item_id": 123, "quantity": 1, "condition": "defective"}
  ]
}
Response: {"rma_number": "RMA-2026-001", "status": "requested"}
```

### Process Refund
```bash
POST /rmas/{id}/approve-and-refund
Body: {"items": [{"id": 1, "approve": true}]}
# Triggers: RefundService.process_rma_refund()
```

---

## Celery Tasks

### Auto-Release Stock
```python
# Run every 5 minutes
@periodic_task(run_every=crontab(minute="*/5"))
def auto_release_expired_stock_reservations():
    StockManagementService.auto_release_expired_reservations()
```

### Send Refund Notifications
```python
# On refund completion
@shared_task
def notify_refund_processed(refund_tx_id):
    tx = RefundTransaction.objects.get(id=refund_tx_id)
    send_email(
        to=tx.order.customer.email,
        subject="Your refund has been processed",
        template="emails/refund_completed.html",
        context={"refund": tx, "order": tx.order}
    )
```

---

## Testing

### Test Suites

**tests/test_production_commerce.py**
- StockReservationTests - Reservation lifecycle
- InvoiceGenerationTests - Invoice numbering and PDF
- RMAAndRefundTests - RMA and refund flow
- OrderLifecycleWithReturnsTests - Return/refund states

### Running Tests
```bash
python manage.py test apps.orders.tests.test_production_commerce.StockReservationTests
python manage.py test apps.orders.tests.test_production_commerce.InvoiceGenerationTests
python manage.py test apps.orders.tests.test_production_commerce.RMAAndRefundTests
```

---

## Tenant Isolation

All models enforce tenant isolation:
- `tenant_id` indexed on every model
- TenantManager filters by tenant by default
- QuerySets must explicitly pass `tenant_id`
- Invoice numbering scoped to tenant
- Refund processing validates tenant ownership

---

## ZATCA Compliance (Saudi Arabia)

Invoice model supports ZATCA e-invoice structure:
- `invoice_number` format: INV-<TENANT>-YYYY-NNNN
- `tax_rate` field (15% for VAT)
- `seller_vat_number` and `buyer_vat_number`
- `zatca_qr_code` field for future QR generation
- PDF includes tax breakdown

---

## Error Handling

### StockManagementService
- `ValueError` - Insufficient stock during reservation

### InvoiceService
- `File not found` - PDF generation optional (`save_pdf=False`)
- Graceful fallback if reportlab not installed

### RefundService
- `ValueError` - Over-refunding validation
- `Payment provider error` - Caught and logged, transaction marked failed
- All operations atomic (@transaction.atomic)

### OrderLifecycleService
- `ValueError` - Invalid status transition
- `ValueError` - Shipment required for delivered/completed

---

## Performance Considerations

### Indexes
- `Order`: (store_id, status), (tenant_id, status)
- `StockReservation`: (expires_at), (product, status)
- `Invoice`: (tenant_id, status), (issue_date)
- `RefundTransaction`: (order_id), (status), (provider_refund_id)
- `RMA`: (order_id), (tenant_id, status)

### Queries
- Stock availability: SELECT COUNT aggregation with filtering
- Invoice numbering: ORDER BY count with pessimistic locking
- Refund lookup: Single index lookup on payment_attempt

### Caching Opportunities
- Invoice counters per tenant/month
- Stock availability (24-hour TTL)
- Customer VAT IDs (during checkout)

---

## Future Enhancements

1. **ZATCA E-Invoicing** - QR code generation and digital signature
2. **Dunning Management** - Automatic retry for failed refunds
3. **Inventory Sync** - Real-time inventory updates from warehouse systems
4. **B2B Returns** - Extended return windows for bulk orders
5. **Partial Payments** - Multiple payment methods per refund
6. **Analytics** - Return/refund rate dashboards
