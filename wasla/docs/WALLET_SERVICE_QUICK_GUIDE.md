# Wallet Service API - Quick Developer Guide

**Status:** Ready for Production  
**Last Updated:** 2026-02-25

## Quick Start

### 1. Basic Wallet Operations

```python
from decimal import Decimal
from apps.wallet.services.wallet_service import WalletService

# Get or create wallet for a store
wallet = WalletService.get_or_create_wallet(
    store_id=5,
    currency="USD",
    tenant_id=1,
)

# Manual credit (top-up)
WalletService.credit(
    wallet=wallet,
    amount=Decimal("100.00"),
    reference="manual-topup:001",
)

# Manual debit (adjustment)
WalletService.debit(
    wallet=wallet,
    amount=Decimal("10.00"),
    reference="adjustment:001",
)
```

### 2. Order Payment Flow

```python
# When order is paid
WalletService.on_order_paid(
    store_id=5,
    net_amount=Decimal("99.99"),
    reference=f"order:{order_id}",
    tenant_id=1,
)

# When order is delivered
WalletService.on_order_delivered(
    store_id=5,
    net_amount=Decimal("99.99"),
    reference=f"order:{order_id}-delivered",
    tenant_id=1,
)
```

### 3. Refund Processing

```python
# When customer requests refund
WalletService.on_refund(
    store_id=5,
    amount=Decimal("99.99"),
    reference=f"refund:{refund_id}",
    tenant_id=1,
)
```

### 4. Withdrawal Request

```python
from django.contrib.auth import get_user_model
User = get_user_model()

# Merchant requests withdrawal
withdrawal = WalletService.create_withdrawal_request(
    store_id=5,
    amount=Decimal("500.00"),
    tenant_id=1,
    note="Weekly settlement",
)

# Admin approves
admin = User.objects.get(username="admin")
WalletService.approve_withdrawal(
    withdrawal_id=withdrawal.id,
    actor_user_id=admin.id,
)

# Mark as paid (when funds actually transferred)
WalletService.mark_withdrawal_paid(
    withdrawal_id=withdrawal.id,
    actor_user_id=admin.id,
)
```

---

## API Reference by Use Case

### Use Case 1: Retrieve Wallet Status

```python
# Get wallet summary
summary = WalletService.get_wallet_summary(
    store_id=5,
    tenant_id=1,
)

print(f"Available: {summary['available_balance']}")
print(f"Pending: {summary['pending_balance']}")
print(f"Effective: {summary['effective_available_balance']}")
```

**Response (dict):**
```python
{
    "wallet_id": 42,
    "store_id": 5,
    "currency": "USD",
    "available_balance": "500.00",
    "pending_balance": "250.00",
    "balance": "750.00",
    "pending_withdrawal_amount": "100.00",  # Sum of pending withdrawals
    "effective_available_balance": "400.00",  # Can actually withdraw this much
    "is_active": True,
}
```

### Use Case 2: List Wallet Transactions

**All transactions:**
```python
txns = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
    limit=100,
)

for txn in txns:
    print(f"{txn.created_at}: {txn.event_type} {txn.amount} ({txn.transaction_type})")
```

**Filter by event type:**
```python
# Only order-related
orders = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
    event_type="order_paid",
)

# Only refunds
refunds = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
    event_type="refund",
)

# Only adjustments
adjustments = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
    event_type="adjustment",
)
```

### Use Case 3: List Withdrawal Requests

**All withdrawals:**
```python
withdrawals = WalletService.list_withdrawal_requests(
    store_id=5,
    tenant_id=1,
    limit=50,
)
```

**Filter by status:**
```python
# Pending approval
pending = WalletService.list_withdrawal_requests(
    store_id=5,
    tenant_id=1,
    status="pending",
)

# Already approved
approved = WalletService.list_withdrawal_requests(
    store_id=5,
    tenant_id=1,
    status="approved",
)

# Completed
paid = WalletService.list_withdrawal_requests(
    store_id=5,
    tenant_id=1,
    status="paid",
)
```

