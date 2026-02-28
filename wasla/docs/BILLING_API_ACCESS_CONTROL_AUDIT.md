# Wasla Billing APIs - Comprehensive Audit & Access Control Review

**Status:** 🔴 CRITICAL FINDINGS - APIs Exist but Not Registered

**Last Updated:** 2026-02-28

---

## Executive Summary

**CRITICAL ISSUE IDENTIFIED:** All billing REST APIs have been implemented (Phase 1) but **NOT registered in main Django URL configuration**. The web template interface (Phase 2) is also NOT wired into the main routes.

### Current State

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| REST APIs Implementation | ✅ Complete | `views_billing.py` (494 lines) | All 6 ViewSets with custom actions |
| API Serializers | ✅ Complete | `serializers_billing.py` | 15+ serializers |
| API URL Routing | ⚠️ Exists but NOT registered | `urls_billing.py` | Routes defined but not included in main config |
| REST API Access Control | ✅ Defined | `views_billing.py` | Permission decorators present |
| Web Template Interface | ✅ Complete | `views_web.py` + templates | 6 customer, 4 email, 1 admin template |
| Web Template Routes | ⚠️ Exists but NOT registered | `urls_web.py` | Routes defined but not included in main config |
| Web Template Access Control | ✅ Defined | `views_web.py`, `forms.py` | Authentication required |

---

## Part 1: REST APIs Audit

### API ViewSets Implemented

#### 1. **SubscriptionViewSet** (Primary)
**File:** `views_billing.py` (lines 38-231)

**Purpose:** Full subscription lifecycle management

**Endpoints:**
```
GET    /subscriptions/              - List subscriptions
POST   /subscriptions/              - Create subscription
GET    /subscriptions/<id>/         - Get details
PUT    /subscriptions/<id>/         - Update subscription
DELETE /subscriptions/<id>/         - Delete subscription
POST   /subscriptions/<id>/change_plan/      - Change plan
POST   /subscriptions/<id>/cancel/           - Cancel subscription
POST   /subscriptions/<id>/suspend/          - Suspend (ADMIN ONLY)
POST   /subscriptions/<id>/reactivate/       - Reactivate (ADMIN ONLY)
POST   /subscriptions/<id>/add_grace_period/ - Add grace period
GET    /subscriptions/<id>/billing_status/   - Get billing status
```

**Access Control:**
- `change_plan`: All authenticated users
- `cancel`: All authenticated users
- `suspend`: Admin only (`permission_classes=[permissions.IsAdminUser]`)
- `reactivate`: Admin only (`permission_classes=[permissions.IsAdminUser]`)
- `add_grace_period`: All authenticated users
- `billing_status`: All authenticated users

**Current Access:** None (not registered in main URLs)

---

#### 2. **InvoiceViewSet**
**File:** `views_billing.py` (lines 233-266)

**Purpose:** Read-only invoice access

**Endpoints:**
```
GET    /invoices/        - List invoices (filtered by tenant)
GET    /invoices/<id>/   - Get invoice details
```

**Access Control:**
- All authenticated users (tenant-filtered in queryset)

**Current Access:** None (not registered)

---

#### 3. **BillingCycleViewSet**
**File:** `views_billing.py` (lines 268-300)

**Purpose:** Read-only billing cycle history

**Endpoints:**
```
GET    /billing-cycles/      - List cycles (filtered by tenant)
GET    /billing-cycles/<id>/ - Get cycle details
```

**Access Control:**
- All authenticated users (tenant-filtered in queryset)

**Current Access:** None (not registered)

---

#### 4. **PaymentMethodViewSet**
**File:** `views_billing.py` (lines 302-356)

**Purpose:** Payment method management

**Endpoints:**
```
GET    /payment-methods/<subscription_id>/  - Get payment method
POST   /payment-methods/<subscription_id>/  - Create/update payment method
```

**Access Control:**
- All authenticated users (subscription ownership verified)

