# Enterprise Accounting System for Wasla Wallet

**Status:** Production-Ready  
**Version:** 2.0  
**Last Updated:** 2026-02-25  

## Executive Summary

The Wasla wallet system has been upgraded to enterprise accounting level with dual-balance ledger management, withdrawal approvals, and ledger integrity validation. This ensures accurate settlement tracking, compliance-ready reporting, and fraud prevention.

### Key Features

✅ **Dual-Balance Accounting**: Available vs. Pending balance tracking  
✅ **Automatic State Transitions**: Payment → Pending → Available → Withdrawal  
✅ **Withdrawal Lifecycle**: Request → Approve → Reject → Paid with audit trails  
✅ **Ledger Integrity**: Transaction-by-transaction validation and reconciliation  
✅ **Reference Tracking**: Unique withdrawal codes for reconciliation  
✅ **Multi-Tenant Isolation**: Store-scoped wallets with tenant enforcement  
✅ **Race Condition Protection**: `select_for_update()` for concurrent safety  

---

## 1. Architecture Overview

### 1.1 Data Models

#### `Wallet` Model
Represents a merchant's account with dual-balance accounting.

```python
class Wallet(models.Model):
    tenant_id: int  # Multi-tenant isolation
    store_id: int  # Unique per store
    
    # Dual-balance accounting
    balance: Decimal  # Total (available + pending)
    available_balance: Decimal  # Can be withdrawn immediately
    pending_balance: Decimal  # Locked until fulfillment
    
    currency: str  # Default "USD"
    is_active: bool  # Enable/disable payments
    
    # Constraint: Unique per store within tenant
```

**Business Rules:**
- `balance = available_balance + pending_balance` (always synced)
- Cannot go negative
- Store can have only one wallet


#### `WalletTransaction` Model
Immutable ledger entry for audit trails.

```python
class WalletTransaction(models.Model):
    wallet: FK[Wallet]  # Which wallet
    
    transaction_type: Choice["credit", "debit"]
    balance_bucket: Choice["available", "pending"]
    event_type: Choice[
        "order_paid",
        "order_delivered",
        "refund",
        "withdrawal",
        "adjustment"
    ]
    
    amount: Decimal
    reference: str  # For grouping related transactions
    metadata_json: dict  # Event-specific data
    created_at: DateTime  # Immutable timestamp
```

**Constraints:**
- Write-once, never deleted
- Indexed by wallet, created_at, event_type, reference


#### `WithdrawalRequest` Model
Tracks merchant withdrawal requests with approval workflow.

```python
class WithdrawalRequest(models.Model):
    wallet: FK[Wallet]
    store_id: int
    tenant_id: int
    
    amount: Decimal
    status: Choice[
        "pending",    # Initial state
        "approved",   # Admin approved
        "rejected",   # Admin rejected
        "paid"        # Funds sent
    ]
    
    reference_code: str  # Unique: WD-{store_id}-{uuid}
    requested_at: DateTime
    processed_at: DateTime | None
    processed_by_user_id: int | None
    note: str
```

**Indexes:**
- `(store_id, requested_at)` - List withdrawals per store
- `(status)` - Find pending/approved
- `reference_code` - Unique, idempotency key

---

## 2. Business Logic

### 2.1 Payment Flow State Machine

```
Order Created
    ↓
[Payment Processed]
    ↓
Wallet.pending_balance += amount  ← Funds locked, awaiting delivery
    ↓
[Order Delivered]
    ↓
Wallet.pending_balance -= amount  ← Remove from pending
Wallet.available_balance += amount  ← Move to available
    ↓
[Merchant Requests Withdrawal]
    ↓
WithdrawalRequest(status=pending)  ← Awaiting approval
    ↓
[Admin Approves]
    ↓
WithdrawalRequest(status=approved)  ← Approved, ready to pay
    ↓
[Mark as Paid]
    ↓
Wallet.available_balance -= amount  ← Deduct from wallet
WithdrawalRequest(status=paid)  ← Complete
```

### 2.2 Refund Handling

When customer initiates refund:

```
[Refund Requested]
    ↓
Calculate refund amount
    ↓
IF refund <= pending_balance:
    pending_balance -= refund
ELSE:
    pending_deduction = pending_balance
    available_deduction = refund - pending_deduction
    
    pending_balance -= pending_deduction
    available_balance -= available_deduction
```

