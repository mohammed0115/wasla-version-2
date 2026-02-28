# Billing API & Web Interface - Implementation Checklist

**Status:** 🟢 CRITICAL FIXES IN PROGRESS

**Updated:** 2026-02-28

---

## ✅ COMPLETED FIXES

### 1. ✅ Registered REST APIs in Main URL Configuration
**File:** `/wasla/config/urls.py` (Line ~66)

**Change:** Added
```python
path("api/", include(("apps.subscriptions.urls_billing", "subscriptions_billing"), 
                      namespace="subscriptions_billing")),
```

**Result:** All REST APIs now accessible at:
- `GET  /api/subscriptions/`
- `POST /api/subscriptions/`
- `GET  /api/invoices/`
- `GET  /api/billing-cycles/`
- GET  /api/payment-methods/`
- `POST /api/webhooks/`
- etc.

---

### 2. ✅ Registered Web Templates in Main URL Configuration
**File:** `/wasla/config/urls.py` (Line ~19)

**Change:** Added
```python
path("billing/", include(("apps.subscriptions.urls_web", "subscriptions_web"), 
                         namespace="subscriptions_web")),
```

**Result:** All customer web pages now accessible at:
- `GET  /billing/dashboard/`
- `GET  /billing/subscription/`
- `GET  /billing/invoices/`
- `GET  /billing/invoices/<id>/`
- `GET  /billing/payment-method/`
- `GET  /billing/plan-change/`
- `GET  /billing/admin/dashboard/`

---

### 3. ✅ Fixed Import Paths in views_web.py
**File:** `/wasla/apps/subscriptions/views_web.py` (Line 15-20)

**Changes:**
```python
# BEFORE (WRONG):
from .models import (Subscription, Invoice, ...)
from .services import SubscriptionService, BillingService, DunningService

# AFTER (CORRECT):
from .models_billing import (Subscription, Invoice, ...)
from .services_billing import SubscriptionService, BillingService, DunningService
```

**Result:** Views can now properly import models and services

---

### 4. ✅ Fixed Import Paths in forms.py
**File:** `/wasla/apps/subscriptions/forms.py` (Line 14)

**Change:**
```python
# BEFORE (WRONG):
from .models import PaymentMethod, SubscriptionPlan

# AFTER (CORRECT):
from .models_billing import PaymentMethod, SubscriptionPlan
```

**Result:** Forms can now properly import models

---

## 🟡 IN PROGRESS

### 5. 🟡 Initialize Database for New Models (NEEDS VERIFICATION)
**Status:** Unknown - Phase 1 migration may have been applied

**Check:**
```bash
python manage.py showmigrations subscriptions
```

**If not applied:**
```bash
python manage.py migrate subscriptions
```

---

## 🔴 REMAINING TASKS

### 6. 🔴 Implement Webhook Signature Validation
**File:** `/wasla/apps/subscriptions/views_billing.py` (Line 358-404)

**Issue:** Webhook endpoint allows all traffic, signature validation not implemented

**Fix:**
```python
from django.views.decorators.csrf import csrf_exempt
import hmac
import hashlib

@csrf_exempt
def payment_webhook(request):
    # Verify signature
    signature = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
    body = request.body
    
    expected_sig = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
        return JsonResponse({'error': 'Invalid signature'}, status=403)
    
    # Process webhook...
```

**Effort:** 20 minutes

**Priority:** HIGH (Security critical)

---

### 7. 🔴 Update services_notifications.py to Build Email Context URLs
**File:** `/wasla/apps/subscriptions/services_notifications.py`

**Issue:** Email templates reference `{{ payment_url }}` but service doesn't build these

**Fix - Example for send_invoice_issued():**
```python
def send_invoice_issued(self, invoice, subscription, request=None):
    """Send invoice issued notification."""
    
    # Build context URLs
    if request:
        base_url = request.build_absolute_uri('/')
    else:
        base_url = settings.SITE_URL
    
    context = {
        'subscription': subscription,
        'invoice': invoice,
        'payment_url': f"{base_url}billing/invoices/{invoice.id}/",
        'invoice_url': f"{base_url}billing/invoices/{invoice.id}/",
        'manage_subscription_url': f"{base_url}billing/subscription/",
        'support_url': f"{base_url}support/",
        'help_url': f"{base_url}help/",
        'faq_url': f"{base_url}faq/",
    }
    
    # Render both text and HTML versions
    text_message = render_to_string(
        'subscriptions/emails/invoice_issued.txt',
        context
    )
    html_message = render_to_string(
        'subscriptions/emails/invoice_issued.html',
        context
    )
    
    send_mail(
        f'Invoice {invoice.invoice_number} Issued',
        text_message,
        settings.DEFAULT_FROM_EMAIL,
        [subscription.user.email],
        html_message=html_message,
    )
