# Merchant Journey QA (Option C: Store Provisioning After Admin Approval)

Date: 2026-02-27

## 1) Located code paths (required summary)

- Tenant/store detection middleware:
   - `wasla/apps/tenants/middleware.py`
   - `wasla/apps/tenants/guards.py`
   - `wasla/apps/tenants/services/domain_resolution.py`
- Store model:
   - `wasla/apps/stores/models.py` (`Store`)
- Merchant model/context:
   - `wasla/apps/accounts/models.py` (`Profile`)
   - `wasla/apps/tenants/models.py` (`StoreProfile`, `TenantMembership`)
- Subscription / plans:
   - `wasla/apps/subscriptions/models.py` (`SubscriptionPlan`, `StoreSubscription`)
- Manual payment model:
   - `wasla/apps/subscriptions/models.py` (`PaymentTransaction`)
   - `wasla/apps/subscriptions/services/payment_transaction_service.py`
- Provisioning service (Option C):
   - `wasla/apps/tenants/services/provisioning.py` (`provision_store_after_payment`)
- Admin payment approval/actions:
   - `wasla/apps/admin_portal/views.py`
   - `wasla/apps/admin_portal/forms.py`
   - `wasla/apps/admin_portal/urls.py`
   - `wasla/templates/admin_portal/payment_transactions.html`
   - `wasla/apps/subscriptions/admin.py`

## 2) Merchant journey checklist

1. Register/Login merchant
2. Choose plan
3. Payment required page
4. Submit manual payment (pending)
5. Pending activation page
6. Admin approves payment
7. Store gets created automatically
8. Merchant dashboard loads
9. Subdomain works
10. Invalid subdomain shows friendly store-not-found page

## 3) URLs to test + expected status/page

- `GET /persona/plans/`
   - Expected: `200`, plan list from DB (`plans.html`)
- `GET /billing/payment-required/`
   - Expected: `200`, `dashboard/payment_required.html`
- `GET /billing/pending-activation/`
   - Expected: `200`, `dashboard/pending_activation.html`
- `GET /dashboard/` (merchant before approval)
   - Expected: redirect to `/billing/payment-required/` or `/billing/pending-activation/` (never raw `403`)
- `GET /store/create`
   - Expected: `200`, store profile setup page (tenant/profile only; no physical store yet)
- `POST /admin-portal/payments/transactions/<id>/approve-create-store/`
   - Expected: `302` back to transactions list, payment marked paid, store provisioned
- `GET /dashboard/` (after approval)
   - Expected: `200`, dashboard page
- `GET http://<store_slug>.w-sala.com/storefront`
   - Expected: storefront renders
- `GET http://invalid.w-sala.com/...`
   - Expected: `404` friendly `storefront/store_not_found.html`, no debug traceback

## 4) Local nip.io testing (required)

Use hostnames like:
- Valid store: `http://<store_slug>.127.0.0.1.nip.io:8000/storefront`
- Invalid store: `http://missing.127.0.0.1.nip.io:8000/storefront`

Expected behavior:
- Valid store subdomain resolves tenant/store and loads storefront.
- Invalid store subdomain renders friendly store-not-found page (no Django debug page).
- Merchant dashboard routes redirect to billing-friendly pages until approval provisions the store.

## 5) Categories + Pricing consistency checks

- Categories source is DB-backed in product flows:
   - `wasla/apps/catalog/forms.py` (`Category.objects.filter(store_id__in=[0, store_id])`)
   - `wasla/apps/catalog/services/category_service.py` (global category seed/read)
- Pricing plan UI is DB-backed and uses active plans:
   - `wasla/apps/accounts/persiona/views.py::persona_plans` (`SubscriptionPlan.objects.filter(is_active=True)`)
   - `wasla/templates/plans.html` (renders plans from context)
- Admin updates on `SubscriptionPlan` reflect immediately in plans page (no reseed overwrite if plans already exist).

## 6) Seed command

- Safe seed command available:
   - `python manage.py seed_wasla`
   - Optional demo provisioning: `python manage.py seed_wasla --with-demo-store`
