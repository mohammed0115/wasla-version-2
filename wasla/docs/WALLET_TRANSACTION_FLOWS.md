# Wallet Double-Entry Transaction Flows - Quick Reference

## 📋 Standard Transaction Patterns

### 1. Payment Captured (Order Paid)

**Scenario:** Customer pays $100 for order, platform charges 2.5% fee

**Accounting Entry:**
```
DR: CASH                           $100.00
    CR: MERCHANT_PAYABLE_PENDING    $97.50
    CR: PLATFORM_REVENUE_FEES        $2.50
```

**Code:**
```python
WalletService.on_order_paid(
    store_id=1,
    order_id=123,
    gross_amount=Decimal("100.00"),
    shipping_amount=Decimal("0.00"),
    payment_id=456,
    plan_id=None,
    tenant_id=1,
)
```

**Result:**
- Wallet.pending_balance += $97.50
- PaymentAllocation created: gross=$100, fee=$2.50, net=$97.50
- JournalEntry created with 3 lines

---

### 2. Order Delivered

**Scenario:** Order #123 delivered, release $97.50 from pending to available

**Accounting Entry:**
```
DR: MERCHANT_PAYABLE_PENDING       $97.50
    CR: MERCHANT_PAYABLE_AVAILABLE  $97.50
```

**Code:**
```python
WalletService.on_order_delivered(
    store_id=1,
    order_id=123,
    merchant_net=Decimal("97.50"),
    tenant_id=1,
)
```

**Result:**
- Wallet.pending_balance -= $97.50
- Wallet.available_balance += $97.50
- JournalEntry created with 2 lines

---

### 3. Full Refund (No Fee Reversal)

**Scenario:** Refund $100 to customer, deduct $97.50 from merchant, keep $2.50 fee

**Accounting Entry:**
```
DR: MERCHANT_PAYABLE_PENDING       $30.00  (if available)
DR: MERCHANT_PAYABLE_AVAILABLE     $67.50  (remainder)
    CR: CASH                        $97.50
```

**Code:**
```python
WalletService.on_refund(
    store_id=1,
    order_id=123,
    refund_amount=Decimal("97.50"),
    reverse_full_fee=False,
    tenant_id=1,
)
```

**Result:**
- Deducts from pending first, then available
- Wallet.pending_balance -= $30.00 (example)
- Wallet.available_balance -= $67.50 (example)
- JournalEntry created

---

### 4. Full Refund (With Fee Reversal)

**Scenario:** Refund $100, platform absorbs the loss (reverses $2.50 fee)

**Accounting Entry:**
```
DR: MERCHANT_PAYABLE_PENDING       $30.00
DR: MERCHANT_PAYABLE_AVAILABLE     $67.50
DR: PLATFORM_REVENUE_FEES           $2.50  (reversal)
    CR: CASH                       $100.00
```

**Code:**
```python
WalletService.on_refund(
    store_id=1,
    order_id=123,
    refund_amount=Decimal("100.00"),
    reverse_full_fee=True,
    tenant_id=1,
)
```

**Result:**
- Merchant loses $97.50, platform loses $2.50
- Total refund to customer: $100.00
- JournalEntry created with 4 lines

---

### 5. Withdrawal Paid

**Scenario:** Merchant withdraws $50, bank transfer completed

**Accounting Entry:**
```
DR: MERCHANT_PAYABLE_AVAILABLE     $50.00
    CR: PLATFORM_CASH_OUT           $50.00
```

**Code:**
```python
# Step 1: Merchant requests
withdrawal = WalletService.create_withdrawal_request(
    store_id=1,
    amount=Decimal("50.00"),
    requested_by_id=10,
    tenant_id=1,
)

# Step 2: Admin approves (no accounting yet)
WalletService.approve_withdrawal(
    withdrawal_id=withdrawal.id,
    actor_user_id=2,
)

# Step 3: Admin marks paid (creates accounting entry)
WalletService.mark_withdrawal_paid(
    withdrawal_id=withdrawal.id,
    actor_user_id=2,
    payout_reference="BANK-TX-123456",
)
```

**Result:**
- Wallet.available_balance -= $50.00
- WithdrawalRequest.status = 'paid'
- WithdrawalRequest.journal_entry linked
- JournalEntry created with 2 lines

---

### 6. Opening Balance (Migration)

**Scenario:** Backfill existing wallet with $200 available, $50 pending

**Accounting Entry:**
```
DR: ADJUSTMENTS                    $250.00  (equity)
    CR: MERCHANT_PAYABLE_AVAILABLE $200.00
    CR: MERCHANT_PAYABLE_PENDING    $50.00
```