```

**Effort:** 1-2 hours (for all 6 notification methods)

**Priority:** MEDIUM (Email delivery critical)

---

### 8. 🔴 Create Permission Classes for API Access Control
**File:** `/wasla/apps/subscriptions/permissions.py` (NEW)

**Rationale:** Currently access control is scattered and inconsistent

**Create:**
```python
from rest_framework import permissions

class IsSubscriptionOwner(permissions.BasePermission):
    """Allow access only if user owns the subscription."""
    
    def has_object_permission(self, request, view, obj):
        return (obj.user == request.user and 
                obj.tenant == request.user.tenant)

class IsMerchantOrAdmin(permissions.BasePermission):
    """Allow access for merchant portal or admin."""
    
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated and
                (hasattr(request.user, 'is_merchant') or request.user.is_staff))

class IsAdminUser(permissions.BasePermission):
    """Allow access only for admin users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
```

**Then update views_billing.py** to use these classes consistently

**Effort:** 30 minutes

**Priority:** HIGH (Security & consistency)

---

### 9. 🔴 Add Web View Permission Mixins
**File:** `/wasla/apps/subscriptions/views_web.py` (TOP)

**Add:**
```python
class SubscriptionRequiredMixin(LoginRequiredMixin):
    """Ensure user has an active subscription."""
    
    def dispatch(self, request, *args, **kwargs):
        try:
            Subscription.objects.get(
                user=request.user,
                tenant=request.user.tenant
            )
        except Subscription.DoesNotExist:
            messages.error(request, 'No active subscription found.')
            return redirect('subscriptions:no-subscription')
        
        return super().dispatch(request, *args, **kwargs)

class TenantOwnershipMixin:
    """Verify object belongs to user's tenant."""
    
    def get_object(self):
        obj = super().get_object()
        if obj.tenant != self.request.user.tenant:
            raise PermissionDenied
        return obj
```

**Then update views** to use these mixins

**Effort:** 30 minutes

**Priority:** MEDIUM (Code quality & consistency)

---

### 10. 🔴 Test All API Endpoints
**Framework:** Django test suite

**Endpoints to test:**
```
✅ GET    /api/subscriptions/ - List
✅ POST   /api/subscriptions/ - Create
✅ GET    /api/subscriptions/<id>/ - Retrieve
✅ PUT    /api/subscriptions/<id>/ - Update
✅ DELETE /api/subscriptions/<id>/ - Delete
✅ POST   /api/subscriptions/<id>/change_plan/ - Change plan
✅ POST   /api/subscriptions/<id>/cancel/ - Cancel
✅ POST   /api/subscriptions/<id>/suspend/ - Suspend (admin)
✅ POST   /api/subscriptions/<id>/reactivate/ - Reactivate (admin)
✅ POST   /api/subscriptions/<id>/add_grace_period/ - Grace period
✅ GET    /api/subscriptions/<id>/billing_status/ - Status

✅ GET    /api/invoices/ - List
✅ GET    /api/invoices/<id>/ - Retrieve

✅ GET    /api/billing-cycles/ - List
✅ GET    /api/billing-cycles/<id>/ - Retrieve

✅ GET    /api/payment-methods/<sub_id>/ - Get
✅ POST   /api/payment-methods/<sub_id>/ - Create

✅ POST   /api/webhooks/ - Webhook

