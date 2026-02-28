"""
Integration guide for hardened tenant isolation layer.

This document explains how to integrate the new security components
into your existing Django application.

========================================================================
QUICK START GUIDES (START HERE)
========================================================================

For step-by-step practical examples:
→ See: TENANT_HARDENING_QUICK_START.md
  - Shows BEFORE/AFTER code patterns
  - Model migration examples
  - View hardening patterns
  - Signal protection
  - Admin interface security
  - Test examples

For detailed integration checklist:
→ See: TENANT_HARDENING_INTEGRATION_CHECKLIST.md
  - Phase-by-phase deployment plan
  - Model priority levels
  - Exact file paths and line numbers
  - Time estimates for each task
  - Testing procedures
  - Monitoring setup
  - Rollback procedures
  - Success criteria

For core implementation files:
→ See: querysets.py (enforces tenant scoping)
→ See: security_middleware.py (validates requests)
→ See: tests_tenant_isolation.py (25+ integration tests)

========================================================================
"""

# ============================================================================
# 1. OVERVIEW & ARCHITECTURE
# ============================================================================

"""
The hardened tenant isolation layer consists of 3 core components:

1. QUERYSETS LAYER (querysets.py)
   - TenantQuerySet: Enforces .for_tenant() requirement
   - TenantManager: Wraps TenantQuerySet
   - TenantProtectedModel: Base class with save/delete validation
   - get_object_for_tenant(): Type-safe single object retrieval

2. MIDDLEWARE LAYER (security_middleware.py)
   - TenantSecurityMiddleware: Guards requests with missing tenant
   - TenantContextMiddleware: Validates tenant doesn't change mid-request
   - TenantAuditMiddleware: Logs all tenant access patterns

3. TESTING LAYER (tests_tenant_isolation.py)
   - 25+ test cases covering isolation scenarios
   - Unscoped query detection
   - Cross-tenant access prevention
   - Permission validation
   - Concurrent access safety
   - Attack scenario simulation

Integration Points:
- Django ORM models (inherit from TenantProtectedModel)
- Views/ViewSets (call .for_tenant() explicitly)
- API serializers (use context['tenant'])
- Admin interface (override get_queryset)
- Signals (validate tenant before processing)
- Cache layer (include tenant in cache key)

Security Model:
- Defense in depth: Multiple layers catch violations
- Fail-safe: Errors when tenant is missing/mismatched
- Audit trail: All access patterns logged
- Configuration-driven: Paths can require/bypass tenant

Expected Guarantees After Hardening:
✓ No unscoped queries execute (ValidationError raised)
✓ No cross-tenant data access (isolation enforced per query)
✓ No middleware bypass (request validation at entry point)
✓ No model save without tenant (TENANT_FIELD validation)
✓ All access audited (logging middleware)
✓ Superadmin can bypass safely (with audit trail)
"""


# ============================================================================
# 2. UPDATE DJANGO SETTINGS
# ============================================================================

# settings.py additions:
"""
# ============================================================================
# TENANT SECURITY SETTINGS
# ============================================================================

# Paths that require explicit tenant resolution
TENANT_REQUIRED_PATHS = {
    '/api/subscriptions/',
    '/api/orders/',
    '/api/invoices/',
    '/billing/',
    '/dashboard/',
    '/merchant/',
}

# Allow superadmin to bypass tenant checks (set to False for strict mode)
TENANT_BYPASS_SUPERADMIN = True

# Audit all tenant access
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'tenant_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/tenant_access.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'apps.tenants': {
            'handlers': ['tenant_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps.tenants.querysets': {
            'handlers': ['tenant_file'],
            'level': 'INFO',
        },
        'apps.tenants.security_middleware': {
            'handlers': ['tenant_file'],
            'level': 'INFO',
        },
    },
}

# Update MIDDLEWARE with security layers (order matters)
MIDDLEWARE = [
    # Security middleware BEFORE authentication
    'apps.tenants.security_middleware.TenantSecurityMiddleware',
    
    # Existing middleware
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    
    # Tenant context middleware
    'apps.tenants.middleware.TenantResolverMiddleware',
    'apps.tenants.middleware.TenantMiddleware',
    'apps.tenants.security_middleware.TenantContextMiddleware',
    'apps.tenants.security_middleware.TenantAuditMiddleware',
    
    # Internationalization AFTER tenant locale
    'apps.tenants.middleware.TenantLocaleMiddleware',
    'django.middleware.locale.LocaleMiddleware',
]
"""