**Code:**
```python
# Automatically created by migration 0006
# No manual code needed
```

**Result:**
- Double-entry system reflects existing balances
- Can now reconcile forward from this point

---

## 🔍 Fee Calculation Examples

### Example 1: Percentage Fee (2.5%)

```python
from apps.wallet.services.accounting_service import AccountingService
from apps.wallet.models import FeePolicy
from decimal import Decimal

policy = FeePolicy(
    fee_type='percentage',
    fee_value=Decimal('2.5'),
    apply_to_shipping=False
)

fee, net = AccountingService.calculate_fee(
    gross_amount=Decimal("100.00"),
    fee_policy=policy,
    shipping_amount=Decimal("10.00")
)

# Calculation:
# Fee base = $100 - $10 (shipping excluded) = $90
# Fee = $90 * 2.5% = $2.25
# Net = $100 - $2.25 = $97.75
print(f"Fee: ${fee}, Net: ${net}")
# Output: Fee: $2.25, Net: $97.75
```

### Example 2: Percentage Fee with Minimum

```python
policy = FeePolicy(
    fee_type='percentage',
    fee_value=Decimal('2.5'),
    minimum_fee=Decimal('1.00'),
    apply_to_shipping=False
)

fee, net = AccountingService.calculate_fee(
    gross_amount=Decimal("10.00"),
    fee_policy=policy,
    shipping_amount=Decimal("2.00")
)

# Calculation:
# Fee base = $10 - $2 = $8
# Fee = $8 * 2.5% = $0.20
# Minimum = $1.00
# Actual fee = max($0.20, $1.00) = $1.00
# Net = $10 - $1.00 = $9.00
print(f"Fee: ${fee}, Net: ${net}")
# Output: Fee: $1.00, Net: $9.00
```

### Example 3: Fixed Fee

```python
policy = FeePolicy(
    fee_type='fixed',
    fee_value=Decimal('0.30'),
    apply_to_shipping=False
)

fee, net = AccountingService.calculate_fee(
    gross_amount=Decimal("100.00"),
    fee_policy=policy,
    shipping_amount=Decimal("10.00")
)

# Calculation:
# Fee = $0.30 (fixed)
# Net = $100 - $0.30 = $99.70
print(f"Fee: ${fee}, Net: ${net}")
# Output: Fee: $0.30, Net: $99.70
```

### Example 4: Fee Includes Shipping

```python
policy = FeePolicy(
    fee_type='percentage',
    fee_value=Decimal('2.5'),
    apply_to_shipping=True  # Fee applies to total
)

fee, net = AccountingService.calculate_fee(
    gross_amount=Decimal("100.00"),
    fee_policy=policy,
    shipping_amount=Decimal("10.00")
)

# Calculation:
# Fee base = $100 (shipping included)
# Fee = $100 * 2.5% = $2.50
# Net = $100 - $2.50 = $97.50
print(f"Fee: ${fee}, Net: ${net}")
# Output: Fee: $2.50, Net: $97.50
```

---

## 🔄 Settlement Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                  Payment Captured (Order Paid)                   │
│                                                                  │
│  Customer pays → Funds go to PENDING bucket                     │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Wallet State:                                             │ │
│  │   available_balance: $0.00                                │ │
│  │   pending_balance:   $97.50  ← Merchant net after fee    │ │
│  │   balance:           $97.50                               │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                      (Order Delivered)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       Order Delivered                            │
│                                                                  │
│  Funds move from PENDING → AVAILABLE                            │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Wallet State:                                             │ │
│  │   available_balance: $97.50  ← Ready for withdrawal      │ │
│  │   pending_balance:   $0.00                                │ │
│  │   balance:           $97.50                               │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    (Merchant Requests Withdrawal)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Withdrawal Request Created                     │
│                                                                  │
│  Status: PENDING (awaiting admin approval)                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Wallet State: (NO CHANGE YET)                             │ │
│  │   available_balance: $97.50                               │ │
│  │   pending_balance:   $0.00                                │ │
│  │   effective_available: $47.50  (minus pending withdrawal) │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                      (Admin Approves)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Withdrawal Approved                           │
│                                                                  │
│  Status: APPROVED (ready for bank transfer)                     │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Wallet State: (STILL NO CHANGE)                           │ │
│  │   available_balance: $97.50                               │ │
│  │   pending_balance:   $0.00                                │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                   (Admin Marks Paid + Payout Ref)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Withdrawal Paid                              │
│                                                                  │
│  Status: PAID (funds deducted, bank transfer completed)         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Wallet State:                                             │ │
│  │   available_balance: $47.50  ← Deducted $50              │ │
│  │   pending_balance:   $0.00                                │ │
│  │   balance:           $47.50                               │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧮 Balance Reconciliation

