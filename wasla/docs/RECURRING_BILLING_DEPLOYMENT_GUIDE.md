# Recurring Billing System - Deployment Guide

## Pre-Deployment Checklist

- [ ] All tests passing locally
- [ ] Migration created and reviewed
- [ ] Payment provider accounts configured (Stripe/Tap/PayMob)
- [ ] Celery and Redis running
- [ ] Email/SMS notification system configured
- [ ] Logging infrastructure set up
- [ ] Staging environment ready
- [ ] Database backup strategy in place

## Step 1: Database Setup

### 1.1 Create and Apply Migration

```bash
# In development first
cd /home/mohamed/Desktop/wasla-version-2/wasla

# Check if migration exists
ls -la apps/subscriptions/migrations/0007_*

# Create migration (if models changed)
python manage.py makemigrations subscriptions

# Apply to development database
python manage.py migrate subscriptions 0007_billing_system

# Verify tables created
python manage.py dbshell
sqlite> .tables | grep subscriptions_
sqlite> .quit
```

### 1.2 Verify Schema

```bash
# Check model->database mapping
python manage.py inspectdb --database=default | grep -A 20 "class Subscription"

# Verify indexes created
python manage.py inspectdb | grep "Index("
```

### 1.3 Test Database Operations

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from apps.tenants.models import Tenant
from apps.subscriptions.models_billing import BillingPlan, Subscription, PaymentMethod
from decimal import Decimal
from datetime import date

# Create test tenant
tenant = Tenant.objects.create(
    name='Test Store',
    domain='test.wasla.local'
)

# Create test plan
plan = BillingPlan.objects.create(
    name='Test Plan',
    price=Decimal('99.00'),
    currency='SAR',
    billing_cycle='monthly',
    features=['test']
)

# Create payment method
pm = PaymentMethod.objects.create(
    method_type='card',
    provider_customer_id='cus_test',
    provider_payment_method_id='pm_test',
    display_name='Test Card'
)

# Create subscription
sub = Subscription.objects.create(
    tenant=tenant,
    plan=plan,
    currency='SAR',
    billing_cycle_anchor=date(2026, 3, 1),
    next_billing_date=date(2026, 3, 1),
    state='active'
)

print(f"✓ Subscription created: {sub}")
print(f"✓ Tenant: {sub.tenant.name}")
print(f"✓ State: {sub.state}")

# Exit
exit()
```

## Step 2: Celery Configuration

### 2.1 Update settings.py

```python
# Django settings.py

# 1. Add Celery configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# 2. Configure timezone
from django.conf import settings
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# 3. Add Celery Beat Schedule
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'process-recurring-billing': {
        'task': 'apps.subscriptions.tasks_billing.process_recurring_billing',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'options': {'queue': 'billing'}
    },
    'process-dunning-attempts': {
        'task': 'apps.subscriptions.tasks_billing.process_dunning_attempts',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
        'options': {'queue': 'billing'}
    },
    'check-grace-periods': {
        'task': 'apps.subscriptions.tasks_billing.check_and_expire_grace_periods',
        'schedule': crontab(hour=4, minute=0),  # 4 AM daily
        'options': {'queue': 'billing'}
    },
    'sync-payment-events': {
        'task': 'apps.subscriptions.tasks_billing.sync_unprocessed_payment_events',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'queue': 'webhooks'}
    },
    'cleanup-billing-records': {
        'task': 'apps.subscriptions.tasks_billing.cleanup_old_billing_records',
        'schedule': crontab(hour=2, minute=0, day_of_week=6),  # Sunday 2 AM
        'options': {'queue': 'cleanup'}
    },
}

# 4. Configure task routing
CELERY_TASK_ROUTES = {
    'apps.subscriptions.tasks_billing.process_recurring_billing': {'queue': 'billing'},
    'apps.subscriptions.tasks_billing.process_dunning_attempts': {'queue': 'billing'},
    'apps.subscriptions.tasks_billing.check_and_expire_grace_periods': {'queue': 'billing'},
    'apps.subscriptions.tasks_billing.sync_unprocessed_payment_events': {'queue': 'webhooks'},
    'apps.subscriptions.tasks_billing.cleanup_old_billing_records': {'queue': 'cleanup'},
}

# 5. Billing-specific settings
BILLING_CYCLE_DAYS = 30
DUNNING_MAX_ATTEMPTS = 5
GRACE_PERIOD_DAYS = 7
INVOICE_DUE_DAYS = 14
VAT_RATE = Decimal('0.15')  # 15% for Saudi Arabia
```

### 2.2 Update celery.py

```python
# config/celery.py

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('wasla')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Load Beat schedule from settings
from django.conf import settings
if hasattr(settings, 'CELERY_BEAT_SCHEDULE'):
    app.conf.beat_schedule = settings.CELERY_BEAT_SCHEDULE
