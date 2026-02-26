# Payment Security Quick Start Checklist

## ✅ Pre-Deployment (1 Day)

### Documentation Review (30 min)
- [ ] Read [PAYMENT_SECURITY_README.md](../PAYMENT_SECURITY_README.md)
- [ ] Skim [docs/PAYMENT_SECURITY_ARCHITECTURE.md](docs/PAYMENT_SECURITY_ARCHITECTURE.md)
- [ ] Understand the 5 security layers

### Code Review (30 min)
- [ ] Review [apps/payments/security.py](../apps/payments/security.py)
- [ ] Check [apps/payments/models.py](../apps/payments/models.py) changes
- [ ] Review [apps/payments/services/webhook_security_handler.py](../apps/payments/services/webhook_security_handler.py)

### Testing (30 min)
- [ ] Install dependencies if needed
- [ ] Run: `pytest tests/test_payment_security.py -v`
- [ ] Verify all tests pass
- [ ] Check test coverage: `pytest tests/test_payment_security.py --cov=apps.payments`

### Preparation (30 min)
- [ ] Gather webhook secrets from all payment providers:
  - [ ] Stripe webhook secret (from Dashboard → Webhooks)
  - [ ] PayPal webhook secret
  - [ ] Square webhook secret (if applicable)
  - [ ] Other providers...
- [ ] Plan maintenance window (15 min, during low traffic)
- [ ] Backup production database
- [ ] Notify team of upcoming changes

---

## 🚀 Staging Deployment (1 Day)

### Database Setup (10 min)
```bash
# Apply migration
python manage.py migrate payments

# Verify migration applied
python manage.py showmigrations payments
# Should show: [X] 0008_payment_security_hardening
```
- [ ] Migration completed successfully
- [ ] No data loss (migration is backward compatible)
- [ ] Indexes created (verify with: `\d+ payments_paymentattempt` in psql)

### Configuration (20 min)
```bash
# Set environment variables
export STRIPE_WEBHOOK_SECRET="whsec_test_..."
export PAYPAL_WEBHOOK_SECRET="webhook_secret_..."
export PAYMENT_RISK_SCORE_THRESHOLD="75"
export PAYMENT_RETRY_MAX_ATTEMPTS="3"
```
- [ ] All webhook secrets configured
- [ ] Django settings updated with PAYMENT_SECURITY config
- [ ] Logging configured for payment_security.log

### Model Configuration (10 min)
```python
from apps.payments.models import PaymentProviderSettings

# Configure each provider
for provider in ['stripe', 'paypal', 'square']:
    try:
        settings = PaymentProviderSettings.objects.get(
            provider_code=provider
        )
        settings.webhook_secret = os.environ.get(
            f'{provider.upper()}_WEBHOOK_SECRET'
        )
        settings.webhook_timeout_seconds = 30
        settings.retry_max_attempts = 3
        settings.idempotency_key_required = True
        settings.save()
        print(f"✓ {provider} configured")
    except PaymentProviderSettings.DoesNotExist:
        print(f"! {provider} not found - skip")
```
- [ ] Stripe webhook secret saved
- [ ] PayPal webhook secret saved
- [ ] Other providers configured

### Integration Testing (20 min)

**Test 1: Idempotency**
```bash
# Make same request twice with same idempotency key
curl -X POST http://staging/api/payments/charge/ \
  -H "Idempotency-Key: key123" \
  -d '{"amount": 100}'

# Same key again - should return cached result
curl -X POST http://staging/api/payments/charge/ \
  -H "Idempotency-Key: key123" \
  -d '{"amount": 100}'

# Verify: Both return same result, no duplicate charge
```
- [ ] Idempotency working correctly

**Test 2: Webhook Signature Validation**
```bash
# Generate test signature
PAYLOAD='{"event_id": "evt_test_123", "amount": 100}'
SIGNATURE=$(python3 -c "
import hmac, hashlib
secret = 'your_webhook_secret'
sig = hmac.new(secret.encode(), '$PAYLOAD'.encode(), hashlib.sha256)
print(sig.hexdigest())
")

# Send webhook with signature
curl -X POST http://staging/webhooks/stripe/ \
  -H "X-Webhook-Signature: $SIGNATURE" \
  -H "X-Webhook-Timestamp: $(date +%s)" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

# Verify: Webhook processed successfully (status 200)
```
- [ ] Valid signatures accepted
- [ ] Invalid signatures rejected
- [ ] Timestamp validation working

**Test 3: Risk Scoring**
```python
from apps.payments.security import RiskScoringEngine

risk_score, details = RiskScoringEngine.calculate_risk_score(
    store_id=1,
    order_id=123,
    ip_address="203.0.113.45",
    amount=100,
    is_new_customer=True,
)

print(f"Risk Score: {risk_score}")
print(f"Triggered Rules: {details['triggered_rules']}")

# Verify: New customer flag triggers +10 points
```
- [ ] Risk scoring returning valid scores (0-100)
- [ ] Triggered rules populated correctly

