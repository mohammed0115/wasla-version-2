# Merchant Journey QA Checklist (Wasla)

Date: 2026-02-23

## Prereqs
- Run migrations: `python manage.py migrate`
- Seed demo: `python manage.py seed_wasla_demo`
- Start server: `python manage.py runserver`
- Base domain (local): `127.0.0.1.nip.io`

Demo credentials (from seed output):
- Admin: `admin / admin12345`
- Merchant: `merchant / merchant12345`

---

## DO-1: Merchant can complete onboarding and create store
1) Login merchant at `http://127.0.0.1:8000/auth/`
2) Expected: redirected to onboarding (if not completed) or store setup
3) Visit `http://127.0.0.1:8000/dashboard/setup`
4) Fill store name + slug → Save
5) Expected: Store created, step advances to payment/shipping setup

## DO-2: After store creation, merchant is forced to select a plan (if none)
1) Ensure no subscription exists for the tenant (DB check)
2) Go to `http://127.0.0.1:8000/dashboard/`
3) Expected: redirect to `http://127.0.0.1:8000/persona/plans/` (plan selection)

## DO-3: Plans list reflects DB changes immediately
1) Update plan in Django Admin:
   - `http://127.0.0.1:8000/admin/subscriptions/subscriptionplan/`
2) Change plan name/price/features, save
3) Visit `http://127.0.0.1:8000/persona/plans/`
4) Expected: UI shows updated plan data from DB

## DO-4: Plan selected but unpaid → Payment Required page
1) Choose a paid plan in `http://127.0.0.1:8000/persona/plans/`
2) Ensure subscription status is `pending`
3) Visit `http://127.0.0.1:8000/dashboard/`
4) Expected: `Payment required` page (no raw 403)

## DO-5: Admin records payment → subscription active
1) Login admin portal: `http://127.0.0.1:8000/admin-portal/login/`
2) Go to Manual Payments: `http://127.0.0.1:8000/admin-portal/payments/manual/`
3) Click **New Manual Payment**
4) Select tenant + plan, amount, status=paid → Save
5) Expected: Payment transaction appears in list
6) DB check:
   - `StoreSubscription.status = active`
   - `PaymentTransaction.status = paid`

## DO-6: Pending activation page
1) With active subscription but not published, visit:
   - `http://127.0.0.1:8000/dashboard/`
2) Expected: `Pending activation` page (no raw 403)

## DO-7: Admin activates/publishes store
1) Admin portal → Tenants → Tenant Detail
2) Click **Publish**
3) Expected:
   - `Tenant.is_published = True`
   - `Tenant.activated_at` set
   - `Tenant.activated_by` set
   - Store status updated to `active`
4) Merchant dashboard becomes accessible

## DO-8: Storefront opens on subdomain (nip.io)
1) Visit `http://store1.127.0.0.1.nip.io:8000/storefront`
2) Expected: Storefront home renders (not 404)

## DO-9: Feature gating shows Upgrade Required
1) Remove `custom_domain` feature from plan
2) Visit `http://127.0.0.1:8000/dashboard/domains`
3) Expected: Upgrade Required page (HTTP 200, no raw 403)

## DO-10: Domain mapping uses store_id/merchant_id (no re-ask name)
1) Go to `http://127.0.0.1:8000/dashboard/domains`
2) Add a domain
3) Expected:
   - Domain saved linked to tenant
   - No prompt for merchant/store name

## DO-11: Friendly “Store not found”
1) Visit `http://missingstore.127.0.0.1.nip.io:8000/storefront`
2) Expected: Friendly 404 page (no raw Django debug)

## DO-12: Provide QA validation file
- This file (`MERCHANT_JOURNEY_QA.md`) must exist and be up to date.

---

## Extra checks (recommended)
- `http://127.0.0.1:8000/dashboard/domains` shows domain status + verification token path
- `http://127.0.0.1:8000/admin-portal/subscriptions/` lists subscriptions
- `http://127.0.0.1:8000/admin-portal/payments/manual/` lists manual payments