**Current Access:** None (not registered)

---

#### 5. **WebhookViewSet**
**File:** `views_billing.py` (lines 358-404)

**Purpose:** Payment provider webhook handling

**Endpoints:**
```
POST   /webhooks/payment-events/  - Receive webhook events
```

**Access Control:**
- `permission_classes=[permissions.AllowAny]` (Signature-verified instead)

**Current Access:** None (not registered)

---

#### 6. **DunningViewSet**
**File:** `views_billing.py` (lines 406-494)

**Purpose:** Payment retry management

**Endpoints:**
```
GET    /dunning/<subscription_id>/      - Get dunning status
POST   /dunning/<subscription_id>/retry/ - Manually retry dunning
```

**Access Control:**
- All authenticated users (subscription ownership verified)

**Current Access:** None (not registered)

---

### Additional Legacy APIs

#### Store Subscription APIs (views/api.py)
```
GET    /plans/                    - List active plans
POST   /stores/<store_id>/subscribe/ - Subscribe store to plan
```

**Current Access:** Defined but routing unclear

---

## Part 2: Web Template Interface Audit

### Templates & Views Implemented

#### Customer-Facing Views

| View | URL | Template | Purpose | Auth | Data |
|------|-----|----------|---------|------|------|
| `billing_dashboard` | `/dashboard/` | `dashboard.html` | Main overview | ✅ Required | Subscription, invoices, balance |
| `subscription_detail` | `/subscription/` | `subscription_detail.html` | Plan mgmt | ✅ Required | Plan features, items, actions |
| `invoice_list` | `/invoices/` | `invoice_list.html` | Invoice browsing | ✅ Required | Paginated invoices |
| `invoice_detail` | `/invoices/<id>/` | `invoice_detail.html` | Invoice view | ✅ Required | Full invoice breakdown |
| `payment_method` | `/payment-method/` | `payment_method.html` | Payment mgmt | ✅ Required | Current method, update form |
| `plan_change` | `/plan-change/` | `plan_change.html` | Plan comparison | ✅ Required | All plans, proration calc |

#### Admin Views

| View | URL | Template | Purpose | Auth | Data |
|------|-----|----------|---------|------|------|
| `admin_billing_dashboard` | `/admin/dashboard/` | `admin_dashboard.html` | Admin analytics | ✅ Staff only | MRR, subscriptions, payments |

#### Email Templates

| Template | Use Case | Context |
|----------|----------|---------|
| `invoice_issued.html` | Invoice notification | Subscription, invoice, URLs |
| `payment_received.html` | Payment confirmation | Payment event, invoice, method |
| `grace_period_expiring.html` | Payment reminder | Dunning attempt, grace period |
| `store_suspended.html` | Suspension notice | Suspension reason, recovery steps |

### Web Template Access Control Status

**Current Access:** None (not registered in main URLs)

---

## Part 3: ACCESS CONTROL MATRIX

### Proposed Access Control by User Type

```
                        | CUSTOMER | MERCHANT | ADMIN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subscriptions:
  List own              |    ✅    |    ✅    |  ✅
  Get details           |    ✅    |    ✅    |  ✅
  Create                |    ❌    |    ✅    |  ✅
  Change plan           |    ✅    |    ✅    |  ✅
  Cancel                |    ✅    |    ✅    |  ✅
  Suspend               |    ❌    |    ❌    |  ✅
  Reactivate            |    ❌    |    ❌    |  ✅
  Add grace period      |    ✅    |    ✅    |  ✅
  Get billing status    |    ✅    |    ✅    |  ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Invoices:
  List own              |    ✅    |    ✅    |  ✅
  Get details           |    ✅    |    ✅    |  ✅
  Download PDF          |    ✅    |    ✅    |  ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Billing Cycles:
  List own              |    ✅    |    ✅    |  ✅
  Get details           |    ✅    |    ✅    |  ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Payment Methods:
  Get                   |    ✅    |    ✅    |  ✅
  Create/Update         |    ✅    |    ✅    |  ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dunning:
  Get status            |    ✅    |    ✅    |  ✅
  Manual retry          |    ✅    |    ✅    |  ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Webhooks:
  Receive events        |    ❌    |    ❌    |  ✅*
                        |          |          | *No auth
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Legend:
✅ = Should have access
❌ = Should NOT have access
```