**Test 4: Retry Strategy**
```python
from apps.payments.retry_strategy import RetryStrategy

# Test backoff calculation
for attempt in range(5):
    next_retry = RetryStrategy.calculate_next_retry(
        retry_count=attempt,
        initial_delay=1,
        max_delay=60,
    )
    delay = (next_retry - timezone.now()).total_seconds()
    print(f"Attempt {attempt+1}: {delay:.1f}s")

# Verify: 1s, 2s, 4s, 8s, 16s (with ±10% jitter)
```
- [ ] Exponential backoff calculated correctly
- [ ] Jitter applied (not exact times)

### Logging Verification (10 min)
```bash
# Check payment security logs
tail -f logs/payment_security.log

# Should see JSON formatted events:
# {"timestamp": "2024-01-15T10:15:00Z", "event_type": "webhook_received", ...}
```
- [ ] Structured JSON logging working
- [ ] Events logged with timestamps
- [ ] Payment events in separate log file

### API Testing (10 min)
```bash
# List flagged payments
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://staging/api/v1/admin/payment-risk/?flagged=true

# Approve risky payment
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"review_notes": "Verified customer"}' \
  http://staging/api/v1/admin/payment-risk/123/approve/

# Get order payment status
curl -H "Authorization: Bearer $MERCHANT_TOKEN" \
  http://staging/api/v1/orders/456/payment-status/
```
- [ ] Admin APIs returning data
- [ ] Merchant APIs working correctly
- [ ] Authentication/authorization enforced

### Monitoring Setup (20 min)
- [ ] Set up success rate tracking
- [ ] Set up risk score distribution monitoring
- [ ] Set up webhook failure alerts
- [ ] Set up duplicate prevention alerts
- [ ] Dashboard created with key metrics

---

## 📊 Staging Validation (1 Day)

### Metrics Baseline (Daily)
```sql
-- Run daily for 24 hours
SELECT 
  DATE_TRUNC('hour', created_at) as hour,
  COUNT(*) as total,
  COUNT(CASE WHEN status = 'paid' THEN 1 END) as successful,
  ROUND(100.0 * COUNT(CASE WHEN status = 'paid' THEN 1 END) / COUNT(*), 2) as success_rate
FROM payments_paymentattempt
WHERE created_at > NOW() - INTERVAL 24 HOUR
GROUP BY 1
ORDER BY 1 DESC;
```

### Success Rate Target: > 99%
- [ ] First 6 hours: > 99%
- [ ] First 12 hours: > 99%
- [ ] Full 24 hours: > 99%

### Risk Scoring Validation
```sql
SELECT 
  risk_level,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM payments_paymentrisk), 2) as percent
FROM payments_paymentrisk
WHERE created_at > NOW() - INTERVAL 24 HOUR
GROUP BY risk_level;
```
- [ ] Risk distribution reasonable
- [ ] No excessive false positives
- [ ] Flagged payments in manual review queue

### Webhook Processing Validation
```sql
SELECT 
  status,
  COUNT(*) as count,
  ROUND(AVG(retry_count), 2) as avg_retries
FROM payments_webhookevent
WHERE created_at > NOW() - INTERVAL 24 HOUR
GROUP BY status;
```
- [ ] Most webhooks with status='processed'
- [ ] Few retries needed (< 5%)
- [ ] No stuck webhooks

### Idempotency Validation
```sql
SELECT 
  COUNT(DISTINCT idempotency_key) as unique_keys,
  COUNT(*) as total_attempts,
  COUNT(*) - COUNT(DISTINCT idempotency_key) as duplicates_prevented
FROM payments_paymentattempt
WHERE created_at > NOW() - INTERVAL 24 HOUR;
```
- [ ] Duplicate prevention active (duplicates_prevented > 0)
- [ ] No false positives (success rate = 100% for deduplicated)

### Team Sign-Off
- [ ] Developer: "Code review passed"
- [ ] QA: "All tests passed"
- [ ] DevOps: "Metrics normal"
- [ ] Security: "Security validation passed"
- [ ] Product: "User experience normal"

---

## 🚀 Production Deployment (0.5 Day)

### Pre-Deployment (30 min)
- [ ] All staging validations passed ✓
- [ ] Staging metrics show > 99% success rate ✓
- [ ] All team members notified
- [ ] Backup of production database created
- [ ] Rollback plan documented

