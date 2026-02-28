# Wasla Automated Recurring Billing System

## Overview

This document provides a comprehensive guide to Wasla's production-grade SaaS recurring billing system. The system automates subscription management, billing cycles, dunning flows, and payment synchronization for multi-tenant merchant stores.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                  Subscription Management                     │
│  (subscription_service.py)                                  │
│  - Create/upgrade/downgrade/cancel subscriptions            │
│  - Plan change with proration                               │
│  - State machine (active → past_due → grace → suspended)    │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┬──────────────┬──────────────┐
        │                 │              │              │
        ▼                 ▼              ▼              ▼
┌─────────────┐  ┌──────────────┐  ┌────────────┐  ┌────────┐
│  Billing    │  │  Dunning     │  │  Webhook   │  │ Celery │
│  Service    │  │  Service     │  │  Service   │  │ Tasks  │
│             │  │              │  │            │  │        │
│ -Cycles     │  │ -Retry logic │  │ -Provider  │  │ -Daily │
│ -Invoices   │  │ -Grace       │  │  sync      │  │  jobs  │
│ -Proration  │  │ -Suspend     │  │ -Events    │  │        │
└─────────────┘  └──────────────┘  └────────────┘  └────────┘
        │                 │              │              │
        └────────────────┬┴──────────────┴──────────────┘
                         │
                    ┌────▼────────────────┐
                    │ Payment Orchestrator │
                    │ (Tap/Stripe/PayMob)  │
                    └─────────────────────┘
```

## Subscription States

```
┌──────────┐
│  ACTIVE  │◄─────────────────────────────────────────┐
└────┬─────┘                                           │
     │                                                 │
     │ Payment failed                                  │
     ▼                                                 │
┌──────────────┐                                       │
│  PAST_DUE    │                                       │
└────┬─────────┘                                       │
     │                                                 │
     │ Add grace period                                │
     ▼                                                 │
┌──────────┐         ┌──────────────┐                 │
│  GRACE   │────────►│   SUSPENDED  │                 │
└─────┬────┘ Expired └─────┬────────┘                 │
      │            (no payment)     │                 │
      │                             │ Payment received│
      │                             ▼                 │
      └──────────────────────────  ACTIVE ◄──────────┘
                  (payment)
      
Additional path:
┌──────────┐
│ ACTIVE/  │
│ PAST_DUE │
└────┬─────┘
     │
     │ Customer request
     ▼
┌──────────────┐
│  CANCELLED   │
└──────────────┘ (terminal state)
```

## Billing Cycle Flow

```
1. DAILY JOB (2 AM) - process_recurring_billing
   ├─ Find subscriptions with next_billing_date = today
   ├─ Create BillingCycle (period_start, period_end)
   ├─ Calculate amounts (subtotal, tax=15%, total)
   ├─ Create Invoice with unique number (INV-YYYY-0001)
   └─ Attempt charge via PaymentOrchestrator

2. CHARGE ATTEMPT
   ├─ If successful: Mark invoice PAID, status → ACTIVE
   └─ If failed: Start dunning flow, status → PAST_DUE

3. DUNNING JOB (3 AM) - process_dunning_attempts
   ├─ Find pending dunning attempts (scheduled_for <= now)
   ├─ Retry charge using PaymentMethod
   ├─ Success: Record payment, reactivate subscription
   └─ Failure: Schedule next attempt (exponential backoff)

4. GRACE PERIOD JOB (4 AM) - check_and_expire_grace_periods
   ├─ Find subscriptions with grace_until <= now
   ├─ Check if invoice still unpaid
   └─ Suspend subscription if unpaid

5. WEBHOOK SYNC (Hourly) - sync_unprocessed_payment_events
   ├─ Retry failed webhook events
   └─ Max 100 per run
```

## Proration Logic

Proration handles mid-cycle plan changes with fair credit/charge:

```
Formula:
  daily_rate_new = new_plan.price / 30
  daily_rate_old = old_plan.price / 30
  days_remaining = (next_billing_date - today).days
  
  proration = (daily_rate_new - daily_rate_old) * days_remaining

Examples:
  • Upgrade $49 → $99 (15 days): +$25.00
  • Downgrade $99 → $49 (20 days): -$33.33 (credit)
