# Payment System Hardening - Migration Guide

## Overview
This guide helps you migrate existing Wasla deployments to use the new production-hardened payment system.

## Pre-Migration Checklist

### 1. Backup Database
```bash
# PostgreSQL
pg_dump wasla_db > backup_before_payment_hardening_$(date +%Y%m%d).sql

# SQLite (dev)
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d)
```

### 2. Test in Staging First
```bash
# Apply to staging environment first
python manage.py migrate payments --plan
python manage.py migrate payments
```

### 3. Check Existing Data
```sql
-- Count active payment intents
SELECT COUNT(*) FROM payments_paymentintent WHERE status != 'succeeded';

-- Count pending webhooks
SELECT COUNT(*) FROM webhooks_webhookevent WHERE processing_status = 'pending';
```

## Migration Steps

### Step 1: Apply Database Migration
```bash
cd /path/to/wasla
source venv/bin/activate

# Check migration plan
python manage.py migrate payments --plan

# Apply migration
python manage.py migrate payments

# Verify
python manage.py showmigrations payments
```

**Expected Output:**
```
[X] 0010_payment_hardening
[X] 0011_rename_payments_pr_provide_7a8f2c_idx_payments_pr_provide_200664_idx_and_more
```

### Step 2: Configure Webhook Secrets

#### Stripe Example
```python
from apps.payments.models import PaymentProviderSettings

# Add webhook secret
PaymentProviderSettings.objects.update_or_create(
    tenant_id=YOUR_TENANT_ID,
    provider_code="stripe",
    defaults={
        "webhook_secret": "whsec_abc123xyz...",  # From Stripe dashboard
        "is_active": True,
    }
)
```

#### PayPal Example
```python
PaymentProviderSettings.objects.update_or_create(
    tenant_id=YOUR_TENANT_ID,
    provider_code="paypal",
    defaults={
        "webhook_secret": "your-paypal-webhook-id",
        "is_active": True,
    }
)
```

### Step 3: Update Provider Adapters (Optional)

If you have custom payment adapters, wrap API calls with retry logic:

**Before:**
```python
def initiate_payment(self, order, amount, currency, return_url):
    response = self.provider_api.create_payment(...)
    return PaymentRedirect(...)
```

**After:**
```python
from apps.payments.security import PaymentProviderRetry, ProviderCommunicationLogger

def initiate_payment(self, order, amount, currency, return_url):
    with ProviderCommunicationLogger.track_operation(
        tenant_id=order.tenant_id,
        provider_code=self.code,
        operation="initiate_payment",
        request_data={"amount": str(amount), "currency": currency},
        idempotency_key=f"{self.code}:{order.id}:init",
        attempt_number=1,
    ) as tracker:
        def _api_call():
            return self.provider_api.create_payment(...)
        
        response = PaymentProviderRetry.execute_with_retry(
            operation=_api_call,
            operation_name="create_payment"
        )
        
        tracker.set_response({"payment_id": response.id}, status_code=200)
        return PaymentRedirect(...)
```

### Step 4: Backfill Existing Data (Optional)

If you want to analyze existing payments with fraud scoring:

```python
from decimal import Decimal
from apps.payments.models import PaymentIntent
from apps.payments.security import FraudDetectionService

# Backfill risk scores for recent payments
for intent in PaymentIntent.objects.filter(risk_score__isnull=True)[:1000]:
    fraud_result = FraudDetectionService.check_payment_risk(
        tenant_id=intent.tenant_id,
        order_id=intent.order_id,
        amount=intent.amount or Decimal("0.00"),
        currency=intent.currency or "USD",
    )
    
    intent.risk_score = fraud_result["risk_score"]
    intent.is_flagged = fraud_result["is_flagged"]
    intent.fraud_checks = fraud_result["checks"]
    intent.save(update_fields=["risk_score", "is_flagged", "fraud_checks"])
```

### Step 5: Update Webhook Endpoints

#### Django Views
If you have webhook endpoint views, update to extract security headers:

**Before:**
```python
@csrf_exempt
def stripe_webhook(request):
    payload = json.loads(request.body)
    HandleWebhookEventUseCase.execute(
        HandleWebhookEventCommand(
            provider_code="stripe",
            headers=dict(request.headers),
            payload=payload,
        )
    )
```

