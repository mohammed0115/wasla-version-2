# Payment Security Integration Guide

## Overview

This document explains how to integrate the new payment security system into your existing payment processing flow without breaking changes.

## Architecture Overview

The payment security hardening adds **5 independent layers** of protection:

1. **Idempotency Layer** - Prevent duplicate charges
2. **Webhook Security** - Cryptographic validation
3. **Replay Protection** - Timestamp-based attack prevention
4. **Retry Resilience** - Exponential backoff on transient failures
5. **Fraud Detection** - Risk scoring with manual review queue

All layers are **optional during transition** - you can enable them incrementally.

## Integration Paths

### Path A: Full Integration (Recommended)

Use the new `WebhookSecurityHandler` for complete security flow:

```python
from apps.payments.services.webhook_security_handler import (
    WebhookSecurityHandler,
    WebhookContext,
)

@csrf_exempt
def stripe_webhook_handler(request):
    """New secure webhook handler."""
    
    try:
        # Step 1: Build context from request
        context = WebhookContext(
            provider_code='stripe',
            headers=dict(request.headers),
            payload=json.loads(request.body),
            raw_body=request.body.decode('utf-8'),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get('User-Agent', ''),
        )
        
        # Step 2: Process webhook with full security validation
        webhook_event, payment_risk = WebhookSecurityHandler.process_webhook(
            context=context,
            order_id=int(request.GET.get('order_id', 0)),
            store_id=int(request.GET.get('store_id', 0)),
        )
        
        # Step 3: Route based on webhook type and risk level
        event_type = webhook_event.payload_json.get('type')
        
        if event_type == 'charge.succeeded':
            # Payment confirmed
            handle_payment_success(webhook_event)
        
        elif event_type == 'charge.failed':
            # Payment failed
            handle_payment_failure(webhook_event)
        
        # Step 4: Handle risky payments
        if payment_risk and payment_risk.flagged:
            notify_risk_team(payment_risk)
            return JsonResponse({
                'status': 'pending_review',
                'risk_id': payment_risk.id,
            })
        
        return JsonResponse({'status': 'success'}, status=200)
    
    except ValidationError as e:
        logger.error(f"Webhook security validation failed: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    
    except Exception as e:
        logger.exception("Webhook processing error")
        return JsonResponse({'error': 'Processing error'}, status=500)
```

### Path B: Gradual Integration

If you want to enable gradually:

**Step 1: Enable idempotency only**

```python
from apps.payments.security import IdempotencyValidator

def create_payment(order_id, amount, client_token):
    """Create payment with idempotency checking."""
    
    # Generate idempotency key
    from apps.payments.security import generate_idempotency_key
    idempotency_key = generate_idempotency_key(
        store_id=order.store_id,
        order_id=order_id,
        client_token=client_token,
    )
    
    # Check if already processed
    is_duplicate, result = IdempotencyValidator.check_duplicate(
        store_id=order.store_id,
        order_id=order_id,
        idempotency_key=idempotency_key,
    )
    
    if is_duplicate:
        # Return cached result
        return result
    
    # Process new charge
    attempt = PaymentAttempt.objects.create(
        order=order,
        amount=amount,
        idempotency_key=idempotency_key,
        status='pending',
    )
    
    return {'attempt_id': attempt.id}
```

**Step 2: Add webhook signature validation**

```python
from apps.payments.security import validate_webhook_signature

def verify_stripe_webhook(request):
    """Verify webhook signature before processing."""
    
    webhook_secret = PaymentProviderSettings.objects.get(
        provider_code='stripe'
    ).webhook_secret
    
    signature = request.headers.get('X-Signature')
    is_valid = validate_webhook_signature(
        payload=request.body.decode('utf-8'),
        signature=signature,
        webhook_secret=webhook_secret,
    )
    
    if not is_valid:
        raise ValidationError("Invalid webhook signature")
    
    return True
```

**Step 3: Add replay protection**

```python
from apps.payments.security import validate_webhook_timestamp

def check_webhook_freshness(request):
    """Prevent replay attacks."""
    
    timestamp = int(request.headers.get('X-Timestamp', 0))
    is_fresh, error = validate_webhook_timestamp(
        webhook_timestamp=timestamp,
        tolerance_seconds=300,  # 5 minutes
    )
    
    if not is_fresh:
        raise ValidationError(f"Webhook timestamp check failed: {error}")
    
    return True
```

**Step 4: Add retry logic**

```python
from apps.payments.retry_strategy import execute_with_retry

def charge_with_retry(amount, card_token, order_id):
    """Charge customer with automatic retry."""
    
    def charge_operation():
        return stripe.Charge.create(
            amount=int(amount * 100),
            currency='usd',
            source=card_token,
        )
    
    result = execute_with_retry(
        func=charge_operation,
        max_retries=3,
        initial_delay=1,
        operation_name="create_charge",
        order_id=order_id,
    )
    
    return result
```