### Use Case 4: Get Specific Withdrawal

**By ID:**
```python
withdrawal = WalletService.get_withdrawal_request(
    withdrawal_id=123,
)

if withdrawal:
    print(f"Amount: {withdrawal.amount}")
    print(f"Status: {withdrawal.status}")
else:
    # Not found
    pass
```

**By Reference Code:**
```python
withdrawal = WalletService.get_withdrawal_request_by_reference(
    reference_code="WD-5-ABC123XYZ",
)

if withdrawal:
    print(f"Created: {withdrawal.requested_at}")
    print(f"Processed: {withdrawal.processed_at}")
```

### Use Case 5: Validate Ledger Integrity

```python
result = WalletService.ledger_integrity_check(
    store_id=5,
    tenant_id=1,
)

if result["is_valid"]:
    print("✅ Ledger is valid")
else:
    print("❌ Ledger corruption detected!")
    print(f"Computed: {result['computed']}")
    print(f"Stored: {result['stored']}")
    # Alert admin/ops team
```

---

## Error Handling

### Common Errors

```python
from apps.wallet.services.wallet_service import WalletService

try:
    WalletService.on_order_paid(
        store_id=5,
        net_amount=Decimal("-10.00"),  # Invalid!
        reference="order:123",
    )
except ValueError as e:
    print(f"Error: {e}")  # "Amount must be positive"
```

### Error Types

```python
# Insufficient balance
try:
    WalletService.create_withdrawal_request(
        store_id=5,
        amount=Decimal("10000.00"),  # More than available
    )
except ValueError as e:
    print(e)  # "Withdrawal amount exceeds available balance"

# Invalid state transition
try:
    WalletService.approve_withdrawal(
        withdrawal_id=789,  # Already approved
    )
except ValueError as e:
    print(e)  # "Only pending withdrawal can be approved"

# Not found
wd = WalletService.get_withdrawal_request(withdrawal_id=99999)
if not wd:
    print("Withdrawal not found")
```

---

## Integration Examples

### Example 1: Webhook Handler for Order Paid

```python
# In your order/payment app
from decimal import Decimal
from apps.wallet.services.wallet_service import WalletService

def handle_payment_webhook(webhook_data):
    """Called when payment provider confirms payment."""
    
    order_id = webhook_data["order_id"]
    amount = Decimal(webhook_data["amount"])
    
    try:
        WalletService.on_order_paid(
            store_id=webhook_data["store_id"],
            net_amount=amount,
            reference=f"order:{order_id}",
            tenant_id=webhook_data["tenant_id"],
        )
        
        return {"status": "success"}
    
    except ValueError as e:
        logger.error(f"Failed to record payment for order {order_id}: {e}")
        # Don't fail the webhook, but alert
        send_alert(f"Wallet error: {e}")
        return {"status": "recorded_with_warning"}
```

### Example 2: Custom Admin Command for Batch Settlement

```python
# management/commands/process_settlements.py
from django.core.management.base import BaseCommand
from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.wallet.models import WithdrawalRequest
from apps.wallet.services.wallet_service import WalletService

User = get_user_model()

class Command(BaseCommand):
    help = "Process approved withdrawals"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
        )
    
    def handle(self, *args, **options):
        admin = User.objects.get(username="settlement_bot")
        batch_size = options["batch_size"]
        
        # Get approved withdrawals
        approved = WithdrawalRequest.objects.filter(
            status="approved"
        ).order_by("requested_at")[:batch_size]
        
        paid_count = 0
        failed_count = 0
        
        for withdrawal in approved:
            try:
                WalletService.mark_withdrawal_paid(
                    withdrawal_id=withdrawal.id,
                    actor_user_id=admin.id,
                )
                paid_count += 1
                
            except ValueError as e:
                logger.error(f"Failed to pay withdrawal {withdrawal.id}: {e}")
                failed_count += 1
        
        self.stdout.write(
            f"Processed {paid_count}, Failed {failed_count}"
        )
```