**Example:**
```
Before refund:
  pending_balance: 100.00
  available_balance: 50.00

Refund Amount: 120.00

After refund:
  pending_balance: 0.00       (100 deducted from pending)
  available_balance: 30.00    (20 deducted from available)
```

### 2.3 Withdrawal Lifecycle

```python
# 1. Request Withdrawal
withdrawal = WalletService.create_withdrawal_request(
    store_id=123,
    amount=Decimal("100.00"),
    tenant_id=1,
)
# withdrawal.status = "pending"
# wallet.available_balance stays unchanged
# (can be held by pending_withdrawal_amount in summary)

# 2. Admin Approves
WalletService.approve_withdrawal(
    withdrawal_id=withdrawal.id,
    actor_user_id=staff_user.id,
)
# withdrawal.status = "approved"
# withdrawal.processed_at = now()
# wallet.available_balance still unchanged

# 3. Mark as Paid
WalletService.mark_withdrawal_paid(
    withdrawal_id=withdrawal.id,
    actor_user_id=staff_user.id,
)
# withdrawal.status = "paid"
# wallet.available_balance -= amount
# Creates debit transaction: "withdrawal"

# OR Reject
WalletService.reject_withdrawal(
    withdrawal_id=withdrawal.id,
    actor_user_id=staff_user.id,
    note="Missing KYC documents",
)
# withdrawal.status = "rejected"
# wallet balance unchanged
```

### 2.4 Effective Available Balance

When multiple pending withdrawals exist, the effective available balance is:

```
effective_available = available_balance - sum(pending_withdrawal_amounts)
```

**Example:**
```
available_balance: 1000.00
pending_withdrawal_request_1: 200.00
pending_withdrawal_request_2: 150.00

effective_available = 1000.00 - 200.00 - 150.00 = 650.00
```

This prevents over-withdrawal of approved requests.

---

## 3. WalletService API Reference

### Core Methods

#### Payment Event: `on_order_paid()`

```python
WalletService.on_order_paid(
    store_id: int,
    net_amount: Decimal,
    reference: str,
    tenant_id: int | None = None,
) -> Wallet
```

**Behavior:**
- Adds amount to `pending_balance`
- Records transaction with `event_type="order_paid"`
- **Idempotent**: Duplicate reference codes are ignored

**Example:**
```python
wallet = WalletService.on_order_paid(
    store_id=5,
    net_amount=Decimal("75.50"),
    reference="order:12345",
    tenant_id=1,
)
# wallet.pending_balance += 75.50
# wallet.balance += 75.50
```

#### Fulfillment Event: `on_order_delivered()`

```python
WalletService.on_order_delivered(
    store_id: int,
    net_amount: Decimal,
    reference: str,
    tenant_id: int | None = None,
) -> Wallet
```

**Behavior:**
- Moves amount from `pending_balance` to `available_balance`
- Records dual transactions (debit pending, credit available)
- **Idempotent**: Duplicate references ignored
- **Safe**: If pending < amount, moves only available amount

**Example:**
```python
wallet = WalletService.on_order_delivered(
    store_id=5,
    net_amount=Decimal("75.50"),
    reference="order:12345-delivered",
    tenant_id=1,
)
# wallet.pending_balance -= 75.50
# wallet.available_balance += 75.50
```

#### Refund Event: `on_refund()`

```python
WalletService.on_refund(
    store_id: int,
    amount: Decimal,
    reference: str,
    tenant_id: int | None = None,
) -> Wallet
```

**Behavior:**
- Deducts from `pending_balance` first (FIFO)
- Then deducts from `available_balance` if needed
- Raises `ValueError` if insufficient total balance

**Example:**
```python
# Wallet state: pending=100, available=50
wallet = WalletService.on_refund(
    store_id=5,
    amount=Decimal("120.00"),
    reference="refund:order:12345",
    tenant_id=1,
)
# pending: 100 → 0 (100 deducted)
# available: 50 → 30 (20 deducted)
```

#### Withdrawal: `create_withdrawal_request()`

```python
WalletService.create_withdrawal_request(
    store_id: int,
    amount: Decimal,
    tenant_id: int | None = None,
    note: str = "",
    reference_code: str | None = None,
) -> WithdrawalRequest
```

**Validation:**
- Amount must be > 0
- Amount must be ≤ `available_balance`
- Generates unique `reference_code` if not provided: `WD-{store_id}-{uuid}`

**Returns:** `WithdrawalRequest` with status `"pending"`

#### Approval: `approve_withdrawal()`

```python
WalletService.approve_withdrawal(
    withdrawal_id: int,
    actor_user_id: int | None = None,
) -> WithdrawalRequest
```

