# Payments Module | موديول المدفوعات (Payments)

**AR:** تسجيل ومعالجة المدفوعات المرتبطة بالطلبات (MVP).  
**EN:** Records and processes order payments (MVP).

---

## Key model | أهم جدول

**AR/EN:** `apps/payments/models.py::Payment`
- Links to `orders.Order`
- `status`: pending/success/failed
- Stores gateway reference if needed

---

## Services | الخدمات

**AR/EN:** `apps/payments/services/`:
- `payment_service.py`
- `gateway_service.py` (gateway abstraction placeholder)

---

## Enterprise hardening

- Idempotent charge protection via `PaymentAttempt.idempotency_key` (store+order scoped).
- Webhook security via HMAC SHA256 + timestamp replay tolerance.
- Retry and resilience for provider calls with exponential backoff.
- Risk scoring with flagged payments routed to admin review queue.
- Structured JSON logs for charge/webhook/retry/risk events.

## Webhook secret configuration

Set provider webhook secrets in `PaymentProviderSettings` per store/tenant:

- `webhook_secret`: shared secret from provider dashboard.
- `webhook_tolerance_seconds`: replay protection window (default `300`).
- `retry_max_attempts`: provider API retry limit (default `3`).

Example (Django shell):

```python
from apps.payments.models import PaymentProviderSettings

cfg = PaymentProviderSettings.objects.get(store_id=1, provider_code="stripe")
cfg.webhook_secret = "whsec_..."
cfg.webhook_tolerance_seconds = 300
cfg.retry_max_attempts = 3
cfg.save(update_fields=["webhook_secret", "webhook_tolerance_seconds", "retry_max_attempts"])
```

## API | واجهة API

**AR/EN:** See `apps/payments/interfaces/api/urls.py`.

