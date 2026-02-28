# SaaS Recurring Billing System - Deployment & Configuration Guide

## Overview

This document provides complete setup and deployment instructions for the automated recurring billing system.

**Last Updated**: February 2024  
**Version**: 1.0  
**Status**: Production Ready

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Database Migration](#database-migration)
3. [Settings Configuration](#settings-configuration)
4. [Celery Beat Scheduling](#celery-beat-scheduling)
5. [Payment Provider Integration](#payment-provider-integration)
6. [Email Configuration](#email-configuration)
7. [Testing](#testing)
8. [Deployment Checklist](#deployment-checklist)
9. [Monitoring & Troubleshooting](#monitoring--troubleshooting)

---

## Prerequisites

### Required Packages

All packages are included in `requirements.txt`:

```bash
# Core
Django>=4.2.0
djangorestframework>=3.14.0

# Celery
celery>=5.2.0
redis>=4.2.0  # Or use rabbitmq

# Database
psycopg2-binary>=2.9.0  # PostgreSQL

# Payment Providers
stripe>=5.0.0  # Optional: if using Stripe
paymob-api>=1.0.0  # Optional: if using PayMob

# Notifications
django-templated-email>=3.0.0

# Configuration
python-decouple>=3.8  # For env vars
```

**Installation**:
```bash
pip install -r requirements.txt
```

### Environment Variables

Create or update `.env` file:

```env
# Django
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/wasla_db

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=billing@yourdomain.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=billing@yourdomain.com
SUPPORT_EMAIL=support@yourdomain.com
SUPPORT_PHONE=+966-50-XXX-XXXX

# Dashboard
DASHBOARD_URL=https://yourdomain.com/dashboard

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Payment Providers
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_test_...

PAYMOB_API_KEY=api_key_...
PAYMOB_MERCHANT_ID=merchant_id_...
PAYMOB_WEBHOOK_SECRET=whsec_...

# Timezone
TIME_ZONE=Asia/Riyadh
```

---

## Database Migration

### Step 1: Create migration

```bash
cd wasla
python manage.py makemigrations subscriptions --name billing_models
```

This generates `/wasla/apps/subscriptions/migrations/0002_automated_recurring_billing.py`

### Step 2: Review migration

```bash
python manage.py sqlmigrate subscriptions 0002
```

This shows the SQL that will be generated. Review for correctness.

### Step 3: Run migration

In **development**:
```bash
python manage.py migrate subscriptions
```

In **staging/production**:
```bash
# With a backup first
pg_dump wasla_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migration with verbose output
python manage.py migrate subscriptions --verbosity=2
```

### Step 4: Verify tables

```bash
python manage.py dbshell
\dt subscriptions_*;  -- List all billing tables
```

**Expected tables**:
- subscriptions_subscription
- subscriptions_subscription_item
- subscriptions_billing_cycle
- subscriptions_invoice
- subscriptions_dunning_attempt
- subscriptions_payment_event
- subscriptions_payment_method

---

## Settings Configuration

### 1. Update `config/settings.py`

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... existing apps
    'subscriptions',
]
```

Ensure `subscriptions` is already in the list (it should be).

### 2. Add Billing-specific Settings

Add to end of `config/settings.py`:

```python
# ============================================================
# BILLING CONFIGURATION
# ============================================================

# Billing Timezone (Saudi Arabia)
BILLING_TIMEZONE = 'Asia/Riyadh'

# VAT Rate (15% Saudi Arabia)
VAT_RATE = 0.15

# Currency (Saudi Riyal)
DEFAULT_CURRENCY = 'SAR'

# Grace Period Settings
GRACE_PERIOD_DAYS = 3  # Days before suspension during grace
GRACE_PERIOD_RETRIES = [3, 5, 7, 14]  # Dunning retry schedule in days

# Dunning Settings
MAX_DUNNING_ATTEMPTS = 4
DUNNING_RETRY_BACKOFF = [3, 5, 7, 14]  # Exponential backoff days

# Billing Date Settings
BILLING_MONTH_START_DAY = 1  # Day of month to start cycles

# Payment Provider Settings
PAYMENT_PROVIDERS = {
    'stripe': {
        'enabled': True,
        'api_key': os.getenv('STRIPE_API_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', ''),
    },
    'paymob': {
        'enabled': True,
        'api_key': os.getenv('PAYMOB_API_KEY', ''),
        'merchant_id': os.getenv('PAYMOB_MERCHANT_ID', ''),
        'webhook_secret': os.getenv('PAYMOB_WEBHOOK_SECRET', ''),
    },
}

# Notification Settings
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://yourdomain.com/dashboard')
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'support@yourdomain.com')
SUPPORT_PHONE = os.getenv('SUPPORT_PHONE', '+966-50-XXX-XXXX')

# Email Templates
EMAIL_TEMPLATES = {
    'invoice_issued': 'subscriptions/emails/invoice_issued.txt',
    'payment_received': 'subscriptions/emails/payment_received.txt',
    'grace_period_expiring': 'subscriptions/emails/grace_period_expiring.txt',
    'store_suspended': 'subscriptions/emails/store_suspended.txt',
}

# Logging for Billing
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
    },
    'loggers': {
        'subscriptions.services_billing': {
            'handlers': ['billing_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'subscriptions.tasks_billing': {
            'handlers': ['billing_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### 3. Create Logs Directory

```bash
mkdir -p logs
chmod 755 logs
```

---

## Celery Beat Scheduling

### Step 1: Configure Celery Beat

Update `config/celery.py`:

```python
from celery.schedules import crontab
from django.conf import settings

# Update task routers
app.conf.task_routes = {
    'subscriptions.tasks_billing.process_recurring_billing': {'queue': 'billing'},
    'subscriptions.tasks_billing.process_dunning_attempts': {'queue': 'billing'},
    'subscriptions.tasks_billing.check_and_expire_grace_periods': {'queue': 'billing'},
    'subscriptions.tasks_billing.sync_unprocessed_payment_events': {'queue': 'webhooks'},
    'subscriptions.tasks_billing.cleanup_old_billing_records': {'queue': 'maintenance'},
}

# Configure Beat schedule
app.conf.beat_schedule = {
    # Daily at 2:00 AM Makkah Time - Process billing
    'process-recurring-billing': {
        'task': 'subscriptions.tasks_billing.process_recurring_billing',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'billing'}
    },
    
    # Daily at 3:00 AM - Process dunning
    'process-dunning-attempts': {
        'task': 'subscriptions.tasks_billing.process_dunning_attempts',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'billing'}
    },
    
    # Daily at 4:00 AM - Check grace periods
    'check-grace-periods': {
        'task': 'subscriptions.tasks_billing.check_and_expire_grace_periods',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'billing'}
    },
    
    # Every hour - Sync payment events
    'sync-payment-events': {
        'task': 'subscriptions.tasks_billing.sync_unprocessed_payment_events',
        'schedule': crontab(minute=0),
        'options': {'queue': 'webhooks'}
    },
    
    # Weekly Sunday at 2:00 AM - Cleanup
    'cleanup-billing': {
        'task': 'subscriptions.tasks_billing.cleanup_old_billing_records',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),
        'options': {'queue': 'maintenance'}
    },
}

# Time zone for beat
app.conf.timezone = 'Asia/Riyadh'
```

### Step 2: Start Celery Beat Worker

```bash
# For development
celery -A config beat -l info

# For production with daemonization
supervisord -c etc/supervisord/celery_beat.conf
```

### Step 3: Start Celery Worker

```bash
# For development (multi-queue)
celery -A config worker -l info -Q billing,webhooks,maintenance

# For production
supervisord -c etc/supervisord/celery_worker.conf
```

### Step 4: Verify Beat Schedule

```bash
celery -A config inspect scheduled
```

Expected output:
```
{
  'worker1@host': {
    'scheduled': [
      {
        'task': 'subscriptions.tasks_billing.process_recurring_billing',
        'next_run_at': '2024-02-21 02:00:00'
      },
      ...
    ]
  }
}
```

---

## Payment Provider Integration

### Stripe Integration

#### 1. Install Stripe

```bash
pip install stripe
```

#### 2. Create Stripe Service

Create `/wasla/apps/subscriptions/payment_providers/stripe_provider.py`:

```python
import stripe
from django.conf import settings

stripe.api_key = settings.PAYMENT_PROVIDERS['stripe']['api_key']

class StripePaymentProvider:
    """Stripe payment provider integration."""
    
    @staticmethod
    def create_customer(subscription):
        """Create Stripe customer."""
        customer = stripe.Customer.create(
            name=subscription.tenant.name,
            email=subscription.tenant.contact_email,
            metadata={'subscription_id': str(subscription.id)}
        )
        return customer.id
    
    @staticmethod
    def charge(amount, currency, customer_id, payment_method_id):
        """Process payment charge."""
        try:
            charge = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                customer=customer_id,
                payment_method=payment_method_id,
                confirm=True,
                off_session=True,
            )
            return {
                'success': charge.status == 'succeeded',
                'transaction_id': charge.id,
                'status': charge.status,
                'error': None
            }
        except stripe.error.CardError as e:
            return {
                'success': False,
                'transaction_id': None,
                'status': 'failed',
                'error': str(e.user_message)
            }
    
    @staticmethod
    def verify_webhook(signature, payload):
        """Verify Stripe webhook signature."""
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.PAYMENT_PROVIDERS['stripe']['webhook_secret']
            )
            return True, event
        except ValueError:
            return False, None
```

#### 3. Register Webhook

In Stripe Dashboard:
- Go to Developers → Webhooks
- Add endpoint: `https://yourdomain.com/api/billing/webhooks/`
- Select events:
  - `payment_intent.succeeded`
  - `payment_intent.payment_failed`
  - `customer.update`

### PayMob Integration

#### 1. Install PayMob SDK

```bash
pip install paymob-api
```

#### 2. Create PayMob Service

Create `/wasla/apps/subscriptions/payment_providers/paymob_provider.py`:

```python
from paymob import PayMob
from django.conf import settings

class PayMobPaymentProvider:
    """PayMob payment provider integration."""
    
    def __init__(self):
        self.client = PayMob(
            api_key=settings.PAYMENT_PROVIDERS['paymob']['api_key']
        )
    
    def create_customer(self, subscription):
        """Create PayMob customer."""
        customer = self.client.create_customer(
            first_name=subscription.tenant.name,
            email=subscription.tenant.contact_email,
            phone=subscription.tenant.phone or '',
        )
        return customer['id']
    
    def charge(self, amount, currency, customer_id, token):
        """Process payment charge."""
        try:
            result = self.client.create_charge(
                amount_cents=int(amount * 100),
                currency=currency,
                customer_id=customer_id,
                source='token',
                source_id=token,
            )
            return {
                'success': result['success'],
                'transaction_id': result['id'],
                'status': 'succeeded' if result['success'] else 'failed',
                'error': result.get('error_message', None)
            }
        except Exception as e:
            return {
                'success': False,
                'transaction_id': None,
                'status': 'failed',
                'error': str(e)
            }
    
    def verify_webhook(self, signature, payload):
        """Verify PayMob webhook signature."""
        expected_sig = self._calculate_signature(payload)
        return signature == expected_sig, payload
    
    def _calculate_signature(self, payload):
        """Calculate PayMob webhook signature."""
        import hmac
        import hashlib
        secret = settings.PAYMENT_PROVIDERS['paymob']['webhook_secret']
        message = json.dumps(payload, sort_keys=True)
        return hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
```

#### 3. Register Webhook

In PayMob Dashboard:
- Settings → Webhooks
- Add: `https://yourdomain.com/api/billing/webhooks/`
- Select events: chargesucceeded, chargefailed

---

## Email Configuration

### Gmail Setup (Recommended for Testing)

1. **Enable 2-Step Verification**: https://myaccount.google.com/security
2. **Create App Password**: https://myaccount.google.com/apppasswords
3. **Update `.env`**:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=billing@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx  # 16-char app password
```

### Production SMTP Setup

```env
EMAIL_HOST=smtp.yourdomain.com
EMAIL_HOST_USER=billing@yourdomain.com
EMAIL_HOST_PASSWORD=your-secure-password
EMAIL_PORT=587
EMAIL_USE_TLS=True
```

### Test Email Configuration

```bash
python manage.py shell
from django.core.mail import send_mail

send_mail(
    'Test Subject',
    'Test Message',
    'billing@yourdomain.com',
    ['test@example.com'],
    fail_silently=False,
)
```

---

## Testing

### Run Unit Tests

```bash
# All billing tests
pytest wasla/apps/subscriptions/tests_billing.py -v

# Specific test class
pytest wasla/apps/subscriptions/tests_billing.py::SubscriptionServiceTests -v

# Specific test
pytest wasla/apps/subscriptions/tests_billing.py::SubscriptionServiceTests::test_create_subscription -v

# With coverage
pytest wasla/apps/subscriptions/tests_billing.py --cov=subscriptions
```

### Test Key Scenarios

#### 1. Create Subscription

```python
from subscriptions.models_billing import Subscription, SubscriptionPlan
from subscriptions.services_billing import SubscriptionService

plan = SubscriptionPlan.objects.first()
subscription = SubscriptionService.create_subscription(
    tenant=tenant,
    plan=plan,
    payment_method_id='pm_test_123',
)
assert subscription.state == 'active'
```

#### 2. Test Dunning Flow

```python
from subscriptions.services_billing import DunningService

# Create overdue invoice
invoice.status = 'overdue'
invoice.save()

# Start dunning
DunningService.start_dunning(invoice)

# Verify dunning attempt created
attempt = invoice.dunning_attempts.first()
assert attempt.status == 'pending'
assert attempt.scheduled_for <= timezone.now()
```

#### 3. Test Idempotency

```python
from subscriptions.services_billing import SubscriptionService

idempotency_key = 'test-idem-key-123'

# Create once
sub1 = SubscriptionService.create_subscription(
    tenant=tenant,
    plan=plan,
    idempotency_key=idempotency_key,
)

# Create again with same key
sub2 = SubscriptionService.create_subscription(
    tenant=tenant,
    plan=plan,
    idempotency_key=idempotency_key,
)

assert sub1.id == sub2.id  # Same subscription returned
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All tests passing: `pytest wasla/apps/subscriptions/tests_billing.py -v`
- [ ] Database migration created: `0002_automated_recurring_billing.py`
- [ ] `.env` file configured for production
- [ ] Email credentials verified with test send
- [ ] Payment provider API keys obtained
- [ ] Webhook endpoints registered in payment providers
- [ ] SSL certificate valid
- [ ] Redis running and accessible
- [ ] PostgreSQL backup created
- [ ] Django settings reviewed (DEBUG=False, ALLOWED_HOSTS, etc.)

### Deployment Steps

**1. Deploy Code**
```bash
git pull origin main
```

**2. Install Dependencies**
```bash
pip install -r requirements.txt
```

**3. Run Migration**
```bash
python manage.py migrate subscriptions
```

**4. Collect Static Files**
```bash
python manage.py collectstatic --noinput
```

**5. Update Admin Site**
```bash
# Reload Django app server (if using systemd/supervisord)
systemctl restart wasla  # or supervisorctl restart wasla
```

**6. Start Celery Workers**
```bash
supervisorctl restart celery-beat
supervisorctl restart celery-worker
```

**7. Verify Services**
```bash
# Check app is running
curl https://yourdomain.com/api/billing/subscriptions/ -H "Authorization: Bearer token"

# Check Celery beat scheduled tasks
celery -A config inspect scheduled

# Check billing logs
tail -f logs/billing.log
```

### Post-Deployment Verification

- [ ] Subscription API endpoints working
- [ ] Invoice list loading
- [ ] Celery tasks executing on schedule
- [ ] Webhooks being received and processed
- [ ] Email notifications being sent
- [ ] No errors in application logs
- [ ] Database backups automated
- [ ] Monitoring alerts configured

---

## Monitoring & Troubleshooting

### Health Checks

```bash
# Check Celery worker status
celery -A config inspect active

# Check scheduled tasks
celery -A config inspect scheduled

# Check Redis connection
redis-cli ping  # Should return PONG

# Check database
python manage.py dbshell
SELECT COUNT(*) FROM subscriptions_subscription;
```

### Common Issues

#### 1. Celery Tasks Not Running

**Problem**: Beat schedule isn't executing tasks

**Solution**:
```bash
# Check beat is running
ps aux | grep celery

# Check timezone matches
python -c "from django.conf import settings; print(settings.TIME_ZONE)"

# Restart beat
supervisorctl restart celery-beat

# Check task logs
tail -f logs/billing.log | grep process_recurring_billing
```

#### 2. Webhook Events Not Processing

**Problem**: Payment webhooks received but not processed

**Solution**:
```bash
# Check payment events in database
python manage.py shell
>>> from subscriptions.models_billing import PaymentEvent
>>> PaymentEvent.objects.filter(status='failed').count()
>>> PaymentEvent.objects.filter(status='failed').first().error_message

# Manually retry
>>> from subscriptions.services_billing import WebhookService
>>> WebhookService.handle_payment_event(failed_event)
```

#### 3. Invoices Not Emailed

**Problem**: Invoices created but notifications not sent

**Solution**:
```bash
# Test email configuration
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Hello', 'from@example.com', ['to@example.com'])

# Check email logs
grep -i "invoice issued" logs/billing.log

# Verify email backend in settings
python -c "from django.conf import settings; print(settings.EMAIL_BACKEND)"
```

#### 4. Database Connection Issues

**Problem**: Migration fails or queries slow

**Solution**:
```bash
# Check connection
psql $DATABASE_URL -c "SELECT 1"

# Check slow queries
psql $DATABASE_URL -c "SELECT query, mean_exec_time FROM pg_stat_statements WHERE mean_exec_time > 1000 ORDER BY mean_exec_time DESC;"

# Check index usage
python manage.py shell
>>> from django.db import connection
>>> connection.queries  # To see recent queries
```

### Performance Optimization

```python
# In views_billing.py, add select_related for billing list
class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        # Optimize with select_related
        return Invoice.objects.select_related(
            'subscription',
            'billing_cycle'
        ).filter(subscription__tenant=self.request.user.tenant)
```

### Logging Configuration for Debugging

Update `config/settings.py` LOGGING:

```python
'loggers': {
    'subscriptions.services_billing': {
        'level': 'DEBUG',  # Enable debug logging
        'handlers': ['billing_file', 'console'],
    },
}
```

### Monitoring Recommendations

- **Application Monitoring**: Sentry or New Relic
- **Task Monitoring**: Flower (Celery monitoring web interface)
- **Database**: AWS CloudWatch or Datadog
- **Alerts**: Set up alerts for:
  - Failed tasks
  - Failed webhooks
  - Overdue invoices
  - High dunning attempt failures

---

## Next Steps

1. **Integration Testing**: Test with real payment provider sandbox
2. **Load Testing**: Use locust to test under load
3. **Disaster Recovery**: Create recovery procedures
4. **Documentation**: Add API documentation with Swagger/OpenAPI
5. **Analytics**: Add billing analytics dashboard
6. **Audit Logging**: Implement audit trail for all billing actions

---

## Support

For issues or questions:
- Documentation: `/docs/BILLING_SYSTEM.md`
- Admin Panel: `/admin/subscriptions/`
- API Documentation: `/api/schema/`
- Support Email: support@yourdomain.com