---

## Part 4: MERCHANT PORTAL REQUIREMENTS

### Current State
**Status:** Unknown - need to audit admin_portal app

### Expected Access Patterns

**Merchant Portal should access:**

1. **Subscription Management**
   - View own subscription (if merchant = one per tenant)
   - Change plan
   - Monitor billing status
   - View invoices

2. **Team Subscriptions** (if multi-user)
   - List all team subscriptions
   - View team usage
   - Manage team billing

3. **Billing Analytics**
   - View billing history
   - Payment status
   - Upcoming charges

4. **Payment Methods**
   - View current method
   - Update payment method

5. **NOT Accessible to Merchant**
   - Suspend/reactivate (admin only)
   - Create new subscriptions (admin only)
   - View other merchant's data (tenant isolation)

---

## Part 5: ADMIN PORTAL REQUIREMENTS

### Expected Access Patterns

**Admin Portal should access:**

1. **Subscription Management**
   - List all subscriptions
   - Suspend/reactivate subscriptions
   - Force plan changes
   - View any subscription details

2. **Billing Administration**
   - Create manual invoices
   - Mark invoices as paid
   - Adjust charges (credits/refunds)
   - Manage dunning strategy

3. **Analytics & Reporting**
   - MRR (Monthly Recurring Revenue)
   - Churn analysis
   - Payment success rates
   - Revenue trends

4. **Payment Methods**
   - View stored payment methods
   - Remove invalid methods
   - Manage failed payments

5. **Webhooks**
   - View webhook logs
   - Manually retry failed webhooks
   - Test webhook delivery

---

## Part 6: CUSTOMER PORTAL (WEB) REQUIREMENTS

### Current Implementation

✅ All necessary views created in `views_web.py`
✅ All necessary templates created
✅ All necessary forms created

### Expected Access Patterns

**Customer Portal (Web Templates) should provide:**

1. **Dashboard**
   - Subscription status
   - Outstanding balance
   - Next billing date
   - Recent invoices

2. **Invoice Management**
   - List all invoices
   - View invoice details
   - Download PDF
   - Filter by status

3. **Payment Method**
   - View current method
   - Update payment method
   - View expiry warnings

4. **Subscription Management**
   - View plan details
   - Change plan (with proration)
   - Request grace period
   - Cancel subscription

5. **NOT Accessible to Customer**
   - Other customer's data (tenant isolation ✅)
   - Admin functions
   - Webhook management

---

## Part 7: CRITICAL ISSUES & RECOMMENDATIONS

### 🔴 CRITICAL - APIs Not Registered

**Issue:** All REST APIs implemented in Phase 1 are NOT registered in main Django URL configuration.

**Impact:** 
- APIs cannot be accessed by any client
- Mobile apps, third-party integrations cannot use APIs
- Admin portal cannot consume billing APIs
- Web templates must access models directly (not REST APIs)

**Current Location:** `urlpatterns` in `/wasla/config/urls.py` (line 50-72)

**Missing Registration:**
```python
# NOT PRESENT IN CONFIG - NEEDS TO BE ADDED
path("api/", include(("apps.subscriptions.urls_billing", "subscriptions_billing"), 
                       namespace="subscriptions_billing")),
```

---

### 🔴 CRITICAL - Web Templates Not Registered

**Issue:** All web templates implemented in Phase 2 are NOT registered in main Django URL configuration.

**Impact:**
- Customer portal pages inaccessible
- `/billing/dashboard/` returns 404
- Users cannot access billing interface
- Web templates are dead code