**After:**
```python
@csrf_exempt
def stripe_webhook(request):
    payload = json.loads(request.body)
    HandleWebhookEventUseCase.execute(
        HandleWebhookEventCommand(
            provider_code="stripe",
            headers=dict(request.headers),  # Now includes X-Webhook-Signature
            payload=payload,
            raw_body=request.body.decode("utf-8"),  # Required for signature validation
        )
    )
```

### Step 6: Configure Monitoring Alerts

Add monitoring for new security events:

```python
# Add to your monitoring setup (Sentry, CloudWatch, etc.)
from apps.payments.models import PaymentIntent, ProviderCommunicationLog
from apps.webhooks.models import WebhookEvent

def check_fraud_alerts():
    """Alert on high-risk payment blocks"""
    recent_high_risk = PaymentIntent.objects.filter(
        is_flagged=True,
        risk_score__gte=75,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    if recent_high_risk > 10:
        send_alert("High fraud activity detected", count=recent_high_risk)

def check_webhook_security():
    """Alert on webhook signature failures"""
    failed_webhooks = WebhookEvent.objects.filter(
        signature_verified=False,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    if failed_webhooks > 5:
        send_alert("Webhook signature failures detected", count=failed_webhooks)

def check_provider_health():
    """Alert on provider communication failures"""
    failed_calls = ProviderCommunicationLog.objects.filter(
        status_code__gte=500,
        created_at__gte=timezone.now() - timedelta(minutes=30)
    ).count()
    
    if failed_calls > 20:
        send_alert("Provider API experiencing high failure rate", count=failed_calls)
```

## Rollback Plan

### If Migration Fails
```bash
# Rollback to previous migration
python manage.py migrate payments 0009_webhookevent

# Restore database from backup
psql wasla_db < backup_before_payment_hardening_YYYYMMDD.sql
```

### If Issues Found Post-Migration
```bash
# Temporarily disable fraud checks by setting high threshold
# In Django admin or shell:
from apps.payments.security.fraud_detection import FraudDetectionService
FraudDetectionService.RISK_THRESHOLD_HIGH = 200  # Effectively disables auto-block

# Continue with existing flow while investigating
```

## Verification Checklist

### 1. Database Schema
```sql
-- Verify new columns exist
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'payments_paymentintent' 
AND column_name IN ('risk_score', 'is_flagged', 'fraud_checks', 'attempt_count');

-- Verify new table created
SELECT COUNT(*) FROM payments_providercommunicationlog;

-- Verify indexes
SELECT indexname FROM pg_indexes WHERE tablename = 'payments_providercommunicationlog';
```

### 2. Payment Flow Test
```python
# Create test payment
from apps.payments.application.use_cases.initiate_payment import InitiatePaymentCommand, InitiatePaymentUseCase
from apps.tenants.domain.tenant_context import TenantContext

cmd = InitiatePaymentCommand(
    tenant_ctx=TenantContext(tenant_id=1, store_id=1, currency="USD", user_id=None, session_key="test"),
    order_id=TEST_ORDER_ID,
    provider_code="dummy",
    return_url="https://example.com/return",
)

result = InitiatePaymentUseCase.execute(cmd)

# Verify fraud fields populated
from apps.payments.models import PaymentIntent
intent = PaymentIntent.objects.filter(order_id=TEST_ORDER_ID).latest('created_at')
assert intent.risk_score is not None
assert intent.fraud_checks is not None
print(f"✅ Payment created with risk score: {intent.risk_score}")
```

### 3. Webhook Security Test
```python
# Send test webhook with signature
from apps.payments.application.use_cases.handle_webhook_event import HandleWebhookEventCommand, HandleWebhookEventUseCase
from apps.payments.security import WebhookSecurityValidator
import time

payload = '{"event_id": "evt_test", "intent_reference": "ref_test", "status": "succeeded"}'
secret = "test_webhook_secret"
timestamp = str(int(time.time()))

# Compute valid signature
signature = WebhookSecurityValidator.compute_signature(
    payload=payload,
    secret=secret,
    algorithm="sha256"
)

cmd = HandleWebhookEventCommand(
    provider_code="dummy",
    headers={
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": timestamp,
    },
    payload={"event_id": "evt_test", "intent_reference": "ref_test", "status": "succeeded"},
    raw_body=payload,
)

# Execute (will verify signature internally)
event = HandleWebhookEventUseCase.execute(cmd)
print(f"✅ Webhook processed with signature: {event.signature_verified}")
```

