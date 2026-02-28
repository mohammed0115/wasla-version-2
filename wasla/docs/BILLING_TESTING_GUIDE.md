# 🧪 Billing API & Web Interface - Testing Guide

**Purpose:** Verify that all critical fixes are working correctly  
**Estimated Time:** 30-45 minutes  
**Prerequisites:** Django dev server running, test user account

---

## Quick Verification (5 minutes)

### 1. Check Database Migrations
```bash
cd /home/mohamed/Desktop/wasla-version-2
python manage.py showmigrations subscriptions
```

**Expected Output:**
```
subscriptions
 [x] 0001_initial
 [x] 0002_automated_recurring_billing
```

If `0002_automated_recurring_billing` is `[ ]`, run:
```bash
python manage.py migrate subscriptions
```

### 2. Check URL Registration
```bash
python manage.py show_urls | grep -E "(billing|subscriptions)" | head -20
```

**Expected Output:**
```
/billing/                           subscriptions_web
/api/subscriptions/                 subscriptions_billing
/api/subscriptions/                 subscriptions_billing
...and more
```

### 3. Check Imports
```bash
python manage.py shell
```

```python
>>> from wasla.apps.subscriptions.views_web import billing_dashboard
>>> from wasla.apps.subscriptions.services_billing import SubscriptionService
>>> from wasla.apps.subscriptions.forms import PaymentMethodForm
>>> print("✅ All imports successful")
>>> exit()
```

---

## Web Interface Testing (15 minutes)

### 1. Start Dev Server
```bash
python manage.py runserver 0.0.0.0:8000
```

**Navigate to:** `http://localhost:8000`

### 2. Test Authentication Flow
1. **Go to:** `/accounts/login/`
2. **Login** with your test account
3. **Expected:** Redirect to home page after login
4. **Verify:** You're now authenticated (can see profile menu)

### 3. Test Dashboard Access
1. **Navigate to:** `http://localhost:8000/billing/dashboard/`
2. **Expected:** 
   - ✅ Page loads without 404 error
   - ✅ Shows "No active subscription" message (if first time)
   - ✅ Contains dashboard layout
3. **Check browser console:** No JavaScript errors

### 4. Test Subscription Creation
If you have a test subscription:

1. **Navigate to:** `http://localhost:8000/billing/subscription/`
2. **Expected:**
   - ✅ Page loads
   - ✅ Shows subscription details
   - ✅ Shows current plan
   - ✅ Shows cancel/change options

### 5. Test Invoices Page
1. **Navigate to:** `http://localhost:8000/billing/invoices/`
2. **Expected:**
   - ✅ Page loads
   - ✅ Shows invoice list (empty is OK)
   - ✅ Table headers visible
   - ✅ Pagination works (if multiple invoices)

### 6. Test Invoice Detail
If you have invoices:

1. **Click an invoice** in the list
2. **Expected:**
   - ✅ Detail page loads
   - ✅ Shows invoice number, date, amount
   - ✅ Shows line items
   - ✅ Shows payment status
   - ✅ Download PDF button works (or shows)

### 7. Test Payment Method Page
1. **Navigate to:** `http://localhost:8000/billing/payment-method/`
2. **Expected:**
   - ✅ Page loads
   - ✅ Form displays
   - ✅ Can enter card details (test mode)
   - ✅ Form submits correctly

### 8. Test Plan Change Page
1. **Navigate to:** `http://localhost:8000/billing/plan-change/`
2. **Expected:**
   - ✅ Page loads
   - ✅ Shows available plans
   - ✅ Shows current plan highlighted
   - ✅ Comparison table visible
   - ✅ Can select new plan

---

## API Testing (15 minutes)

### 1. Get Authentication Token

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'
```

**Expected:** Returns `{"access":"<token>","refresh":"<token>"}`

Save the token:
```bash
TOKEN="<paste-token-here>"
```

### 2. Test List Subscriptions
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/subscriptions/
```

