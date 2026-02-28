"""
Tenant Isolation Integration Checklist - Implementation Priority

This document provides the step-by-step order to integrate the tenant isolation
hardening into production. Follow this checklist sequentially.
"""

# ============================================================================
# PHASE 0: SETUP & VALIDATION (30 minutes)
# ============================================================================

## 0.1 Deploy Core Tenant Security Files
Status: [_] Not Started [_] In Progress [_] Complete

Files to deploy:
□ /wasla/apps/tenants/querysets.py (280 lines)
  - Contains: TenantQuerySet, TenantManager, TenantProtectedModel, get_object_for_tenant()
  - Deployment: No config changes needed
  - Testing: Import verification only

□ /wasla/apps/tenants/security_middleware.py (170 lines)
  - Contains: TenantSecurityMiddleware, TenantContextMiddleware, TenantAuditMiddleware
  - Deployment: Add to settings.MIDDLEWARE (see 0.3)
  - Testing: No validation errors expected

□ /wasla/apps/tenants/tests_tenant_isolation.py (600 lines)
  - Contains: 25+ test cases for isolation verification
  - Deployment: No config changes
  - Testing: Should pass completely

## 0.2 Update Django Settings
Status: [_] Not Started [_] In Progress [_] Complete

File: /wasla/config/settings.py

Add to MIDDLEWARE (after AuthenticationMiddleware):

```python
MIDDLEWARE = [
    # ... existing middleware ...
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    
    # ADD THESE THREE (in order):
    'apps.tenants.security_middleware.TenantSecurityMiddleware',    # NEW
    'apps.tenants.security_middleware.TenantContextMiddleware',     # NEW
    'apps.tenants.security_middleware.TenantAuditMiddleware',       # NEW
    
    # ... rest of middleware ...
]
```

Add tenant isolation settings:

```python
# Tenant Isolation Configuration
TENANT_REQUIRED_PATHS = [
    '/api/',
    '/admin/',
    '/dashboard/',
]

TENANT_OPTIONAL_PATHS = [
    '/health/',
    '/api/health/',
]

TENANT_BYPASS_SUPERADMIN = True
TENANT_AUDIT_LOG_LEVEL = 'INFO'  # or 'DEBUG'
```

## 0.3 Verify Test Environment
Status: [_] Not Started [_] In Progress [_] Complete

Commands to run:

```bash
# Verify files exist
ls -la /wasla/apps/tenants/querysets.py
ls -la /wasla/apps/tenants/security_middleware.py
ls -la /wasla/apps/tenants/tests_tenant_isolation.py

# Run basic import test
python manage.py shell -c "
from apps.tenants.querysets import TenantProtectedModel, TenantManager
from apps.tenants.security_middleware import TenantSecurityMiddleware
print('✓ All imports successful')
"

# Run isolation tests (should have 25+ test cases)
python manage.py test apps.tenants.tests_tenant_isolation -v 2
```

Expected results:
- ✓ All files present and importable
- ✓ Isolation test suite passes completely
- ✓ No import errors in security middleware


# ============================================================================
# PHASE 1: MODEL MIGRATION (2 days)
# ============================================================================

## 1.1 Priority 1 Models - CRITICAL DATA
Status: [_] Not Started [_] In Progress [_] Complete

These models must be hardened FIRST - they are attack surfaces for cross-tenant data leakage.

### Model: apps.stores.models.Store
File: /wasla/apps/stores/models.py

Current structure:
```python
class Store(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    objects = TenantManager()
```

Tasks:
□ Edit /wasla/apps/stores/models.py
  - Line: Find `class Store(models.Model):`
  - Change to: `class Store(TenantProtectedModel, models.Model):`
  - Add import: `from apps.tenants.querysets import TenantProtectedModel, TenantManager`
  
□ Update Meta class:
  - Add TENANT_FIELD = 'tenant' to Meta
  - Add database index for efficient querying

□ Verify existing code works:
```bash
python manage.py makemigrations stores
python manage.py migrate stores
python manage.py test apps.stores.tests_store_tests
```

### Model: apps.orders.models.Order
File: /wasla/apps/orders/models.py

Current structure:
```python
class Order(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    objects = TenantManager()
```

Same steps as Store:
□ Update base classes
□ Update imports
□ Add TENANT_FIELD
□ Add indexes
□ Run migrations
□ Run tests

### Model: apps.subscriptions.models.Subscription
File: /wasla/apps/subscriptions/models.py

Note: This is part of the new subscription system we built.
Same hardening steps:
□ Update base classes
□ Update imports
□ Add TENANT_FIELD = 'subscription_plan'  (or relevant FK field)
□ Add indexes
□ Run migrations
□ Run tests

