"""
Settings.py Updates for Production Hardening.

Add these configurations to wasla/config/settings.py

This file documents all changes needed for:
1. JWT tenant validation middleware
2. TOTP middleware for 2FA
3. Database hardening
4. Transaction safety
5. Backup automation
"""

# ==========================================
# 1. MIDDLEWARE ADDITIONS
# ==========================================

MIDDLEWARE = [
    # ... existing middleware ...
    
    # IMPORTANT: Order matters!
    # JWTTenantValidationMiddleware must run BEFORE TenantMiddleware
    "config.security_middleware.JWTTenantValidationMiddleware",
    "tenants.middleware.TenantMiddleware",
    "config.security_middleware.TOTPVerificationMiddleware",
    
    # ... rest of middleware ...
]

# ==========================================
# 2. DATABASE HARDENING
# ==========================================

# Import database hardening config
from config.database_hardening import *

# Connection pooling configuration
# (See database_hardening.py for detailed pgbouncer setup)

# Transaction settings
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ATOMIC_REQUESTS = False  # Use explicit transaction.atomic

# ==========================================
# 3. JWT CONFIGURATION
# ==========================================

JWT_AUTH = {
    "JWT_ALGORITHM": "HS256",
    "JWT_SECRET_KEY": SECRET_KEY,
    "JWT_VERIFY_SIGNATURE": True,
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_EXPIRATION_DELTA": 3600,  # 1 hour
    "JWT_REFRESH_EXPIRATION_DELTA": 7 * 24 * 3600,  # 7 days
}

# ==========================================
# 4. TOTP / 2FA CONFIGURATION
# ==========================================

# Required packages: pyotp, qrcode
INSTALLED_APPS = [
    # ... existing apps ...
    "django_otp",
    "django_otp.plugins.otp_totp",
]

# TOTP settings
TOTP_ISSUER_NAME = "Wasla"
TOTP_TOKEN_LENGTH = 6  # 6-digit codes (standard)
TOTP_QR_CODE_SIZE = 10  # QR code box size

# ==========================================
# 5. FINANCIAL TRANSACTION SAFETY
# ==========================================

# Enable transaction-level security
DATABASE = {
    "default": {
        # ... existing config ...
        "ATOMIC_REQUESTS": False,  # Use explicit @transaction.atomic
        "AUTOCOMMIT": False,  # Explicit transaction control
        "CONN_MAX_AGE": 600,  # Connection pooling: 10 min TTL
    }
}

# Query timeouts (seconds)
DATABASE_STATEMENT_TIMEOUT = 30000  # 30 seconds
DATABASE_LOCK_TIMEOUT = 10000  # 10 seconds (deadlock prevention)

# ==========================================
# 6. LOGGING CONFIGURATION
# ==========================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/wasla/django.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "json",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/wasla/security.log",
            "maxBytes": 10485760,
            "backupCount": 10,
            "formatter": "json",
        },
        "financial_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/wasla/financial.log",
            "maxBytes": 52428800,  # 50MB
            "backupCount": 30,
            "formatter": "json",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "wasla.security": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",  # Log all security events
            "propagate": False,
        },
        "wasla.payments": {
            "handlers": ["console", "financial_file"],
            "level": "INFO",
            "propagate": False,
        },
        "wasla.settlements": {
            "handlers": ["console", "financial_file"],
            "level": "INFO",
            "propagate": False,
        },
        "wasla.auth": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ==========================================
# 7. SECURITY SETTINGS
# ==========================================

# HTTPS & TLS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Content Security Headers
SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ("'self'",),
    "style-src": ("'self'", "'unsafe-inline'"),  # Relax for Bootstrap
    "script-src": ("'self'",),
    "img-src": ("'self'", "data:", "https:"),
}

# X-Frame-Options (prevent clickjacking)
X_FRAME_OPTIONS = "DENY"

# ==========================================
# 8. PAYMENT PROVIDER CONFIGURATION
# ==========================================

# Use environment variables for all sensitive config
PAYMENT_PROVIDERS = {
    "tap": {
        "api_key": os.getenv("TAP_API_KEY"),
        "secret_key": os.getenv("TAP_SECRET_KEY"),
        "webhook_signature_key": os.getenv("TAP_WEBHOOK_KEY"),
    },
    "stripe": {
        "api_key": os.getenv("STRIPE_API_KEY"),
        "secret_key": os.getenv("STRIPE_SECRET_KEY"),
        "webhook_signature_key": os.getenv("STRIPE_WEBHOOK_KEY"),
    },
}

# ==========================================
# 9. BACKUP AUTOMATION
# ==========================================

# Crontab entry:
# 0 2 * * * /opt/wasla/scripts/backup.sh >> /var/log/wasla/backup.log 2>&1

# Backup configuration
BACKUP_CONFIG = {
    "enabled": True,
    "schedule": "0 2 * * *",  # Daily at 2 AM
    "retention_days": 30,  # Keep 30 days of backups
    "backup_dir": "/mnt/backups/wasla",
    "media_dir": "/opt/wasla/media",
}

# ==========================================
# 10. CELERY TASK CONFIGURATION
# ==========================================

# Ensure financial tasks have proper settings
CELERY_TASK_ALWAYS_EAGER = False  # Run async in production
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TASK_TIME_LIMIT = 25 * 60  # 25 minutes (hard limit)
CELERY_TASK_SOFT_TIME_LIMIT = 20 * 60  # 20 minutes (soft limit, gives chance to timeout gracefully)

# Financial tasks should retry on failure
CELERY_TASK_AUTORETRY_FOR = (Exception,)
CELERY_TASK_RETRY_KWARGS = {"max_retries": 3}
CELERY_TASK_RETRY_BACKOFF = True

# ==========================================
# 11. MONITORING & ALERTING
# ==========================================

# Error tracking (e.g., Sentry)
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=ENVIRONMENT,
    )

# Metrics export (Prometheus)
METRICS_EXPORT_ENABLED = True

# ==========================================
# 12. REQUIRED DEPENDENCIES
# ==========================================

"""
Add to requirements.txt:

# 2FA / OTP
pyotp==2.8.0
qrcode==7.4.2

# Logging
python-json-logger==2.0.7

# JWT
PyJWT==2.8.1

# Database
psycopg2-binary==2.9.9  # PostgreSQL adapter

# Error tracking
sentry-sdk==1.39.1

# Monitoring
prometheus-client==0.19.0

# Background tasks
celery==5.3.4
redis==5.0.1
"""

# ==========================================
# VERIFICATION CHECKLIST
# ==========================================

"""
After adding these settings, verify:

1. [ ] Middleware order is correct (JWT before Tenant)
2. [ ] Database connection uses pgbouncer
3. [ ] JWT_SECRET_KEY is strong (Django default OK)
4. [ ] TOTP issuer name set
5. [ ] Financial logs configured (payments, settlements)
6. [ ] Security logs configured (auth, security)
7. [ ] Backup script setup in crontab
8. [ ] All required packages installed
9. [ ] Environment variables set:
      - DB_PASSWORD
      - TAP_API_KEY, TAP_SECRET_KEY
      - STRIPE_API_KEY, STRIPE_SECRET_KEY
      - SENTRY_DSN (optional)
10. [ ] Test JWT validation: Try modifying tenant_id claim
11. [ ] Test TOTP: Enable 2FA and verify code
12. [ ] Test refund ledger sync: Process test refund
13. [ ] Test backup script: ./scripts/backup.sh
14. [ ] Verify logs are being written
"""