```

### 2.3 Verify Celery Configuration

```bash
# Check Celery can connect to broker
celery -A config inspect ping

# Check registered tasks
celery -A config inspect registered

# Check beat schedule
celery -A config inspect scheduled

# Example output:
# {
#   'celery@hostname': {
#     'scheduled': {
#       'process-recurring-billing': {
#         'enabled': True,
#         'schedule': '<crontab: 2 0 * * *>'
#       }
#     }
#   }
# }
```

## Step 3: Payment Provider Integration

### 3.1 Stripe Integration

```python
# apps/subscriptions/payment_integrations/stripe.py

import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeIntegration:
    @staticmethod
    def charge(payment_method, amount):
        """Charge a registered payment method."""
        try:
            charge = stripe.Charge.create(
                amount=int(amount * 100),  # Convert to cents
                currency='sar',
                customer=payment_method.provider_customer_id,
                payment_method=payment_method.provider_payment_method_id,
                off_session=True,
                confirm=True
            )
            return {
                'success': True,
                'provider_id': charge.id,
                'amount': Decimal(str(charge.amount / 100))
            }
        except stripe.error.CardError as e:
            return {
                'success': False,
                'error_code': e.code,
                'error_message': e.message
            }

    @staticmethod
    def refund(provider_payment_id, amount):
        """Refund a payment."""
        try:
            refund = stripe.Refund.create(
                payment_intent=provider_payment_id,
                amount=int(amount * 100)
            )
            return {
                'success': True,
                'refund_id': refund.id
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error_message': str(e)
            }
```

Update `tasks_billing.py` to use:

```python
def _attempt_charge(invoice, payment_method):
    """Attempt to charge a payment method."""
    from apps.subscriptions.payment_integrations.stripe import StripeIntegration
    
    result = StripeIntegration.charge(
        payment_method=payment_method,
        amount=invoice.total
    )
    
    if result['success']:
        BillingService.record_payment(
            invoice=invoice,
            amount=invoice.total,
            provider_payment_id=result['provider_id']
        )
        return True
    else:
        logger.warning(
            f"Payment charge failed for invoice {invoice.number}: "
            f"{result['error_code']}"
        )
        return False
```

### 3.2 Tap Integration (Similar Pattern)

```python
# apps/subscriptions/payment_integrations/tap.py

import requests
from django.conf import settings

class TapIntegration:
    BASE_URL = 'https://api.tap.company/v2'
    
    def __init__(self):
        self.api_key = settings.TAP_API_KEY
        self.headers = {'Authorization': f'Bearer {self.api_key}'}
    
    def charge(self, payment_method, amount):
        """Charge via Tap."""
        payload = {
            'amount': float(amount),
            'currency': 'sar',
            'customer': {
                'id': payment_method.provider_customer_id
            },
            'source': {
                'id': payment_method.provider_payment_method_id
            }
        }
        
        response = requests.post(
            f'{self.BASE_URL}/charges',
            json=payload,
            headers=self.headers
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'provider_id': data['id'],
                'amount': Decimal(str(data['amount']))
            }
        else:
            return {
                'success': False,
                'error_code': response.status_code,
                'error_message': response.text
            }
```

### 3.3 Configure Webhook Endpoints

```python
# urls.py

from django.urls import path
from . import webhook_views

urlpatterns = [
    # Stripe webhook
    path('webhooks/stripe/', 
         webhook_views.stripe_webhook, 
         name='stripe_webhook'),
    
    # Tap webhook
    path('webhooks/tap/', 
         webhook_views.tap_webhook, 
         name='tap_webhook'),
    
    # PayMob webhook
    path('webhooks/paymob/', 
         webhook_views.paymob_webhook, 
         name='paymob_webhook'),
]
```

```python
# webhook_views.py

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.subscriptions.services_billing import WebhookService

@csrf_exempt
def stripe_webhook(request):
    event = json.loads(request.body)
    
    mapping = {
        'charge.succeeded': 'payment.succeeded',
        'charge.failed': 'payment.failed',
        'invoice.payment_succeeded': 'invoice.paid',
        'invoice.payment_failed': 'invoice.payment_failed',
    }
    
    event_type = mapping.get(event['type'])
    if not event_type:
        return JsonResponse({'status': 'ignored'})
    
    WebhookService.handle_payment_event(
        event_type=event_type,
        provider_event_id=event['id'],
        payload=event['data']['object']
    )
    
    return JsonResponse({'status': 'received'})

