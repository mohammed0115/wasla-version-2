# .env Configuration Guide

## Overview

This guide helps you properly configure the `.env` file for WASLA deployment. The `.env` file contains sensitive environment variables and **should NEVER be committed to version control**.

## Quick Setup

1. **Copy the example file:**
```bash
cp .env.example .env
```

2. **Generate a secure SECRET_KEY:**
```bash
# Option 1: Using Django
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Option 2: Using OpenSSL
openssl rand -hex 32
```

3. **Fill in all required values** (see sections below)

4. **Verify .env is in .gitignore:**
```bash
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
```

---

## Security Configuration

### 1. DEBUG Mode (Critical)

```env
# Development ONLY
DEBUG=True

# Production ONLY
DEBUG=False
```

**Why:** When `DEBUG=True`, Django exposes sensitive information in error pages, including database queries, environment variables, and stack traces.

---

### 2. SECRET_KEY (Critical)

```env
# Development (simple, just for testing)
SECRET_KEY=your-development-key-can-be-simple

# Production (MUST be cryptographically secure)
SECRET_KEY=generated-random-string-50-chars-minimum-change-per-environment
```

**How to generate:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Why:** Django uses this to:
- Sign session cookies
- Generate CSRF tokens
- Create password reset tokens
- Encrypt sensitive data

**Best practices:**
- Different key per environment (dev, staging, production)
- Minimum 50 characters
- Use cryptographically secure randomization
- Rotate periodically in production

---

### 3. ALLOWED_HOSTS (Critical)

```env
# Development
ALLOWED_HOSTS=localhost,127.0.0.1

# Production
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,api.yourdomain.com
```

**Why:** Django only accepts requests to domains listed here. Prevents Host header injection attacks.

**Format:** Comma-separated, no spaces.

---

### 4. CORS Configuration (Important)

```env
# Trusted origins for CSRF (Django internal)
CSRF_TRUSTED_ORIGINS=http://localhost:3000,https://yourdomain.com

# CORS allowed origins (for django-cors-headers)
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

**Why:** Controls which frontend domains can make requests to your API.

**Difference:**
- `CSRF_TRUSTED_ORIGINS`: Django form submission protection
- `CORS_ALLOWED_ORIGINS`: Browser CORS policy (allows cross-origin requests)

---

### 5. HTTPS/SSL Configuration (Production)

```env
# Development: False
SECURE_SSL_REDIRECT=False

# Production: True (requires SSL certificate)
SECURE_SSL_REDIRECT=True

# HSTS Header (tell browsers to always use HTTPS)
SECURE_HSTS_SECONDS=31536000

# Trust proxy's SSL information
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
```

**Setup before enabling:**
1. Install SSL certificate (Let's Encrypt recommended)
2. Configure Nginx/reverse proxy for HTTPS
3. Only then set `SECURE_SSL_REDIRECT=True`

---

## Database Configuration

### MySQL (Recommended)

```env
# Selection
DB_ENGINE=django.db.backends.mysql
DJANGO_DB_DEFAULT=mysql

# Connection
MYSQL_DB_HOST=localhost
MYSQL_DB_PORT=3306
MYSQL_DB_NAME=wasla
MYSQL_DB_USER=wasla_user
MYSQL_DB_PASSWORD=your-very-secure-password-16-chars-minimum

# Root (for initial setup only)
MYSQL_ROOT_PASSWORD=your-root-password-change-immediately
```

**Password requirements:**
- Minimum 16 characters
- Mix of uppercase, lowercase, numbers, symbols
- Example: `P@ssw0rd!SecureDB2024`

**Setup:**
```bash
# Run deploy script
bash wasla/deploy.sh
# Select: 1 (MySQL)
```

---

### PostgreSQL (Advanced)

```env
# Selection
DB_ENGINE=django.db.backends.postgresql
DJANGO_DB_DEFAULT=postgresql

# Connection
PG_DB_HOST=localhost
PG_DB_PORT=5432
PG_DB_NAME=wasla
PG_DB_USER=wasla_user
PG_DB_PASSWORD=your-very-secure-password-16-chars-minimum
```

**Setup:**
```bash
# Run deploy script
bash wasla/deploy.sh
# Select: 2 (PostgreSQL)
```

---

### Backup Configuration

```env
# Strategy: daily, weekly, hourly, monthly
DB_BACKUP_STRATEGY=daily

