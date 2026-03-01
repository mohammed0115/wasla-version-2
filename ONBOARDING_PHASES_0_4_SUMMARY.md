# ONBOARDING FLOW - PHASES 0-4 IMPLEMENTATION SUMMARY

**Status:** ✅ PHASES 0-2 COMPLETE, PHASE 4 COMPLETE  
**Date:** 2026-03-01

## PHASE 0 ✅ - Audit & Discovery

**FILE:** `ONBOARDING_PHASE_0_COMPLETE_AUDIT.md` (235 lines)

- Mapped all existing models (SubscriptionPlan, Subscription, Store, StoreDomain, Payment models)
- Verified middleware ordering (Auth before TenantSecurity)
- Identified integration points (PaymentOrchestrator, WebhookEvent, Theme/StoreBranding)
- Documented reserved subdomains and validation rules
- Created comprehensive file inventory

---

## PHASE 1 ✅ - Data Model Additions

### Files Modified

#### 1. `wasla/apps/stores/models.py`
**Changes:**
- Added import: `from apps.subscriptions.models_billing import Subscription`
- Added PAYMENT_METHOD constants:
  - `PAYMENT_METHOD_STRIPE = "stripe"`
  - `PAYMENT_METHOD_TAP = "tap"`
  - `PAYMENT_METHOD_MANUAL = "manual"`
- Added `PAYMENT_METHOD_CHOICES` list
- Fixed Store.subscription FK to use direct import (not lazy string)
- Added `payment_method` CharField with choices

**Migration:** `0004_store_add_payment_method_field.py`

#### 2. `wasla/apps/payments/models.py`
**Changes:**
- Added imports: `from django.conf import settings`, `from django.utils import timezone`
- Created new **ManualPayment model** with:
  - `store` FK → Store (CASCADE)
  - `plan` FK → SubscriptionPlan (PROTECT)
  - `amount, currency` for tracking payment amount
  - `reference, receipt_file, notes_user` for customer submission
  - `status` with choices: PENDING, APPROVED, REJECTED
  - `reviewed_at, reviewed_by, notes_admin` for admin tracking
  - Methods: `approve(approved_by)`, `reject(rejected_by, reason)`
  - Meta: ordering by `-created_at`, indexes on (store, status) and (status, created_at)

**Migration:** `0016_manualpayment_model.py`

#### 3. `wasla/apps/tenants/services/domain_resolution.py`
**Changes:**
- Added **subdomain validation function** `validate_subdomain(subdomain)`
  - Validates format: lowercase a-z, 0-9, hyphen, 3-30 chars
  - Prevents starts/ends with hyphen
  - Deny reserved names: www, admin, api, static, media, mail, billing, etc. (20 reserved)
  - Check uniqueness in StoreDomain table (case-insensitive)
  - Returns: `(is_valid bool, error_message str)`

---

## PHASE 2 ✅ - Web Flow Endpoints & Forms

### Files Created

#### 1. `wasla/apps/subscriptions/forms_onboarding.py` (NEW)
**Form Classes:**
- **PlanSelectForm**: RadioSelect widget over active SubscriptionPlan objects, ordered by is_free then price
- **SubdomainSelectForm**: CharField with custom validation using `validate_subdomain()`, cleaned to lowercase
- **PaymentMethodSelectForm**: RadioSelect with choices (stripe, tap, manual)
- **ManualPaymentUploadForm**: Fields for reference, receipt_file (optional), notes

#### 2. `wasla/apps/subscriptions/views/onboarding.py` (NEW)
**Views:**

1. **onboarding_plan_select** (GET/POST)
   - Display available plans as radio options
   - Store `plan_id` in session
   - Redirect to subdomain selection

2. **onboarding_subdomain_select** (GET/POST)
   - Verify plan was selected
   - Display subdomain form
   - Validate using `validate_subdomain()`
   - If FREE: skip to checkout
   - If PAID: go to payment method selection

3. **onboarding_payment_method** (GET/POST) 
   - PAID plans only
   - Show 3 payment options: Stripe, Tap, Manual
   - Store selection in session

4. **onboarding_checkout** (GET/POST)
   - Show summary: plan, subdomain, payment method
   - POST executes: `_execute_onboarding_checkout()`
   - Atomic transaction:
     - Create Tenant
     - Create Store (status=ACTIVE if FREE, PENDING_PAYMENT if PAID)
     - Create StoreDomain
     - IF FREE: call `publish_default_storefront()` → redirect success
     - IF PAID: initiate provider payment (Stripe/Tap) or redirect to manual payment form

5. **onboarding_manual_payment** (GET/POST)
   - For PAID plans with MANUAL payment method
   - Display bank transfer details (hardcoded placeholder)
   - Form to submit reference + receipt file + notes
   - Create ManualPayment record with status=PENDING
   - Await admin review

6. **onboarding_success** (GET)
   - Display success message
   - Show store info (name, URL, plan, status)
   - Links to store and dashboard

#### 3. URL Configuration Update
**File:** `wasla/apps/subscriptions/urls_web.py`

**Imports Added:**
```python
from .views.onboarding import (
    onboarding_plan_select,
    onboarding_subdomain_select,
    onboarding_payment_method,
    onboarding_checkout,
    onboarding_manual_payment,
    onboarding_success,
)
```

**Routes Added:**
```
/billing/onboarding/plan/          → onboarding_plan_select
/billing/onboarding/subdomain/     → onboarding_subdomain_select
/billing/onboarding/payment-method/ → onboarding_payment_method
/billing/onboarding/checkout/      → onboarding_checkout
/billing/onboarding/manual-payment/ → onboarding_manual_payment
/billing/onboarding/success/       → onboarding_success
```

**Changed:** `app_name` from `'subscriptions'` to `'subscriptions_web'`