**Missing Registration:**
```python
# NOT PRESENT IN CONFIG - NEEDS TO BE ADDED
path("billing/", include(("apps.subscriptions.urls_web", "subscriptions_web"), 
                         namespace="subscriptions_web")),
```

---

### ⚠️ HIGH - Admin Portal Integration Unclear

**Issue:** Unclear how admin_portal accesses billing APIs

**Status:** Need to audit `/wasla/apps/admin_portal/` to understand:
- Does it consume REST APIs or access models directly?
- How should it authenticate?
- What permissions model is used?

**Recommendation:** Admin portal should either:
1. Use REST APIs (client-side approach)
2. Use direct model access with permission checks (server-side approach)

---

### ⚠️ HIGH - Merchant Portal Not Yet Designed

**Issue:** Unclear if merchants see billing data or subscription management

**Questions:**
1. Are merchants = tenants (yes / no)?
2. Does each merchant have ONE subscription or MULTIPLE?
3. Who creates subscriptions (admin / merchant)?
4. Does merchant see team billing?

---

### ⚠️ MEDIUM - Access Control Inconsistency

**Issue:** Some views override permission classes, some don't

**Examples:**
- `suspend` and `reactivate` use `permission_classes=[permissions.IsAdminUser]` (correct)
- But other views like `cancel` and `add_grace_period` allow ALL authenticated users
- No explicit ownership verification in some endpoints

**Recommendation:** Add explicit ownership check or use custom permission class:

```python
class IsSubscriptionOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user and obj.tenant == request.user.tenant
```

---

### ⚠️ MEDIUM - Webhook Security

**Issue:** Webhook endpoint uses `permission_classes=[permissions.AllowAny]`

**Current State:**
- Comment says "Verify signature instead"
- But signature verification code not implemented

**Recommendation:** Implement HMAC validation:

```python
def verify_webhook_signature(request):
    signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
    body = request.body
    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)
```

---

### ⚠️ MEDIUM - Email Template Context

**Issue:** Email templates expect URLs to be passed in context

**Current State:** Service `services_notifications.py` doesn't build URLs
**Problem:** Templates reference variables like `{{ support_url }}` but these aren't provided

**Recommendation:** Update `services_notifications.py` to build all required URLs:

```python
def send_invoice_issued(self, invoice, subscription):
    context = {
        'invoice': invoice,
        'subscription': subscription,
        'payment_url': request.build_absolute_uri('/billing/invoices/{}/'.format(invoice.id)),
        'support_url': request.build_absolute_uri('/support/'),
        # ... more URLs
    }
```

---

### ⚠️ MEDIUM - Web Views Using Old Service Classes

**Issue:** Web views import from `.services` but Phase 1 services are `.services_billing`

**Current Code:**
```python
from .services import SubscriptionService, BillingService, DunningService
```

**Problem:** This module doesn't exist, should be:
```python
from .services_billing import SubscriptionService, BillingService, DunningService
```

---

## Part 8: IMPLEMENTATION ROADMAP

### Phase A: Register APIs (TODAY)
**Time:** 15 minutes

```python
# Step 1: Update /wasla/config/urls.py
# Add this line after payments API (around line 52):
path("api/", include(("apps.subscriptions.urls_billing", "subscriptions_billing"), 
                      namespace="subscriptions_billing")),
```

**Deliverable:** All REST APIs accessible at `/api/subscriptions/`, `/api/invoices/`, etc.

---

### Phase B: Register Web Templates (TODAY)
**Time:** 15 minutes

```python
# Step 2: Update /wasla/config/urls.py  
# Add this line in web section (around line 43):
path("billing/", include(("apps.subscriptions.urls_web", "subscriptions_web"), 
                         namespace="subscriptions_web")),
```

**Deliverable:** Customer portal accessible at `/billing/dashboard/`, etc.

---

### Phase C: Fix Web Views Imports (TODAY)
**Time:** 10 minutes

**File:** `/wasla/apps/subscriptions/views_web.py`