```

## Dunning Retry Schedule

The system uses **exponential backoff** for payment retries:

```
Attempt │ Days to Wait │ Strategy        │ Total Days
────────┼──────────────┼─────────────────┼──────────
   1    │      0       │ Immediate       │    0
   2    │      3       │ 3-day wait      │    3
   3    │      5       │ 5-day wait      │    8
   4    │      7       │ 7-day wait      │   15
   5    │     14       │ 14-day wait     │   29

After 5 failed attempts (~29 days):
  - Subscription moves to SUSPENDED
  - Store becomes inactive (is_active = False)
  - Merchant receives suspension notice
  - Automatic reactivation upon successful payment
```

## Models

### Subscription
```python
# State machine
state: CharField(
    choices=[
        'active',       # Billing normally
        'past_due',     # Payment failed, in dunning
        'grace',        # Extended deadline (usually 7 days)
        'suspended',    # Store inactive due to non-payment
        'cancelled'     # Terminated (terminal)
    ]
)

# Key fields
tenant: OneToOneField(Tenant)          # Unique per merchant
plan: ForeignKey(BillingPlan)          # Current plan
next_billing_date: DateField()         # When to bill next
grace_until: DateTimeField()           # Grace deadline
suspended_at: DateTimeField()          # When suspended (if applicable)

# Tracking
started_at: DateTimeField()            # When subscription began
cancelled_at: DateTimeField()          # When cancelled
created_at: DateTimeField()
updated_at: DateTimeField()
```

### BillingCycle
```python
# A single billing period (e.g., 1 month)
subscription: ForeignKey(Subscription)
period_start: DateField()              # Start of billing period
period_end: DateField()                # End of billing period

# Amounts
subtotal: DecimalField()               # Plan price
tax: DecimalField()                    # 15% VAT (Saudi Arabia)
discount: DecimalField()               # Any discounts
total: DecimalField()                  # Final amount to charge

# Proration
proration_total: DecimalField()        # Credit/charge for plan changes
proration_reason: CharField()          # Why (e.g., "Plan change: Basic → Pro")

# Lifecycle
status: CharField(
    choices=['pending', 'billed', 'partial', 'paid', 'failed', 'cancelled']
)
```

### Invoice
```python
# Payment document for a billing cycle
number: CharField(unique=True)         # INV-2026-0001 per tenant
status: CharField(
    choices=['draft', 'issued', 'overdue', 'partial', 'paid', 'void']
)

# Amounts
subtotal, tax, discount, total: DecimalField()
amount_paid: DecimalField()            # Total received so far
amount_due: DecimalField()             # Remaining balance

# Dates
issued_date: DateField()
due_date: DateField()                  # Payment deadline
paid_date: DateField()                 # When fully paid

# Idempotency
idempotency_key: CharField(unique=True)  # Ensures single creation
```

### DunningAttempt
```python
# Tracks payment retry attempts
invoice: ForeignKey(Invoice)
subscription: ForeignKey(Subscription)

# Details
attempt_number: PositiveIntegerField()  # 1-5 (max)
strategy: CharField(
    choices=['immediate', 'incremental', 'exponential']
)
status: CharField(
    choices=['pending', 'in_progress', 'success', 'failed']
)

# Scheduling
scheduled_for: DateTimeField()         # When to execute retry
attempted_at: DateTimeField()          # When actually attempted
next_retry_at: DateTimeField()         # When next retry scheduled

# Error tracking
error_code: CharField()
error_message: TextField()
```

### PaymentEvent
```python
# Webhook from payment provider (idempotent)
provider_event_id: CharField(unique=True)  # External ID (idempotency key)
event_type: CharField(
    choices=[
        'payment.succeeded',
        'payment.failed',
        'invoice.paid',
        'invoice.payment_failed',
        'customer.subscription.updated'
    ]
)

# Processing
status: CharField(
    choices=['received', 'processing', 'processed', 'failed']
)
payload: JSONField()                   # Full webhook payload
processed_at: DateTimeField()
error_message: TextField()

# Relations
subscription: ForeignKey(Subscription, null=True)
invoice: ForeignKey(Invoice, null=True)
```

### PaymentMethod
```python
# Credit card, bank account, wallet, etc.
subscription: OneToOneField(Subscription)
method_type: CharField(
    choices=['card', 'bank', 'wallet', 'other']
)

# Provider tokens
provider_customer_id: CharField()           # Stripe customer_id
provider_payment_method_id: CharField()     # Stripe pm_xxxx

