# Deployment Checklist - Django 5.2 Middleware Fix

**Issue Fixed:** `AttributeError: 'TenantSecurityMiddleware' object has no attribute 'async_mode'`

---

## Pre-Deployment

### Code Review
- [ ] Review changes in `wasla/apps/tenants/security_middleware.py`
  - [ ] All 3 middleware classes refactored (TenantSecurityMiddleware, TenantContextMiddleware, TenantAuditMiddleware)
  - [ ] No `MiddlewareMixin` inheritance
  - [ ] No `process_request()` or `process_response()` methods
  - [ ] New `__call__()` method implemented for each class
  - [ ] Type hints added
- [ ] Review new test file: `wasla/apps/tenants/tests_security_middleware.py`
  - [ ] 17 comprehensive test cases
  - [ ] Tests cover all three middleware classes
  - [ ] Integration tests included
- [ ] Verify `wasla/config/settings.py` middleware order is correct
  - [ ] TenantResolverMiddleware comes first
  - [ ] TenantMiddleware comes second
  - [ ] TenantSecurityMiddleware comes third
  - [ ] TenantAuditMiddleware comes fourth

### Local Testing
- [ ] **Environment Setup**
  ```bash
  cd /home/mohamed/Desktop/wasla-version-2
  source .venv/bin/activate
  ```

- [ ] **Run System Checks**
  ```bash
  cd wasla
  python manage.py check
  # Expected: System check identified no issues (0 silenced).
  ```

- [ ] **Run Middleware Unit Tests**
  ```bash
  python manage.py test apps.tenants.tests_security_middleware -v 2
  # Expected: All tests pass
  ```

- [ ] **Run All Tenant Tests**
  ```bash
  python manage.py test apps.tenants -v 2
  # Expected: No failures
  ```

- [ ] **Start Dev Server**
  ```bash
  python manage.py runserver 0.0.0.0:8000
  # Expected: 
  # - No AttributeError about async_mode
  # - "Starting development server at http://0.0.0.0:8000/"
  ```

- [ ] **Test Key Endpoints**
  ```bash
  # In another terminal
  curl http://localhost:8000/
  curl http://localhost:8000/healthz
  curl http://localhost:8000/api/v1/
  # Expected: No 500 errors from middleware
  ```

- [ ] **Stop Dev Server**
  ```bash
  # Ctrl+C in the terminal running runserver
  ```

---

## Git Operations

- [ ] **Check Git Status**
  ```bash
  cd /home/mohamed/Desktop/wasla-version-2
  git status
  # Expected: Modified files and new files showing
  ```

- [ ] **Review Changes**
  ```bash
  git diff wasla/apps/tenants/security_middleware.py | less
  git diff wasla/config/settings.py  # Should be empty/no change
  git diff --cached  # To see staged changes
  ```

- [ ] **Stage Changes**
  ```bash
  git add wasla/apps/tenants/security_middleware.py
  git add wasla/apps/tenants/tests_security_middleware.py
  # Don't stage settings.py unless you made actual changes
  ```

- [ ] **Verify Staged Changes**
  ```bash
  git status
  # Expected: 2 files staged for commit
  ```

- [ ] **Create Commit**
  ```bash
  git commit -m "fix: Refactor tenant security middleware to Django 5.2 new-style pattern

- Remove MiddlewareMixin inheritance from all three middleware classes
  - TenantSecurityMiddleware
  - TenantContextMiddleware  
  - TenantAuditMiddleware
- Replace process_request/process_response with __call__ method
- Add comprehensive unit test suite (17 tests)
- Verify middleware order: TenantMiddleware before TenantSecurityMiddleware

Fixes: AttributeError at /: 'TenantSecurityMiddleware' has no attribute 'async_mode'
Tested: python manage.py check
        python manage.py test apps.tenants.tests_security_middleware -v 2
Django: 5.2.11"
  ```

- [ ] **Verify Commit**
  ```bash
  git log --oneline -5
  # Expected: New commit at top of list
  ```

- [ ] **Push to Remote**
  ```bash
  git push origin main
  # Expected: Successfully pushed
  ```

- [ ] **Verify Push**
  ```bash
  git log origin/main --oneline -5
  # Expected: New commit visible on remote
  ```

---

## Production Deployment

### Pre-Deployment Checks

- [ ] **Maintenance Window Notification**
  - Notify team of deployment time
  - Check for ongoing critical operations
  - Plan for < 5 minute downtime

- [ ] **Create Backup**
  ```bash
  # On production server
  sudo mysqldump -u root -p wasla_db > /backups/wasla_db_$(date +%Y%m%d_%H%M%S).sql
  ```

- [ ] **Check Production Status**
  ```bash
  # On production server
  systemctl status gunicorn  # or your WSGI server
  # Expected: active (running)
  ```

### Deployment Steps

- [ ] **Stop Application**
  ```bash
  # On production server
  sudo systemctl stop gunicorn
  # Wait for graceful shutdown (≤ 30 seconds)
  ```

- [ ] **Pull Latest Code**
  ```bash
  # On production server, in Django project directory
  cd /path/to/wasla-version-2
  git pull origin main
  # Should show:
  # - Updating <commit>...<commit>
  # - 2 files changed, ~250 insertions
  ```

- [ ] **Verify File Permissions**
  ```bash
  # On production server
  ls -la wasla/apps/tenants/security_middleware.py
  ls -la wasla/apps/tenants/tests_security_middleware.py
  # Expected: proper read/execute permissions
  ```

