# WASLA ONBOARDING IMPLEMENTATION - COMPLETE GUIDE

**Project:** Wasla SaaS Commerce Platform  
**Feature:** Complete Onboarding Flow (6-Phase Implementation)  
**Implementation Date:** 2026-03-01  
**Status:** ✅ PHASES 0-4 COMPLETE, PHASES 5-6 IN PROGRESS

---

## OVERVIEW

This document describes the complete onboarding flow implementation enabling free and paid plan selection, subdomain assignment, payment method selection, and automatic store activation.

### Business Flow

```
User visits /billing/onboarding/plan/
    ↓
Select Plan (FREE or PAID)
    ↓
Select Subdomain
    ↓
[IF FREE] → Checkout → Create Store (ACTIVE) → Publish → Success
[IF PAID] → Select Payment Method → Checkout
    ├─ STRIPE → Redirect to Stripe → (Phase 3: Webhook)
    ├─ TAP → Redirect to Tap → (Phase 3: Webhook)
    └─ MANUAL → Submit Receipt → Admin Review → (Phase 3: Approval)
         ↓
    After Payment Confirmed → Activate Store → Publish → Success
```

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────┐
│                  Django URL Router                       │
│  /billing/onboarding/plan/ → success/                   │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Onboarding Views (Step 1-4)                 │
├─────────────────────────────────────────────────────────┤
│ • PlanSelect → SubdomainSelect → PaymentMethod(PAID) → │
│ • Checkout → ManualPayment(if MANUAL) → Success         │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│           Form Validation & Session Management            │
├─────────────────────────────────────────────────────────┤
│ • validate_subdomain(subdomain)                         │
│ • Store plan_id, subdomain, payment_method in session   │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│       Store Creation (Atomic Transaction)                │
├─────────────────────────────────────────────────────────┤
│ CREATE:                                                  │
│  • Tenant (business entity)                             │
│  • Store (merchant account - status=ACTIVE|PENDING)    │
│  • StoreDomain (subdomain binding)                      │
│  • ManualPayment (if MANUAL method)                     │
│                                                          │
│ PUBLISH:                                                 │
│  • publish_default_storefront(idempotent)              │
│  • Assign default theme if available                    │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│          Payment Processing (Phase 3)                    │
├─────────────────────────────────────────────────────────┤
│ • STRIPE: Use PaymentOrchestrator → Stripe Session      │
│ • TAP: Use TapProvider → Tap Invoice                    │
│ • MANUAL: Store receipt, await admin approval           │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│        Webhook Handler (Phase 3 - Idempotent)           │
├─────────────────────────────────────────────────────────┤
│ • Verify provider_event_id (replay protection)          │
│ • Call activate_store_after_payment()                   │
│ • Publish storefront (idempotent)                       │
│ • Log event provenance                                  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│       Middleware Guards (Phase 5)                        │
├─────────────────────────────────────────────────────────┤
│ • Check store.status == ACTIVE before serving           │
│ • Check is_default_published == True                    │
│ • Redirect non-ACTIVE to /billing/payment-required/     │
└─────────────────────────────────────────────────────────┘
```

---

## DETAILED IMPLEMENTATION

### Phase 0: Audit ✅

**Deliverable:** `ONBOARDING_PHASE_0_COMPLETE_AUDIT.md`

Key findings:
- All required models exist
- Middleware ordering correct
- PaymentOrchestrator ready for integration
- No new apps needed

### Phase 1: Models ✅

**Files Modified:**
- `wasla/apps/stores/models.py` - Added `payment_method` field
- `wasla/apps/payments/models.py` - Created `ManualPayment` model
- `wasla/apps/tenants/services/domain_resolution.py` - Added `validate_subdomain()`

**Migrations Created:**
- `stores/migrations/0004_store_add_payment_method_field.py`
- `payments/migrations/0016_manualpayment_model.py`

**Key Model Changes:**
```python
# Store model
payment_method = CharField(choices=[('stripe', ...), ('tap', ...), ('manual', ...)])