# Status
status: CharField(
    choices=['active', 'inactive', 'expired', 'invalid']
)
is_valid(): Checks status and expiration
```

## Services

### SubscriptionService

```python
# Create subscription
sub = SubscriptionService.create_subscription(
    tenant=tenant,
    plan=plan,
    payment_method=payment_method,
    billing_cycle_anchor=1,        # Day of month (1-28)
    currency='SAR',
    idempotency_key='sub_key_123'  # Optional, for idempotency
)

# Change plan (with proration)
sub = SubscriptionService.change_plan(
    subscription=sub,
    new_plan=new_plan,
    idempotency_key='change_key_456'
)

# Cancel subscription
sub = SubscriptionService.cancel_subscription(
    subscription=sub,
    reason='Customer request',
    immediately=False              # End of period vs. immediate
)

# Suspend subscription (non-payment)
sub = SubscriptionService.suspend_subscription(
    subscription=sub,
    reason='Non-payment'
)

# Reactivate subscription
sub = SubscriptionService.reactivate_subscription(subscription=sub)
```

### BillingService

```python
# Create billing cycle
cycle = BillingService.create_billing_cycle(
    subscription=sub,
    period_start=date.today(),
    period_end=date.today() + timedelta(days=29),
    idempotency_key='cycle_key_789'
)

# Create invoice
invoice = BillingService.create_invoice(cycle)

# Record payment (full or partial)
invoice = BillingService.record_payment(
    invoice=invoice,
    amount=amount,
    provider_payment_id='stripe_charge_id'
)

# Calculate proration
proration = BillingService.calculate_proration(
    subscription=sub,
    old_plan=old_plan,
    new_plan=new_plan
)
# Returns Decimal (positive = charge, negative = credit)
```

### DunningService

```python
# Start dunning flow for failed invoice
attempt = DunningService.start_dunning(invoice=invoice)

# Process a dunning attempt (retry charge)
success = DunningService.process_dunning_attempt(attempt)

# Add grace period
sub = DunningService.add_grace_period(
    subscription=sub,
    days=7
)

# Retry schedule (exponential backoff)
RETRY_SCHEDULE = {
    1: 3,   # 3 days
    2: 5,   # 5 days
    3: 7,   # 7 days
    4: 14   # 14 days
}
```

### WebhookService

```python
# Handle webhook from payment provider
event = WebhookService.handle_payment_event(
    event_type='payment.succeeded',
    provider_event_id='evt_stripe_123',  # Idempotency!
    payload={
        'customer_id': 'cus_123',
        'amount': '99.00',
        'payment_id': 'pay_123',
        # ... full webhook payload
    }
)

# Routes to appropriate handler:
# - _handle_payment_succeeded()
# - _handle_payment_failed()
# - _handle_invoice_paid()
# - _handle_invoice_payment_failed()
```

## Celery Tasks

### `process_recurring_billing`
**Schedule**: Daily at 2 AM  
**Function**: Charge all subscriptions due for billing

```python
# Pseudo-code
today = date.today()
for sub in Subscription.objects.filter(
    state='active',
    next_billing_date=today
):
    create_billing_cycle()
    create_invoice()
    attempt_charge()
    if failed:
        start_dunning()
```

### `process_dunning_attempts`
**Schedule**: Daily at 3 AM  
**Function**: Retry failed payments

```python
# Pseudo-code
now = timezone.now()
for attempt in DunningAttempt.objects.filter(
    status='pending',
    scheduled_for__lte=now
):
    if retry_charge():
        mark_success()
    else:
        schedule_next_retry_or_suspend()
```

### `check_and_expire_grace_periods`
**Schedule**: Daily at 4 AM  
**Function**: Suspend subscriptions if grace period expires

```python
# Pseudo-code
for sub in Subscription.objects.filter(
    state='grace',
    grace_until__lte=timezone.now()
):
    if latest_invoice.status != 'paid':
        suspend_subscription()
        notify_merchant()
```

### `sync_unprocessed_payment_events`
**Schedule**: Hourly  
**Function**: Retry failed webhook events

```python
# Pseudo-code
for event in PaymentEvent.objects.filter(
    status='failed'
)[:100]:
    try:
        reprocess_event()
    except:
        continue
```

### `cleanup_old_billing_records`
**Schedule**: Weekly (Sunday 2 AM)  
**Function**: Archive old records

```python
# Delete failed events older than 90 days
cutoff = now - timedelta(days=90)
PaymentEvent.objects.filter(
    status='failed',
    created_at__lt=cutoff
).delete()
```

## Configuration

### Django Settings

```python
# settings.py

