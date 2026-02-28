# Recurring Billing System - Quick Reference

## TL;DR: How It Works

```
DAILY JOB (2 AM):    Charge all subscriptions due
╭─────────────────────────────────────╮
│ Create BillingCycle + Invoice       │
│ Attempt payment via PaymentMethod   │
│ Start dunning if failed             │
╰─────────────────────────────────────╯

DAILY JOB (3 AM):    Retry failed payments  
╭─────────────────────────────────────╮
│ Process queued DunningAttempts      │
│ Exponential backoff (3, 5, 7, 14d)  │
│ Suspend after 5 failed retries      │
╰─────────────────────────────────────╯

HOURLY:              Sync payment provider webhooks
╭─────────────────────────────────────╮
│ Reprocess failed PaymentEvents      │
│ Idempotent (provider_event_id key)  │
╰─────────────────────────────────────╯
```

## Key Models (Quick Glance)

```python
Subscription            # Main entity (1 per tenant)
├── state: 'active' | 'past_due' | 'grace' | 'suspended' | 'cancelled'
├── plan: BillingPlan
├── payment_method: PaymentMethod
├── next_billing_date: When to bill next
└── grace_until: Extended deadline (if in grace)

BillingCycle           # Month of billing (many per subscription)
├── period_start, period_end: Billing period
├── status: 'pending' | 'billed' | 'partial' | 'paid' | 'failed'
└── total: Amount to charge

Invoice                # Payment document (1 per cycle)
├── number: Unique per tenant (INV-2026-0001)
├── status: 'draft' | 'issued' | 'overdue' | 'partial' | 'paid'
├── idempotency_key: Prevents duplicate creation
└── amount_due: Remaining balance

DunningAttempt         # Retry tracker
├── attempt_number: 1-5
├── scheduled_for: When to retry
└── status: 'pending' | 'in_progress' | 'success' | 'failed'

PaymentMethod          # Credit card, bank, wallet
├── method_type: 'card' | 'bank' | 'wallet'
├── provider_customer_id: From Stripe/Tap/PayMob
└── is_valid(): Check status & expiration

PaymentEvent           # Webhook from provider (idempotent!)
├── provider_event_id: Unique from provider (idempotency key)
├── event_type: 'payment.succeeded' | 'payment.failed' | etc
├── status: 'received' | 'processing' | 'processed' | 'failed'
└── payload: Full webhook data
```

## API Cheat Sheet

### Create Subscription
```python
from apps.subscriptions.services_billing import SubscriptionService

sub = SubscriptionService.create_subscription(
    tenant=tenant_obj,
    plan=plan_obj,
    payment_method=pm_obj,
    idempotency_key='unique_key_123'  # Optional, for idempotency
)
```

### Change Plan (Upgrade/Downgrade)
```python
sub = SubscriptionService.change_plan(
    subscription=sub,
    new_plan=new_plan_obj
    # Proration calculated automatically
)
```

### Record Payment
```python
from apps.subscriptions.services_billing import BillingService

invoice = BillingService.record_payment(
    invoice=invoice_obj,
    amount=Decimal('99.00'),
    provider_payment_id='stripe_charge_id'
)
# Updates: amount_paid, amount_due, status
```

### Start Dunning (Manual)
```python
from apps.subscriptions.services_billing import DunningService

attempt = DunningService.start_dunning(invoice=invoice_obj)
# Creates first retry attempt, marks invoice overdue
```

### Add Grace Period
```python
sub = DunningService.add_grace_period(
    subscription=sub,
    days=7
)
# Extends deadline, changes state to 'grace'
```

### Handle Webhook (Idempotent!)
```python
from apps.subscriptions.services_billing import WebhookService

event = WebhookService.handle_payment_event(
    event_type='payment.succeeded',
    provider_event_id='evt_stripe_123',  # MUST be unique!
    payload={'customer_id': 'cus_123', 'amount': '99.00', ...}
)
# Same provider_event_id = returns cached result
```

## State Transitions

```
Active ─payload──────────────┐
  │                          │
  │ (payment fails)          │ (payment succeeds)
  ▼                          │
Past Due                      │
  │                          │
  │ (add grace)              │
  ▼                          │
Grace ────────────────────────┘
  │              (payment)
  │ (expires)
  ▼
Suspended
  │
  │ (payment received)
  └────────────► Active
```

## Database Queries

### Find subscriptions needing billing
```python
from datetime import date
from apps.subscriptions.models_billing import Subscription

today = date.today()
due = Subscription.objects.filter(
    state='active',
    next_billing_date=today
).select_related('plan', 'payment_method')
```

### Find overdue invoices
```python
from apps.subscriptions.models_billing import Invoice

overdue = Invoice.objects.filter(
    status__in=['issued', 'overdue', 'partial'],
    due_date__lt=date.today()
)
```

### Find due dunning attempts
```python
from apps.subscriptions.models_billing import DunningAttempt
from django.utils import timezone

due = DunningAttempt.objects.filter(
    status='pending',
    scheduled_for__lte=timezone.now()
)
```

### Find failed webhooks (for manual retry)
```python
failed = PaymentEvent.objects.filter(status='failed')
max_age = timezone.now() - timedelta(days=1)
recent_failures = failed.filter(created_at__gte=max_age)
```

## Common Tasks

### Check if subscription can access service
```python
sub = Subscription.objects.get(tenant=tenant)
if sub.can_use_service():
    # Merchant can use service (active, past_due, or grace)
    print("Access granted")
else:
    # Suspended or cancelled
    print("Access denied")
```

### Get next billing date
```python
sub.next_billing_date  # DateField
days_until = (sub.next_billing_date - date.today()).days
```

