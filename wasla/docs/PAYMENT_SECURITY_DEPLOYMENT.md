# Payment Security Hardening - Deployment Guide

## Overview

This guide covers enterprise-grade payment security implementation for the Wasla SaaS platform. All changes are backward compatible and extend existing payment infrastructure without breaking changes.

## Architecture

### Security Layers

```
1. IDEMPOTENCY LAYER
   ├─ Prevents duplicate charge processing
   ├─ Unique constraint: (store_id, order_id, idempotency_key)
   └─ Status-aware: Allows retry on failure

2. WEBHOOK SECURITY LAYER
   ├─ HMAC-SHA256 signature validation
   ├─ Replay attack protection (timestamp window)
   ├─ Payload integrity verification
   └─ Event deduplication

3. RETRY RESILIENCE LAYER
   ├─ Exponential backoff: 1s → 2s → 4s → 60s max
   ├─ Jitter: ±10% to prevent thundering herd
   ├─ Status-aware: Retryable vs terminal states
   └─ Maximum 3 retry attempts (configurable)

4. FRAUD DETECTION LAYER
   ├─ Risk scoring: 0-100 scale
   ├─ Multi-factor analysis: velocity, amount, history
   ├─ Automated flagging: score > 75
   └─ Manual review workflow: approve/reject

5. AUDIT & LOGGING LAYER
   ├─ Structured JSON logging
   ├─ All state changes tracked
   ├─ Compliance: PCI-DSS + industry standards
   └─ Integration: ELK, Datadog, CloudWatch
```

## Database Migration

### 1. Run Migration

```bash
python manage.py migrate payments
```

This applies `0008_payment_security_hardening.py` with:
- Enhanced `PaymentAttempt`: 11 new fields
- Enhanced `WebhookEvent`: 8 new fields
- Created `PaymentRisk`: 24-field fraud detection model
- 5 new database indexes for performance
- Unique constraint: `WebhookEvent(provider, event_id)`

### 2. Verify Migration

```bash
python manage.py showmigrations payments
# Should show: [X] 0008_payment_security_hardening

python manage.py shell
>>> from apps.payments.models import PaymentRisk
>>> PaymentRisk.objects.count()  # Should return 0 (no data yet)
```

## Configuration

### 1. Webhook Secrets Setup

For each payment provider, configure webhook secret in PaymentProviderSettings:

```bash
python manage.py shell
```

```python
from apps.payments.models import PaymentProviderSettings

# Stripe example
stripe_settings = PaymentProviderSettings.objects.get(provider_code='stripe')
stripe_settings.webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
stripe_settings.webhook_timeout_seconds = 30
stripe_settings.retry_max_attempts = 3
stripe_settings.idempotency_key_required = True
stripe_settings.save()

# PayPal example
paypal_settings = PaymentProviderSettings.objects.get(provider_code='paypal')
paypal_settings.webhook_secret = os.environ.get('PAYPAL_WEBHOOK_SECRET')
paypal_settings.save()
```

### 2. Environment Variables

Add to your `.env` or deployment config:

```bash
# Stripe
STRIPE_WEBHOOK_SECRET=whsec_test_...

# PayPal
PAYPAL_WEBHOOK_SECRET=webhook_secret_...

# Payment Security Settings
PAYMENT_IDEMPOTENCY_REQUIRED=true
PAYMENT_WEBHOOK_TIMEOUT_SECONDS=30
PAYMENT_RETRY_MAX_ATTEMPTS=3
PAYMENT_RISK_SCORE_THRESHOLD=75

# Logging
PAYMENT_SECURITY_LOG_LEVEL=INFO
PAYMENT_AUDIT_LOG_ENABLED=true
```

### 3. Django Settings

Add to `config/settings.py`:

```python
# Payment Security Configuration
PAYMENT_SECURITY = {
    'IDEMPOTENCY_REQUIRED': True,
    'WEBHOOK_TIMEOUT_SECONDS': 30,
    'WEBHOOK_REPLAY_PROTECTION_WINDOW': 300,  # 5 minutes
    'RETRY_MAX_ATTEMPTS': 3,
    'RETRY_INITIAL_DELAY': 1,  # seconds
    'RETRY_MAX_DELAY': 60,  # seconds
    'RETRY_JITTER_PERCENT': 10,
    'RISK_SCORE_THRESHOLD': 75,  # Flag if score > 75
    'RISK_SCORING_ENABLED': True,
    'STRUCTURED_LOGGING_ENABLED': True,
    'AUDIT_LOG_RETENTION_DAYS': 90,
}

# Logging configuration for payment events
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(timestamp)s %(name)s %(levelname)s %(message)s',
        },
    },
    'handlers': {
        'payment_security': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/payment_security.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'json',
        },
    },
    'loggers': {
        'apps.payments.security': {
            'handlers': ['payment_security'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.payments.services.webhook_security_handler': {
            'handlers': ['payment_security'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

## API Integration

### 1. Register Routes

In `config/urls.py`:

```python
from rest_framework.routers import DefaultRouter
from apps.payments.views_security import register_payment_routes

router = DefaultRouter()
register_payment_routes(router)

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
```

### 2. Admin APIs

**List Flagged Payments**

```bash
GET /api/v1/admin/payment-risk/?risk_level=high&reviewed=false

Response:
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 123,
      "order_id": 456,
      "order_number": "ORD-789",
      "customer_name": "John Doe",
      "amount": "250.00",
      "risk_score": 82,
      "risk_level": "critical",
      "triggered_rules": [
        "New Customer",
        "High IP Velocity (5 min)"
      ],
      "ip_address": "203.0.113.45",
      "reviewed": false
    }
  ]
}
```

**Approve Risky Payment**

```bash
POST /api/v1/admin/payment-risk/123/approve/

Request:
{
  "review_notes": "Payment looks legitimate, customer verified"
}

Response:
{
  "id": 123,
  "order_id": 456,
  "review_decision": "approved",
  "reviewed_by": "admin@wasla.com",
  "reviewed_at": "2024-01-15T10:30:00Z"
}
```

**Reject Risky Payment**

```bash
POST /api/v1/admin/payment-risk/123/reject/

Request:
{
  "review_notes": "Payment declined due to fraud indicators"
}

Response:
{
  "id": 123,
  "order_id": 456,
  "review_decision": "rejected",
  "reviewed_by": "admin@wasla.com",
  "reviewed_at": "2024-01-15T10:30:00Z"
}
```

**Webhook Event Log**

```bash
GET /api/v1/admin/webhook-events/?provider=stripe&signature_verified=true

Response:
{
  "count": 150,
  "results": [
    {
      "id": 789,
      "provider": "stripe",
      "event_id": "evt_1234567890",
      "signature_verified": true,
      "status": "processed",
      "retry_count": 0,
      "created_at": "2024-01-15T10:15:00Z",
      "processed_at": "2024-01-15T10:15:02Z"
    }
  ]
}
```

### 3. Merchant APIs

**Order Payment Status**

```bash
GET /api/v1/orders/456/payment-status/

Response:
{
  "id": 456,
  "order_number": "ORD-789",
  "grand_total": "250.00",
  "overall_status": "paid",
  "payment_attempts": [
    {
      "id": 123,
      "provider": "stripe",
      "status": "paid",
      "amount": "250.00",
      "webhook_verified": true,
      "created_at": "2024-01-15T10:15:00Z",
      "confirmed_at": "2024-01-15T10:15:05Z"
    }
  ],
  "payment_timeline": [
    {
      "timestamp": "2024-01-15T10:15:00Z",
      "event_type": "payment_attempt",
      "status": "pending",
      "message": "Payment attempt with Stripe"
    },
    {
      "timestamp": "2024-01-15T10:15:05Z",
      "event_type": "webhook_processed",
      "status": "processed",
      "message": "Webhook processed: evt_123"
    }
  ]
}
```

## Webhook Integration

### 1. Webhook Handler Setup

The webhook handler now integrates all security layers. To use:

```python
from apps.payments.services.webhook_security_handler import (
    WebhookSecurityHandler,
    WebhookContext,
)

