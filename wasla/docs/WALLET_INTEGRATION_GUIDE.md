# Wallet Integration Guide

## Overview

This guide explains how to integrate the enterprise wallet system with other Wasla apps (payments, orders, refunds, settlements).

The wallet system is **event-driven** - it listens for signals from other apps and automatically posts accounting entries and updates merchant balances.

---

## Integration Points

### 1. Payment Captured (Order Payment Received)

**When:** Customer completes payment for an order
**Trigger:** Payment gateway confirms transaction
**Action:** Add funds to merchant's pending balance, calculate and deduct fees

**Signal:** `apps.payments.signals.payment_captured`

**Implementation:**

```python
# File: apps/payments/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.payments.models import Payment
from apps.wallet.services.wallet_service import WalletService
from apps.wallet.models import FeePolicy

@receiver(post_save, sender=Payment)
def on_payment_captured(sender, instance, created, **kwargs):
    """
    Signal handler: Customer payment received.
    Posts journal entry and updates merchant balance.
    """
    if not created or instance.status != 'completed':
        return
    
    # Get merchant fee policy
    fee_policy = FeePolicy.objects.filter(
        store=instance.order.store,
        is_active=True
    ).first() or FeePolicy.objects.filter(
        scope='global',
        is_active=True
    ).first()
    
    # Record payment in wallet accounting
    WalletService.on_order_paid(
        store=instance.order.store,
        order_id=instance.order.id,
        amount=instance.amount,
        fee_policy=fee_policy,
        user=None,  # System generated
        idempotency_key=f"payment-{instance.id}"
    )
```

**Database Transaction:**
```
Debit:  CASH (Asset)                    100.00
Credit: MERCHANT_PAYABLE_PENDING        97.50
        PLATFORM_REVENUE_FEES            2.50
```

**Balance Change:**
- `pending_balance` += 97.50
- `available_balance` unchanged (pending until delivery)

---

### 2. Order Delivered (Fulfillment Complete)

**When:** Merchant confirms order delivery
**Trigger:** Order status changes to "delivered"
**Action:** Move balance from pending to available

**Signal:** `apps.orders.signals.order_delivered`

**Implementation:**

```python
# File: apps/orders/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.orders.models import Order
from apps.wallet.services.wallet_service import WalletService

@receiver(post_save, sender=Order)
def on_order_delivered(sender, instance, created, **kwargs):
    """
    Signal handler: Order marked as delivered.
    Moves balance from pending to available settlement.
    """
    if instance.status != 'delivered':
        return
    
    # Get the payment amount (net of fees)
    # This should come from payment/allocation
    from apps.wallet.models import PaymentAllocation
    
    allocation = PaymentAllocation.objects.filter(
        journal_entry__reference_id=str(instance.id)
    ).first()
    
    if not allocation:
        return
    
    # Move from pending to available
    WalletService.on_order_delivered(
        store=instance.store,
        order_id=instance.id,
        amount=allocation.net_amount,
        user=None,
        idempotency_key=f"delivery-{instance.id}"
    )
```

**Database Transaction:**
```
Debit:  MERCHANT_PAYABLE_PENDING        97.50
Credit: MERCHANT_PAYABLE_AVAILABLE      97.50
```

**Balance Change:**
- `pending_balance` -= 97.50
- `available_balance` += 97.50

---

### 3. Refund Issued (Customer Return)

**When:** Order is refunded (customer return, cancel, damage)
**Trigger:** Refund request approved, payment reversed
**Action:** Credit merchant back, optionally refund platform fee

**Signal:** `apps.refunds.signals.refund_issued`

**Implementation:**

```python
# File: apps/refunds/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.refunds.models import Refund
from apps.wallet.services.wallet_service import WalletService

@receiver(post_save, sender=Refund)
def on_refund_issued(sender, instance, created, **kwargs):
    """
    Signal handler: Refund issued to customer.
    Reverses payment and optionally fee on merchant account.
    """
    if not created or instance.status != 'approved':
        return
    
    # Determine if platform absorbs fee loss
    # (Business policy: usually YES for damage/return, NO for courtesy)
    reverse_platform_fee = instance.reason in [
        'damaged',
        'defective',
        'lost_in_shipping'
    ]
    
    WalletService.on_refund(
        store=instance.order.store,
        order_id=instance.order.id,
        amount=instance.amount,
        reverse_full_fee=reverse_platform_fee,
        user=None,
        idempotency_key=f"refund-{instance.id}"
    )
```

**Database Transaction (with fee reversal):**
```
Debit:  PLATFORM_REVENUE_FEES           2.50
Credit: MERCHANT_PAYABLE_AVAILABLE      2.50
        REFUNDS_PAYABLE                 100.00
```

**Balance Change:**
- If in `pending`: `pending_balance` -= 97.50
- If in `available`: `available_balance` -= 97.50
- If fee reversed: effective loss to platform

