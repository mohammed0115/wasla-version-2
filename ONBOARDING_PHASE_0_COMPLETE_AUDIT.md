# ONBOARDING FLOW - PHASE 0 COMPLETE AUDIT

**Date:** 2026-03-01  
**Status:** ✅ COMPLETE  
**Phase:** Discovery & Architectural Planning

## EXECUTIVE SUMMARY

This document maps the existing Wasla codebase architecture for implementing the 6-phase onboarding flow. **No new apps required.** All necessary models, services, and patterns already exist.

### What Already Works
- ✅ SubscriptionPlan model with `is_free` flag
- ✅ Store model with `STATUS_PENDING_PAYMENT` & publication tracking
- ✅ StoreDomain model for subdomain management
- ✅ PaymentOrchestrator for multi-provider payment initiation
- ✅ WebhookEvent model with idempotency/replay protection
- ✅ Middleware stack properly ordered (Auth before tenant security)
- ✅ ConfirmPaymentWebhook use case for webhook handling
- ✅ Theme/StoreBranding models for default theming
- ✅ TenantSecurityMiddleware Django 5+ compatible

### What Needs Implementation
- ❌ Subdomain validation function (PHASE 1)
- ❌ Onboarding web flow endpoints (PHASE 2)
- ❌ Payment webhook integration for store activation (PHASE 3)
- ❌ `publish_default_storefront()` service (PHASE 4)
- ❌ Guards to block access to non-ACTIVE stores (PHASE 5)
- ❌ Comprehensive test suite (PHASE 6)

### KNOWN PRODUCTION BUGS (Fixed in this implementation)

1. **Bug:** "'TenantSecurityMiddleware' object has no attribute 'async_mode'"
   - **Root:** Django 5.2 expects `__init__(get_response)` + `__call__(request)` pattern
   - **Status:** ✅ VERIFIED FIXED - Middleware already uses correct pattern

2. **Bug:** "'WSGIRequest' object has no attribute 'user'" in security_middleware.py
   - **Root:** Accessing `request.user` before AuthenticationMiddleware runs
   - **Status:** ✅ VERIFIED FIXED - Code uses `getattr(request, 'user', None)` safely

3. **Bug:** "Store context required" for /billing/payment-required/
   - **Root:** Route expects tenant context but can't crash on missing store
   - **Status:** ⚠️ ADDRESSABLE - PHASE 2 will create graceful onboarding redirect

4. **Bug:** Missing prometheus_client → metrics endpoints crash
   - **Status:** ⏳ NO CHANGES NEEDED - Will add safe import guard if metrics called

---

## PART 1: EXISTING MODELS & FIELDS

### 1.1 SubscriptionPlan (apps/subscriptions/models.py)

**Location:** `apps/subscriptions/models.py`, lines 19-49

**Status:** ✅ HAS `is_free` FIELD (added in previous work)

```python
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(...)
    billing_cycle = models.CharField(...)
    is_free = models.BooleanField(default=False)  # ← KEY FOR ONBOARDING
    features = models.JSONField(...)
    max_products = models.PositiveIntegerField(...)
    max_orders_monthly = models.PositiveIntegerField(...)
    max_staff_users = models.PositiveIntegerField(...)
    is_active = models.BooleanField(default=True)
```

**Onboarding Usage:**
- `plan.is_free == True` → activate store immediately, publish default
- `plan.is_free == False` → require payment before activation

---

### 1.2 Store (apps/stores/models.py)

**Location:** `apps/stores/models.py`, lines 22-170

**Status:** ✅ HAS TRACKING FIELDS (added in previous work)

```python
class Store(models.Model):
    # Status states
    STATUS_DRAFT = "draft"
    STATUS_PENDING_PAYMENT = "pending_payment"  # ← NEW FOR ONBOARDING
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_SUSPENDED = "suspended"
    
    # Publication tracking
    is_default_published = models.BooleanField(default=False)      # ← NEW
    default_published_at = models.DateTimeField(...)               # ← NEW
    
    # Relationship to subscription
    subscription = models.OneToOneField(
        'subscriptions.models_billing.Subscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='store'
    )  # ← NEW (links to billing subscription)
```

**Onboarding Flow:**
1. User selects FREE plan → Store created with `status=ACTIVE`, `is_default_published=True`
2. User selects PAID plan → Store created with `status=PENDING_PAYMENT`, `is_default_published=False`
3. Payment webhook succeeds → Store `status=ACTIVE`, `is_default_published=True`
4. Cannot publish default if `status != ACTIVE` (guard in PHASE 5)