### Wallet Balance Formula

```python
wallet.balance = wallet.available_balance + wallet.pending_balance
```

### Effective Available Balance

```python
effective_available = wallet.available_balance - sum(pending_withdrawals)
```

**Example:**
```python
wallet.available_balance = Decimal("100.00")
wallet.pending_balance = Decimal("50.00")

# 2 pending withdrawals: $30 + $20 = $50
pending_withdrawals_sum = Decimal("50.00")

effective_available = Decimal("100.00") - Decimal("50.00")  # = $50.00
max_withdrawal = effective_available  # Can only withdraw $50
```

### Journal Entry Balance Check

```python
from apps.wallet.models import JournalEntry

entry = JournalEntry.objects.get(id=42)
is_balanced, message = entry.validate_balanced()

print(f"Balanced: {is_balanced}, Message: {message}")
# Output: Balanced: True, Message: Entry is balanced
```

### Ledger Integrity Check

```python
from apps.wallet.services.wallet_service import WalletService

result = WalletService.ledger_integrity_check(store_id=1, tenant_id=1)

print(result)
# Output:
# {
#     'store_id': 1,
#     'wallet_id': 5,
#     'is_valid': True,
#     'computed': {
#         'available_balance': '97.50',
#         'pending_balance': '0.00',
#         'balance': '97.50'
#     },
#     'stored': {
#         'available_balance': '97.50',
#         'pending_balance': '0.00',
#         'balance': '97.50'
#     },
#     'transaction_count': 12
# }
```

---

## 🔐 Idempotency Keys

### Pattern

```
{event_type}-{entity_type}-{entity_id}
```

### Examples

```python
# Payment capture
idempotency_key = f"payment-capture-order-{order_id}"
# Example: "payment-capture-order-123"

# Order delivered
idempotency_key = f"order-delivered-{order_id}"
# Example: "order-delivered-123"

# Refund
idempotency_key = f"refund-order-{order_id}"
# Example: "refund-order-123"

# Withdrawal paid
idempotency_key = f"withdrawal-paid-{withdrawal_id}"
# Example: "withdrawal-paid-456"
```

### Usage

```python
from apps.wallet.services.accounting_service import AccountingService

# First call - creates entry
entry1 = AccountingService.record_payment_capture(
    store_id=1,
    order_id=123,
    gross_amount=Decimal("100.00"),
    idempotency_key="payment-capture-order-123",  # ← Key
    tenant_id=1,
)

# Second call - returns existing entry (no duplicate)
entry2 = AccountingService.record_payment_capture(
    store_id=1,
    order_id=123,
    gross_amount=Decimal("100.00"),
    idempotency_key="payment-capture-order-123",  # ← Same key
    tenant_id=1,
)

assert entry1.id == entry2.id  # True - same entry returned
```

---

## 📞 Quick Commands

### Create Global Fee Policy

```python
from apps.wallet.models import FeePolicy
from decimal import Decimal

policy = FeePolicy.objects.create(
    name="Global Platform Fee - 2.5% + $0.30 min",
    fee_type="percentage",
    fee_value=Decimal("2.5"),
    minimum_fee=Decimal("0.30"),
    apply_to_shipping=False,
    is_active=True,
    # Leave store_id and plan_id as NULL for global
)
```

### Get Wallet Summary

```python
from apps.wallet.services.wallet_service import WalletService

summary = WalletService.get_wallet_summary(store_id=1, tenant_id=1)
print(summary)
```

### Query Journal Entries

```python
from apps.wallet.models import JournalEntry

entries = JournalEntry.objects.filter(
    store_id=1,
    entry_type='payment_captured'
).order_by('-created_at')[:10]

for entry in entries:
    print(f"{entry.created_at}: {entry.description}")
    for line in entry.lines.all():
        print(f"  {line.get_direction_display()}: {line.account.code} ${line.amount}")
```

### Query Payment Allocations

```python
from apps.wallet.models import PaymentAllocation

allocation = PaymentAllocation.objects.get(order_id=123)
print(f"Gross: ${allocation.gross_amount}")
print(f"Fee: ${allocation.platform_fee}")
print(f"Net: ${allocation.merchant_net}")
```

---

**For full documentation, see:** `docs/WALLET_ENTERPRISE_UPGRADE.md`