**Validation:**
- Withdrawal must be in `"pending"` state
- Available balance must still cover amount (prevents race conditions)

**Side Effects:**
- Sets status → `"approved"`
- Sets `processed_at` → now()
- Sets `processed_by_user_id` → actor

#### Rejection: `reject_withdrawal()`

```python
WalletService.reject_withdrawal(
    withdrawal_id: int,
    actor_user_id: int | None = None,
    note: str = "",
) -> WithdrawalRequest
```

**Validation:**
- Withdrawal must be in `"pending"` state

**Side Effects:**
- Sets status → `"rejected"`
- Sets `processed_at` → now()
- Appends to note (optional)

#### Settlement: `mark_withdrawal_paid()`

```python
WalletService.mark_withdrawal_paid(
    withdrawal_id: int,
    actor_user_id: int | None = None,
) -> WithdrawalRequest
```

**Validation:**
- Withdrawal must be in `"approved"` state
- Available balance must cover amount (prevents double-payment)

**Side Effects:**
- Sets status → `"paid"`
- **Deducts from `available_balance`** (critical side effect)
- Records transaction: `event_type="withdrawal"`
- Sets processed metadata

---

## 4. Reporting & Validation

### 4.1 Ledger Integrity Check

```python
result = WalletService.ledger_integrity_check(
    store_id: int,
    tenant_id: int | None = None,
) -> dict
```

**Returns:**
```python
{
    "store_id": 5,
    "wallet_id": 42,
    "is_valid": True,  # Ledger matches
    "computed": {
        "available_balance": "500.00",
        "pending_balance": "250.00",
        "balance": "750.00",
    },
    "stored": {
        "available_balance": "500.00",
        "pending_balance": "250.00",
        "balance": "750.00",
    },
    "transaction_count": 23,
}
```

**Validation Checks:**
- Recompute balances from all transactions
- Verify `balance = available + pending`
- Verify no negative balances
- Detect ledger corruption early

### 4.2 Wallet Summary

```python
summary = WalletService.get_wallet_summary(
    store_id: int,
    tenant_id: int | None = None,
) -> dict
```

**Returns:**
```python
{
    "wallet_id": 42,
    "store_id": 5,
    "currency": "USD",
    "available_balance": "500.00",
    "pending_balance": "250.00",
    "balance": "750.00",
    "pending_withdrawal_amount": "200.00",  # Sum of pending withdrawals
    "effective_available_balance": "300.00",  # Available - pending_withdrawals
    "is_active": True,
}
```

---

## 5. Usage Examples

### Example 1: Simple Order → Delivery → Withdrawal

```python
from decimal import Decimal
from apps.wallet.services.wallet_service import WalletService

# Step 1: Customer pays for order
wallet = WalletService.on_order_paid(
    store_id=5,
    net_amount=Decimal("99.99"),
    reference="order:1001",
    tenant_id=1,
)
assert wallet.pending_balance == Decimal("99.99")
assert wallet.available_balance == Decimal("0.00")

# Step 2: Order delivered, funds released
wallet = WalletService.on_order_delivered(
    store_id=5,
    net_amount=Decimal("99.99"),
    reference="order:1001-delivered",
    tenant_id=1,
)
assert wallet.pending_balance == Decimal("0.00")
assert wallet.available_balance == Decimal("99.99")

# Step 3: Merchant requests withdrawal
withdrawal = WalletService.create_withdrawal_request(
    store_id=5,
    amount=Decimal("99.99"),
    tenant_id=1,
    note="Weekly settlement",
)
assert withdrawal.status == "pending"
assert withdrawal.reference_code.startswith("WD-5-")

# Step 4: Admin approves
admin = get_user_model().objects.get(username="admin")
withdrawal = WalletService.approve_withdrawal(
    withdrawal_id=withdrawal.id,
    actor_user_id=admin.id,
)
assert withdrawal.status == "approved"

# Step 5: Mark as paid (funds transferred)
withdrawal = WalletService.mark_withdrawal_paid(
    withdrawal_id=withdrawal.id,
    actor_user_id=admin.id,
)
assert withdrawal.status == "paid"
wallet.refresh_from_db()
assert wallet.available_balance == Decimal("0.00")
```

### Example 2: Refund Processing

