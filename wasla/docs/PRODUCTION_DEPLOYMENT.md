# Production Deployment Guide

This guide prepares Wassla for production using Docker, Postgres, Redis, Celery, and Nginx.

## Files Added
- `Dockerfile`
- `docker-compose.prod.yml`
- `infrastructure/nginx/prod.conf`
- `config/settings_prod.py`
- `env/production.env`

## 1) Environment Variables
Populate `env/production.env` with your real values.

Required keys:
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_SESSION_COOKIE_SECURE`
- `DJANGO_CSRF_COOKIE_SECURE`
- `DJANGO_SECURE_HSTS_SECONDS`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `DJANGO_SECURE_HSTS_PRELOAD`
- `DJANGO_SECURE_REFERRER_POLICY`
- `DJANGO_X_FRAME_OPTIONS`
- `WASSLA_BASE_DOMAIN`

- `PG_DB_NAME`
- `PG_DB_USER`
- `PG_DB_PASSWORD`
- `PG_DB_HOST`
- `PG_DB_PORT`

- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

- `DJANGO_STATIC_ROOT`
- `DJANGO_MEDIA_ROOT`

- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `SERVER_EMAIL`

- `LOG_LEVEL`
- `WASLA_REQUEST_LOG_LEVEL`
- `WASLA_PERFORMANCE_LOG_LEVEL`

## 2) Build and Run
```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

For docker-compose usage, set:
- `PG_DB_HOST=db`
- `PG_DB_PORT=5432`

## 3) Health Check
```
GET /health/
GET /healthz/
```

## 4) Static and Media
Static files are collected into `DJANGO_STATIC_ROOT` and served by Nginx.
Media is served from `DJANGO_MEDIA_ROOT`.

## 5) Security Headers
Production settings enforce:
- SSL redirect
- HSTS (with optional preload)
- Secure cookies
- X-Frame-Options
- Referrer-Policy

## 6) Logs
Logs are structured JSON to stdout, suitable for container log aggregation.

## 7) Celery
Worker runs with:
```
celery -A config.celery app worker --loglevel=INFO --queues=default,settlements,notifications
```

## 8) Migrations
The `web` service runs:
```
python manage.py migrate
python manage.py collectstatic --noinput
```
on container startup.
