# PHASE 0 - AUDIT & HOOKS REPORT
## Wasla Onboarding Flow Implementation

**Date:** March 1, 2026
**Status:** ✅ Audit Complete

---

## 1. EXISTING MODELS & INFRASTRUCTURE (VERIFIED)

### Payment & Subscription
- ✅ **SubscriptionPlan** (`apps/subscriptions/models.py`)
  - Fields: name, price, billing_cycle, features (JSON), max_products, max_orders_monthly, max_staff_users, is_active
  - **Need to add:** is_free (bool) field to distinguish FREE vs PAID plans
  
- ✅ **Subscription** (`apps/subscriptions/models_billing.py`)  
  - Full state machine: active, past_due, grace, suspended, cancelled
  - FK: tenant OneToOne, plan FK, currency, next_billing_date, state, grace_until
  - **Use this for:** Tracking subscription activation after payment

- ✅ **StoreSubscription** (`apps/subscriptions/models.py`)
  - Simple model linking store_id + plan with status (active, expired, cancelled)
  - **May be deprecated in favor of Subscription** - check usage

### Stores & Tenants
- ✅ **Store** (`apps/stores/models.py`)
  - Fields: status (DRAFT, ACTIVE, INACTIVE, SUSPENDED), plan FK, subdomain (unique), slug (unique), custom_domain
  - **Need to add:** 
    - status PENDING_PAYMENT constant
    - is_default_published (bool) OR default_published_at (datetime) field
    - subscription FK (link to Subscription model)

- ✅ **Tenant** (`apps/tenants/models.py`)  
  - Fields: slug, name, is_active, domain, subdomain
  - **Use for:** Housing tenant data once store activated

- ✅ **StoreDomain** (`apps/tenants/models.py`)
  - Status: PENDING_VERIFICATION → VERIFIED → CERT_REQUESTED → CERT_ISSUED → ACTIVE
  - Fields: domain (unique), tenant FK, is_primary, status, verification method
  - **Need to add:** Store FK or reference to link domain to store during onboarding

### Themes & Storefront
- ✅ **Theme** (`apps/themes/models.py`)
  - Fields: name, preview_image_path, is_active

- ✅ **StoreBranding** (`apps/themes/models.py`)
  - Fields: store FK, theme_code, primary_color, secondary_color
  - **Use for:** Applying default theme to new stores

### Payment Processing
- ✅ **PaymentOrchestrator** (`apps/payments/orchestrator.py`)
  - Methods: initiate_payment(), refund()
  - Manages Payment Intent + PaymentEvent 
  - Supports multiple providers (Stripe, Apple, Google, Saudi banks)
  - **Key:** Can initiate payment for subscription plans

- ✅ **Webhook Security** (`apps/payments/security/webhook_security.py`)
  - WebhookSecurityValidator: compute_signature, verify_signature, check_replay_attack
  - **Use for:** Validating payment success webhooks

---

## 2. EXISTING VIEWS & ENDPOINTS

### Onboarding  
- ✅ **AI Onboarding API** (`apps/ai_onboarding/`)
  - OnboardingAnalyzeAPIView, OnboardingProvisionAPIView
  - **Separate concern** - not part of plan/subdomain selection flow
  - **Can be called after** store activated if needed

### Payment Views
- ✅ **Payment API endpoints** (likely in `apps/payments/interfaces/`)
  - No explicit onboarding → payment flow found yet
  - **Will need to create:** Custom endpoints for subscription plan payment

### No existing plan selection flow found
- **Need to create from scratch:**
  - /onboarding/plan/ - Plan selection (GET form, POST selection)
  - /onboarding/subdomain/ - Subdomain selection (GET form, POST with validation)
  - /onboarding/checkout/ - Payment/confirmation page (redirect to payment gateway)

---

## 3. DOMAIN RESOLUTION & SUBDOMAIN VALIDATION

### Current Infrastructure
- ✅ **extract_subdomain()** (`apps/tenants/infrastructure/subdomain_resolver.py`)
  - Extracts subdomain from host header
  - **Use for:** Validating subdomain format

- ✅ **Domain resolution** (`apps/tenants/services/domain_resolution.py`)
  - resolve_tenant_by_host(), resolve_store_by_slug()
  - **Use for:** Looking up existing subdomains during validation

### Reserved Words (Need to Define)
Currently no validation list found. Will create:
```python
RESERVED_SUBDOMAINS = {
    'www', 'admin', 'api', 'static', 'media', 'mail',
    'shop', 'store', 'dashboard', 'billing', 'support',
    'smtp', 'pop', 'imap', 'ftp', 'git', 'vpn'
}
```

---

## 4. FILES TO MODIFY / CREATE

### Phase 1 (Models)
1. **apps/subscriptions/models.py**
   - Add: `is_free` (bool) field to SubscriptionPlan
   