```python
# Setup: Wallet with funds
wallet = WalletService.get_or_create_wallet(store_id=5, tenant_id=1)
wallet.pending_balance = Decimal("100.00")
wallet.available_balance = Decimal("150.00")
wallet.balance = Decimal("250.00")
wallet.save()

# Customer initiates refund for pending order
wallet = WalletService.on_refund(
    store_id=5,
    amount=Decimal("120.00"),  # More than pending, some from available
    reference="refund:order:1001",
    tenant_id=1,
)

# Results:
# - pending_balance: 100.00 → 0.00 (fully deducted)
# - available_balance: 150.00 → 30.00 (20 deducted)
# - balance: 250.00 → 30.00

assert wallet.pending_balance == Decimal("0.00")
assert wallet.available_balance == Decimal("30.00")
```

### Example 3: Concurrent Withdrawal Requests

```python
# Multiple pending withdrawals
wallet = WalletService.get_or_create_wallet(store_id=5, tenant_id=1)
wallet.available_balance = Decimal("1000.00")
wallet.balance = Decimal("1000.00")
wallet.save()

wd1 = WalletService.create_withdrawal_request(
    store_id=5,
    amount=Decimal("300.00"),
    tenant_id=1,
)

wd2 = WalletService.create_withdrawal_request(
    store_id=5,
    amount=Decimal("400.00"),
    tenant_id=1,
)

# Check effective balance
summary = WalletService.get_wallet_summary(store_id=5, tenant_id=1)
assert summary["available_balance"] == "1000.00"
assert summary["pending_withdrawal_amount"] == "700.00"
assert summary["effective_available_balance"] == "300.00"

# This prevents approving withdrawal #2 if only #1 is approved:
# Can only pay 300 more, but wd2 is 400
```

### Example 4: Ledger Integrity Check

```python
# Run after critical operations
result = WalletService.ledger_integrity_check(
    store_id=5,
    tenant_id=1,
)

if not result["is_valid"]:
    logger.error(f"Ledger corruption detected: {result}")
    # Trigger alert, prevent payouts
else:
    logger.info(f"Ledger valid, {result['transaction_count']} transactions")
```

---

## 6. Database Schema

### Wallet Table
```sql
CREATE TABLE wallet_wallet (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER,
    store_id INTEGER NOT NULL,
    balance NUMERIC(14, 2) DEFAULT 0,
    available_balance NUMERIC(14, 2) DEFAULT 0,
    pending_balance NUMERIC(14, 2) DEFAULT 0,
    currency VARCHAR(10) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE (store_id),
    INDEX (tenant_id, store_id)
);
```

### WalletTransaction Table
```sql
CREATE TABLE wallet_wallettransaction (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER,
    wallet_id INTEGER NOT NULL,
    transaction_type VARCHAR(10),
    balance_bucket VARCHAR(20),
    event_type VARCHAR(30),
    amount NUMERIC(14, 2),
    reference VARCHAR(255),
    metadata_json JSON,
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (wallet_id) REFERENCES wallet_wallet(id) ON DELETE PROTECT,
    INDEX (tenant_id, created_at),
    INDEX (wallet_id, created_at),
    INDEX (wallet_id, event_type),
    INDEX (reference)
);
```

### WithdrawalRequest Table
```sql
CREATE TABLE wallet_withdrawalrequest (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER,
    store_id INTEGER NOT NULL,
    wallet_id INTEGER NOT NULL,
    amount NUMERIC(14, 2),
    status VARCHAR(20),
    reference_code VARCHAR(64) UNIQUE NOT NULL,
    requested_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP NULL,
    note TEXT,
    processed_by_user_id INTEGER NULL,
    
    FOREIGN KEY (wallet_id) REFERENCES wallet_wallet(id) ON DELETE PROTECT,
    INDEX (tenant_id, status),
    INDEX (store_id, requested_at),
    INDEX (reference_code)
);
```

---

## 7. Testing Strategy

### Test Classes

1. **WalletOperationalAccountingServiceTests**
   - Order paid → delivered flow
   - Refund with mixed pending/available
   - Prevention of over-withdrawal

2. **WithdrawalReferenceCodeTests**
   - Auto-generation of codes
   - Custom code support
   - Reference-based lookup

3. **WithdrawalLifecycleTests**
   - Full lifecycle: pending → approved → paid
   - Rejection flow
   - Idempotency checks

4. **WithdrawalEdgeCaseTests**
   - Negative amounts rejected
   - Insufficient balance checks
   - Race condition detection

5. **LedgerIntegrityTests**
   - Complex transaction sequences
   - Idempotent transaction handling
   - Balance consistency

