# Quick Command Reference - Caching & Observability Stack

## Deployment Commands

```bash
# 1. Apply migrations
python manage.py migrate observability

# 2. Check Redis (optional, if using Redis)
python manage.py check_redis_cache

# 3. Run performance benchmark
python manage.py check_performance --json --save-report

# 4. Restart app
systemctl restart wasla
# OR for dev:
python manage.py runserver
```

---

## Cache API (In Code)

```python
from apps.core.cache import cache_get, cache_set, cache_delete, make_cache_key

# Get
data = cache_get("product_list", store_id=request.store.id)

# Set
cache_set("product_list", data, store_id=request.store.id, ttl=600)

# Delete
cache_delete("product_list", store_id=request.store.id)

# Manual key construction
key = make_cache_key("custom:key", store_id=1)
```

---

## Admin Dashboard

**URL**: `/admin-portal/performance/`

**KPIs**: 
- Total requests
- Avg response time (ms)
- Avg DB queries

**Tables**:
- Slowest endpoints (24h)
- Avg by endpoint
- Query trends
- Recent logs (filterable)

---

## Monitoring

### View Performance Logs (Django Shell)
```python
from apps.observability.models import PerformanceLog

# Slowest requests in last hour
from datetime import timedelta
from django.utils import timezone

one_hour_ago = timezone.now() - timedelta(hours=1)
slow = PerformanceLog.objects.filter(
    created_at__gte=one_hour_ago,
    duration_ms__gte=500
).order_by("-duration_ms")[:10]

for log in slow:
    print(f"{log.path} took {log.duration_ms}ms (queries: {log.query_count})")

# Cache hit rate
total = PerformanceLog.objects.count()
hits = PerformanceLog.objects.filter(cache_status="HIT").count()
print(f"Hit rate: {hits}/{total} = {100*hits/total:.1f}%")

# Slowest endpoint
from django.db.models import Avg
by_path = PerformanceLog.objects.values("path").annotate(
    avg_ms=Avg("duration_ms")
).order_by("-avg_ms")[:1]
print(by_path)
```

### View Benchmark Reports
```python
from apps.observability.models import PerformanceReport

# Latest report
latest = PerformanceReport.objects.latest("created_at")
print(f"Generated: {latest.created_at}")
print(latest.endpoint, latest.avg_duration_ms, "ms")
```

### Real-Time Log Tail
```bash
# Dev server with JSON logs
tail -f logs/performance.json | python -m json.tool

# Filter slowness
grep "is_slow.*true" logs/performance.json

# Count by endpoint
jq '.path' logs/performance.json | sort | uniq -c | sort -rn
```

---

## Environment Variables

```bash
# Required if using Redis
CACHE_BACKEND=django_redis.cache.RedisCache
CACHE_LOCATION=redis://127.0.0.1:6379/1

# TTL settings (in seconds)
CACHE_TTL_DEFAULT=300      # 5 min (products, listings)
CACHE_TTL_SHORT=60         # 1 min (permissions, auth)
CACHE_TTL_LONG=3600        # 1 hour (store config)

# Performance monitoring
PERFORMANCE_SLOW_REQUEST_MS=500    # Mark as slow if > this
PERFORMANCE_MIDDLEWARE_ENABLED=true

# Optional
DEBUG_CACHE_OPERATIONS=false       # Verbose logging
CACHE_KEY_PREFIX=wasla_prod_       # For multi-deploy scenarios
```

---

## Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| Cache not working | Redis running? | `redis-cli ping` |
| 500 error on startup | Logs in LOGGING config | Ensure indent correct in settings.py |
| Admin dashboard empty | Requests made since migration? | Make test API call to populate logs |
| Slow invalidation | Too many cache keys? | Use namespace versioning instead |
| High memory (Redis) | TTL too long? | Reduce CACHE_TTL_DEFAULT |
| Cache not clearing | Signal not registered? | Check apps/observability/signals.py |

---

## Configuration Locations