Expected migration output:
```
No migrations to make. 'stores' is already up-to-date.
✓ All existing queries validated
```

## 1.2 Priority 2 Models - HIGH RISK
Status: [_] Not Started [_] In Progress [_] Complete

Models to update during week 2:
- [ ] apps.customers.models.Customer
- [ ] apps.catalog.models.Product
- [ ] apps.catalog.models.ProductVariant
- [ ] apps.cart.models.Cart
- [ ] apps.cart.models.CartItem
- [ ] apps.checkout.models.Checkout
- [ ] apps.checkout.models.CheckoutItem

For each model:
□ Update base classes: TenantProtectedModel
□ Update manager: TenantManager
□ Add TENANT_FIELD
□ Add database indexes
□ Run migrations
□ Run tests

Estimated time: 2-3 hours per model
Total for Phase 1.2: 1 day

## 1.3 Priority 3 Models - BUSINESS LOGIC
Status: [_] Not Started [_] In Progress [_] Complete

Models to update during week 3:
- [ ] apps.reviews.models.Review
- [ ] apps.analytics.models.*
- [ ] apps.notifications.models.*
- [ ] apps.wallet.models.*

Same hardening process as above.
Estimated time: 1 day


# ============================================================================
# PHASE 2: VIEW LAYER HARDENING (1.5 days)
# ============================================================================

## 2.1 REST API Endpoints - CRITICAL
Status: [_] Not Started [_] In Progress [_] Complete

Goal: All REST API endpoints must validate tenant scope

File: /wasla/apps/stores/views.py (Example)

Pattern:
```python
# BEFORE
class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
```

```python
# AFTER
class StoreViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            raise PermissionDenied('Tenant context required')
        return Store.objects.for_tenant(tenant)
```

Models needing API view hardening (in priority order):
□ apps.stores.views_api.StoreViewSet
□ apps.orders.views.OrderViewSet
□ apps.subscriptions.views_billing.SubscriptionViewSet
□ apps.customers.views.CustomerViewSet
□ apps.catalog.views.ProductViewSet
□ apps.cart.views.CartViewSet
□ apps.checkout.views.CheckoutViewSet

For each ViewSet:
□ Override get_queryset()
□ Add tenant context extraction
□ Add validation/permission check
□ Use .for_tenant(tenant) on all queries
□ Add error handling

Estimated time: 30 minutes per ViewSet
Total: 3.5 hours

## 2.2 Web Views (Django Templates)
Status: [_] Not Started [_] In Progress [_] Complete

Goal: All web views must validate tenant context

Affected files:
□ apps.stores.views_web.py (store dashboard, settings)
□ apps.orders.views_web.py (order list, detail)
□ apps.subscriptions.views_web.py (subscription management)
□ apps.catalog.views_web.py (product browse)
□ apps.cart.views_web.py (cart management)

For each view:
```python
# BEFORE
def store_dashboard(request):
    stores = Store.objects.all()  # VULNERABLE

# AFTER
def store_dashboard(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        raise Http404('Store context required')
    stores = Store.objects.for_tenant(tenant)
```

Estimated time: 20 minutes per view
Total: 2 hours

## 2.3 Admin Interface
Status: [_] Not Started [_] In Progress [_] Complete

Goal: Admin interface must enforce tenant scoping

File: /wasla/apps/stores/admin.py (Example)

Pattern:
```python
# BEFORE
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request)

# AFTER
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = Store.objects.unscoped_for_migration()
        
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'tenant'):
            qs = qs.for_tenant(request.user.tenant)
        
        return qs
```

Admin classes to update:
□ stores.StoreAdmin
□ orders.OrderAdmin
□ subscriptions.SubscriptionAdmin
□ customers.CustomerAdmin
□ catalog.ProductAdmin
□ payments.PaymentAdmin
□ settlements.SettlementAdmin

Estimated time: 15 minutes per admin class
Total: 1.75 hours


# ============================================================================
# PHASE 3: TESTING & VALIDATION (1.5 days)
# ============================================================================

## 3.1 Unit Tests
Status: [_] Not Started [_] In Progress [_] Complete

Create isolation tests for each model:

File: /wasla/apps/stores/tests_isolation.py (New)

