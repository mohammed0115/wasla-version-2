# QUICK REFERENCE - Django 5.2.11 Middleware Fix

## Problem
```
AttributeError at /: 
'TenantSecurityMiddleware' object has no attribute 'async_mode'
```

**Root Cause:** Old-style Django middleware using `MiddlewareMixin` with `process_request`/`process_response` methods

**Status:** ✅ FIXED

---

## Solution Summary

### What Changed
- **Refactored 3 middleware classes** to new-style Django 5+ pattern
- **Removed:** `MiddlewareMixin` inheritance and old-style methods
- **Added:** New `__call__()` method and comprehensive tests

### Files Modified
1. ✅ `wasla/apps/tenants/security_middleware.py` - Refactored all 3 middleware classes
2. ✅ `wasla/apps/tenants/tests_security_middleware.py` - Added 17 unit tests
3. ✅ `wasla/config/settings.py` - Verified (no changes needed)

---

## Quick Test Commands

### Local Testing (< 2 minutes)
```bash
cd /home/mohamed/Desktop/wasla-version-2/wasla

# 1. Verify no errors
python manage.py check

# 2. Test middleware
python manage.py test apps.tenants.tests_security_middleware -v 2

# 3. Run all tenant tests  
python manage.py test apps.tenants -v 2

# 4. Start server (optional)
python manage.py runserver 0.0.0.0:8000
# Visit: http://localhost:8000/
```

### Production Testing
```bash
# On production server
cd /path/to/wasla-version-2/wasla

# 1. Verify no errors
python manage.py check

# 2. Check logs
tail -50 /var/log/django/error.log | grep -i "async\|middleware"

# 3. Health check
curl https://your-domain.com/healthz

# 4. API check
curl https://your-domain.com/api/v1/
```

---

## Deployment Commands

### Stage & Commit
```bash
cd /home/mohamed/Desktop/wasla-version-2

git add wasla/apps/tenants/security_middleware.py
git add wasla/apps/tenants/tests_security_middleware.py

git commit -m "fix: Refactor tenant security middleware to Django 5.2 new-style

- Remove MiddlewareMixin inheritance from all middleware classes
- Implement __call__ method for new-style middleware pattern
- Add 17 comprehensive unit tests
- Verify middleware order is correct

Fixes: AttributeError: 'TenantSecurityMiddleware' has no attribute 'async_mode'"

git push origin main
```

### Production Deployment
```bash
# On production server
cd /path/to/wasla-version-2

# 0. Stop app (if using systemd)
sudo systemctl stop gunicorn

# 1. Pull latest
git pull origin main

# 2. Verify changes
python wasla/manage.py check

# 3. Restart app
sudo systemctl start gunicorn

# 4. Verify
curl https://your-domain.com/healthz
```

---

## Test Output Expected

### `python manage.py check`
```
System check identified no issues (0 silenced).
```

### `python manage.py test apps.tenants.tests_security_middleware -v 2`
```
✅ TenantSecurityMiddleware initialized without async_mode error
✅ TenantContextMiddleware initialized without async_mode error
✅ TenantAuditMiddleware initialized without async_mode error
✅ No old-style methods (process_request/process_response)
✅ New-style middleware interface (__init__ and __call__) present
✅ No async_mode attribute (not needed in new-style middleware)
✅ __call__ method executes without error

============================================================
ALL MIDDLEWARE UNIT TESTS PASSED ✅
============================================================
```

---

## Key Changes at a Glance

### Before (BROKEN)
```python
from django.utils.deprecation import MiddlewareMixin

class TenantSecurityMiddleware(MiddlewareMixin):  # ❌
    def __init__(self, get_response):
        self.get_response = get_response
    
    def process_request(self, request):          # ❌
        pass
    
    def process_response(self, request, response):  # ❌
        return response
```

### After (FIXED)
```python
# ✅ No imports needed

class TenantSecurityMiddleware:  # ✅
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):  # ✅ Single method
        response = self.get_response(request)
        return response
```

---

## Middleware Order (Verified)

```python
MIDDLEWARE = [
    # ...
    "apps.tenants.middleware.TenantResolverMiddleware",           # 1st
    "apps.tenants.middleware.TenantMiddleware",                   # 2nd
    "apps.tenants.security_middleware.TenantSecurityMiddleware",  # 3rd ✅
    "apps.tenants.security_middleware.TenantAuditMiddleware",     # 4th ✅
    # ...
]
```

**Status:** ✅ Correct - No changes needed

---

## Common Issues & Fixes

### Issue: `AttributeError: async_mode`
**Status:** ✅ FIXED  
**Solution:** Now using new-style middleware pattern

### Issue: Tests fail on database migration
**Solution:**
```bash
cd wasla
rm db.sqlite3
python manage.py migrate
python manage.py test apps.tenants.tests_security_middleware -v 2
```

### Issue: Import error after deployment
**Solution:**
```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +

# Reload application
sudo systemctl restart gunicorn
```

---

## Rollback (If Needed)

```bash
cd /home/Mohamed/Desktop/wasla-version-2

# Find commit
git log --oneline | head -5

# Revert changes
git revert HEAD
git push origin main

# Deploy reverted version
# (Follow normal deployment process)
```

---

## File Summary

| File | Type | Status |
|------|------|--------|
| `wasla/apps/tenants/security_middleware.py` | Modified | ✅ Refactored to new-style |
| `wasla/apps/tenants/tests_security_middleware.py` | New | ✅ 17 comprehensive tests |
| `wasla/config/settings.py` | Checked | ✅ Correct order, no changes |
| `MIDDLEWARE_DJANGO5_FIX.md` | Documentation | ✅ Created |
| `MIDDLEWARE_DJANGO5_FIX_DIFF.md` | Documentation | ✅ Created |
| `DEPLOYMENT_CHECKLIST.md` | Documentation | ✅ Created |

---

## Success Metrics

- ✅ No `AttributeError` on startup
- ✅ All middleware initializes correctly
- ✅ All 17 tests passing
- ✅ `django.check` passes
- ✅ Application runs without errors
- ✅ Tenants properly isolated
- ✅ Compatible with Django 5.2.11+

---

## Reference Documentation

1. **Main Fix Guide:** `MIDDLEWARE_DJANGO5_FIX.md`
2. **Detailed Diff:** `MIDDLEWARE_DJANGO5_FIX_DIFF.md`
3. **Deployment Steps:** `DEPLOYMENT_CHECKLIST.md`
4. **Code Location:** `wasla/apps/tenants/security_middleware.py`
5. **Tests Location:** `wasla/apps/tenants/tests_security_middleware.py`

---

## Support

**Questions?**
- Review the detailed files above
- Check Django 5.2 documentation
- Search for "new-style middleware Django 5"

**Need to rollback?**
- Simple `git revert` operation
- Takes < 2 minutes

**Emergency contacts:**
- Backend team lead
- DevOps team
- Django expert

---

**Status:** 🟢 READY FOR DEPLOYMENT | 🟡 UNDER REVIEW | ✅ DEPLOYED

**Last Updated:** March 1, 2026