| Setting | File | Line Range |
|---------|------|-----------|
| Cache backend | `config/settings.py` | CACHES = {...} |
| Middleware | `config/settings.py` | MIDDLEWARE = [...] |
| Logging | `config/settings.py` | LOGGING = {...} |
| Performance settings | `config/settings.py` | PERFORMANCE_* |
| Admin route | `apps/admin_portal/urls.py` | path('performance/', ...) |
| Dashboard view | `apps/admin_portal/views.py` | performance_monitoring_view() |
| Cache service | `apps/core/cache.py` | cache_get(), cache_set(), ... |
| Invalidation | `apps/observability/signals.py` | @receiver decorators |
| Middleware class | `apps/observability/middleware/timing.py` | PerformanceMiddleware |

---

## Files Modified Summary

| File | Change | Impact |
|------|--------|--------|
| `config/settings.py` | Added CACHES, LOGGING, middleware | Global setup |
| `apps/observability/models.py` | Added PerformanceLog, PerformanceReport | DB schema (migrations) |
| `apps/observability/apps.py` | Added signal import | Django startup |
| `apps/observability/signals.py` | New file: invalidation handlers | Auto cache clearing |
| `apps/observability/middleware/timing.py` | PerformanceMiddleware | Request timing |
| `apps/core/cache.py` | New file: cache API | Developer interface |
| `core/infrastructure/store_cache.py` | Namespace versioning | Atomic invalidation |
| `apps/tenants/interfaces/web/storefront_views.py` | Added cache wrap | Product list caching |
| `apps/cart/application/use_cases/get_product.py` | Added cache wrap | Product detail caching |
| `apps/catalog/api.py` | Added cache wrap | Variant price API caching |
| `apps/security/rbac.py` | Added cache wrap | Permission caching |
| `apps/admin_portal/urls.py` | Added /performance/ route | Admin dashboard |
| `apps/admin_portal/views.py` | Added performance_monitoring_view | Dashboard view |
| `templates/admin_portal/performance/dashboard.html` | New file: dashboard template | Admin UI |

---

## Zero-Downtime Deploy Steps

```bash
# 1. Pre-deploy validation
python manage.py check
python manage.py migrate --plan observability

# 2. Deploy (blue-green or rolling restart)
# - New code deployed
# - Migrations applied: python manage.py migrate observability
# - Graceful restart (workers process in-flight requests)

# 3. Warm cache (optional, post-deploy)
python manage.py check_performance --save-report

# 4. Verify
curl https://your-app/admin-portal/performance/
# Verify admin dashboard loads without 404/500

# 5. Monitor
tail -f logs/performance.json
# Watch for errors in structured logs
```

---

## Rollback Steps (if needed)

```bash
# Option 1: Disable caching (keep app running)
# Edit config/settings.py, change:
# CACHES['default']['BACKEND'] to 'django.core.cache.backends.dummy.DummyCache'
# No restart needed; requests will skip cache

# Option 2: Disable middleware (keep caching)
# Edit config/settings.py, remove or comment:
# 'apps.observability.middleware.timing.PerformanceMiddleware'
# Restart app

# Option 3: Full database rollback
python manage.py migrate observability zero

# Option 4: Git revert
git revert <commit-sha> --no-edit
git push
# Restart app
```

---

## Performance Tuning

### Reduce Query Count
```python
# NO: N+1 queries
for product in products:
    print(product.category.name)  # Query per item!

# YES: Prefetch
from django.db.models import prefetch_related_objects
prefetch_related_objects(products, "category")

# Cache it
cache_set("products_with_category", products, store_id=1, ttl=600)
```

### Reduce Cache Misses
```python
# Increase TTL for stable data
CACHE_TTL_LONG = 3600  # 1 hour for store config

# Warm cache on startup
from apps.core.cache import cache_set
cache_set("store_config", config, store_id=1, ttl=3600)
```

### Monitor Cache Efficiency
```python
# In Django shell:
from apps.observability.models import PerformanceLog
from django.db.models import Count

efficiency = PerformanceLog.objects.aggregate(
    total=Count("id"),
    hits=Count("id", filter=Q(cache_status="HIT")),
)
hit_rate = efficiency["hits"] / efficiency["total"]
print(f"Hit rate: {hit_rate:.1%}")

# Target: >70% hit rate on read-heavy endpoints
```

---

**[End of Quick Reference]**
