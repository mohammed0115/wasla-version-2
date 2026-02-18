# Emails Module | موديول البريد (Emails)

**AR:** طبقة بريد مرنة (Tenant-aware) لتسجيل الإرسال، دعم مزودين متعددين (SMTP/SendGrid/Mailgun)، ودعم إرسال async عبر Celery عند توفره.  
**EN:** A tenant-aware email layer with logging, multi-provider support (SMTP/SendGrid/Mailgun), and optional Celery async sending.

---

## Key models | أهم الجداول

**AR/EN (see `apps/emails/models.py`):**
- `GlobalEmailSettings` + audit log
- `TenantEmailSettings` (per tenant overrides)
- `EmailLog` (idempotency + status transitions)

---

## Provider resolution | اختيار مزود البريد

**AR/EN:** `apps/emails/application/services/provider_resolver.py::TenantEmailProviderResolver` resolves the active provider and builds the correct gateway adapter.

---

## Async sending | الإرسال غير المتزامن

**AR:** `apps/emails/tasks.py` يحاول استخدام Celery إن كان متاحًا وإلا يرسل بشكل synchronous.  
**EN:** `apps/emails/tasks.py` uses Celery when available; otherwise it falls back to synchronous sending.

---

## API | واجهة API

**AR/EN:** See `apps/emails/urls.py` and `apps/emails/interfaces/`.