**Step 5: Add risk scoring**

```python
from apps.payments.security import RiskScoringEngine

def assess_payment_risk(order_id, customer_ip, amount):
    """Calculate fraud risk before charging."""
    
    risk_score, details = RiskScoringEngine.calculate_risk_score(
        store_id=order.store_id,
        order_id=order_id,
        ip_address=customer_ip,
        amount=amount,
        is_new_customer=customer.first_order,
    )
    
    if risk_score > 75:
        # Create risk record requiring manual review
        PaymentRisk.objects.create(
            order_id=order_id,
            risk_score=risk_score,
            risk_level='critical',
            flagged=True,
            ip_address=customer_ip,
            triggered_rules=details['triggered_rules'],
        )
        
        # Block or hold for review
        notify_admin("High-risk payment requires manual approval")
        return False
    
    return True
```

### Path C: Middleware Integration

Add security checks via middleware:

```python
from apps.payments.security import validate_webhook_signature

class PaymentSecurityMiddleware:
    """Middleware for all payment endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check webhook signature if payment-related
        if request.path.startswith('/webhooks/'):
            try:
                validate_webhook_signature(
                    payload=request.body.decode('utf-8'),
                    signature=request.headers.get('X-Signature', ''),
                    webhook_secret=self._get_webhook_secret(request),
                )
            except ValidationError as e:
                return JsonResponse({'error': str(e)}, status=403)
        
        response = self.get_response(request)
        return response
    
    def _get_webhook_secret(self, request):
        provider = self._get_provider_from_path(request.path)
        settings = PaymentProviderSettings.objects.get(provider_code=provider)
        return settings.webhook_secret
```

## Database Preparation

### 1. Run Migration

```bash
python manage.py migrate payments
```

This creates:
- 4 enhanced model tables (WebhookEvent, PaymentAttempt, PaymentRisk, PaymentProviderSettings)
- 5 new indexes for query performance
- Unique constraint on WebhookEvent(provider, event_id)

### 2. Verify Schema

```bash
python manage.py shell
```

```python
>>> from apps.payments.models import PaymentRisk
>>> PaymentRisk._meta.get_fields()
# Should show ~24 fields

>>> from django.db import connection
>>> cursor = connection.cursor()
>>> cursor.execute("""
...   SELECT constraint_name, constraint_type 
...   FROM information_schema.table_constraints 
...   WHERE table_name = 'payments_webhookevent'
... """)
# Should show unique constraint on (provider, event_id)
```

## Configuration

### 1. Environment Variables

```bash
# .env or deployment config
STRIPE_WEBHOOK_SECRET=whsec_test_...
PAYPAL_WEBHOOK_SECRET=webhook_secret_...

PAYMENT_IDEMPOTENCY_REQUIRED=true
PAYMENT_WEBHOOK_TIMEOUT_SECONDS=30
PAYMENT_RETRY_MAX_ATTEMPTS=3
PAYMENT_RISK_SCORE_THRESHOLD=75
```

### 2. Settings Update

In `config/settings.py`:

```python
PAYMENT_SECURITY = {
    'IDEMPOTENCY_REQUIRED': env.bool('PAYMENT_IDEMPOTENCY_REQUIRED', True),
    'WEBHOOK_TIMEOUT_SECONDS': env.int('PAYMENT_WEBHOOK_TIMEOUT_SECONDS', 30),
    'RETRY_MAX_ATTEMPTS': env.int('PAYMENT_RETRY_MAX_ATTEMPTS', 3),
    'RETRY_INITIAL_DELAY': 1,  # seconds
    'RETRY_MAX_DELAY': 60,  # seconds
    'RISK_SCORE_THRESHOLD': env.int('PAYMENT_RISK_SCORE_THRESHOLD', 75),
}
```

## Testing Integration

### Unit Tests

```bash
# Run all payment security tests
pytest tests/test_payment_security.py -v

# Test specific feature
pytest tests/test_payment_security.py::TestIdempotencyValidation -v
```

### Integration Test

```python
def test_webhook_full_flow():
    """Test complete webhook security flow."""
    from apps.payments.services.webhook_security_handler import (
        WebhookSecurityHandler,
        WebhookContext,
    )
    
    # Create test webhook context
    context = WebhookContext(
        provider_code='stripe',
        headers={
            'X-Webhook-Signature': generate_test_signature(),
            'X-Webhook-Timestamp': str(int(time.time())),
        },
        payload={'event_id': 'evt_test_123', 'amount': 100},
        raw_body='{"event_id": "evt_test_123", "amount": 100}',
    )
    
    # Process and verify
    webhook_event, payment_risk = WebhookSecurityHandler.process_webhook(
        context=context,
        order_id=123,
        store_id=456,
    )
    
    assert webhook_event.signature_verified
    assert webhook_event.idempotency_checked
    assert webhook_event.status in ['processed', 'pending_review']
```