#### 4. HTML Templates (NEW)
All templates located in `wasla/apps/subscriptions/templates/subscriptions/onboarding/`

- **plan_select.html** - Plan selection with progress indicator (Step 1/4)
- **subdomain_select.html** - Subdomain input with live validation (Step 2/4)
- **payment_method_select.html** - 3 payment option cards (Step 3/4)
- **checkout.html** - Order summary & confirmation (Step 4/4)
- **manual_payment.html** - Bank details + receipt submission form
- **success.html** - Confirmation with store details and next steps

---

## PHASE 4 ✅ - Publish Default Storefront Service

### File Created

**File:** `wasla/apps/storefront/services.py` (NEW)

**Function:** `publish_default_storefront(store: Store) -> bool`

**Behavior:**
- Idempotent: Returns False if already published
- Sets `store.is_default_published = True`
- Sets `store.default_published_at = timezone.now()`
- Saves store
- Attempts to create/activate default StoreBranding (assigns first active Theme)
- Returns True if newly published, False if already published
- Safe error handling: logs warnings but doesn't fail if theming unavailable

**Integration:**
- Called from `_execute_onboarding_checkout()` after store creation (FREE & PAID after payment)
- Safe to call multiple times (idempotent)
- No request/user dependencies

---

## PHASE 3 ⏳ - Payment Webhook Handlers (TODO)

**Not yet implemented:**

1. **Stripe Payment Integration**
   - Use existing PaymentOrchestrator.initiate_payment()
   - Create Stripe session, store session_id
   - Redirect user to Stripe checkout
   - Webhook handler: On success, activate store

2. **Tap Payment Integration**
   - Use existing Tap gateway
   - Create Tap invoice/charge
   - Redirect to Tap payment page
   - Webhook handler: On success, activate store

3. **Manual Payment Approval** (Admin action)
   - In Django admin, add action "Approve Manual Payment"
   - On approval: Mark ManualPayment.status=APPROVED, activate store

4. **Idempotent Webhook Processing**
   - Check WebhookEvent.provider_event_id before processing
   - Webhook handler logic:
     ```python
     def handle_payment_success_webhook(webhook_event):
         if WebhookEvent.objects.filter(provider_event_id=event_id).exists():
             return 200  # Already processed
         
         # First time seeing this event
         activation_service.activate_store_after_payment(store)
         publish_default_storefront(store)  # idempotent
         WebhookEvent.mark_processed(event_id)
         return 200
     ```

---

## PHASE 5 ⏳ - Middleware Guards (TODO)

**Not yet implemented:**

1. **Domain Resolution Guard**
   - In `apps/tenants/middleware.py`
   - Check store.status before serving storefront
   - If not ACTIVE: redirect to `/billing/payment-required/`
   - If not published: same redirect

2. **Storefront Guard**
   - Check `store.is_default_published` before displaying
   - Prevent access if PENDING_PAYMENT or not published

3. **Safe Request.User Handling**
   - Verify already fixed: all code uses `getattr(request, 'user', None)`
   - AuthenticationMiddleware already runs before TenantSecurityMiddleware

---

## PHASE 6 ⏳ - Tests (TODO)

**Not yet implemented:**

Test suite to cover:

1. **FREE Plan Flow**
   - Select plan → select subdomain → store created ACTIVE → published → redirect success

2. **PAID Plan - Manual**
   - Select plan → select subdomain → select manual → submit receipt → PENDING_PAYMENT
   - Admin approves → store ACTIVE → published

3. **PAID Plan - Stripe** (when implemented)
   - Select plan → select subdomain → select stripe → create session → redirect checkout
   - Webhook: payment success → store ACTIVE → published

4. **Validations**
   - Invalid subdomain rejected
   - Duplicate subdomain rejected
   - Reserved subdomains rejected

5. **Idempotency**
   - Double webhook processing ignored
   - publish_default_storefront() called multiple times: only first succeeds

---

## MIGRATION STATUS

### Created:
- `stores/migrations/0004_store_add_payment_method_field.py`
- `payments/migrations/0016_manualpayment_model.py`

### Apply:
```bash
python manage.py migrate stores payments
```

---

## TESTING

### Run all tests:
```bash
python manage.py test apps.subscriptions.views.test_onboarding
```

### Manual testing:
1. Navigate to `/billing/onboarding/plan/`
2. Select a plan
3. Enter subdomain
4. (If PAID) select payment method
5. Review and click proceed
6. Observe store creation

---

## CURRENT BLOCKERS

1. **Stripe Integration:** Needs PaymentOrchestrator integration (Phase 3)
2. **Tap Integration:** Needs existing Tap gateway usage (Phase 3)
3. **Admin Manual Payment Approval:** Needs Django admin action (Phase 3)
4. **Webhook Handlers:** Phase 3 implementation incomplete
5. **Middleware Guards:** Phase 5 not yet implemented

---

## API CONTRACTS (Ready for Phase 3)

### Function Signatures Used in Views

```python
# Domain validation
validate_subdomain(subdomain: str) -> tuple[bool, str]

# Publishing
publish_default_storefront(store: Store) -> bool

# Models
Store.objects.create(...)  # status, payment_method, subscription
ManualPayment.objects.create(...)  # store, plan, amount, reference
```

---

## DEPLOYMENT CHECKLIST

- [ ] Run all migrations
- [ ] Verify `manage.py check` passes
- [ ] Verify server starts without errors
- [ ] Test onboarding flow end-to-end
- [ ] Implement Phase 3 (webhooks)
- [ ] Implement Phase 5 (guards)
- [ ] Run comprehensive test suite
- [ ] Deploy to staging
- [ ] Smoke test in staging
- [ ] Deploy to production