### Example 3: API Endpoint for Merchant Withdrawal

```python
# In your merchant API
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.wallet.services.wallet_service import WalletService
from apps.stores.models import Store

class MerchantWalletViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=["get"])
    def balance(self, request):
        """Get merchant's wallet balance."""
        store = request.user.store  # Assuming user has store
        
        summary = WalletService.get_wallet_summary(
            store_id=store.id,
            tenant_id=store.tenant_id,
        )
        
        return Response(summary)
    
    @action(detail=False, methods=["post"])
    def request_withdrawal(self, request):
        """Request a withdrawal."""
        from decimal import Decimal
        
        amount = Decimal(request.data.get("amount"))
        note = request.data.get("note", "")
        
        try:
            withdrawal = WalletService.create_withdrawal_request(
                store_id=request.user.store.id,
                amount=amount,
                tenant_id=request.user.store.tenant_id,
                note=note,
            )
            
            return Response({
                "id": withdrawal.id,
                "reference_code": withdrawal.reference_code,
                "status": withdrawal.status,
                "amount": str(withdrawal.amount),
            }, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=["get"])
    def withdrawals(self, request):
        """List merchant's withdrawals."""
        withdrawals = WalletService.list_withdrawal_requests(
            store_id=request.user.store.id,
            tenant_id=request.user.store.tenant_id,
        )
        
        return Response([{
            "id": w.id,
            "amount": str(w.amount),
            "status": w.status,
            "requested_at": w.requested_at,
            "reference_code": w.reference_code,
        } for w in withdrawals])
```

---

## Testing Examples

### Unit Test

```python
from django.test import TestCase
from decimal import Decimal
from apps.wallet.services.wallet_service import WalletService
from apps.stores.models import Store
from apps.tenants.models import Tenant

class WalletServiceTestCase(TestCase):
    
    def test_order_payment_flow(self):
        """Test order payment → delivery → withdrawal."""
        
        # Setup
        tenant = Tenant.objects.create(slug="test", name="Test")
        store = Store.objects.create(
            tenant=tenant,
            slug="test-store",
            owner_id=1,
        )
        
        # Pay
        wallet = WalletService.on_order_paid(
            store_id=store.id,
            net_amount=Decimal("100.00"),
            reference="order:1",
            tenant_id=tenant.id,
        )
        
        self.assertEqual(wallet.pending_balance, Decimal("100.00"))
        self.assertEqual(wallet.available_balance, Decimal("0.00"))
        
        # Deliver
        wallet = WalletService.on_order_delivered(
            store_id=store.id,
            net_amount=Decimal("100.00"),
            reference="order:1-delivered",
            tenant_id=tenant.id,
        )
        
        self.assertEqual(wallet.pending_balance, Decimal("0.00"))
        self.assertEqual(wallet.available_balance, Decimal("100.00"))
        
        # Request withdrawal
        withdrawal = WalletService.create_withdrawal_request(
            store_id=store.id,
            amount=Decimal("100.00"),
            tenant_id=tenant.id,
        )
        
        self.assertEqual(withdrawal.status, "pending")
```

### Integration Test

```python
from django.test import TestCase, Client
from decimal import Decimal

class WalletAPITestCase(TestCase):
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="merchant",
            password="pass123",
        )
    
    def test_merchant_can_request_withdrawal(self):
        """Test API endpoint for withdrawal request."""
        
        self.client.login(username="merchant", password="pass123")
        
        response = self.client.post("/api/merchant/wallet/request-withdrawal/", {
            "amount": "100.00",
            "note": "Weekly settlement",
        })
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "pending")
        self.assertIn("reference_code", data)
```

---

## Debugging Commands

### Check Wallet Health