2. **apps/stores/models.py**
   - Add: `PENDING_PAYMENT`, `is_default_published` fields to Store
   - Add: `subscription` FK to Subscription model
   - Add: `StoreDomain` FK for tracking assigned domain
   - Add migration

3. **apps/tenants/models.py**
   - Add: `store` FK to StoreDomain (reverse: store_domains)
   - Add migration

### Phase 2 (Onboarding Views)
4. **apps/subscriptions/interfaces/onboarding_views.py** (NEW)
   - PlanSelectView (GET/POST)
   - SubdomainSelectView (GET/POST)
   - OnboardingSessionService

5. **apps/subscriptions/urls_onboarding.py** (NEW)
   - Route /onboarding/plan/, /onboarding/subdomain/, /onboarding/checkout/

6. **apps/subscriptions/templates/onboarding/** (NEW)
   - plan_select.html
   - subdomain_select.html
   - checkout_confirmation.html

### Phase 3 (Payment Integration)
7. **apps/subscriptions/services/onboarding_service.py** (NEW)
   - OnboardingService: handle_free_plan(), handle_paid_plan()
   - Atomic transaction management
   - Domain creation & subdomain validation

8. **apps/payments/views/webhook.py** (MODIFY or CREATE)
   - Payment success webhook handler
   - Call store_activation_service after payment confirmed
   - Idempotency key tracking

### Phase 4 (Storefront Publishing)
9. **apps/storefront/services/publish_service.py** (NEW)
   - publish_default_storefront(store)
   - Creates Store Branding with default theme
   - Sets store.is_default_published = True
   - Idempotent and logging

### Phase 5 (Guards & Middleware)
10. **apps/tenants/middleware.py** (MODIFY)
    - Add: check store.status in ACTIVE before serving storefront
    - Add: redirect to payment if PENDING_PAYMENT
    - Add: friendly messages for unpublished stores

11. **apps/subscriptions/middleware.py** (NEW)
    - Onboarding flow guards
    - Prevent access to /billing/* if no store created yet

### Phase 6 (Tests)
12. **apps/subscriptions/tests/test_onboarding_flow.py** (NEW)
    - test_free_plan_creates_store_and_publishes()
    - test_paid_plan_pending_payment()
    - test_payment_webhook_activates_store()
    - test_subdomain_validation()
    - test_storefront_blocked_until_published()

---

## 5. KEY INTEGRATION POINTS

### ✅ Confirmed Methods to Use:

1. **Initiate Payment:**
   ```python
   from apps.payments.orchestrator import PaymentOrchestrator
   PaymentOrchestrator.initiate_payment(
       tenant_id, plan_id, amount, provider_code='stripe'
   )
   ```

2. **Get Store by Slug:**
   ```python
   from apps.stores.models import Store
   store = Store.objects.get(slug='mystore')
   ```

3. **Create Default Domain:**
   ```python
   from apps.tenants.models import StoreDomain
   domain = StoreDomain.objects.create(
       domain=f'{subdomain}.w-sala.com',
       tenant=tenant,
       status=StoreDomain.STATUS_ACTIVE
   )
   ```

4. **Apply Theme:**
   ```python
   from apps.themes.models import StoreBranding, Theme
   default_theme = Theme.objects.filter(is_active=True).first()
   StoreBranding.objects.create(
       store=store,
       theme_code=default_theme.name
   )
   ```

5. **Extract Subdomain.**
   ```python
   from apps.tenants.infrastructure.subdomain_resolver import extract_subdomain
   subdomain = extract_subdomain('mystore.w-sala.com')
   ```

---

## 6. ACTION ITEMS FOR PHASES

| Phase | File | Action |
|-------|------|--------|
| 1 | models.py | Add fields + migration |
| 2 | onboarding_views.py | Create plan/subdomain selection views |
| 2 | urls.py | Route new onboarding endpoints |
| 2 | templates/ | Create form templates |
| 3 | onboarding_service.py | Implement atomic create logic |
| 3 | webhook.py | Handle payment success → activate store |
| 4 | publish_service.py | Implement publish_default_storefront() |
| 5 | middleware.py | Add guards for unpublished stores |
| 6 | test_onboarding_flow.py | Comprehensive test suite |

---

## 7. RISK & MITIGATION CHECKLIST

| Risk | Mitigation |
|------|-----------|
| Subdomain collision | StoreDomain.domain unique constraint + check on create |
| Webhook delivered twice | Idempotency key (store webhook event provider id) |
| Payment but no store activation | Webhook handler must set store.status=ACTIVE atomically |
| Store accessible before published | Middleware checks is_default_published before rendering |
| Domain creation fails after plan selected | Transaction rollback; show error; allow retry |
| Concurrent subdomain selection | Database unique constraint prevents race condition |

---

## 8. SUMMARY

✅ **Ready to proceed with PHASE 1**
- All key models identified
- Integration points confirmed
- File modification plan clear
- No blocking issues found

**Next Step:** Start PHASE 1 - Add model fields for plan tracking and publication