### 4. Communication Logging Test
```python
# Verify logs created
from apps.payments.models import ProviderCommunicationLog

recent_logs = ProviderCommunicationLog.objects.all()[:10]
for log in recent_logs:
    print(f"✅ {log.operation} @ {log.created_at}: {log.status_code} ({log.duration_ms}ms)")
```

## Performance Impact

### Expected Changes:
- **Payment Initiation:** +50-100ms (fraud check queries)
- **Webhook Processing:** +10-20ms (signature validation)
- **Database Growth:** ~1MB per 1000 communication logs

### Optimization Tips:
```python
# Cache recent attempt counts for hot tenants
from django.core.cache import cache

def get_cached_attempt_count(tenant_id, order_id):
    cache_key = f"fraud:attempts:{tenant_id}:{order_id}"
    count = cache.get(cache_key)
    if count is None:
        count = PaymentIntent.objects.filter(
            tenant_id=tenant_id,
            order_id=order_id,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        cache.set(cache_key, count, timeout=300)  # 5 minutes
    return count
```

## Troubleshooting

### Issue: "Payment blocked due to high risk score"
**Cause:** Fraud detection triggered by multiple recent attempts or large amount.

**Solution:**
```python
# Check fraud details
intent = PaymentIntent.objects.get(id=INTENT_ID)
print(f"Risk Score: {intent.risk_score}")
print(f"Fraud Checks: {intent.fraud_checks}")

# Manually approve if legitimate
intent.is_flagged = False
intent.save()
```

### Issue: "Invalid webhook signature"
**Cause:** Webhook secret not configured or incorrect.

**Solution:**
```python
# Verify webhook secret
from apps.payments.models import PaymentProviderSettings
settings = PaymentProviderSettings.objects.filter(provider_code="stripe").first()
print(f"Webhook Secret: {settings.webhook_secret if settings else 'NOT CONFIGURED'}")

# Update webhook secret
settings.webhook_secret = "whsec_correct_secret_here"
settings.save()
```

### Issue: "Webhook timestamp expired"
**Cause:** Clock skew or webhook replay.

**Solution:**
```python
# Check server time sync
import time
from django.utils import timezone
print(f"Server time: {timezone.now()}")
print(f"Unix time: {int(time.time())}")

# Adjust tolerance if needed (in webhook_security.py)
WebhookSecurityValidator.REPLAY_WINDOW_SECONDS = 600  # 10 minutes
```

### Issue: High database growth from communication logs
**Cause:** Logging all provider interactions.

**Solution:**
```python
# Set up log rotation (add to cron)
from django.utils import timezone
from datetime import timedelta
from apps.payments.models import ProviderCommunicationLog

# Delete logs older than 30 days
cutoff = timezone.now() - timedelta(days=30)
deleted = ProviderCommunicationLog.objects.filter(created_at__lt=cutoff).delete()
print(f"Deleted {deleted[0]} old communication logs")
```

## Support

### Getting Help
- Check logs in `ProviderCommunicationLog` for detailed error context
- Review fraud check details in `PaymentIntent.fraud_checks` JSON field
- Check webhook signature verification in `WebhookEvent.signature_verified`

### Reporting Issues
When reporting issues, include:
1. Payment intent ID and order ID
2. Risk score and fraud_checks JSON
3. Communication log entries for the operation
4. Webhook event details if applicable

## Next Steps

After successful migration:
1. Monitor fraud detection effectiveness for 1-2 weeks
2. Adjust risk thresholds based on false positive rate
3. Configure webhook secrets for all active providers
4. Set up automated alerts for security events
5. Review communication logs to identify provider performance issues

## References
- [PAYMENT_HARDENING_SUMMARY.md](./PAYMENT_HARDENING_SUMMARY.md) - Complete feature documentation
- [PAYMENT_COMPLIANCE.md](./PAYMENT_COMPLIANCE.md) - Compliance implications
- Django Admin: `/admin/payments/paymentintent/` - View payment risk scores
- Django Admin: `/admin/payments/providercommunicationlog/` - Audit trail