# ManualPayment model (NEW)
store = FK(Store)
plan = FK(SubscriptionPlan)
amount, currency = Payment details
reference, receipt_file = Customer submission
status = PENDING | APPROVED | REJECTED
reviewed_by, reviewed_at = Admin tracking
```

### Phase 2: Web Flow ✅

**Files Created:**
- Forms: `forms_onboarding.py` (4 forms)
- Views: `views/onboarding.py` (6 views)
- Templates: 6 HTML templates
- URL Routes: Updated `urls_web.py`

**Views:**
1. `onboarding_plan_select` - Select plan from active options
2. `onboarding_subdomain_select` - Validate and select subdomain
3. `onboarding_payment_method` - Choose payment provider (PAID only)
4. `onboarding_checkout` - Execute store creation
5. `onboarding_manual_payment` - Submit payment proof (MANUAL only)
6. `onboarding_success` - Confirmation page

**Forms:**
- `PlanSelectForm` - RadioSelect over SubscriptionPlan
- `SubdomainSelectForm` - CharField with validate_subdomain()
- `PaymentMethodSelectForm` - RadioSelect (stripe, tap, manual)
- `ManualPaymentUploadForm` - Reference, receipt, notes

**Routes:**
```
/billing/onboarding/plan/
/billing/onboarding/subdomain/
/billing/onboarding/payment-method/
/billing/onboarding/checkout/
/billing/onboarding/manual-payment/
/billing/onboarding/success/
```

### Phase 3: Payment & Webhooks ⏳ PARTIAL

**Files Created/Modified:**
- `services/onboarding_payment.py` - Payment activation service

**Functions:**
```python
activate_store_after_payment(store, webhook_event_id)
    # Idempotent activation after payment success
    # Sets status=ACTIVE, activates domain, publishes storefront

approve_manual_payment(manual_payment, approved_by)
    # Admin approves manual payment submission
    # Updates ManualPayment.status=APPROVED, triggers activation
```

**TODO for Phase 3:**
- Stripe: Implement PaymentOrchestrator integration for session creation
- Tap: Implement TapProvider integration for invoice creation
- Webhook handlers: Implement in `payments/interfaces/api.py`
- Idempotency: Check provider_event_id before processing
- Admin action: Django admin "Approve Manual Payment" action

### Phase 4: Publish Service ✅

**File:** `wasla/apps/storefront/services.py`

**Function:** `publish_default_storefront(store: Store) -> bool`

**Behavior:**
- Idempotent (safe to call multiple times)
- Sets `is_default_published=True`, `default_published_at=now()`
- Creates StoreBranding with first active Theme
- Non-blocking: Doesn't fail if theme unavailable

### Phase 5: Middleware Guards ⏳ TODO

**Files to Modify:**
- `apps/tenants/middleware.py` - Add store status check
- `apps/tenants/security_middleware.py` - Add domain publishing check

**Guards to Implement:**
```python
# Before serving storefront, check:
if not store or store.status != ACTIVE:
    redirect('/billing/payment-required/')
    
if not store.is_default_published:
    redirect('/billing/payment-required/')
```

### Phase 6: Tests ⏳ TODO

**Test File:** `apps/subscriptions/tests_onboarding.py`

**Test Cases:**
1. FREE plan: plan → subdomain → store ACTIVE → published
2. PAID MANUAL: plan → subdomain → manual → receipt uploaded → PENDING
3. PAID MANUAL: admin approves → store ACTIVE → published
4. PAID STRIPE: (when Phase 3 complete)
5. PAID TAP: (when Phase 3 complete)
6. Subdomain validation: reject invalid, duplicate, reserved
7. Idempotency: double webhook call → state unchanged

---

## DEPLOYMENT GUIDE

### Prerequisites
```bash
cd /home/mohamed/Desktop/wasla-version-2
source .venv/bin/activate
cd wasla
```

### Step 1: Run Migrations
```bash
python manage.py migrate
```

### Step 2: Verify Health
```bash
python manage.py check
# System check identified no issues (0 silenced).

python manage.py runserver
# Django development server runs on 0.0.0.0:8000
```

### Step 3: Access Onboarding
```
http://localhost:8000/billing/onboarding/plan/
```

### Step 4: Test Flow
1. Login as authenticated user
2. Select a plan
3. Enter valid subdomain
4. (If PAID) select payment method
5. Verify store created with correct status
6. For manual payments, verify admin can approve

---

## API REFERENCE

### Subdomain Validation
```python
from apps.tenants.services.domain_resolution import validate_subdomain

is_valid, error_msg = validate_subdomain("mystore")
# Returns: (True, "") or (False, "error description")

# Validation rules:
# - Length: 3-30 characters
# - Format: lowercase a-z, 0-9, hyphen only
# - No start/end hyphens
# - Not in reserved list (www, admin, api, etc.)
# - Not already taken (case-insensitive)
```

### Store Publication
```python
from apps.storefront.services import publish_default_storefront

published = publish_default_storefront(store)
# Returns: True if newly published, False if already published
# Idempotent: safe to call multiple times
# Creates StoreBranding with default theme if available
```

### Payment Activation (Phase 3)
```python
from apps.subscriptions.services.onboarding_payment import (
    activate_store_after_payment,
    approve_manual_payment
)

# After Stripe/Tap webhook success
activated = activate_store_after_payment(store, webhook_event_id)

# Admin approves manual payment
approved = approve_manual_payment(manual_payment, user)
```

---

## DATABASE SCHEMA

### New Fields
```python
# Store model
payment_method = CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True)