---

### 4. Settlement/Payout (Periodic Merchant Payouts)

**When:** Scheduled settlement run (daily/weekly/monthly)
**Trigger:** Settlement batch job
**Action:** Create bulk withdrawal requests, settle merchants

**Implementation:**

```python
# File: apps/settlements/tasks.py (Celery task)

from celery import shared_task
from apps.stores.models import Store
from apps.wallet.services.wallet_service import WalletService
from apps.wallet.models import SettlementBatch

@shared_task
def run_settlement_batch():
    """
    Daily settlement task:
    Create withdrawal requests for all merchants above threshold.
    """
    stores = Store.objects.filter(
        is_active=True,
        auto_settlement_enabled=True
    )
    
    batch = SettlementBatch.objects.create()
    
    for store in stores:
        wallet = store.wallet
        
        # Only settle if balance exceeds minimum
        if wallet.available_balance < store.settlement_threshold:
            continue
        
        # Auto-request withdrawal
        withdrawal = WalletService.request_withdrawal(
            store=store,
            amount=wallet.available_balance,
            note="Automatic daily settlement",
            requested_by=None  # System
        )
        
        batch.withdrawals.add(withdrawal)
    
    return {
        'batch_id': batch.id,
        'total_withdrawals': batch.withdrawals.count()
    }
```

---

## Configuration

### Enable Signals in App Config

```python
# File: apps/wallet/apps.py

from django.apps import AppConfig

class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.wallet'
    
    def ready(self):
        """Register signal handlers when Django starts."""
        # Import payment signals
        try:
            from apps.payments.signals import on_payment_captured  # noqa
        except ImportError:
            pass
        
        # Import order signals
        try:
            from apps.orders.signals import on_order_delivered  # noqa
        except ImportError:
            pass
        
        # Import refund signals
        try:
            from apps.refunds.signals import on_refund_issued  # noqa
        except ImportError:
            pass
```

### Settings Configuration

```python
# File: config/settings.py

# Wallet Configuration
WALLET_CONFIG = {
    # Auto-settlement settings
    'AUTO_SETTLEMENT_ENABLED': True,
    'SETTLEMENT_THRESHOLD': Decimal('100.00'),  # Min $100 to trigger withdrawal
    'SETTLEMENT_SCHEDULE': 'daily',  # or 'weekly', 'monthly'
    
    # Fee settings
    'DEFAULT_FEE_PERCENTAGE': Decimal('2.50'),
    'MINIMUM_FEE': Decimal('0.50'),
    
    # Withdrawal settings
    'WITHDRAWAL_MIN_AMOUNT': Decimal('10.00'),
    'WITHDRAWAL_PROCESSING_TIME_HOURS': 24,  # Typical processing time
    
    # Refund settings
    'REFUND_REVERSES_FULL_FEE': True,  # Platform absorbs fee on refunds
}
```

---

## Idempotency Keys

All wallet operations use **idempotency keys** to prevent duplicate processing.

```python
# Always use unique, deterministic keys
idempotency_key = f"payment-{payment.id}"      # Payment capture
idempotency_key = f"delivery-{order.id}"       # Order delivery
idempotency_key = f"refund-{refund.id}"        # Refund
idempotency_key = f"withdrawal-{wd.id}"        # Withdrawal
```

If the same operation is retried (webhook retry, failed task retry):
1. Check if idempotency_key already exists in JournalEntry
2. If exists: return existing entry (no duplicate)
3. If not: create new entry

---

## Error Handling

### Webhook Retry Logic

```python
# File: apps/payments/webhooks.py

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import hmac
import hashlib

@csrf_exempt
def payment_webhook(request):
    """
    Payment gateway webhook (Stripe, PayPal, etc.)
    Gets called when payment is completed.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    
    # Verify webhook signature
    signature = request.headers.get('X-Signature')
    payload = request.body
    
    if not verify_signature(signature, payload):
        return JsonResponse({'status': 'unauthorized'}, status=401)
    
    try:
        data = json.loads(payload)
        payment = Payment.objects.get(id=data['payment_id'])
        
        # Process payment (wallet update happens via signal)
        payment.status = 'completed'
        payment.save()
        
        return JsonResponse({'status': 'success'})
    
    except Payment.DoesNotExist:
        # Payment not found - likely duplicate/test
        return JsonResponse({'status': 'not_found'}, status=404)
    
    except Exception as e:
        # Log error and return 500 for retry
        logger.error(f"Payment webhook error: {e}")
        return JsonResponse({'status': 'error'}, status=500)
```

### Wallet Service Retry