---

### 1.3 StoreDomain (apps/tenants/models.py)

**Location:** `apps/tenants/models.py`, lines 62-130

**Status:** ✅ HAS STORE REFERENCE (added in previous work)

```python
class StoreDomain(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    tenant = models.ForeignKey(Tenant, ...)
    store = models.ForeignKey(
        'stores.Store',
        null=True,
        blank=True,
        related_name='domains'
    )  # ← NEW FOR ONBOARDING
    
    status = models.CharField(
        choices=[("active", "Active"), ("inactive", "Inactive")],
        default="active"
    )
    is_primary = models.BooleanField(default=False)
    ssl_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Onboarding Usage:**
- Create StoreDomain in onboarding → links subdomain to store
- Domain becomes accessible once store is ACTIVE

---

### 1.4 Subscription (Full State Machine) (apps/subscriptions/models_billing.py)

**Location:** `apps/subscriptions/models_billing.py`

**Status:** ✅ EXISTS with full state machine

```python
class Subscription(models.Model):
    """Full lifecycle subscription with 6-state machine."""
    
    # States
    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_GRACE_PERIOD = "grace_period"
    STATUS_SUSPENDED = "suspended"
    STATUS_CANCELLED = "cancelled"
    
    status = models.CharField(...)
    provider_subscription_id = models.CharField(...)  # Stripe/Tap etc.
    next_billing_date = models.DateField(...)
```

**Onboarding Detail:**
- For PAID plans, Store.subscription points to this Subscription after payment
- Payment webhook handler updates Subscription status → which triggers Store activation

---

### 1.5 PaymentIntent (apps/payments/models.py)

**Location:** `apps/payments/models.py`, lines TBD

**Status:** ✅ EXISTS with idempotency tracking

```python
class PaymentIntent(models.Model):
    """Payment intent with provider-specific tracking."""
    
    order = models.ForeignKey(Order, ...)
    provider_code = models.CharField(...)  # "stripe", "tap", etc.
    provider_reference = models.CharField(...)
    status = models.CharField(choices=[...])
    amount = models.DecimalField(...)
    currency = models.CharField(...)
    idempotency_key = models.CharField(unique=True)
```

**Onboarding Detail:**
- For PAID plans, create PaymentIntent → initiate_payment() → get redirect URL

---

### 1.6 WebhookEvent (apps/payments/models.py)

**Location:** `apps/payments/models.py`, lines 210-287

**Status:** ✅ EXISTS with replay protection

```python
class WebhookEvent(models.Model):
    """Webhook with idempotency & replay protection."""
    
    provider_code = models.CharField(...)
    provider_event_id = models.CharField(unique=True)  # ← IDEMPOTENCY KEY
    webhook_timestamp = models.DateTimeField(...)
    signature = models.CharField(...)
    is_verified = models.BooleanField(default=False)
    payload_json = models.JSONField(...)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_payment_webhook_store_event",
                fields=["tenant_id", "provider_event_id"]
            )
        ]
```

**Onboarding Detail:**
- Payment webhook includes provider_event_id (e.g., Stripe event ID "evt_123...")
- Idempotent: Process same webhook multiple times → store activation only once

---

### 1.7 Tenant (apps/tenants/models.py)

**Location:** `apps/tenants/models.py`, lines 12-60

**Status:** ✅ EXISTS - Business entity housing store

```python
class Tenant(models.Model):
    """Multi-tenant business entity."""
    
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Onboarding Detail:**
- One Tenant per business/merchant
- Store → Tenant relationship (store has tenant_id FK)

---

### 1.8 Theme & StoreBranding (apps/themes/models.py)

**Location:** `apps/themes/models.py`

**Status:** ✅ EXISTS - For styling stores

```python
class Theme(models.Model):
    """Reusable theme template."""
    code = models.CharField(unique=True)
    name = models.CharField(...)
    is_active = models.BooleanField(default=True)
    # ... styling fields

class StoreBranding(models.Model):
    """Store-specific theme application."""
    store = models.OneToOneField(Store, ...)
    theme = models.ForeignKey(Theme, ...)
    primary_color = models.CharField(...)
    # ... customization fields
```

**Onboarding Detail:**
- `publish_default_storefront()` will create StoreBranding if not exists
- Assigns first active Theme as default for new stores

---