**Expected Response:**
```json
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "user": 1,
      "plan": "Pro",
      "status": "active",
      "current_period_start": "2026-01-01T00:00:00Z",
      "current_period_end": "2026-02-01T00:00:00Z",
      ...
    }
  ]
}
```

### 3. Test Get Subscription Detail
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/subscriptions/1/
```

**Expected:** Returns single subscription object with all fields

### 4. Test Create Subscription
```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": 1,
    "payment_method": 1
  }'
```

**Expected:** 
```json
{
  "id": 2,
  "status": "active",
  ...
}
```

### 5. Test List Invoices
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/invoices/
```

**Expected:** Returns list of invoices

### 6. Test Get Invoice Detail
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/invoices/1/
```

**Expected:** Returns invoice with line items and payment info

### 7. Test Change Plan
```bash
curl -X POST http://localhost:8000/api/subscriptions/1/change_plan/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": 2,
    "proration": "calculate"
  }'
```

**Expected:** Returns updated subscription

### 8. Test Cancel Subscription
```bash
curl -X POST http://localhost:8000/api/subscriptions/1/cancel/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"too_expensive"}'
```

**Expected:** Returns subscription with `status: "cancelled"`

### 9. Test Suspend (Admin Only)
```bash
curl -X POST http://localhost:8000/api/subscriptions/1/suspend/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"days": 30}'
```

**Expected:** Returns subscription with `status: "suspended"`

### 10. Test Unauthorized Access
```bash
# Without token
curl http://localhost:8000/api/subscriptions/

# Without proper auth
curl -H "Authorization: Bearer invalid-token" \
  http://localhost:8000/api/subscriptions/
```

**Expected:** 
```json
{"detail":"Authentication credentials were not provided."}
```

---

## Form Validation Testing (10 minutes)

### 1. Payment Method Form
```bash
# Missing required fields
curl -X POST http://localhost:8000/billing/payment-method/ \
  -d '{}'

# Should show validation errors
```

### 2. Plan Change Form
```bash
# Invalid plan
curl -X POST http://localhost:8000/billing/plan-change/ \
  -d '{
    "new_plan": 999,
    "billing_cycle": "invalid"
  }'
```

### 3. Cancel Subscription Form
```bash
# Valid cancel request
curl -X POST http://localhost:8000/billing/subscription/ \
  -d '{
    "action": "cancel",
    "reason": "too_expensive"
  }'
```

---

## Permission Testing (10 minutes)

### 1. Unauthenticated Access
```bash
# Should redirect to login
curl http://localhost:8000/billing/dashboard/
```

**Expected:** 302 redirect to login

### 2. Cross-Tenant Access
```bash
# Get subscriptions as user A
TOKEN_A="<tokenforUserA>"

# Get subscription from tenant B (should fail)
curl -H "Authorization: Bearer $TOKEN_A" \
  http://localhost:8000/api/subscriptions/?tenant=tenant_b
```

**Expected:** Returns only subscriptions for user's tenant

### 3. Admin-Only Access
```bash
# As regular user
curl -H "Authorization: Bearer $USER_TOKEN" \
  http://localhost:8000/api/subscriptions/1/suspend/ \
  -X POST -d '{"days": 30}'
```

**Expected:** 403 Forbidden (can't suspend as regular user)

```bash
# As admin
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/subscriptions/1/suspend/ \
  -X POST -d '{"days": 30}'
```

**Expected:** 200 OK, subscription suspended

---

## Error Handling Testing (5 minutes)

### 1. 404 Errors
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/subscriptions/999999/
```

**Expected:**
```json
{"detail":"Not found."}
```

### 2. 400 Bad Request
```bash
curl -X POST http://localhost:8000/api/subscriptions/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"invalid_field": "value"}'
```

**Expected:**
```json
{"plan":["This field is required."]}
```