# How long to keep backups (days)
DB_BACKUP_RETENTION_DAYS=30

# Backup directory
DB_BACKUP_DIRECTORY=/var/backups/wasla
```

---

## Payment Provider Configuration

### All Payment Providers (Critical for Security)

**IMPORTANT:** Never expose webhook secrets in logs or error messages. Always verify HMAC signatures.

### Tap (GCC Payment Gateway)

```env
# API Keys (from Tap dashboard)
TAP_API_KEY=pk_live_your_tap_api_key
TAP_SECRET_KEY=sk_live_your_tap_secret_key

# Webhook Secret (from Tap > Webhooks > Signing Secret)
TAP_WEBHOOK_SECRET=whsec_your_tap_webhook_secret_key

TAP_MERCHANT_ID=your-merchant-id
TAP_SANDBOX=False
```

**Where to find:**
1. Login to Tap merchant dashboard
2. Settings > API Keys > Get your keys
3. Webhooks > Copy webhook signing secret

### Stripe

```env
# Keys (from Stripe dashboard)
STRIPE_API_KEY=sk_live_your_stripe_secret_key
STRIPE_PUBLIC_KEY=pk_live_your_stripe_public_key

# Webhook Secret (from Stripe > Webhooks > Signing secret)
STRIPE_WEBHOOK_SECRET=whsec_your_stripe_webhook_secret

STRIPE_SANDBOX=False
```

**Where to find:**
1. Login to Stripe dashboard
2. Developers > API Keys > Secret key (starts with sk_live_)
3. Developers > Webhooks > Click endpoint > Signing secret

### PayPal

```env
# Credentials (from PayPal developer portal)
PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_SECRET=your-paypal-client-secret

# Webhook ID (from PayPal > Webhooks)
PAYPAL_WEBHOOK_ID=your-paypal-webhook-id

PAYPAL_SANDBOX=False
```

---

## Email Configuration

```env
# Gmail (Recommended for small projects)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
# IMPORTANT: Use App Password, not your Gmail password!
EMAIL_HOST_PASSWORD=your-app-specific-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

**Gmail setup:**
1. Enable 2-Factor Authentication
2. Go to: https://myaccount.google.com/apppasswords
3. Create app password for "Mail" on "Other devices"
4. Copy the 16-character password to `EMAIL_HOST_PASSWORD`

**SendGrid (for production):**
```env
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.your-sendgrid-api-key
```

**AWS SES:**
```env
EMAIL_HOST=email-smtp.{{ region }}.amazonaws.com
EMAIL_PORT=587
EMAIL_HOST_USER=smtp-username
EMAIL_HOST_PASSWORD=smtp-password
```

---

## AWS S3 Configuration (Production)

```env
# Enable S3 for production
USE_S3=True

# AWS Credentials
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_STORAGE_BUCKET_NAME=wasla-media-bucket
AWS_S3_REGION_NAME=us-east-1

# CloudFront CDN (optional)
AWS_S3_CUSTOM_DOMAIN=https://cdn.yourdomain.com
```

**Setup:**
1. Create S3 bucket: `wasla-media-bucket`
2. Create IAM user with S3 permissions
3. Follow [AWS S3 setup guide](../docs/AWS_S3_SETUP.md)

**Security:**
- Set bucket to private
- Only serve through CloudFront
- Use IAM user with minimal permissions

---

## Redis & Cache Configuration

```env
# Redis Server
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0

# In production, set password:
REDIS_PASSWORD=your-secure-redis-password

# Cache
CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
CACHE_LOCATION=redis://redis:6379/1
CACHE_TIMEOUT=3600

# Sessions
SESSION_ENGINE=django.contrib.sessions.backends.cache
SESSION_CACHE_ALIAS=default
```

---

## Monitoring & Error Tracking

### Sentry (Error Tracking)

```env
# Get from: https://sentry.io/projects/your-project/settings/keys/
SENTRY_DSN=https://your-key@sentry.io/project-id

# Environment name
SENTRY_ENVIRONMENT=production

# Release version
SENTRY_RELEASE=1.0.0

# Tracing sample rate (0-1, 0.1 = 10% of transactions)
SENTRY_TRACES_SAMPLE_RATE=0.1
```

**Setup:**
1. Create account at https://sentry.io
2. Create project for your application
3. Copy DSN from Settings > Client Keys

### Datadog (APM)