@csrf_exempt
def tap_webhook(request):
    payload = json.loads(request.body)
    
    mapping = {
        'charge.succeeded': 'payment.succeeded',
        'charge.failed': 'payment.failed',
    }
    
    event_type = mapping.get(payload.get('type'))
    if not event_type:
        return JsonResponse({'status': 'ignored'})
    
    WebhookService.handle_payment_event(
        event_type=event_type,
        provider_event_id=payload['id'],
        payload=payload
    )
    
    return JsonResponse({'success': True})
```

Register webhook URLs on provider dashboards:
- Stripe: `https://yourdomain.com/webhooks/stripe/`
- Tap: `https://yourdomain.com/webhooks/tap/`
- PayMob: `https://yourdomain.com/webhooks/paymob/`

## Step 4: Logging & Monitoring

### 4.1 Configure Logging

```python
# settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'billing_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/billing.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'billing_error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/billing_error.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'apps.subscriptions.services_billing': {
            'handlers': ['billing_file', 'billing_error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.subscriptions.tasks_billing': {
            'handlers': ['billing_file', 'billing_error_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory
import os
os.makedirs('logs', exist_ok=True)
```

### 4.2 Set Up Alerts

```python
# management/commands/billing_health_check.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.subscriptions.models_billing import (
    Subscription, Invoice, PaymentEvent, DunningAttempt
)

class Command(BaseCommand):
    help = 'Check billing system health and alert on issues'
    
    def handle(self, *args, **options):
        now = timezone.now()
        
        # Check 1: Invoices overdue > 30 days
        old_overdue = Invoice.objects.filter(
            status__in=['issued', 'overdue'],
            due_date__lt=now.date() - timedelta(days=30)
        ).count()
        
        if old_overdue > 0:
            self.send_alert(f'⚠️  {old_overdue} invoices overdue 30+ days')
        
        # Check 2: Failed webhooks accumulating
        failed_events = PaymentEvent.objects.filter(
            status='failed',
            created_at__gte=now - timedelta(hours=24)
        ).count()
        
        if failed_events > 10:
            self.send_alert(f'⚠️  {failed_events} failed webhook events in 24h')
        
        # Check 3: Suspended subscriptions
        suspended = Subscription.objects.filter(state='suspended').count()
        
        if suspended > 0:
            self.send_alert(f'⚠️  {suspended} subscriptions suspended')
        
        # Check 4: Dunning attempts failing
        failed_dunning = DunningAttempt.objects.filter(
            status='failed',
            created_at__gte=now - timedelta(hours=24)
        ).count()
        
        if failed_dunning > 5:
            self.send_alert(f'⚠️  {failed_dunning} failed dunning attempts in 24h')
        
        self.stdout.write(self.style.SUCCESS('✓ Health check complete'))
    
    def send_alert(self, message):
        """Send alert via email/Slack."""
        # TODO: Integrate with notification system
        self.stdout.write(self.style.WARNING(message))
```

Schedule daily:
```python
# In CELERY_BEAT_SCHEDULE
'billing-health-check': {
    'task': 'django.core.management.call_command',
    'args': ('billing_health_check',),
    'schedule': crontab(hour=5, minute=0),  # 5 AM daily
},
```

## Step 5: Testing on Staging

### 5.1 Run Full Test Suite

```bash
# Run all billing tests
pytest apps/subscriptions/tests_billing.py -v

# Check test coverage
pytest apps/subscriptions/tests_billing.py --cov=apps.subscriptions --cov-report=html

# Test with multiple databases (if applicable)
pytest apps/subscriptions/tests_billing.py --db=staging
```

### 5.2 Staging Smoke Tests

```python
# management/commands/test_billing_flow.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.tenants.models import Tenant
from apps.subscriptions.models_billing import BillingPlan, PaymentMethod
from apps.subscriptions.services_billing import (
    SubscriptionService, BillingService, DunningService
)
from decimal import Decimal
from datetime import date

class Command(BaseCommand):
    help = 'Test complete billing flow on staging'
    
    def handle(self, *args, **options):
        # 1. Create test tenant
        t, _ = Tenant.objects.get_or_create(
            name='Staging Test Store',
            defaults={'domain': 'staging-test.local'}
        )
        
        # 2. Create test plan
        plan, _ = BillingPlan.objects.get_or_create(
            name='Staging Test',
            defaults={
                'price': Decimal('50.00'),
                'currency': 'SAR',
                'billing_cycle': 'monthly'
            }
        )
        
        # 3. Create payment method
        pm, _ = PaymentMethod.objects.get_or_create(
            provider_customer_id='test_cus_staging',
            defaults={
                'method_type': 'card',
                'provider_payment_method_id': 'test_pm_staging',
                'display_name': 'Test Card'
            }
        )
        
        # 4. Create subscription
        sub = SubscriptionService.create_subscription(
            tenant=t,
            plan=plan,
            payment_method=pm
        )
        self.stdout.write(f'✓ Created subscription: {sub.id}')
        
        # 5. Create billing cycle
        cycle = BillingService.create_billing_cycle(
            subscription=sub,
            period_start=date.today(),
            period_end=date.today().replace(day=28)
        )
        self.stdout.write(f'✓ Created billing cycle: {cycle.id}')
        
        # 6. Create invoice
        invoice = BillingService.create_invoice(cycle)
        self.stdout.write(f'✓ Created invoice: {invoice.number}')
        
        # 7. Record payment
        BillingService.record_payment(
            invoice=invoice,
            amount=invoice.total,
            provider_payment_id='test_pay_staging'
        )
        self.stdout.write(f'✓ Recorded payment')
        
        # 8. Verify invoice paid
        invoice.refresh_from_db()
        assert invoice.status == 'paid'
        self.stdout.write(f'✓ Invoice marked paid')
        
        self.stdout.write(
            self.style.SUCCESS('✓ All tests passed!')
        )
```