6. **WalletSummaryTests**
   - Pending + available reporting
   - Currency tracking

7. **TransactionListingTests**
   - List transactions with filters
   - Withdrawal listing

8. **RefundEdgeCaseTests**
   - Refund from pending only
   - Refund from available only
   - Insufficient balance scenarios

### Running Tests

```bash
# All wallet tests
python manage.py test apps.wallet

# Specific test class
python manage.py test apps.wallet.tests.WithdrawalLifecycleTests

# Specific test method
python manage.py test apps.wallet.tests.WithdrawalLifecycleTests.test_withdrawal_pending_to_approved_to_paid

# With coverage
coverage run --source='apps.wallet' manage.py test apps.wallet
coverage report
```

---

## 8. Integration Guide

### 8.1 Payment Processing Integration

When payment service confirms payment:

```python
from apps.wallet.services.wallet_service import WalletService

def on_payment_captured(order):
    """Called by payment service after charge succeeds."""
    try:
        WalletService.on_order_paid(
            store_id=order.store_id,
            net_amount=order.net_amount,  # After platform fee
            reference=f"order:{order.id}",
            tenant_id=order.tenant_id,
        )
    except ValueError as e:
        logger.error(f"Failed to record order {order.id}: {e}")
        # Don't block payment confirmation, but alert
```

### 8.2 Fulfillment Integration

When order delivery is confirmed:

```python
def on_order_fulfilled(order):
    """Called by fulfillment service after delivery."""
    try:
        WalletService.on_order_delivered(
            store_id=order.store_id,
            net_amount=order.net_amount,
            reference=f"order:{order.id}-fulfilled",
            tenant_id=order.tenant_id,
        )
    except ValueError as e:
        logger.error(f"Failed to release funds for order {order.id}: {e}")
```

### 8.3 Refund Integration

When refund is processed:

```python
def on_refund_processed(refund):
    """Called by refund service after refund is issued."""
    try:
        WalletService.on_refund(
            store_id=refund.order.store_id,
            amount=refund.amount,
            reference=f"refund:{refund.order.id}",
            tenant_id=refund.order.tenant_id,
        )
    except ValueError as e:
        logger.error(f"Refund {refund.id} failed: {e}")
        refund.status = "failed"
        refund.save()
```

---

## 9. Performance Considerations

### Indexes

All critical queries have indexes:
- `WalletTransaction (wallet_id, created_at)` - Transaction history
- `WalletTransaction (event_type)` - Filter by event
- `WithdrawalRequest (store_id, requested_at)` - List withdrawals
- `WithdrawalRequest (status)` - Find pending/approved

### Query Optimization

**Use prefetch_related for relationships:**
```python
withdrawals = WithdrawalRequest.objects.select_related("wallet").filter(
    status="pending"
)
```

**Limit large transactions:**
```python
txns = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
    limit=100,  # Default, paginate for large stores
)
```

### Concurrency Safety

All wallet mutations use `select_for_update()` to prevent race conditions:
```python
wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
# Protected against concurrent modifications
```

---

## 10. Security & Compliance

### Data Integrity

✅ **ACID Transactions**: All mutations wrapped in `@transaction.atomic`  
✅ **Idempotent Operations**: Duplicate event references are ignored  
✅ **Write-Once Audit Trail**: `WalletTransaction` never modified  
✅ **Race Condition Protection**: `select_for_update()` on all mutations  

### Audit Trail

Every transaction is logged with:
- Timestamp (immutable)
- Event type (order_paid, refund, withdrawal, etc.)
- Reference code (links to source event)
- Metadata (additional context)

### Tenant Isolation

```python
# All queries filtered by tenant_id
wallet = Wallet.objects.filter(
    store_id=store_id,
    tenant_id=tenant_id,  # Prevents cross-tenant access
).first()
```

---

## 11. Troubleshooting

### Issue: Ledger Integrity Check Fails

**Resolution:**
```python
# 1. Identify discrepancy
result = WalletService.ledger_integrity_check(store_id=5, tenant_id=1)
print(f"Computed: {result['computed']}")
print(f"Stored: {result['stored']}")

# 2. Recompute from transactions
from apps.wallet.models import WalletTransaction
txns = WalletTransaction.objects.filter(wallet_id=wallet.id).order_by("created_at")
for txn in txns:
    print(f"{txn.event_type}: {txn.amount} ({txn.transaction_type})")

# 3. Manual correction (last resort)
wallet.available_balance = Decimal("X.XX")
wallet.pending_balance = Decimal("Y.YY")
wallet.balance = wallet.available_balance + wallet.pending_balance
wallet.save()
```