```env
DATADOG_API_KEY=your-datadog-api-key
DATADOG_SITE=us5.datadoghq.com
```

---

## Admin Panel

```env
# CRITICAL: Change these before production deployment!
ADMIN_USER=admin
ADMIN_PASSWORD=admin123
ADMIN_EMAIL=admin@yourdomain.com
```

**Generate strong password:**
```bash
openssl rand -base64 16
```

---

## Environment-Specific Examples

### Development (.env)

```env
DEBUG=True
SECRET_KEY=dev-key-simple-for-testing
ALLOWED_HOSTS=localhost,127.0.0.1
SECURE_SSL_REDIRECT=False
DB_ENGINE=django.db.backends.mysql
DJANGO_DB_DEFAULT=mysql
MYSQL_DB_PASSWORD=dev-password
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

### Staging (.env.staging)

```env
DEBUG=False
SECRET_KEY=staging-secure-random-key-50-chars
ALLOWED_HOSTS=staging.yourdomain.com
SECURE_SSL_REDIRECT=True
DB_ENGINE=django.db.backends.mysql
DJANGO_DB_DEFAULT=mysql
MYSQL_DB_PASSWORD=staging-secure-password
EMAIL_HOST=smtp.sendgrid.net
SENTRY_ENVIRONMENT=staging
LOG_LEVEL=INFO
ENVIRONMENT=staging
```

### Production (.env.production)

```env
DEBUG=False
SECRET_KEY=production-ultra-secure-random-key-50-chars-different-from-staging
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,api.yourdomain.com
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
DB_ENGINE=django.db.backends.mysql
DJANGO_DB_DEFAULT=mysql
MYSQL_DB_PASSWORD=production-very-secure-password-16-chars
EMAIL_HOST=smtp.sendgrid.net
SENTRY_DSN=your-sentry-dsn
SENTRY_TRACES_SAMPLE_RATE=0.01
LOG_LEVEL=WARNING
ENVIRONMENT=production
USE_S3=True
AWS_STORAGE_BUCKET_NAME=wasla-prod-media
```

---

## Validation Checklist

Before deploying, verify all critical variables:

```bash
#!/bin/bash
# check-env.sh

required_vars=(
    "SECRET_KEY"
    "DEBUG"
    "ALLOWED_HOSTS"
    "MYSQL_DB_PASSWORD"
    "EMAIL_HOST_USER"
    "TAP_WEBHOOK_SECRET"
    "STRIPE_WEBHOOK_SECRET"
)

for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env; then
        echo "❌ Missing: $var"
    fi
done
echo "✓ All required variables present"
```

---

## Common Mistakes

❌ **DON'T:**
- Commit .env to git
- Use same SECRET_KEY across environments
- Use simple passwords for production
- Store webhook secrets in logs
- Leave DEBUG=True in production
- Expose payment API keys

✅ **DO:**
- Use .env.example as template
- Generate new SECRET_KEY per environment
- Use strong passwords (16+ chars)
- Verify webhook signatures
- Keep .env in .gitignore
- Rotate secrets regularly
- Use environment variables for all secrets

---

## Troubleshooting

**"Bad Request (400)" errors**
- Check ALLOWED_HOSTS configuration
- Verify CSRF_TRUSTED_ORIGINS includes your frontend

**"CSRF verification failed" errors**
- Ensure CSRF_TRUSTED_ORIGINS is set correctly
- Check frontend domain matches

**Database connection errors**
- Verify MYSQL_DB_PASSWORD is correct
- Check MYSQL_DB_HOST is accessible
- Confirm database and user exist

**Email not sending**
- Verify email credentials
- Check EMAIL_HOST and EMAIL_PORT
- For Gmail: Use app-specific password, not account password

**Payment webhooks not processing**
- Verify webhook secret matches provider dashboard
- Check webhook URL is publicly accessible
- Review logs for signature verification errors

---

## Security Audit

Run before production:

```bash
# Check for .env in git
grep -r "SECRET_KEY=" .git/

# Check DEBUG mode
grep "DEBUG=" .env

# Check password strength
grep "DB_PASSWORD" .env | wc -c

# Verify .env is ignored
cat .gitignore | grep ".env"
```

---

## Support

For issues:
- Check [DEPLOYMENT.md](./DEPLOYMENT.md#troubleshooting)
- Review Sentry error tracking
- Check application logs
- See specific service guides in `docs/`