### Check if payment method is valid
```python
if sub.payment_method.is_valid():
    # Card not expired, status is 'active'
    can_charge = True
else:
    # Expired or invalid
    need_update = True
```

### Calculate invoice amount due
```python
invoice.amount_due  # Decimal field
invoice.amount_paid  # Decimal field
still_owed = invoice.amount_due - invoice.amount_paid
```

### Get current billing cycle
```python
from apps.subscriptions.models_billing import BillingCycle

current = BillingCycle.objects.filter(
    subscription=sub,
    status__in=['pending', 'billed']
).first()

if current:
    days_in_period = (current.period_end - current.period_start).days
```

## Testing Locally

```bash
# Run all billing tests
pytest apps/subscriptions/tests_billing.py -v

# Run specific test
pytest apps/subscriptions/tests_billing.py::SubscriptionServiceTests::test_create_subscription -v

# Test idempotency
pytest apps/subscriptions/tests_billing.py::IdempotencyTests -v

# Test tenant isolation
pytest apps/subscriptions/tests_billing.py::TenantIsolationTests -v

# Check coverage
pytest apps/subscriptions/tests_billing.py --cov=apps.subscriptions
```

## Celery Beat Jobs (Schedule)

```python
# Add to Django settings.py

CELERY_BEAT_SCHEDULE = {
    # Bill all active subscriptions
    'process-recurring-billing': {
        'task': 'apps.subscriptions.tasks_billing.process_recurring_billing',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
    
    # Retry failed payments
    'process-dunning-attempts': {
        'task': 'apps.subscriptions.tasks_billing.process_dunning_attempts',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
    
    # Auto-suspend after grace expires
    'check-grace-periods': {
        'task': 'apps.subscriptions.tasks_billing.check_and_expire_grace_periods',
        'schedule': crontab(hour=4, minute=0),  # 4 AM daily
    },
    
    # Retry failed webhooks
    'sync-payment-events': {
        'task': 'apps.subscriptions.tasks_billing.sync_unprocessed_payment_events',
        'schedule': crontab(minute=0),  # Every hour
    },
    
    # Clean old records
    'cleanup-billing-records': {
        'task': 'apps.subscriptions.tasks_billing.cleanup_old_billing_records',
        'schedule': crontab(hour=2, minute=0, day_of_week=6),  # Sunday 2 AM
    },
}
```

## Monitoring Checklist

Daily:
- [ ] Check `Invoice.objects.filter(status='paid').count()` (should increase)
- [ ] Check `DunningAttempt.objects.filter(status='success').count()` (recovery rate)
- [ ] Check `Subscription.objects.filter(state='suspended').count()` (at-risk)
- [ ] Check `PaymentEvent.objects.filter(status='failed').count()` (webhook issues)

Weekly:
- [ ] Revenue collected vs. plan prices
- [ ] Failed payment recovery rate  
- [ ] Webhook delivery reliability
- [ ] Manual overrides needed

## Gotchas & Tips

1. **Provider Event ID is Critical**  
   Use provider's event ID (Stripe: `id`, Tap: `id`) as `provider_event_id` for idempotency!

2. **Idempotency Keys**  
   Any operation can include `idempotency_key` parameter for safety in retries.

3. **Billing Cycle Anchor**  
   Day of month (1-28) when subscription renews. Avoid 29-31 for multi-month compatibility.

4. **Proration is Automatic**  
   Plan changes calculate proration automatically. No manual credit/charge needed.

5. **Grace Period is Optional**  
   You can call `add_grace_period()` after dunning fails to give merchants extra time.

6. **Tenant Isolation**  
   All queries must filter by tenant. OneToOne Subscription→Tenant prevents cross-tenant access.

7. **Payment Methods Are Tokens**  
   `provider_customer_id` and `provider_payment_method_id` come from Stripe/Tap/PayMob. Don't store raw card data!

8. **VAT is 15%**  
   Automatically added to all invoices (configurable in settings: `VAT_RATE = Decimal('0.15')`).

## Emergency Procedures

### Manually trigger billing
```python
from apps.subscriptions.tasks_billing import process_recurring_billing
process_recurring_billing()  # Runs immediately
```

### Retry failed webhooks
```python
from apps.subscriptions.tasks_billing import sync_unprocessed_payment_events
sync_unprocessed_payment_events()  # Processes up to 100
```

### Force retry dunning
```python
from apps.subscriptions.services_billing import DunningService

attempt = DunningAttempt.objects.get(id='...')
success = DunningService.process_dunning_attempt(attempt)
```

### Manual payment record
```python
from apps.subscriptions.services_billing import BillingService

invoice = Invoice.objects.get(number='INV-2026-0001')
BillingService.record_payment(
    invoice=invoice,
    amount=Decimal('99.00'),
    provider_payment_id='manual_payment_123'
)
```

### Suspend overdue subscription
```python
from apps.subscriptions.services_billing import SubscriptionService

sub = Subscription.objects.get(tenant=tenant)
SubscriptionService.suspend_subscription(
    subscription=sub,
    reason='Manual: Unpaid after grace period'
)
```

### Reactivate suspended
```python
SubscriptionService.reactivate_subscription(subscription=sub)
```

## Links

- Full docs: [RECURRING_BILLING_SYSTEM.md](./RECURRING_BILLING_SYSTEM.md)
- Models: `apps/subscriptions/models_billing.py`
- Services: `apps/subscriptions/services_billing.py`
- Tasks: `apps/subscriptions/tasks_billing.py`
- Tests: `apps/subscriptions/tests_billing.py`
- Migration: `apps/subscriptions/migrations/0007_billing_system.py`
