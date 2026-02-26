# Domain Monitoring + SSL Automation

## Required environment variables

Set these values in `wasla/.env` for production:

- `CUSTOM_DOMAIN_SSL_ENABLED=1`
- `CUSTOM_DOMAIN_CERTBOT_CMD=/usr/bin/certbot`
- `CUSTOM_DOMAIN_CERTBOT_EMAIL=ops@your-domain.com`
- `CUSTOM_DOMAIN_CERTBOT_MODE=http-01`
- `CUSTOM_DOMAIN_CERTBOT_WEBROOT=/var/www/certbot`
- `CUSTOM_DOMAIN_CERTS_DIR=/etc/letsencrypt/live`
- `CUSTOM_DOMAIN_NGINX_ENABLED=1`
- `CUSTOM_DOMAIN_NGINX_DOMAINS_DIR=/etc/nginx/conf.d/wasla_domains`
- `CUSTOM_DOMAIN_NGINX_UPSTREAM=http://127.0.0.1:8000`
- `CUSTOM_DOMAIN_NGINX_TEST_CMD=nginx -t`
- `CUSTOM_DOMAIN_NGINX_RELOAD_CMD=systemctl reload nginx`

## Certbot path validation

Run on the host:

```bash
command -v /usr/bin/certbot
/usr/bin/certbot --version
```

If certbot is in a different path, set `CUSTOM_DOMAIN_CERTBOT_CMD` to that exact path.

## Celery workers/beat

Run both in production:

```bash
celery -A config worker -l info
celery -A config beat -l info
```

Daily schedules configured:

- `apps.domains.tasks.check_domain_health` at 02:00 UTC
- `apps.domains.tasks.renew_expiring_ssl` at 02:30 UTC

## Manual verification

- Admin list API: `GET /api/admin/domains/`
- Admin force check API: `POST /api/admin/domains/{id}/check/`
- Admin force renew API: `POST /api/admin/domains/{id}/renew/`
- Merchant status API: `GET /api/domains/status/`

## Zero downtime renewal flow

The renewal service performs:

1. Certbot renewal invocation.
2. Certificate copy to temporary files.
3. Certificate validation before activation.
4. Atomic activation for configured destination files.
5. Nginx config test + graceful reload.
6. Rollback to backup files if activation fails.