# ============================================================================
# 3. MIGRATE EXISTING MODELS
# ============================================================================

"""
Step-by-step model migration to use new security layer:

Before (Current):
```python
from apps.tenants.managers import TenantManager

class Store(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    # ... other fields
    objects = TenantManager()
```

After (With Security):
```python
from apps.tenants.querysets import TenantManager, TenantProtectedModel

class Store(TenantProtectedModel, models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    # ... other fields
    objects = TenantManager()
    
    # Explicitly mark if this uses 'tenant' field
    TENANT_FIELD = 'tenant'
    
    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'slug']),
        ]
```

Migration Path:
1. Update managers in all tenant-scoped models
2. Add TenantProtectedModel as base
3. Add/update TENANT_FIELD if not 'tenant' or 'store'
4. Test with inclusion of tests_tenant_isolation.py
5. Run comprehensive test suite
"""


# ============================================================================
# 4. MODEL UPDATE CHECKLIST
# ============================================================================

"""
Models that MUST be updated:

Priority 1 (Critical - Direct tenant access):
✓ Store - /apps/stores/models.py
✓ Subscription - /apps/subscriptions/models_billing.py
✓ Invoice - /apps/subscriptions/models_billing.py
✓ Order - /apps/orders/models.py
✓ Product/Catalog - /apps/catalog/models.py

Priority 2 (High - Sensitive data):
✓ Customer - /apps/customers/models.py
✓ Category - /apps/catalog/models.py
✓ Review - /apps/reviews/models.py
✓ PaymentMethod - /apps/subscriptions/models_billing.py
✓ Cart - /apps/cart/models.py
✓ Checkout - /apps/checkout/models.py

Priority 3 (Medium - Business logic):
✓ Analytics - /apps/analytics/models.py
✓ Settings - various settings models
✓ Notifications - /apps/notifications/models.py
✓ Webhooks - /apps/webhooks/models.py
✓ Settlement - /apps/settlements/models.py

Models that are TENANT_AGNOSTIC:
- Tenant itself
- User/Auth models
- Global settings
- System logs

For each model update:
1. Add TenantProtectedModel as base BEFORE models.Model
2. Update manager to TenantManager
3. Add TENANT_FIELD if custom
4. Set TENANT_AGNOSTIC = True only if actually tenant-agnostic
5. Update all foreign keys to use get_object_for_tenant()
"""


# ============================================================================
# 5. UPDATE VIEWS & QUERYSETS
# ============================================================================

"""
Before (Current - Vulnerable):
```python
def get_store_orders(request):
    orders = Order.objects.filter(store=request.store)
    # Vulnerable: If request.store changes, could leak orders
```

After (Hardened):
```python
def get_store_orders(request):
    if not request.tenant:
        raise Http404()
    
    orders = Order.objects.for_tenant(request.tenant).filter(status='completed')
    # Safe: Order.objects.for_tenant() validates tenant scope
```

Rule: ALWAYS call .for_tenant() explicitly:
✓ GOOD: Order.objects.for_tenant(request.tenant).filter(...)
✓ GOOD: Order.objects.for_tenant(tenant_id).get(...)
✗ BAD:  Order.objects.all()
✗ BAD:  Order.objects.filter(tenant=X)  # Doesn't validate scope


For QuerySets:
- Replace all Model.objects.all() with Model.objects.for_tenant(tenant_id)
- Use get_object_for_tenant() helper for single object retrieval
- Add tenant_id validation in view before queries
"""


# ============================================================================
# 6. API ENDPOINT HARDENING
# ============================================================================

"""
All API endpoints must validate tenant:

from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def get_orders(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response(
            {'error': 'Tenant context required'},
            status=403
        )
    
    orders = Order.objects.for_tenant(tenant)
    # ... serialize and return
"""


# ============================================================================
# 7. TESTING STRATEGY
# ============================================================================

"""
Test all models with tests_tenant_isolation.py tests:

Run tests:
  python manage.py test apps.tenants.tests_tenant_isolation

Specific test classes:
  python manage.py test apps.tenants.tests_tenant_isolation.TenantUnscopedQueryTests
  python manage.py test apps.tenants.tests_tenant_isolation.TenantCrossTenantAccessTests
  python manage.py test apps.tenants.tests_tenant_isolation.TenantSecurityIntegrationTests

For each model:
1. Test unscoped query fails
2. Test for_tenant() works
3. Test cross-tenant returns empty
4. Test save() validates tenant
5. Test delete() validates tenant

Example model test:
```python
def test_custom_model_isolation(self):
    qs = CustomModel.objects.filter(name='test')
    with self.assertRaises(ValidationError):
        qs.count()
    
    # Should work with for_tenant
    qs = CustomModel.objects.for_tenant(self.tenant1)
    qs.filter(name='test').count()
```
"""