✅ GET    /api/dunning/<sub_id>/ - Get status
✅ POST   /api/dunning/<sub_id>/retry/ - Retry
```

**Effort:** 2-3 hours

**Priority:** HIGH (Quality assurance)

---

### 11. 🔴 Test All Web Interface Pages
**Framework:** Django test suite + Browser testing

**Pages to test:**
```
✅ /billing/dashboard/ - Dashboard loads
✅ /billing/subscription/ - Subscription detail loads
✅ /billing/invoices/ - Invoice list loads
✅ /billing/invoices/<id>/ - Invoice detail loads
✅ /billing/payment-method/ - Payment method page loads
✅ /billing/plan-change/ - Plan change page loads
✅ /billing/admin/dashboard/ - Admin dashboard loads (staff only)
```

**Forms to test:**
```
✅ Cancel subscription (POST)
✅ Request grace period (POST)
✅ Update payment method (POST)
✅ Change plan (POST)
```

**Effort:** 2-3 hours

**Priority:** HIGH (Quality assurance)

---

### 12. 🔴 Audit & Fix Admin Portal Integration
**File:** `/wasla/apps/admin_portal/`

**Tasks:**
1. Understand current admin portal structure
2. Determine if it should use REST APIs or direct models
3. Add billing dashboard/views to admin portal
4. Implement proper permission checks
5. Test with admin users

**Questions to Answer:**
- Does admin portal currently have permission to manage subscriptions?
- Should it use our REST APIs or direct model access?
- What metrics should admin portal display?
- Should admins be able to suspend/reactivate memberships directly?

**Effort:** 3-4 hours

**Priority:** HIGH (Admin functionality)

---

### 13. 🔴 Design & Implement Merchant Portal Integration
**File:** `/wasla/apps/admin_portal/` OR new merchant portal

**Tasks:**
1. Determine merchant portal location/structure
2. Design merchant-subscription relationship
3. Implement merchant billing views
4. Add permission checks for merchants
5. Test with merchant users

**Questions to Answer:**
- Are merchants = tenants?
- Does each merchant have 1 subscription or many?
- Who can create subscriptions (admin/merchant)?
- What can merchants see/do with billing?

**Effort:** 4-5 hours

**Priority:** MEDIUM (Merchant functionality)

---

## TESTING CHECKLIST

### API Security Testing
- [ ] Unauthenticated requests rejected
- [ ] Cross-tenant access blocked (user can't see other tenant's data)
- [ ] Admin-only endpoints reject non-admin users
- [ ] Non-owners can't access subscriptions
- [ ] Webhook signature validation works (HMAC verification)

### API Functionality Testing
- [ ] Subscriptions CRUD operations work
- [ ] Plan changes calculate proration correctly
- [ ] Cancellations mark subscription as cancelled
- [ ] Grace period requests work
- [ ] Billing status returns accurate data
- [ ] Invoice listing filters work
- [ ] Payment method operations work

### Web Interface Testing
- [ ] Unauthenticated users redirected to login
- [ ] Subscriptionless users see appropriate message
- [ ] Forms submit correctly
- [ ] Permissions enforced (customer only sees own data)
- [ ] Responsive design works on mobile/tablet/desktop
- [ ] Email forms generate proper context

### Email Notification Testing
- [ ] All 4 email templates send correctly
- [ ] Email context includes all required URLs
- [ ] HTML and text versions both sent
- [ ] Emails appear in user inbox
- [ ] Links in emails work correctly

---

## DEPLOYMENT CHECKLIST

Before pushing to production:

- [ ] All imports fixed and tested
- [ ] URLs registered and accessible
- [ ] Webhook signature validation implemented
- [ ] Email context URLs implemented
- [ ] API permission classes normalized
- [ ] Web permission mixins implemented
- [ ] All tests passing
- [ ] Admin portal integration complete
- [ ] Database migrations applied
- [ ] Email configuration validated
- [ ] Webhook secret configured in settings
- [ ] CSRF middleware verified

---

## Quick Start Commands

### Apply Fixes
```bash
# 1. Verify changes applied
cd /home/mohamed/Desktop/wasla-version-2

# 2. Check migrations
python manage.py showmigrations subscriptions

# 3. Apply migrations if needed
python manage.py migrate subscriptions

# 4. Test imports
python manage.py shell
>>> from wasla.apps.subscriptions.views_web import billing_dashboard
>>> from wasla.apps.subscriptions.services_billing import SubscriptionService
>>> print("✅ Imports successful")

# 5. Check URL routing
python manage.py show_urls | grep subscriptions

# 6. Run tests
python manage.py test wasla.apps.subscriptions

# 7. Start dev server
python manage.py runserver
```

### Test APIs
```bash
# In another terminal:
curl http://localhost:8000/api/subscriptions/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json"
```

### Test Web Interface
```
Visit http://localhost:8000/billing/dashboard/
```

---

## Status Summary

| Task | Status | Time | Priority |
|------|--------|------|----------|
| Register REST APIs | ✅ Done | 2 min | 🔴 CRITICAL |
| Register Web Templates | ✅ Done | 2 min | 🔴 CRITICAL |
| Fix views_web.py imports | ✅ Done | 2 min | 🔴 CRITICAL |
| Fix forms.py imports | ✅ Done | 2 min | 🔴 CRITICAL |
| Verify migrations applied | 🟡 TBD | 5 min | ⚠️ HIGH |
| Webhook signature validation | 🔴 TODO | 20 min | ⚠️ HIGH |
| Email context URLs | 🔴 TODO | 1-2 hrs | ⚠️ MEDIUM |
| Permission classes | 🔴 TODO | 30 min | ⚠️ HIGH |
| Web permission mixins | 🔴 TODO | 30 min | ⚠️ MEDIUM |
| API endpoint tests | 🔴 TODO | 2-3 hrs | ⚠️ HIGH |
| Web interface tests | 🔴 TODO | 2-3 hrs | ⚠️ HIGH |
| Admin portal integration | 🔴 TODO | 3-4 hrs | ⚠️ HIGH |
| Merchant portal design | 🔴 TODO | 4-5 hrs | ⚠️ MEDIUM |

**Total Estimated Time:** 15-20 hours

**Critical Path:** ✅ ✅ ✅ ✅ → Webhook validation → Email context → Tests → Integration

---

**Next Action:** Run `python manage.py migrate subscriptions` to verify database is up to date