### Deployment Steps (15 min)
```bash
# 1. Merge code to main branch
git merge payment-security-hardening

# 2. Pull latest code
git pull origin main

# 3. Run migration on production
python manage.py migrate payments --settings=config.pro_settings

# 4. Configure webhook secrets (if not auto-loaded from environment)
python manage.py shell < scripts/configure_payment_secrets.py

# 5. Restart application server (with zero-downtime strategy)
./deploy.sh payments-security
```
- [ ] Code merged to main
- [ ] Migration applied (no errors)
- [ ] Webhook secrets configured
- [ ] Application restarted
- [ ] Health check passed

### Post-Deployment Validation (15 min)
```bash
# 1. Verify migration applied
python manage.py showmigrations payments

# 2. Check application health
curl http://production/api/health/

# 3. Monitor logs for errors
tail -f logs/payment_security.log
tail -f logs/django.log

# 4. Check metrics dashboard
# Navigate to: https://monitoring.wasla.com/dashboard/payments
```
- [ ] No errors in application logs
- [ ] Health check returning 200
- [ ] Metrics dashboard showing data

### Monitoring (Continuous - Next 24 hours)
- [ ] Success rate > 99% (check every hour)
- [ ] No unexpected errors in logs
- [ ] Webhook processing normal
- [ ] Risk scoring reasonable
- [ ] No customer complaints
- [ ] All alerts configured and active

---

## 📋 Post-Deployment (Ongoing)

### Daily Checks (First Week)
```bash
# Check first thing each morning
./scripts/payment_security_status.sh

# Should show:
# ✓ Success Rate: 99.8%
# ✓ Webhook Processing: Normal
# ✓ Risk Distribution: Good
# ✓ No errors in logs
```
- [ ] Day 1: All metrics normal
- [ ] Day 2: All metrics normal
- [ ] Day 3: All metrics normal
- [ ] Day 4: All metrics normal
- [ ] Day 5: All metrics normal
- [ ] Day 6: All metrics normal
- [ ] Day 7: All metrics normal

### Weekly Checks (First Month)
- [ ] Success rate > 99%
- [ ] Risk scoring reasonable
- [ ] No security issues reported
- [ ] Payment webhook backlog < 100
- [ ] Customer support tickets (payments) < 5

### Monthly Metrics Review
- [ ] Success rate trend (should be stable or improving)
- [ ] Fraud detection effectiveness (false positive rate < 5%)
- [ ] Retry effectiveness (90%+ of retries successful)
- [ ] Duplicate prevention (should have prevented X chargebacks)
- [ ] Risk scoring calibration (need to tune thresholds?)

### Quarterly Security Review
- [ ] Webhook secrets rotated
- [ ] Security logs reviewed
- [ ] Audit trail integrity checked
- [ ] Compliance checklist verified (PCI-DSS)
- [ ] Incident response procedure tested

---

## 🔧 Troubleshooting Quick Links

| Issue | Location |
|-------|----------|
| Webhook signature validation failing | [PAYMENT_SECURITY_DEPLOYMENT.md](docs/PAYMENT_SECURITY_DEPLOYMENT.md#webhook-signature-invalid) |
| Duplicate charges still occurring | [PAYMENT_SECURITY_DEPLOYMENT.md](docs/PAYMENT_SECURITY_DEPLOYMENT.md#idempotency-key-not-working) |
| High retry count | [PAYMENT_SECURITY_DEPLOYMENT.md](docs/PAYMENT_SECURITY_DEPLOYMENT.md#high-retry-count) |
| Risk scoring not triggering | [PAYMENT_SECURITY_DEPLOYMENT.md](docs/PAYMENT_SECURITY_DEPLOYMENT.md#risk-scoring-not-triggering) |

---

## 📞 Support Contacts

- **Technical Questions**: See [PAYMENT_SECURITY_README.md](../PAYMENT_SECURITY_README.md)
- **Integration Help**: See [PAYMENT_SECURITY_INTEGRATION.md](../PAYMENT_SECURITY_INTEGRATION.md)
- **Deployment Issues**: See [PAYMENT_SECURITY_DEPLOYMENT.md](docs/PAYMENT_SECURITY_DEPLOYMENT.md)
- **Architecture Questions**: See [docs/PAYMENT_SECURITY_ARCHITECTURE.md](docs/PAYMENT_SECURITY_ARCHITECTURE.md)

---

## ✅ Sign-Off

**Developer**: _________________ Date: _______

**QA Lead**: _________________ Date: _______

**DevOps Lead**: _________________ Date: _______

**Security Lead**: _________________ Date: _______

**Approved for Production**: _________________ Date: _______

---

**Estimated Total Time**:
- Pre-deployment review: 2 hours
- Staging deployment: 4 hours  
- Staging validation: 24 hours
- Production deployment: 1 hour
- Post-deployment monitoring: 8 hours (next 24 hours)
- **Total: ~40 hours (spread over 3-4 days)**

**Questions?** See [PAYMENT_SECURITY_INDEX.md](../PAYMENT_SECURITY_INDEX.md) for complete file index.