## PART 2: MIDDLEWARE STACK & ORDERING

**Location:** `wasla/config/settings.py`, lines 239-265

**Status:** ✅ CORRECTLY ORDERED

```
1.  SecurityMiddleware
2.  RateLimitMiddleware
3.  FriendlyErrorsMiddleware
4.  SessionMiddleware
5.  LocaleMiddleware
6.  CommonMiddleware
7.  CsrfViewMiddleware
8.  ▶ AuthenticationMiddleware ◀ (MUST BE HERE)
9.  SecurityHeadersMiddleware
10. RequestIdMiddleware
11. AdminPortalSecurityHeadersMiddleware
12. TenantResolverMiddleware        ◀ SAFE: Auth done
13. TenantMiddleware               ◀ SAFE: Auth done
14. TenantSecurityMiddleware       ◀ SAFE: Auth done, uses getattr(request.user)
15. TenantAuditMiddleware          ◀ SAFE
16. TenantLocaleMiddleware         ◀ SAFE
17. PerformanceMiddleware          ◀ SAFE
18. SecurityAuditMiddleware        ◀ SAFE
19. PermissionCacheMiddleware      ◀ SAFE
20. OnboardingFlowMiddleware       ◀ ← HOOKS USER STATE
21. MessageMiddleware
22. XFrameOptionsMiddleware
```

**Key Fix Applied:**
- AuthenticationMiddleware is position 8
- TenantSecurityMiddleware is position 14 (AFTER auth)
- Uses `getattr(request, 'user', None)` safely

---

## PART 3: EXISTING SERVICES & PATTERNS

### 3.1 PaymentOrchestrator (apps/payments/orchestrator.py)

**Location:** `apps/payments/orchestrator.py`, lines 1-80+

**Interface:**
```python
@staticmethod
@transaction.atomic
def initiate_payment(
    order: Order,
    provider_code: str,
    tenant_ctx: TenantContext,
    return_url: str,
) -> PaymentRedirect:
    """
    Initiates payment and returns redirect URL.
    
    Returns:
        PaymentRedirect: {
            'url': 'https://stripe.com/pay/...',
            'client_secret': 'pi_...',
            'provider_reference': '...'
        }
    """
```

**Onboarding Integration:**
- PHASE 3 will call this during PAID plan checkout
- Returns URL to redirect user to payment provider
- Webhook handler will confirm payment success

### 3.2 ConfirmPaymentWebhook (apps/payments/application/confirm_payment_webhook.py)

**Location:** `apps/payments/application/confirm_payment_webhook.py`

**Status:** ✅ EXISTS - Webhook confirmation handler

```python
class ConfirmPaymentWebhook(UseCase):
    """Confirms a payment ONLY from webhook (trusted path)."""
    
    def execute(self, payment_attempt, provider_reference: str):
        """Idempotent: safe to call multiple times."""
        # Updates payment status to CONFIRMED
        # Triggers completion callback
```

**Onboarding Integration:**
- PHASE 3 will extend this to call store activation
- Ensures idempotency via WebhookEvent.provider_event_id

### 3.3 TenantResolverMiddleware (apps/tenants/middleware.py)

**Location:** `apps/tenants/middleware.py`

**Responsibilities:**
- Extract subdomain from request hostname
- Resolve to Tenant
- Attach to `request.tenant`

**Onboarding Integration:**
- PHASE 1 subdomain validation ensures valid format
- PHASE 2 creates subdomains
- This middleware resolves them

---

## PART 4: EXISTING PATTERNS

### 4.1 UseCase Pattern (Clean Architecture)

**Used Throughout:** `apps/*/application/use_cases/` or `apps/*/application/`

```python
class MyUseCase:
    def execute(self, ...args):
        # Business logic here
        return result

# Usage:
usecase = MyUseCase()
result = usecase.execute(...)
```

**Onboarding Usage:**
- PHASE 2: Create `OnboardingService` following this pattern
- PHASE 4: Create `PublishDefaultStorefrontUseCase`

### 4.2 Form Validation Pattern

**Pattern:** Django ModelForms or form validation in views

**Onboarding Usage:**
- PHASE 1: Subdomain validation function in `tenants/services/domain_resolution.py`
- PHASE 2: Use Django Form for subdomain input validation

### 4.3 Transaction Safety

**Pattern:** `@transaction.atomic` decorator

**Existing Example:** PaymentOrchestrator uses it