@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """Handle Stripe webhooks with security validation."""
    
    try:
        # Build context
        context = WebhookContext(
            provider_code='stripe',
            headers=dict(request.headers),
            payload=json.loads(request.body),
            raw_body=request.body.decode('utf-8'),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get('User-Agent', ''),
        )
        
        # Process with full security validation
        webhook_event, payment_risk = WebhookSecurityHandler.process_webhook(
            context=context,
            store_id=request.store.id,
        )
        
        # Handle based on webhook type
        if webhook_event.payload_json.get('type') == 'charge.succeeded':
            handle_charge_success(webhook_event)
        elif webhook_event.payload_json.get('type') == 'charge.failed':
            handle_charge_failure(webhook_event)
        
        # If high risk, requires manual review
        if payment_risk and payment_risk.flagged:
            notify_risk_team(payment_risk)
        
        return JsonResponse({'status': 'success'}, status=200)
    
    except ValidationError as e:
        logger.error(f"Webhook validation failed: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.exception("Webhook processing error")
        return JsonResponse({'error': 'Processing error'}, status=500)
```

### 2. Webhook Signature Setup

**Stripe:**

```python
# Generate webhook secret in Stripe Dashboard
# Settings → Webhooks → Add endpoint

# In PaymentProviderSettings:
stripe_settings.webhook_secret = 'whsec_test_...'
```

**PayPal:**

```python
# Generate webhook ID in PayPal Dashboard
# Apps & Credentials → Webhooks

# In PaymentProviderSettings:
paypal_settings.webhook_secret = 'webhook_secret_...'
```

## Monitoring & Alerts

### 1. Key Metrics to Monitor

```python
# Payment Success Rate
SELECT 
  COUNT(*) as total,
  COUNT(CASE WHEN status = 'paid' THEN 1 END) as successful,
  COUNT(CASE WHEN status = 'paid' THEN 1 END) * 100.0 / COUNT(*) as success_rate
FROM payments_paymentattempt
WHERE created_at > NOW() - INTERVAL 24 HOUR;

# Risk Score Distribution
SELECT 
  risk_level,
  COUNT(*) as count
FROM payments_paymentrisk
WHERE created_at > NOW() - INTERVAL 24 HOUR
GROUP BY risk_level;

# Webhook Processing
SELECT 
  status,
  COUNT(*) as count,
  AVG(retry_count) as avg_retries
FROM payments_webhookevent
WHERE created_at > NOW() - INTERVAL 24 HOUR
GROUP BY status;

# Idempotency Violations (duplicates prevented)
SELECT 
  COUNT(DISTINCT idempotency_key) as unique_payments,
  COUNT(*) as total_attempts,
  COUNT(*) - COUNT(DISTINCT idempotency_key) as duplicates_prevented
FROM payments_paymentattempt
WHERE created_at > NOW() - INTERVAL 7 DAYS;
```

### 2. Alert Conditions

```yaml
Payment Alerts:
  - Name: "High Risk Payments"
    Query: "SUM(flagged=true) > 10 in 1 hour"
    Action: "Notify risk team"
  
  - Name: "Webhook Failures"
    Query: "SUM(status='failed') > 5 in 1 hour"
    Action: "Notify ops, check provider API status"
  
  - Name: "Duplicate Prevention Active"
    Query: "duplicates_prevented > 0"
    Action: "Info: Idempotency working - duplicates blocked"
  
  - Name: "High Retry Rate"
    Query: "AVG(retry_count) > 2"
    Action: "Investigate provider reliability"
```

### 3. Logging Strategy

All payment operations log to structured JSON format:

```json
{
  "timestamp": "2024-01-15T10:15:00.123Z",
  "event_type": "webhook_received",
  "provider": "stripe",
  "order_id": 456,
  "store_id": 789,
  "signature_verified": true,
  "duration_ms": 125,
  "risk_score": 35,
  "risk_level": "low",
  "triggered_rules": [],
  "ip_address": "203.0.113.45"
}
```

Log these to:
- **Local**: `logs/payment_security.log` (rotated)
- **ELK Stack**: Logstash ingest
- **Datadog**: Custom payment metrics
- **CloudWatch**: AWS Lambda/Fargate integration

## Testing

### 1. Run Test Suite

```bash
# All payment security tests
pytest tests/test_payment_security.py -v

# Specific test
pytest tests/test_payment_security.py::TestIdempotencyValidation -v

# With coverage
pytest tests/test_payment_security.py --cov=apps.payments --cov-report=html
```

### 2. Manual Testing

```bash
# Test idempotency
curl -X POST http://localhost:8000/api/payments/charge/ \
  -H "Idempotency-Key: key123" \
  -d '{"amount": 100}'

# Same key again - should return cached result
curl -X POST http://localhost:8000/api/payments/charge/ \
  -H "Idempotency-Key: key123" \
  -d '{"amount": 100}'

# Test webhook with signature
PAYLOAD='{"event_id": "evt_123", "amount": 100}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -hex)

curl -X POST http://localhost:8000/webhooks/stripe/ \
  -H "X-Webhook-Signature: $SIGNATURE" \
  -H "X-Webhook-Timestamp: $(date +%s)" \
  -d "$PAYLOAD"
```

## Troubleshooting

### Common Issues

**1. Webhook Signature Invalid**

```
Error: "Invalid webhook signature"

Solution:
- Verify webhook_secret matches provider settings
- Ensure raw_body is used (not parsed JSON)
- Check timestamp formatting
- Verify HMAC algorithm (must be SHA256)
```

**2. Idempotency Key Not Working**

```
Error: Duplicate charges still occurring

Solution:
- Run migration: python manage.py migrate payments
- Verify idempotency_key field exists in PaymentAttempt
- Check unique constraint in database
- Ensure idempotency_key is generated consistently
```

**3. High Retry Count**

```
Error: Payments stuck in retry loop

Solution:
- Check provider API status
- Verify network connectivity
- Review last_error in webhook_event
- Check rate limiting
```

**4. Risk Scoring Not Triggering**

```
Error: Fraudulent payments not flagged

Solution:
- Verify RISK_SCORE_THRESHOLD setting
- Check RiskScoringEngine calculation
- Review triggered_rules in PaymentRisk
- Ensure store has payment history for velocity calculation
```

## Rollback Plan

If issues arise, rollback is safe:

```bash
# Backward compatible - can disable without rollback
# Option 1: Disable risk scoring
PAYMENT_RISK_SCORING_ENABLED=false

# Option 2: Disable webhook validation
PAYMENT_WEBHOOK_VALIDATION_ENABLED=false

# Option 3: Full rollback (last resort)
python manage.py migrate payments 0007_previous_migration
```

## Compliance & Security

### PCI-DSS Compliance

- ✅ No card data stored (provider-handled)
- ✅ Encrypted webhook secrets in database
- ✅ HMAC-SHA256 for data integrity
- ✅ Audit trail for all operations
- ✅ 90-day log retention

### Security Best Practices

1. **Webhook Secrets**: Use 32+ character random strings
2. **HTTPS Only**: All webhooks over TLS 1.2+
3. **IP Whitelisting**: Consider provider IP whitelist
4. **Rate Limiting**: Implement request throttling
5. **Monitoring**: Real-time alerts for anomalies
6. **Rotation**: Rotate secrets quarterly

## Support & Documentation

- **Code**: [apps/payments/security.py](apps/payments/security.py)
- **Models**: [apps/payments/models.py](apps/payments/models.py)
- **Tests**: [tests/test_payment_security.py](tests/test_payment_security.py)
- **API Docs**: [/api/docs/](http://localhost:8000/api/docs/)

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0  
**Status**: Production Ready ✅