Run it:
```bash
python manage.py test_billing_flow
```

## Step 6: Production Deployment

### 6.1 Pre-Production Checklist

```bash
# Final checks before production
[ ] All tests passing
[ ] Staging smoke tests complete
[ ] Payment provider accounts live
[ ] Webhook endpoints registered
[ ] Celery Beat configured
[ ] Database backed up
[ ] Logging configured
[ ] Monitoring alerts set up
[ ] Runbook reviewed
[ ] Team trained
```

### 6.2 Deploy Steps

```bash
# 1. Stop Celery Beat (pause scheduled jobs)
celery -A config control shutdown

# 2. Create database backup
pg_dump wasla_prod > backups/wasla_$(date +%Y%m%d_%H%M%S).sql

# 3. Apply migration
python manage.py migrate subscriptions 0007_billing_system

# 4. Verify migration
python manage.py inspectdb | grep subscriptions_subscription

# 5. Start Celery Beat
celery -A config beat --loglevel=info

# 6. Monitor first run
tail -f logs/billing.log
```

### 6.3 Post-Deployment

```bash
# 1. Verify jobs ran
# Check logs/billing.log for "process_recurring_billing completed"

# 2. Monitor first 24 hours
# Dashboard: Monitor Subscription states
# Dashboard: Check Invoice creation
# Dashboard: Verify PaymentEvent processing

# 3. Test manual operations
python manage.py shell
from apps.subscriptions.models_billing import Subscription
subs = Subscription.objects.all()
print(f"Total subscriptions: {subs.count()}")
print(f"Active: {subs.filter(state='active').count()}")
```

## Troubleshooting

### Issue: Tasks Not Running

```bash
# Check Celery Beat is running
ps aux | grep celery

# Verify schedule in Redis
celery -A config inspect scheduled

# Check logs
tail -f logs/billing.log | grep ERROR

# Manually trigger task
celery -A config inspect query_task process_recurring_billing
```

### Issue: Invoices Not Creating

```python
# Check subscription next_billing_date
from apps.subscriptions.models_billing import Subscription
from datetime import date

today = date.today()
due = Subscription.objects.filter(next_billing_date=today)
print(f"Subscriptions due today: {due.count()}")

for sub in due:
    print(f"  - {sub.tenant.name}: {sub.state}")
```

### Issue: Webhooks Not Processing

```python
# Check failed events
from apps.subscriptions.models_billing import PaymentEvent

failed = PaymentEvent.objects.filter(status='failed').order_by('-created_at')[:5]
for evt in failed:
    print(f"Event {evt.provider_event_id}: {evt.error_message}")
```

### Issue: Dunning Not Retrying

```python
# Check pending attempts
from apps.subscriptions.models_billing import DunningAttempt
from django.utils import timezone

pending = DunningAttempt.objects.filter(
    status='pending',
    scheduled_for__lte=timezone.now()
)
print(f"Due dunning attempts: {pending.count()}")

for att in pending:
    print(f"  - Invoice {att.invoice.number}, Attempt #{att.attempt_number}")
```

## Rollback Procedure

```bash
# If critical issue occurs:

# 1. Stop Celery Beat
pkill -f "celery.*beat"

# 2. Rollback migration (if needed)
python manage.py migrate subscriptions 0006_add_payment_methods_to_plan_features

# 3. Restore from backup
pg_restore -d wasla_prod backups/wasla_YYYYMMDD_HHMMSS.sql

# 4. Verify
python manage.py check

# 5. Restart Celery
celery -A config beat --loglevel=info
```

## Next Steps

After deployment:

1. Monitor billing operations daily
2. Review failed webhooks weekly
3. Check dunning recovery rate monthly
4. Analyze revenue collection trends
5. Optimize retry schedules based on data

See [RECURRING_BILLING_SYSTEM.md](./RECURRING_BILLING_SYSTEM.md) for full system documentation.