**Onboarding Usage:**
- PHASE 2: Wrap store + domain creation in atomic transaction
- PHASE 3: Wrap webhook handler in atomic transaction

### 4.4 Webhook Idempotency

**Pattern:** Check WebhookEvent.provider_event_id before processing

**Existing Example:** WebhookEvent model has unique constraint on provider_event_id

**Onboarding Usage:**
- PHASE 3: Webhook handler checks `WebhookEvent.provider_event_id` before activation

---

## PART 5: ROUTES & URL PATTERNS

### Current Routes (Existing)

| Path | App | Purpose |
|------|-----|---------|
| `/admin/` | Django admin | Admin portal |
| `/api/auth/` | accounts | Login/signup |
| `/api/v1/orders/` | orders | Order API |
| `/dashboard/` | merchant | Merchant dashboard |
| `/billing/` | payments | Billing portal |
| `/admin-portal/` | admin_portal | Admin dashboard |
| `/static/`, `/media/` | Django | Assets |

### NEW Routes for Onboarding (PHASE 2)

| Path | Method | Purpose | Status |
|------|--------|---------|--------|
| `/onboarding/plan/` | GET | Show available plans | TODO |
| `/onboarding/plan/` | POST | Select plan, save to session | TODO |
| `/onboarding/subdomain/` | GET | Show subdomain form | TODO |
| `/onboarding/subdomain/` | POST | Validate & save subdomain | TODO |
| `/onboarding/checkout/` | GET | Show payment confirmation (PAID only) | TODO |
| `/onboarding/checkout/` | POST | Initiate payment (PAID) or activate store (FREE) | TODO |
| `/onboarding/success/` | GET | Onboarding complete, redirect to dashboard | TODO |

---

## PART 6: IMPLEMENTATION PLAN

### PHASE 1: Subdomain Validation (Single Function)

**File:** `wasla/apps/tenants/services/domain_resolution.py`

**Function to Add:**
```python
def validate_subdomain(subdomain: str) -> tuple[bool, str]:
    """
    Validate subdomain format and uniqueness.
    
    Returns:
        (is_valid, error_message)
    """
    # Validations:
    # - lowercase a-z, 0-9, hyphen only
    # - length 3-30
    # - cannot start/end with hyphen
    # - not in reserved list
    # - not already taken (case-insensitive check in StoreDomain)
```

**Files to Modify:** 1 file
- `wasla/apps/tenants/services/domain_resolution.py`

---

### PHASE 2: Web Flow Endpoints

**Files to Create/Modify:**
1. `wasla/apps/subscriptions/views/onboarding_views.py` (NEW)
2. `wasla/apps/subscriptions/templates/subscriptions/plan_select.html` (NEW)
3. `wasla/apps/subscriptions/templates/subscriptions/subdomain_select.html` (NEW)
4. `wasla/apps/subscriptions/templates/subscriptions/checkout.html` (NEW)
5. `wasla/config/urls.py` (MODIFY - add onboarding routes)

**Views to Create:**
- `PlanSelectView` (GET/POST)
- `SubdomainSelectView` (GET/POST)
- `CheckoutView` (GET/POST)
- `OnboardingSuccessView` (GET)

---

### PHASE 3: Payment Webhook Integration

**Files to Modify:**
1. `wasla/apps/payments/application/confirm_payment_webhook.py` (MODIFY)
2. `wasla/apps/payments/webhooks.py` or new handler (MODIFY/CREATE)

**Logic to Add:**
- On payment success webhook:
  - Confirm/activate Store.subscription
  - Set Store.status = ACTIVE
  - Call `publish_default_storefront(store)`
  - Mark StoreDomain as ACTIVE

---

### PHASE 4: Publish Default Storefront Service

**Files to Create:**
1. `wasla/apps/storefront/services.py` (NEW) OR extend existing
2. Add `publish_default_storefront(store)` function

**Logic:**
- Create StoreBranding if not exists (assign first active Theme)
- Set store.is_default_published = True
- Set store.default_published_at = now()
- Idempotent: return early if already published

---

### PHASE 5: Guards & Middleware

**Files to Modify:**
1. `wasla/apps/tenants/middleware.py` (ADD guard)
2. `wasla/apps/tenants/security_middleware.py` (ADD store status check)

**Logic:**
- Before serving storefront: check store.status == ACTIVE && is_default_published == True
- If missing: redirect to `/onboarding/` with clear message
- If not ACTIVE: redirect to `/billing/payment-required/`

---