```python
class StoreIsolationTests(TestCase):
    def setUp(self):
        self.tenant1 = Tenant.objects.create(slug='t1')
        self.tenant2 = Tenant.objects.create(slug='t2')
        self.store1 = Store.objects.create(tenant=self.tenant1, name='S1')
        self.store2 = Store.objects.create(tenant=self.tenant2, name='S2')
    
    def test_unscoped_query_fails(self):
        with self.assertRaises(ValidationError):
            Store.objects.all()
    
    def test_scoped_query_works(self):
        self.assertEqual(
            Store.objects.for_tenant(self.tenant1).count(),
            1
        )
    
    def test_cross_tenant_blocked(self):
        self.assertFalse(
            Store.objects.for_tenant(self.tenant1)
                .filter(id=self.store2.id)
                .exists()
        )
```

Test files to create/update:
□ apps/stores/tests_isolation.py
□ apps/orders/tests_isolation.py
□ apps/subscriptions/tests_isolation.py
□ apps/customers/tests_isolation.py
□ apps/catalog/tests_isolation.py
□ apps/cart/tests_isolation.py
□ apps/checkout/tests_isolation.py

Run all tests:
```bash
python manage.py test apps.stores.tests_isolation
python manage.py test apps.orders.tests_isolation
python manage.py test apps.subscriptions.tests_isolation
# ... etc
```

Expected: All tests PASS
Estimated time: 2 hours total

## 3.2 Integration Tests
Status: [_] Not Started [_] In Progress [_] Complete

Test complete workflows:

```python
class StoreWorkflowIsolationTests(TestCase):
    def test_create_order_for_store(self):
        tenant = Tenant.objects.create(slug='test')
        store = Store.objects.create(tenant=tenant, name='Store')
        
        # Create order must assign correct tenant
        order = Order.objects.create(
            tenant=tenant,
            store=store,
            customer='...
        )
        
        # Verify isolation
        other_tenant = Tenant.objects.create(slug='other')
        self.assertFalse(
            Order.objects.for_tenant(other_tenant)
                .filter(id=order.id)
                .exists()
        )
```

Estimated time: 2 hours
Expected: 95%+ test pass rate

## 3.3 API Endpoint Tests
Status: [_] Not Started [_] In Progress [_] Complete

Test API security:

```python
class StoreAPIIsolationTests(APITestCase):
    def test_api_respects_tenant_scope(self):
        tenant1 = Tenant.objects.create(slug='t1')
        tenant2 = Tenant.objects.create(slug='t2')
        
        store1 = Store.objects.create(tenant=tenant1, name='S1')
        store2 = Store.objects.create(tenant=tenant2, name='S2')
        
        user1 = User.objects.create_user(username='u1')
        user1.tenant = tenant1
        user1.save()
        
        # User from tenant1 should NOT see store from tenant2
        self.client.force_authenticate(user1)
        response = self.client.get(f'/api/stores/{store2.id}/')
        self.assertEqual(response.status_code, 404)
```

Estimated time: 1.5 hours
Expected: All endpoints properly scoped


# ============================================================================
# PHASE 4: DEPLOYMENT & MONITORING (1 day)
# ============================================================================

## 4.1 Pre-Deployment Checklist
Status: [_] Not Started [_] In Progress [_] Complete

Before deploying to production:

□ All tests passing (run full suite):
  python manage.py test --no-migrations

□ No unscoped query references:
  grep -r "\.objects\.all()" apps/ | grep -v "for_tenant" | grep -v test

□ All models use TenantProtectedModel:
  Check each model in hardening checklist

□ All views use tenant context:
  Check each view function

□ Settings updated:
  grep -l "TenantSecurityMiddleware" config/settings.py

□ Database migrations up to date:
  python manage.py showmigrations

## 4.2 Staging Deployment
Status: [_] Not Started [_] In Progress [_] Complete

Deploy to staging environment:

□ Deploy core isolation files
□ Update Django settings with middleware
□ Run migrations
□ Run full test suite
□ Load test with multiple concurrent tenants
□ Monitor error logs for validation errors
□ Monitor 403 response rates

Expected results:
- Zero import errors
- All tests pass
- No unexpected validation errors
- Normal 403 rate (only unscoped queries)

Testing checklist:
□ Create 3+ tenants
□ Create stores, orders, etc. in each
□ Test that data isolation works
□ Test that admin sees correct data
□ Test API endpoints
□ Test web views

Duration: 4 hours

## 4.3 Production Deployment (Staged Rollout)
Status: [_] Not Started [_] In Progress [_] Complete

Deploy in stages (NEVER all at once):

**Stage 1: Core Framework (Day 1)**
□ Deploy querysets.py
□ Deploy security_middleware.py
□ Deploy tests_tenant_isolation.py
□ Update settings.py
□ Monitor for errors (should be zero)
□ Monitor for 403 responses (should be zero - no models updated yet)