# ============================================================================
# 8. DEPLOYMENT STRATEGY
# ============================================================================

"""
Phase 1 (Week 1): Analysis
- Audit all models for tenant awareness
- Identify cross-tenant vulnerabilities
- Document tenant field names for each model

Phase 2 (Week 2): Core Infrastructure
- Deploy querysets.py security layer
- Update TenantManager in all models
- Deploy security_middleware.py
- Update Django settings

Phase 3 (Week 3): Model Migration
- Update Store and related models
- Run new test suite
- Test in staging environment

Phase 4 (Week 4): Verification
- Enable strict logging
- Monitor for ValidationError exceptions
- Test cross-tenant scenarios
- Performance test with load

Phase 5 (Ongoing): Hardening
- Update remaining models
- Migrate API endpoints
- Add rate limiting per tenant
- Implement audit logging to database

Zero-downtime deployment:
1. Deploy code (middleware is passive initially)
2. Gradually enable stricter checks:
   - Start with logging only (monitor errors)
   - Enable error responses for APIs
   - Enforce for web requests
   - Audit logs for compliance

Rollback plan:
- Keep old TenantManager available
- Feature flag for strict checking
- Ability to disable security middleware
"""


# ============================================================================
# 9. MONITORING & ALERTING
# ============================================================================

"""
Key metrics to monitor:

1. Cross-tenant access attempts:
   - Count ValidationError in queries
   - Alert if > 10 per minute

2. Unscoped query attempts:
   - Count from logs
   - Alert if increasing

3. Permission denied events:
   - Count 403 responses
   - Alert on spike

4. Tenant resolution failures:
   - Count missing tenant context
   - Alert if > 1% of requests

5. Superadmin bypass usage:
   - Log all unscoped_for_migration() calls
   - Alert on production use

Example monitoring query:
```sql
SELECT
    DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i') as minute,
    COUNT(*) as count,
    COUNT(DISTINCT user_id) as users
FROM tenant_access_audit
WHERE event_type = 'validation_error'
GROUP BY minute
HAVING count > 10
ORDER BY minute DESC;
```
"""


# ============================================================================
# 10. SECURITY BEST PRACTICES
# ============================================================================

"""
DO:
✓ Always call .for_tenant() before filtering
✓ Validate tenant in every view
✓ Use get_object_for_tenant() helper
✓ Log all cross-tenant attempts
✓ Test with multiple tenants in test suite
✓ Audit permission changes
✓ Review logs regularly
✓ Update tenant field when migrating users

DON'T:
✗ Trust request.tenant without validation
✗ Use .all() on tenant models
✗ Bypass tenant checks in custom querysets
✗ Cache queries without tenant key
✗ Share QuerySet objects between tenants
✗ Use database-level user permissions as only guard
✗ Assume superadmin access is safe

Common Mistakes:
✗ Caching: queryset = Model.objects.filter(city='NY')
  PROBLEM: Cache doesn't include tenant, leaks across tenants
  SOLUTION: Cache key must include tenant_id

✗ ORM shortcuts: obj = Model.objects.get(id=123)
  PROBLEM: Finds object from any tenant
  SOLUTION: obj = get_object_for_tenant(Model, tenant_id, id=123)

✗ Bulk operations: Model.objects.bulk_create([...])
  PROBLEM: Doesn't validate tenant
  SOLUTION: Validate tenant on each object before bulk_create
"""


# ============================================================================
# 11. TROUBLESHOOTING
# ============================================================================

"""
Issue: "Unscoped query on Model"
Solution: Call .for_tenant(tenant_id) before filtering

Issue: ValidationError on model save
Solution: Ensure tenant field is populated before save

Issue: Empty QuerySet with valid data
Solution: Verify for_tenant() is called with correct tenant ID

Issue: Middleware blocking valid requests
Solution: Check TENANT_REQUIRED_PATHS and TENANT_OPTIONAL_PATHS config

Issue: Performance degradation
Solution: Add database indexes on (tenant, status/id) for filtered queries

Debug queries:
```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as context:
    stores = Store.objects.for_tenant(tenant_id)
    print(context.captured_queries)
```
"""