# Celery Beat Schedule
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'process-recurring-billing': {
        'task': 'apps.subscriptions.tasks_billing.process_recurring_billing',
        'schedule': crontab(hour=2, minute=0),  # 2 AM
    },
    'process-dunning-attempts': {
        'task': 'apps.subscriptions.tasks_billing.process_dunning_attempts',
        'schedule': crontab(hour=3, minute=0),  # 3 AM
    },
    'check-grace-periods': {
        'task': 'apps.subscriptions.tasks_billing.check_and_expire_grace_periods',
        'schedule': crontab(hour=4, minute=0),  # 4 AM
    },
    'sync-payment-events': {
        'task': 'apps.subscriptions.tasks_billing.sync_unprocessed_payment_events',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cleanup-billing-records': {
        'task': 'apps.subscriptions.tasks_billing.cleanup_old_billing_records',
        'schedule': crontab(hour=2, minute=0, day_of_week=6),  # Sunday 2 AM
    },
}

# Billing defaults
BILLING_CYCLE_DAYS = 30
DUNNING_MAX_ATTEMPTS = 5
GRACE_PERIOD_DAYS = 7
INVOICE_DUE_DAYS = 14  # Payment terms
VAT_RATE = Decimal('0.15')  # Saudi Arabia 15% VAT
```

## Idempotency & Safe Retry

### Design Principles

1. **Idempotency Keys**: All write operations support idempotency keys
   ```python
   # Same key = same result, even if called 1000 times
   sub = create_subscription(..., idempotency_key='sub_123')
   sub = create_subscription(..., idempotency_key='sub_123')  # Returns same sub
   ```

2. **Provider Event IDs**: Webhook events use `provider_event_id` as unique key
   ```python
   # Even if webhook delivered twice, only processes once
   event = handle_payment_event(
       provider_event_id='evt_stripe_123',  # Unique from provider
       ...
   )
   ```

3. **Database Constraints**: Unique constraints prevent duplicates
   ```python
   # Invoice.number is unique
   # Invoice.idempotency_key is unique
   # PaymentEvent.provider_event_id is unique
   ```

4. **Atomic Transactions**: All critical operations are @transaction.atomic()
   ```python
   # Either entire operation succeeds or rolls back
   with transaction.atomic():
       create_invoice()
       record_payment()
       update_subscription()
   ```

### Safe Retry Pattern

```python
# In BillingService.create_invoice():

# 1. Check if already exists (idempotency)
existing = Invoice.objects.filter(
    idempotency_key=idempotency_key
).first()
if existing:
    return existing

# 2. Atomic transaction
with transaction.atomic():
    # Create invoice
    invoice = Invoice.objects.create(...)
    
    # Update cycle status
    cycle.status = 'billed'
    cycle.save()

# Result: Can retry infinitely, same invoice returned
return invoice
```

## Tenant Isolation

All billing operations are tenant-scoped:

```python
# Queries always filter by tenant
subscriptions = Subscription.objects.filter(tenant=tenant_id)
invoices = Invoice.objects.filter(subscription__tenant=tenant_id)
payments = PaymentEvent.objects.filter(subscription__tenant=tenant_id)

# Database indexes for performance
indexes = [
    Index(fields=['tenant', 'state']),
    Index(fields=['subscription__tenant', 'status']),
]

# OneToOne relationship prevents cross-tenant access
subscription = Subscription.objects.get(tenant=tenant)  # Max 1 per tenant
```

## Webhook Integration

### Example: Stripe Webhook

```python
# In your Django view handling Stripe webhooks:

from apps.subscriptions.services_billing import WebhookService

@csrf_exempt
def stripe_webhook(request):
    event = json.loads(request.body)
    
    # Map Stripe event to our event type
    mapping = {
        'charge.succeeded': 'payment.succeeded',
        'charge.failed': 'payment.failed',
        'invoice.payment_succeeded': 'invoice.paid',
        'invoice.payment_failed': 'invoice.payment_failed',
    }
    
    event_type = mapping.get(event['type'])
    
    # Process webhook (idempotent!)
    payment_event = WebhookService.handle_payment_event(
        event_type=event_type,
        provider_event_id=event['id'],     # Stripe event ID
        payload=event['data']['object']
    )
    
    return JsonResponse({'status': 'received'})
```

### Example: Tap Webhook

```python
# Similar pattern for Tap:

@csrf_exempt
def tap_webhook(request):
    payload = json.loads(request.body)
    
    # Tap uses 'type' and 'id' fields
    mapping = {
        'charge.succeeded': 'payment.succeeded',
        'charge.failed': 'payment.failed',
    }
    
    event_type = mapping.get(payload['type'])
    
    payment_event = WebhookService.handle_payment_event(
        event_type=event_type,
        provider_event_id=payload['id'],
        payload=payload
    )
    
    return JsonResponse({'success': True})
```

## Deployment Checklist

- [ ] Create migration: `python manage.py makemigrations subscriptions`
- [ ] Apply migration: `python manage.py migrate subscriptions 0007_billing_system`
- [ ] Verify models: `python manage.py inspectdb | grep -i subscription`
- [ ] Test locally: `pytest apps/subscriptions/tests_billing.py -v`
- [ ] Configure Celery Beat schedule (see Configuration section)
- [ ] Set up payment provider webhooks (Stripe/Tap/PayMob)
- [ ] Configure Grace period and retry days (in settings.py)
- [ ] Deploy to staging
- [ ] Monitor logs during first billing cycle
- [ ] Verify invoice generation
- [ ] Test dunning flow with intentional payment failure
- [ ] Deploy to production
- [ ] Monitor billing operations in production
- [ ] Set up alerts for failed payment events

## Monitoring & Debugging

### Key Metrics

```python
# Monitor these daily:
Subscription.objects.filter(state='past_due').count()     # At-risk
Subscription.objects.filter(state='suspended').count()    # Lost revenue
Invoice.objects.filter(status='paid').count()             # Successful
DunningAttempt.objects.filter(status='success').count()   # Recovery rate
PaymentEvent.objects.filter(status='failed').count()      # Webhook issues
```

### Common Issues

**Issue**: Invoices not being created  
**Debug**: Check Celery task log, verify `next_billing_date` is today

**Issue**: Payments not recorded  
**Debug**: Check PaymentMethod.is_valid(), verify provider integration

**Issue**: Webhooks not syncing  
**Debug**: Check PaymentEvent.status = 'failed', verify provider_event_id

**Issue**: Subscriptions not suspending  
**Debug**: Check grace_until deadline, verify DunningAttempt count

## Example Usage

```python
from django.contrib.auth.models import User
from apps.tenants.models import Tenant
from apps.subscriptions.models_billing import BillingPlan, PaymentMethod
from apps.subscriptions.services_billing import SubscriptionService, BillingService

# 1. Create tenant
tenant = Tenant.objects.create(
    name='My Store',
    domain='mystore.com'
)

# 2. Create/get plan
plan, _ = BillingPlan.objects.get_or_create(
    name='Professional',
    defaults={
        'price': Decimal('99.00'),
        'currency': 'SAR',
        'billing_cycle': 'monthly',
        'features': ['tap', 'stripe', 'ai']
    }
)

# 3. Create payment method
payment_method = PaymentMethod.objects.create(
    method_type='card',
    provider_customer_id='cus_12345',       # From Stripe
    provider_payment_method_id='pm_67890',  # From Stripe
    display_name='Visa •••• 4242'
)

# 4. Create subscription
subscription = SubscriptionService.create_subscription(
    tenant=tenant,
    plan=plan,
    payment_method=payment_method,
    billing_cycle_anchor=1,  # Charge on day 1 of month
    idempotency_key='onboarding_tenant_123'
)

# 5. Upgrade plan (automatic proration)
pro_plan = BillingPlan.objects.get(name='Enterprise')
SubscriptionService.change_plan(
    subscription=subscription,
    new_plan=pro_plan
)

# 6. Cancel subscription
SubscriptionService.cancel_subscription(
    subscription=subscription,
    reason='Customer request'
)
```

## Testing

Run the comprehensive test suite:

```bash
# All billing tests
pytest apps/subscriptions/tests_billing.py -v

# Specific test class
pytest apps/subscriptions/tests_billing.py::SubscriptionServiceTests -v

# With coverage
pytest apps/subscriptions/tests_billing.py --cov=apps.subscriptions

# Specific test
pytest apps/subscriptions/tests_billing.py::SubscriptionServiceTests::test_create_subscription -v
```

## References

- [Django ORM Transactions](https://docs.djangoproject.com/en/stable/topics/db/transactions/)
- [Celery Beat Schedules](https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Tap Payment Provider](https://tap.company/en/)