**Stage 2: Priority 1 Models (Day 2)**
□ Update Store, Order, Subscription models
□ Deploy model changes
□ Run migrations on production:
  python manage.py migrate stores
  python manage.py migrate orders
  python manage.py migrate subscriptions
□ Monitor error logs closely
□ Run health checks

Expected: Increased 403 errors (expected)

**Stage 3: Model Validation (Days 3-4)**
□ Fix any validation errors in logging
□ Update views as needed
□ Deploy view/serializer updates
□ Update API endpoints
□ Test all endpoints thoroughly

**Stage 4: Complete Rollout (Days 5-7)**
□ Update Priority 2 models
□ Update Priority 3 models
□ Complete view migration
□ Run comprehensive tests
□ Monitor all metrics

## 4.4 Monitoring & Alerts
Status: [_] Not Started [_] In Progress [_] Complete

Set up monitoring for:

Error Rate Monitoring:
□ Track ValidationError rate (should be zero after Phase 1)
□ Track 403 Forbidden rate (monitor for spikes)
□ Track 404 responses (monitor for issues)
□ Alert if any unscoped query ValidationError occurs

Performance Monitoring:
□ Monitor query count (should decrease after indexes added)
□ Monitor response times (should stay same or improve)
□ Monitor database load

Security Monitoring:
□ Track superadmin bypass usage (should be rare)
□ Track permission denied responses
□ Track cross-tenant attempts
□ Create security dashboard

Logging setup:
```python
import logging

logger = logging.getLogger('tenant.security')

# Monitor unscoped queries
logger.error(f"Unscoped query attempt: {e}")

# Monitor permission denials
logger.warning(f"Permission denied: {user} accessing {tenant}")

# Monitor bypasses
logger.info(f"Superadmin bypass: {user} on {model}")
```


# ============================================================================
# PHASE 5: POST-DEPLOYMENT (Ongoing)
# ============================================================================

## 5.1 First Week Post-Deployment
Status: [_] Not Started [_] In Progress [_] Complete

Daily checklist:
□ Review error logs for validation errors
□ Check 403 response rate (normal for this phase)
□ Verify no unexpected data anomalies
□ Run weekly test suite

Weekly metrics to review:
□ Validation errors by model type
□ API response times (compare to baseline)
□ Database query counts (should be lower)
□ User complaints / incidents

## 5.2 Remaining Model Migration
Status: [_] Not Started [_] In Progress [_] Complete

Continue hardening remaining models:

Week 2:
□ Update Priority 2 models (Customer, Product, Cart, Checkout)
□ Update related views
□ Test and deploy

Week 3:
□ Update Priority 3 models
□ Update supporting code
□ Final testing

Week 4:
□ Audits and security review
□ Performance optimization
□ Document lessons learned

## 5.3 Ongoing Security Audits
Status: [_] Not Started [_] In Progress [_] Complete

Monthly:
□ Review new code for tenant isolation compliance
□ Audit admin interface queries
□ Check for new unscoped query patterns
□ Update documentation

Quarterly:
□ Full security audit of all models/views
□ Load testing with tenant isolation active
□ Penetration test cross-tenant access
□ Update threat model


# ============================================================================
# ROLLBACK PLAN (If Needed)
# ============================================================================

If critical issues occur:

Immediate (< 5 min):
□ Disable TenantSecurityMiddleware in settings
  - Comment out the 3 middleware lines
  - Restart app servers
  - This allows unscoped queries during emergency

Short-term (5-30 min):
□ Revert model changes to previous version
□ Revert view changes to previous version
□ Run migrations backward if needed:
  python manage.py migrate apps.stores 0001  # Rollback to before change

Long-term:
□ Investigate root cause
□ Fix in development
□ Re-test thoroughly
□ Redeploy with fixes

Rollback testing (should run weekly in production):
□ Verify rollback procedure works
□ Verify data integrity after rollback
□ Verify app functions without isolation layer


# ============================================================================
# SUCCESS CRITERIA
# ============================================================================

Deployment is successful when:

✓ All 25+ isolation tests pass consistently
✓ No ValidationError in production logs
✓ 403 response rate < 1% (only cross-tenant attempts blocked)
✓ API response times unchanged or faster
✓ Database query count reduced by 10-20%
✓ Zero cross-tenant data leakage incidents
✓ All models using TenantProtectedModel
✓ All views enforcing tenant scope
✓ All APIs returning tenant-scoped data
✓ Admin interface showing only user's tenant data
✓ Zero security audit failures
✓ Team trained on new patterns

Timeline: 2-3 weeks for full production rollout
Maintenance: 1 developer, 4 hours/week for ongoing hardening