- [ ] **Run System Check**
  ```bash
  # On production server
  cd /path/to/wasla-version-2/wasla
  python manage.py check
  # Expected: System check identified no issues (0 silenced).
  ```

- [ ] **Collect Static Files (if needed)**
  ```bash
  python manage.py collectstatic --noinput
  # Expected: "X static files copied"
  ```

- [ ] **Run Database Migrations (if any)**
  ```bash
  # Usually not needed for this fix, but just in case
  python manage.py migrate
  # Expected: "No migrations to apply" or successful migration
  ```

- [ ] **Start Application**
  ```bash
  sudo systemctl start gunicorn
  # Wait 5-10 seconds for startup
  systemctl status gunicorn
  # Expected: active (running)
  ```

- [ ] **Verify Application Started**
  ```bash
  # Check for errors in the last 20 lines of logs
  sudo tail -20 /var/log/django/error.log
  # Expected: No AttributeError messages
  # Expected: No middleware-related errors
  ```

### Post-Deployment Verification

- [ ] **Health Check Endpoint**
  ```bash
  curl https://your-domain.com/healthz
  # Expected: 200 OK or similar success response
  # NOT: 500 Internal Server Error
  ```

- [ ] **API Endpoint Check**
  ```bash
  curl https://your-domain.com/api/v1/
  # Expected: 401/403 (auth required) 
  # NOT: 500 Internal Server Error
  # NOT: 502 Bad Gateway
  ```

- [ ] **Check Error Logs**
  ```bash
  # Watch logs for 5 minutes
  sudo tail -f /var/log/django/error.log
  # Expected: No new errors appearing
  # Especially: No "async_mode" errors
  # Especially: No middleware errors
  ```

- [ ] **Browser Visit Production**
  - Open https://your-domain.com in browser
  - Check browser console for errors
  - Expected: Site loads normally
  - Expected: No 500 errors

- [ ] **Monitor Uptime/Performance**
  ```bash
  # Check monitoring services (Sentry, DataDog, etc.)
  # Expected: Normal error rate
  # Expected: No spike in 500 errors
  # Expected: Normal response times
  ```

- [ ] **Automated Tests (if any)**
  ```bash
  # Run integration tests against production
  # Expected: All passing
  ```

---

## Rollback Plan

If deployment fails, follow these steps:

- [ ] **Stop Application**
  ```bash
  sudo systemctl stop gunicorn
  ```

- [ ] **Revert Code**
  ```bash
  cd /path/to/wasla-version-2
  git revert HEAD
  git push origin main
  ```

- [ ] **Pull Reverted Code**
  ```bash
  git pull origin main
  ```

- [ ] **Verify Changes Reverted**
  ```bash
  cd wasla
  python manage.py check
  ```

- [ ] **Restart Application**
  ```bash
  sudo systemctl start gunicorn
  ```

- [ ] **Verify Rollback Successful**
  ```bash
  curl https://your-domain.com/healthz
  # Expected: Normal operation restored
  ```

- [ ] **Investigate Root Cause**
  - Check error logs for specific errors
  - Review any custom configuration
  - Coordinate with development team

---

## Success Criteria

### Immediate (Within 5 minutes)
- [ ] Application starts without `AttributeError`
- [ ] No middleware-related errors in logs
- [ ] Health endpoints respond with expected status codes
- [ ] API endpoints respond (even if 403/401 due to auth)

### Short-term (Within 1 hour)
- [ ] No new error log entries from middleware
- [ ] User requests complete normally
- [ ] Performance metrics are normal
- [ ] No spike in HTTP 500 errors

### Long-term (24 hours)
- [ ] Continued normal operation
- [ ] No regressions in tenant isolation
- [ ] No security issues introduced
- [ ] All monitoring systems show green

---

## Team Communication

### Before Deployment
- [ ] Notify #devops channel: Deployment planned for [TIME]
- [ ] Message: "Deploying Django 5.2 middleware fix"
- [ ] Link to this checklist

### During Deployment
- [ ] Continue monitoring in #incident-response
- [ ] Post updates every 2 minutes
- [ ] Message format: "Step X/Y complete - [Status okay/investigating issue]"

### After Deployment
- [ ] Post completion message with timestamp
- [ ] Include brief summary: "Deployment complete. 0 errors observed."
- [ ] Link to diff for review: `MIDDLEWARE_DJANGO5_FIX_DIFF.md`

---

## Documentation

After successful deployment, update:
- [ ] Team wiki/runbook (update django version notes)
- [ ] Deployment guide (add notes about this fix)
- [ ] Incident dashboard (mark as resolved)

---

## Post-Deployment Review

Schedule for 1 day after deployment:

- [ ] Review error logs for any emerging issues
- [ ] Check monitoring dashboard for any anomalies  
- [ ] Run tests again: `python manage.py test apps.tenants`
- [ ] Check git blame/history to verify no unintended changes
- [ ] Schedule knowledge-share session with team about new-style middleware

---

**Deployment Status:** 🟡 READY TO DEPLOY

**Deployment Owner:** [Your Name]  
**Deployment Date:** [YYYY-MM-DD]  
**Deployment Time:** [HH:MM UTC]  
**Estimated Duration:** 5 minutes  
**Rollback Difficulty:** Low (simple revert)  

---

## Sign-Off

- [ ] Code review approved by: _________________ (Date: _______)
- [ ] QA testing approved by: _________________ (Date: _______)
- [ ] DevOps approved by: ___________________ (Date: _______)
- [ ] Ready for deployment: ✅