### PHASE 6: Smoke Tests

**Files to Create:**
1. `wasla/apps/subscriptions/tests_onboarding.py` (NEW)

**Test Cases:**
1. FREE plan: plan select → subdomain → store ACTIVE + published
2. PAID plan: plan select → subdomain → PENDING_PAYMENT + NOT published
3. Payment webhook: PENDING_PAYMENT → ACTIVE + published
4. Invalid subdomain rejection
5. Duplicate subdomain rejection
6. Idempotent double webhook

---

## PART 7: FILE INVENTORY

### Files to MODIFY
```
wasla/config/settings.py
wasla/config/urls.py
wasla/apps/subscriptions/models.py                          (✅ DONE)
wasla/apps/subscriptions/models_billing.py
wasla/apps/stores/models.py                                 (✅ DONE)
wasla/apps/tenants/models.py                                (✅ DONE)
wasla/apps/tenants/services/domain_resolution.py
wasla/apps/tenants/middleware.py
wasla/apps/tenants/security_middleware.py
wasla/apps/payments/models.py
wasla/apps/payments/orchestrator.py
wasla/apps/payments/application/confirm_payment_webhook.py
wasla/apps/themes/models.py
```

### Files to CREATE
```
wasla/apps/subscriptions/views/onboarding_views.py
wasla/apps/subscriptions/services/onboarding_service.py
wasla/apps/subscriptions/templates/subscriptions/plan_select.html
wasla/apps/subscriptions/templates/subscriptions/subdomain_select.html
wasla/apps/subscriptions/templates/subscriptions/checkout.html
wasla/apps/subscriptions/templates/subscriptions/success.html
wasla/apps/storefront/services.py                           (or extend existing)
wasla/apps/subscriptions/tests_onboarding.py
```

---

## PART 8: MIGRATION IMPACT

### New Migrations Needed (from Phase 0 model changes)
- SubscriptionPlan.is_free field
- Store.STATUS_PENDING_PAYMENT constant (no migration needed - just choice constant)
- Store.subscription FK to Subscription
- Store.is_default_published BooleanField
- Store.default_published_at DateTimeField
- StoreDomain.store FK to Store

### Compatibility
- ✅ MySQL 8.0+ compatible (no TEXT indices without length)
- ✅ No breaking changes to existing fields
- ✅ All new fields have defaults (safe migration)

---

## PART 9: TESTING STRATEGY

### Unit Tests
- Subdomain validation (valid/invalid/reserved/duplicate)
- Store creation (FREE vs PAID)
- Domain creation and linking

### Integration Tests
- Full onboarding flow (FREE plan endpoint-to-endpoint)
- Full onboarding flow (PAID plan endpoint-to-endpoint)
- Payment webhook idempotency
- Store status transitions

### Manual Testing Checklist
- [ ] Create FREE plan, select subdomain → store ACTIVE + published
- [ ] Create PAID plan, select subdomain → store PENDING_PAYMENT + not published
- [ ] Payment webhook → store ACTIVE + published
- [ ] Access store via subdomain once active
- [ ] Cannot access subdomain if store not ACTIVE
- [ ] Duplicate webhook processing → no duplicate activations

---

## SUMMARY: WHAT'S NEW vs WHAT'S EXISTING

| Component | Status | Notes |
|-----------|--------|-------|
| Plan selection model | ✅ Existing | SubscriptionPlan + is_free field already added |
| Subdomain validation | ❌ TODO | PHASE 1 - Single function |
| Onboarding forms/templates | ❌ TODO | PHASE 2 - Web endpoints |
| Store creation (atomic) | ❌ TODO | PHASE 2 - Service |
| Payment initiation | ✅ Existing | PaymentOrchestrator.initiate_payment() ready |
| Webhook handler | ⚠️ Partial | Exists but needs store activation logic (PHASE 3) |
| Publish storefront | ❌ TODO | PHASE 4 - New service |
| Guards/middleware | ⚠️ Partial | Exists but needs onboarding check (PHASE 5) |
| Tests | ❌ TODO | PHASE 6 - Full suite |

---

## SUCCESS CRITERIA

✅ **Completion when:**
1. All 6 phases implemented
2. `python manage.py check` passes
3. `python manage.py migrate` succeeds on MySQL
4. Server starts without errors
5. All smoke tests pass
6. Idempotency verified (duplicate webhooks safe)

---

## NEXT STEP

→ **Proceed to PHASE 1: Subdomain Validation Function**