```python
# File: apps/wallet/services/wallet_service.py

from django.db import transaction

def on_order_paid(self, store, order_id, amount, fee_policy, user, idempotency_key):
    """
    Record payment with automatic retry on failure.
    """
    with transaction.atomic():
        try:
            # Check if already processed
            existing = JournalEntry.objects.filter(
                store=store,
                idempotency_key=idempotency_key
            ).first()
            
            if existing:
                return existing  # Already processed
            
            # Create new entry
            entry = AccountingService.record_payment_capture(
                store=store,
                order_id=order_id,
                amount=amount,
                fee_policy=fee_policy,
                idempotency_key=idempotency_key
            )
            
            # Update wallet balances
            wallet = Wallet.objects.get(store=store)
            fee = AccountingService.calculate_fee(amount, fee_policy)
            
            wallet.pending_balance += (amount - fee)
            wallet.save()
            
            return entry
        
        except Exception as e:
            logger.error(f"Payment processing failed: {e}")
            raise  # Re-raise for retry mechanism
```

---

## Testing Integration

### Unit Test Example

```python
# File: apps/wallet/tests/test_integration.py

from django.test import TransactionTestCase
from apps.payments.models import Payment
from apps.wallet.models import Wallet, JournalEntry

class PaymentWalletIntegrationTest(TransactionTestCase):
    
    def test_payment_signal_updates_wallet(self):
        """Test that payment signal correctly updates wallet."""
        # Create payment
        payment = Payment.objects.create(
            amount=Decimal('100.00'),
            status='pending'
        )
        
        # Check wallet before
        wallet = payment.order.store.wallet
        initial_pending = wallet.pending_balance
        
        # Complete payment (triggers signal)
        payment.status = 'completed'
        payment.save()
        
        # Check wallet after
        wallet.refresh_from_db()
        
        # Should have recorded transaction
        self.assertEqual(
            wallet.pending_balance,
            initial_pending + Decimal('97.50')  # After 2.5% fee
        )
        
        # Should have created journal entry
        entry = JournalEntry.objects.filter(
            reference_id=str(payment.id)
        ).first()
        self.assertIsNotNone(entry)
```

---

## Monitoring & Debugging

### Check Wallet Status

```bash
# Django shell
python manage.py shell

from apps.wallet.models import Wallet, JournalEntry
from apps.stores.models import Store

store = Store.objects.get(name="Test Store")
wallet = store.wallet

print(f"Available: {wallet.available_balance}")
print(f"Pending: {wallet.pending_balance}")
print(f"Total: {wallet.available_balance + wallet.pending_balance}")

# Check recent entries
entries = JournalEntry.objects.filter(store=store).order_by('-created_at')[:10]
for entry in entries:
    print(f"{entry.entry_date} {entry.entry_type}: {entry.reference_id}")
```

### Verify Double-Entry Balance

```python
# Check that ledger is balanced
from apps.wallet.models import JournalEntry

store = Store.objects.get(name="Test Store")
entries = JournalEntry.objects.filter(store=store)

for entry in entries:
    try:
        entry.validate_balanced()
        print(f"✓ Entry {entry.id} is balanced")
    except ValidationError:
        print(f"✗ Entry {entry.id} is UNBALANCED - FIX REQUIRED")
```

---

## Rollback & Recovery

### If Integration Fails

```bash
# 1. Check unprocessed entries
python manage.py shell

from apps.wallet.models import JournalEntry
from apps.stores.models import Store

store = Store.objects.get(name="Test Store")
unbalanced = []

for entry in JournalEntry.objects.filter(store=store):
    try:
        entry.validate_balanced()
    except:
        unbalanced.append(entry.id)

print(f"Found {len(unbalanced)} unbalanced entries: {unbalanced}")

# 2. Manual reversal (if needed)
from apps.wallet.services.wallet_service import WalletService

service = WalletService()
service.on_refund(
    store=store,
    order_id=order_id,
    amount=Decimal('100.00'),
    reverse_full_fee=True,
    user=None,
    idempotency_key=f"manual-reversal-{timestamp}"
)

# 3. Verify balance reconciliation
wallet = store.wallet
journal_balance = sum(...)  # Calculate from JournalEntry
print(f"Wallet balance: {wallet.available_balance}")
print(f"Journal balance: {journal_balance}")
assert wallet.available_balance == journal_balance
```

---

## Summary

| Event | Trigger | Action | Balance Impact |
|-------|---------|--------|-----------------|
| **Payment Captured** | Payment complete | Post entry, charge fee | Pending +, Available - |
| **Order Delivered** | Fulfillment complete | Move pending→available | Pending -, Available + |
| **Refund Issued** | Customer return | Reverse payment/fee | Available -, Pending - |
| **Withdrawal Requested** | Merchant request | Hold for approval | No change (pending) |
| **Withdrawal Approved** | Admin action | Mark approved | No change (still pending) |
| **Withdrawal Paid** | Payout sent | Settle merchant | Available (deduct) |

All operations are **idempotent**, **atomic**, and **auditable** via the journal ledger.