### 3. 500 Server Error
Should not happen, but if it does:
```
Check: /wasla/logs/error.log
Or: Django console output
```

---

## Performance Testing (Optional)

### Check Query Optimization
```bash
# Enable query logging
# Add to Django shell:
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as context:
    # Your test here
    print(f"{len(context.captured_queries)} queries")
```

### Load Testing
```bash
# Install: pip install locust

# Create locustfile.py with:
from locust import HttpUser, task

class BillingUser(HttpUser):
    @task
    def dashboard(self):
        self.client.get("/billing/dashboard/")
    
    @task
    def api_list(self):
        headers = {"Authorization": f"Bearer {TOKEN}"}
        self.client.get("/api/subscriptions/", headers=headers)

# Run: locust -f locustfile.py
```

---

## Checklist - Success Criteria

### Web Interface
- [ ] Dashboard loads
- [ ] Subscription detail loads
- [ ] Invoice list loads
- [ ] Invoice detail loads
- [ ] Payment method page loads
- [ ] Plan change page loads
- [ ] Admin dashboard loads (staff only)
- [ ] Form submissions work
- [ ] Permissions enforced

### REST APIs
- [ ] List subscriptions works
- [ ] Create subscription works
- [ ] Get subscription detail works
- [ ] Update subscription works
- [ ] Delete/cancel subscription works
- [ ] Change plan works
- [ ] List invoices works
- [ ] Get invoice detail works
- [ ] Payment methods work
- [ ] Unauthorized access blocked
- [ ] Cross-tenant access blocked

### Error Handling
- [ ] 404 errors return proper messages
- [ ] 400 validation errors show details
- [ ] 403 permission errors work
- [ ] 500 errors are logged

### Data Validation
- [ ] Required fields enforced
- [ ] Email validation works
- [ ] Date validation works
- [ ] Amount validation works
- [ ] Plan selection validation works

---

## Troubleshooting

### Issue: 404 Not Found on `/billing/dashboard/`

**Solution:**
```bash
# 1. Check URLs registered
python manage.py show_urls | grep billing

# 2. Should see:
# /billing/ ...
# /api/subscriptions/ ...

# 3. If missing, check config/urls.py line 19:
# path("billing/", include(("apps.subscriptions.urls_web", ...

# 4. If present, reload Django
# Stop dev server and restart
```

### Issue: ImportError in views_web.py

**Solution:**
```bash
# Check imports in views_web.py line 15-20
# Should be:
# from .models_billing import ...
# from .services_billing import ...

# If wrong, fix imports
```

### Issue: ImportError in forms.py

**Solution:**
```bash
# Check imports in forms.py line 14
# Should be:
# from .models_billing import ...

# If wrong, fix imports
```

### Issue: Migrations Not Applied

**Solution:**
```bash
# Check migration status
python manage.py showmigrations subscriptions

# If 0002_automated_recurring_billing is not [x]
python manage.py migrate subscriptions

# Verify
python manage.py showmigrations subscriptions
```

### Issue: No Active Subscription

**Expected!** This is normal for new users.

**To create test subscription:**
```bash
python manage.py shell
>>> from wasla.apps.subscriptions.models_billing import Subscription, SubscriptionPlan
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.first()
>>> plan = SubscriptionPlan.objects.first()
>>> sub = Subscription.objects.create(user=user, plan=plan)
>>> print(f"Created subscription {sub.id}")
>>> exit()
```

Then navigate to `/billing/dashboard/` to see it.

---

## Next Steps After Testing

If all tests pass ✅:
1. **Document findings** in testing report
2. **Fix any failures** identified
3. **Proceed to Phase 3c remaining work** from checklist
4. **Implement webhook validation** (most critical)
5. **Fix email context URLs**

If tests fail ❌:
1. **Identify specific failure** using this guide
2. **Check logs** for stack traces
3. **Verify fixes** from this session were applied
4. **Report issues** with exact error messages

---

**Happy Testing!** 🚀