### Issue: Withdrawal Approval Fails

**Possible Causes:**
- Available balance decreased (other refund processed)
- Withdrawal already processed
- Withdrawal not found

**Resolution:**
```python
# Check wallet balance
wallet.refresh_from_db()
if withdrawal.amount > wallet.available_balance:
    logger.error("Insufficient balance, reject instead")
    WalletService.reject_withdrawal(
        withdrawal_id=withdrawal.id,
        note="Insufficient balance at approval time"
    )
```

### Issue: Duplicate Transactions Appearing

**This should not happen** (idempotence prevents it).

**If it does:**
```python
# Check for duplicate references
from apps.wallet.models import WalletTransaction
dupes = WalletTransaction.objects.values("reference").annotate(
    count=Count("id")
).filter(count__gt=1)

for dupe in dupes:
    print(f"Reference {dupe['reference']} appears {dupe['count']} times")
```

---

## 12. Migration Path

### From Previous Version

If upgrading from v1.x:

```bash
# 1. Backup existing data
python manage.py dumpdata apps.wallet > wallet_backup.json

# 2. Run migrations
python manage.py migrate wallet

# 3. Verify integrity
python manage.py shell
>>> from apps.wallet.services.wallet_service import WalletService
>>> for store_id in range(1, 100):
...     result = WalletService.ledger_integrity_check(store_id=store_id)
...     if not result["is_valid"]:
...         print(f"Store {store_id} ledger invalid!")
```

---

## 13. Monitoring & Alerts

### Critical Alerts

```python
# Monitor in production
def check_wallet_health():
    from apps.wallet.models import Wallet
    
    invalid_wallets = []
    for wallet in Wallet.objects.all():
        result = WalletService.ledger_integrity_check(
            store_id=wallet.store_id,
            tenant_id=wallet.tenant_id,
        )
        if not result["is_valid"]:
            invalid_wallets.append(wallet.id)
    
    if invalid_wallets:
        alert(f"Ledger integrity issues: {invalid_wallets}")
```

### Monitoring Queries

```python
# Pending withdrawal aging
pending = WithdrawalRequest.objects.filter(
    status="pending",
    requested_at__lt=timezone.now() - timedelta(days=7)
)
# Alert if > 7 days old

# Negative balance detection (should never happen)
negative = Wallet.objects.filter(available_balance__lt=0)
# Critical alert if this appears

# Pending release aging
from django.db.models import Q
pending_orders = WalletTransaction.objects.filter(
    Q(event_type="order_paid") & Q(wallet__pending_balance__gt=0)
)
# Monitor orders stuck in pending
```

---

## 14. Support & Contact

**Issues:**
- Report via internal issue tracker
- Include wallet ID and store ID
- Provide affected date range

**Documentation:**
- Full API docs: See WalletService class
- Test examples: See tests.py
- Django admin: Configure in admin.py

**Escalation:**
- Critical (negative balance): Page on-call
- Ledger corruption: Immediate review required
- High-value withdrawals: Manual approval process

---

## Appendix: Quick Reference

### Service Methods

| Method | Purpose | Key Validators |
|--------|---------|-----------------|
| `on_order_paid()` | Record pending funds | Amount > 0, idempotent |
| `on_order_delivered()` | Release pending funds | Safe partial release |
| `on_refund()` | Deduct funds | Sufficient balance |
| `create_withdrawal_request()` | Initiate withdrawal | Amount ≤ available |
| `approve_withdrawal()` | Admin approval | Balance still sufficient |
| `reject_withdrawal()` | Decline request | Status still pending |
| `mark_withdrawal_paid()` | Complete settlement | Balance still sufficient |
| `ledger_integrity_check()` | Verify consistency | Full transaction replay |
| `get_wallet_summary()` | Current state | Include pending |

### Transaction States

```
PAYMENT FLOW:
pending_balance ← order paid
available_balance ← order delivered (pending → available)
available_balance ← refund (pending/available ← deducted)

WITHDRAWAL FLOW:
pending request → approved → paid (available ← deducted)
              → rejected (no balance change)
```

### Status Codes

- `"pending"` - Awaiting approval
- `"approved"` - Approved, ready to pay
- `"rejected"` - Declined by admin
- `"paid"` - Funds transferred

---

**Version 2.0 - Enterprise Ready**  
For production use with compliance and audit requirements.