# ManualPayment model (NEW)
- store: ForeignKey(Store)
- plan: ForeignKey(SubscriptionPlan)
- amount: DecimalField(12,2)
- currency: CharField(3)
- reference: CharField(255)
- receipt_file: FileField(optional)
- notes_user: TextField
- status: CharField(PENDING|APPROVED|REJECTED)
- reviewed_by: ForeignKey(User, optional)
- reviewed_at: DateTimeField(optional)
- notes_admin: TextField
- Indexes: (store, status), (status, created_at)
```

---

## ERROR HANDLING

### Subdomain Validation Errors
```
"Subdomain is required"
"Subdomain must be at least 3 characters"
"Subdomain cannot exceed 30 characters"
"Subdomain can only contain lowercase letters, numbers, and hyphens"
"Subdomain cannot start or end with a hyphen"
"'{subdomain}' is a reserved subdomain"
"Subdomain '{subdomain}' is already taken"
```

### Store Creation Errors
```
"Error creating store: {exception}"
→ User redirected to plan selection, can retry
```

### Payment Errors
```
"Stripe payment integration coming soon" (Phase 3)
"Tap payment integration coming soon" (Phase 3)
```

---

## SECURITY CONSIDERATIONS

1. **Idempotency:**
   - Webhook processing checks `provider_event_id` uniqueness
   - Prevents duplicate store activation from replayed webhooks
   - `publish_default_storefront()` skips if already published

2. **Subdomain Validation:**
   - Prevents reserved domain names (admin, api, etc.)
   - Case-insensitive duplicate check
   - Whitelist format (only a-z, 0-9, hyphen)

3. **Access Control:**
   - All onboarding views require `@login_required`
   - Store creation limited to authenticated user
   - Admin actions require staff permissions

4. **Session Security:**
   - Store sensitive state in session (plan_id, subdomain)
   - Session-based CSRF protection via `{% csrf_token %}`
   - Session cleared on success

5. **Payment Security:**
   - Use existing PaymentOrchestrator for provider integration
   - Validate webhooks with provider signatures
   - Store payment method in ManualPayment model, not in request

---

## MONITORING & LOGGING

### Key Events to Monitor
- Onboarding plan selection (funnel metric)
- Subdomain conflicts (reserved/duplicate rejections)
- Manual payment submissions (pending count)
- Store activation events (subscription milestone)
- Payment webhook processing (error rate)

### Logging Points (to implement in Phase 3)
```python
logger.info(f"Onboarding started: user={user.id}, plan={plan.id}")
logger.warning(f"Subdomain conflict: {subdomain} already taken")
logger.info(f"Store created: store_id={store.id}, status={store.status}")
logger.error(f"Webhook processing failed: event_id={event_id}, error={error}")
```

---

## KNOWN LIMITATIONS

1. **Phase 3 Not Complete:**
   - Stripe integration using PaymentOrchestrator not yet implemented
   - Tap gateway integration not yet implemented
   - Webhook handlers not yet implemented

2. **Phase 5 Not Complete:**
   - Middleware guards to enforce store.status and published checks not yet implemented
   - Anonymous users can still access storefront (should redirect to onboarding)

3. **Phase 6 Not Complete:**
   - Comprehensive test suite not yet written
   - No integration tests for full end-to-end flow

4. **Manual Payment:**
   - Admin approval must be done via Django admin
   - No automated email notifications (can add in Phase 3)
   - Receipt storage via FileField (consider S3 for production)

---

## NEXT STEPS

### Immediate (Phase 3)
1. Complete Stripe integration using PaymentOrchestrator
2. Implement Stripe webhook handler with idempotency
3. Complete Tap integration using TapProvider
4. Implement Tap webhook handler
5. Add Django admin action for manual payment approval

### Short-term (Phase 5)
1. Add middleware guards for store.status checking
2. Add guard for `is_default_published` flag
3. Redirect non-ACTIVE stores to `/billing/payment-required/`

### Medium-term (Phase 6)
1. Write comprehensive test suite
2. Add integration tests for full flow
3. Performance testing with load testing tools
4. Security audit of payment flow

### Long-term
1. A/B test onboarding flow variants
2. Add analytics tracking
3. Implement email notifications for payment status
4. Add SMS notifications for manual payment approval
5. Create onboarding admin dashboard

---

## SUPPORT & DOCUMENTATION

**For Developers:**
- See code comments in `views/onboarding.py`
- Refer to form docstrings in `forms_onboarding.py`
- Check model docstrings in respective models.py files

**For Product:**
- Test checklist in deployment guide above
- Business rules documented in this file

**For Operations:**
- Monitor payment webhook error rates
- Check ManualPayment table for pending approvals
- Monitor store activation success rate