```bash
python manage.py shell

# Check specific store
from apps.wallet.services.wallet_service import WalletService
result = WalletService.ledger_integrity_check(store_id=5, tenant_id=1)
print(f"Valid: {result['is_valid']}")
print(f"Computed: {result['computed']}")
print(f"Stored: {result['stored']}")

# Check all stores
from apps.wallet.models import Wallet
for wallet in Wallet.objects.all():
    result = WalletService.ledger_integrity_check(
        store_id=wallet.store_id,
        tenant_id=wallet.tenant_id,
    )
    if not result["is_valid"]:
        print(f"❌ Store {wallet.store_id}: {result}")
```

### View Transaction History

```bash
python manage.py shell

from apps.wallet.models import WalletTransaction

# By store
from apps.wallet.services.wallet_service import WalletService
txns = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
)

for txn in txns:
    print(f"{txn.created_at} | {txn.event_type:20} | {txn.amount:>10} | {txn.transaction_type}")

# By event type
order_txns = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
    event_type="order_paid",
)
```

### Pending Withdrawal Report

```bash
python manage.py shell

from apps.wallet.services.wallet_service import WalletService
pending = WalletService.list_withdrawal_requests(
    store_id=5,
    status="pending",
)

total_pending = sum(w.amount for w in pending)
print(f"Pending withdrawals: {len(pending)}")
print(f"Total amount: {total_pending}")

for w in pending:
    days_ago = (timezone.now() - w.requested_at).days
    print(f"  {w.id}: {w.amount} ({days_ago} days old)")
```

---

## Performance Tips

### 1. Use select_related for Foreignkeys

```python
# Avoid N+1 queries
withdrawals = WithdrawalRequest.objects.select_related(
    "wallet"
).filter(status="pending")

for w in withdrawals:
    print(f"{w.wallet.store_id}: {w.amount}")
```

### 2. Prefetch Related for Reverse Relations

```python
# Get withdrawals per wallet efficiently
from django.db.models import Prefetch

wallets = Wallet.objects.prefetch_related(
    Prefetch(
        "withdrawal_requests",
        queryset=WithdrawalRequest.objects.filter(status="pending")
    )
)

for wallet in wallets:
    for wd in wallet.withdrawal_requests.all():
        print(f"{wd.amount}")
```

### 3. Use `.values()` for Reports

```python
# Aggregate without loading all objects
from django.db.models import Sum

summary = WithdrawalRequest.objects.filter(
    status="pending"
).aggregate(
    total=Sum("amount"),
    count=Count("id"),
)

print(f"Total pending: {summary['total']}")
print(f"Requests: {summary['count']}")
```

### 4. Pagination

```python
from django.core.paginator import Paginator

txns = WalletService.list_wallet_transactions(
    store_id=5,
    tenant_id=1,
    limit=1000,
)

paginator = Paginator(txns, 100)

for page_num in paginator.page_range:
    page = paginator.get_page(page_num)
    # Process page
```

---

## FAQ

**Q: Can a withdrawal be cancelled after approval?**  
A: No. Once approved, it must be paid or the whole system rolls back. Reject it before approval.

**Q: What if a refund is larger than available balance?**  
A: The system raises `ValueError`. Check balance before refunding.

**Q: Are withdrawal reference codes globally unique?**  
A: Yes, globally across all stores. Format: `WD-{store_id}-{uuid}`

**Q: Can I manually override a wallet balance?**  
A: Not recommended. Use `ledger_integrity_check()` first to diagnose the issue.

**Q: How do I handle negative balances if they occur?**  
A: Critical issue. Run ledger integrity check, identify the transaction causing it, and investigate.

**Q: What's the difference between available and pending?**  
A: **Pending** = customer paid but not delivered yet (could be refunded)  
**Available** = customer took delivery (merchant earned it)

---

## Support

**Report Issues:**
- Include store_id and tenant_id
- Provide date range of affected transactions
- Include error message and stack trace

**Emergency:**
- Ledger integrity failure
- Negative balance detected
- Large unauthorized withdrawal

For production issues, escalate immediately.