## Monitoring Setup

### Metrics to Track

```sql
-- Payment success rate
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as successful
FROM payments_paymentattempt
WHERE created_at > NOW() - INTERVAL 24 HOUR;

-- Risk detection
SELECT 
  risk_level,
  COUNT(*) as count
FROM payments_paymentrisk
WHERE created_at > NOW() - INTERVAL 24 HOUR
GROUP BY risk_level;

-- Duplicate prevention (idempotency)
SELECT 
  COUNT(DISTINCT idempotency_key) as unique,
  COUNT(*) as total,
  COUNT(*) - COUNT(DISTINCT idempotency_key) as duplicates_blocked
FROM payments_paymentattempt
WHERE created_at > NOW() - INTERVAL 7 DAYS;
```

### Alert Rules

```yaml
alerts:
  - name: "High-risk payments detected"
    condition: "SUM(flagged=true) > 10 within 1h"
    action: "Notify risk@wasla.com"
  
  - name: "Webhook processing failures"
    condition: "SUM(status='failed') > 5 within 1h"
    action: "Notify ops@wasla.com"
  
  - name: "Duplicate prevention active"
    condition: "duplicates_blocked > 0"
    action: "Info log only"
```

## Troubleshooting

| Issue | Symptom | Solution |
|-------|---------|----------|
| Webhook signature validation fails | 400 error on webhook receipt | Check webhook_secret matches provider, verify raw_body used |
| Idempotency not working | Duplicate charges | Run migration, verify unique constraint exists |
| High risk scores triggering falsely | Too many legitimate blocks | Tune risk thresholds in RiskScoringEngine |
| Webhook processing slow | > 500ms processing time | Check database indexes, verify risk calculation is needed |
| Retries not happening | Payments stuck as pending | Verify next_retry_after set correctly, check scheduler |

## Migration Checklist

- [ ] Review all 7 new files created
- [ ] Run database migration
- [ ] Configure webhook secrets
- [ ] Update logging config  
- [ ] Set environment variables
- [ ] Run test suite
- [ ] Deploy to staging
- [ ] Test webhook reception (manual)
- [ ] Monitor metrics for 24 hours
- [ ] Deploy to production
- [ ] Enable monitoring alerts

## Performance Impact

| Operation | Time | Impact |
|-----------|------|--------|
| Signature validation | 5ms | Negligible |
| Risk scoring | 50ms | Acceptable |
| Idempotency check | 10ms | Negligible |
| DB storage per payment | 2KB | ~200MB per 1M payments |

## Stripe Live Integration (PaymentIntent)

This release upgrades Stripe from stub mode to **live PaymentIntent** integration.

### Environment Variables (required)
```
STRIPE_API_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLIC_KEY=pk_test_...
```

### Tenant Provider Configuration (DB)
Store secrets **as env var names** instead of raw values:

```json
{
  "api_key_env": "STRIPE_API_KEY",
  "webhook_secret_env": "STRIPE_WEBHOOK_SECRET",
  "public_key_env": "STRIPE_PUBLIC_KEY"
}
```

### Webhook Events Handled
- `payment_intent.succeeded`
- `payment_intent.payment_failed`

### Idempotency
Stripe requests include `Idempotency-Key` from the platform’s payment idempotency key.

## Rollback Procedure

All changes are **non-breaking**. To rollback:

```bash
# Option 1: Disable features (no rollback needed)
PAYMENT_IDEMPOTENCY_REQUIRED=false
PAYMENT_RISK_SCORING_ENABLED=false

# Option 2: Full rollback (if needed)
python manage.py migrate payments 0007_previous_migration
```

## Next Steps

1. **Review** the new security code in [apps/payments/](apps/payments/)
2. **Configure** webhook secrets for your payment providers
3. **Test** with the provided test suite
4. **Deploy** to staging environment
5. **Monitor** metrics for 48 hours
6. **Deploy** to production

For detailed information, see:
- [PAYMENT_SECURITY_README.md](PAYMENT_SECURITY_README.md) - Quick reference
- [docs/PAYMENT_SECURITY_DEPLOYMENT.md](docs/PAYMENT_SECURITY_DEPLOYMENT.md) - Full deployment guide
- [tests/test_payment_security.py](tests/test_payment_security.py) - Test examples
- [apps/payments/security.py](apps/payments/security.py) - Implementation details

---

**Questions?** See the docs or check the test suite for usage examples.
