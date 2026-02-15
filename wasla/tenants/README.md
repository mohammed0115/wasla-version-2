# Tenants Module | موديول المتاجر/التعدد (Tenants)

**AR:** هذا الموديول هو قلب الـ multi‑tenancy: تحديد المتجر الحالي (`request.tenant`) + عضويات المتجر + إعدادات المتجر + معالج إعداد المتجر (Wizard).  
**EN:** This module is the multi-tenancy core: resolves the current tenant (`request.tenant`), manages memberships/settings, and provides the store setup wizard.

---

## Tenant resolution | تحديد المتجر

**AR/EN:** `apps/tenants/middleware.py::TenantMiddleware` resolves a tenant using:
1) Headers: `X-Tenant` / `X-Tenant-Id`  
2) Session: `store_id`  
3) Custom domain (`StoreDomain` ACTIVE) or legacy `Tenant.domain`  
4) Subdomain under `WASSLA_BASE_DOMAIN`  
5) (In `DEBUG=1`) querystring `?store_id=<id>`

Also: `TenantLocaleMiddleware` activates tenant default language before Django `LocaleMiddleware`.

---

## Key models | أهم الجداول

**AR/EN (see `apps/tenants/models.py`):**
- `Tenant`: يمثل المتجر/الـ tenant.
- `StoreDomain`: ربط الدومينات الخاصة (Custom Domains) مع حالة التحقق والـ SSL.
- `TenantMembership`: عضوية المستخدم داخل المتجر (Owner/Staff…).
- `StoreProfile`: إعدادات المتجر العامة + حالة الإعداد.
- `StorePaymentSettings`, `StoreShippingSettings`: إعدادات الدفع والشحن لكل متجر.

---

## Store setup wizard | معالج إعداد المتجر

**AR:**
يوجد تدفق إعداد تدريجي (Store info → Payment → Shipping → Activate).  
نقطة الدخول الأساسية (ويب): `apps/tenants/interfaces/web/views.py`.

**EN:**
There is a step-by-step setup flow (Store info → Payment → Shipping → Activate).  
Main web entrypoint: `apps/tenants/interfaces/web/views.py`.

---

## Notes | ملاحظات

**AR:** أي CRUD داخل بقية الموديولات يجب أن يحترم `request.tenant` (عزل البيانات).  
**EN:** Other apps must respect `request.tenant` to ensure tenant isolation.

---

## Tests | الاختبارات

Run:
`python manage.py test apps.tenants`