```python
# Remove:
from .services import SubscriptionService, BillingService, DunningService

# Add:
from .services_billing import SubscriptionService, BillingService, DunningService
```

---

### Phase D: Implement Webhook Signature Validation (TODAY)
**Time:** 20 minutes

**File:** `/wasla/apps/subscriptions/views_billing.py`

Complete the webhook signature verification in `WebhookViewSet.create()`

---

### Phase E: Fix Email Template Context Building (TOMORROW)
**Time:** 30 minutes

**File:** `/wasla/apps/subscriptions/services_notifications.py`

Update all email methods to build complete URL context

---

### Phase F: Audit Admin Portal Integration (TOMORROW)
**Time:** 1-2 hours

**Task:** Review `/wasla/apps/admin_portal/` to understand:
1. How it should access billing data
2. What permissions it needs
3. Whether it should use REST APIs or direct model access

---

### Phase G: Design Merchant Portal Billing (THIS WEEK)
**Time:** 2-3 hours

**Task:** Decide on merchant/subscription relationship and design appropriate views

---

## Part 9: TESTING CHECKLIST

### REST API Testing
- [ ] GET /api/subscriptions/ - List subscriptions (auth required)
- [ ] POST /api/subscriptions/ - Create subscription
- [ ] GET /api/subscriptions/<id>/billing_status/ - Get status
- [ ] POST /api/subscriptions/<id>/change_plan/ - Change plan
- [ ] POST /api/subscriptions/<id>/cancel/ - Cancel
- [ ] POST /api/subscriptions/<id>/suspend/ - Suspend (admin only)
- [ ] GET /api/invoices/ - List invoices
- [ ] GET /api/webhooks/ - Webhook receive

### Web Template Testing
- [ ] GET /billing/dashboard/ - Dashboard loads
- [ ] GET /billing/invoices/ - Invoice list loads
- [ ] GET /billing/invoices/<id>/ - Invoice details load
- [ ] POST /billing/payment-method/ - Update payment method
- [ ] POST /billing/subscription/ - Cancel subscription
- [ ] GET /billing/plan-change/ - Plan change loads

### Permission Testing
- [ ] Customer can only see own subscription
- [ ] Admin can suspend subscriptions
- [ ] Unauthenticated users redirected to login
- [ ] Webhook validates signature (when implemented)

### Email Testing
- [ ] Invoice issued email sends with all context
- [ ] Payment received email sends
- [ ] Grace period email sends with countdown
- [ ] Suspension email sends with recovery info

---

## Part 10: SUMMARY TABLE

| Component | Status | Location | Issues | Priority |
|-----------|--------|----------|--------|----------|
| REST API Implementation | ✅ | `views_billing.py` | Not registered | 🔴 CRITICAL |
| REST API Routing Config | ✅ | `urls_billing.py` | Not included in main URLs | 🔴 CRITICAL |
| Web Templates | ✅ | `views_web.py` + `templates/` | Not registered | 🔴 CRITICAL |
| Web Template Routing | ✅ | `urls_web.py` | Not included in main URLs | 🔴 CRITICAL |
| Access Control (APIs) | ⚠️ | `views_billing.py` | Webhook not validated | ⚠️ HIGH |
| Access Control (Web) | ✅ | `views_web.py`, `forms.py` | Good | ✅ |
| Email Templates | ⚠️ | `templates/emails/` | Missing context URLs | ⚠️ MEDIUM |
| Services | ✅ | `services_billing.py` | Good | ✅ |
| Forms | ✅ | `forms.py` | Good | ✅ |
| Permissions Model | ⚠️ | Scattered | Needs standardization | ⚠️ MEDIUM |
| Admin Portal Integration | ❓ | Unknown | Audit needed | ⚠️ HIGH |
| Merchant Portal | ❓ | None yet | Design needed | ⚠️ HIGH |

---

**Status:** Ready for implementation
**Estimate:** 2-3 days to fully integrate and test

