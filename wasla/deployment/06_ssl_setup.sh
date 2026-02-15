#!/usr/bin/env bash
set -Eeuo pipefail

# 06_ssl_setup.sh
# SSL setup:
# - Installs certbot
# - Issues SSL for domain + www (webroot)
# - Enables HTTP -> HTTPS redirect
# - Enables auto-renew
# - Validates SSL installation

PROJECT_NAME="${PROJECT_NAME:-wasla}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

RUNTIME_DIR="/var/lib/${PROJECT_NAME}"
STATIC_DIR="${RUNTIME_DIR}/static"
MEDIA_DIR="${RUNTIME_DIR}/media"
CERTBOT_WEBROOT="/var/www/certbot"

SOCKET_PATH="/run/gunicorn-${PROJECT_NAME}.sock"

HTTP_LINK="/etc/nginx/sites-enabled/${PROJECT_NAME}.http.conf"
SSL_CONF="/etc/nginx/sites-available/${PROJECT_NAME}.ssl.conf"
SSL_LINK="/etc/nginx/sites-enabled/${PROJECT_NAME}.ssl.conf"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [[ "$(id -u)" -ne 0 ]]; then
  fail "Must run as root."
fi

if [[ -z "${DOMAIN_NAME}" ]]; then
  fail "DOMAIN_NAME is required (export DOMAIN_NAME=yourdomain.com)."
fi

if [[ -z "${CERTBOT_EMAIL}" ]]; then
  CERTBOT_EMAIL="admin@${DOMAIN_NAME}"
fi

systemctl is-active --quiet nginx || fail "Nginx must be running before issuing SSL. Run deployment/05_nginx_setup.sh first."

mkdir -p "${CERTBOT_WEBROOT}" "${STATIC_DIR}" "${MEDIA_DIR}"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends certbot openssl

certbot certonly \
  --non-interactive \
  --agree-tos \
  --email "${CERTBOT_EMAIL}" \
  --webroot -w "${CERTBOT_WEBROOT}" \
  -d "${DOMAIN_NAME}" -d "www.${DOMAIN_NAME}" \
  --keep-until-expiring

fullchain="/etc/letsencrypt/live/${DOMAIN_NAME}/fullchain.pem"
privkey="/etc/letsencrypt/live/${DOMAIN_NAME}/privkey.pem"
if [[ ! -s "${fullchain}" ]] || [[ ! -s "${privkey}" ]]; then
  fail "Certificate files not found after certbot run."
fi

cat > "${SSL_CONF}" <<EOF
upstream ${PROJECT_NAME}_gunicorn {
  server unix:${SOCKET_PATH};
}

server {
  listen 80;
  server_name ${DOMAIN_NAME} www.${DOMAIN_NAME};

  location ^~ /.well-known/acme-challenge/ {
    root ${CERTBOT_WEBROOT};
    default_type "text/plain";
  }

  location / {
    return 301 https://\$host\$request_uri;
  }
}

server {
  listen 443 ssl http2;
  server_name ${DOMAIN_NAME} www.${DOMAIN_NAME};

  access_log /var/log/nginx/${PROJECT_NAME}.access.log;
  error_log  /var/log/nginx/${PROJECT_NAME}.error.log;

  ssl_certificate     ${fullchain};
  ssl_certificate_key ${privkey};
  ssl_session_timeout 1d;
  ssl_session_cache shared:SSL:10m;
  ssl_session_tickets off;

  ssl_protocols TLSv1.2 TLSv1.3;
  ssl_prefer_server_ciphers off;

  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

  client_max_body_size 25m;

  location /static/ {
    alias ${STATIC_DIR}/;
    access_log off;
    expires 7d;
  }

  location /media/ {
    alias ${MEDIA_DIR}/;
    access_log off;
    expires 7d;
  }

  location / {
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_redirect off;
    proxy_pass http://${PROJECT_NAME}_gunicorn;
  }
}
EOF

ln -sf "${SSL_CONF}" "${SSL_LINK}"
rm -f "${HTTP_LINK}" || true

nginx -t
systemctl reload nginx

if systemctl list-unit-files | grep -q "^certbot\\.timer"; then
  systemctl enable --now certbot.timer
fi

timeout 12 curl -fsSLI "https://${DOMAIN_NAME}" >/dev/null || fail "SSL validation failed (HTTPS request failed)."

ENV_DIR="/etc/${PROJECT_NAME}"
DJANGO_ENV_FILE="${ENV_DIR}/django.env"
SERVICE_NAME="gunicorn-${PROJECT_NAME}.service"
if [[ -f "${DJANGO_ENV_FILE}" ]]; then
  # Enable HTTPS-related security flags after SSL is live.
  sed -i \
    -e 's/^DJANGO_SECURE_SSL_REDIRECT=.*/DJANGO_SECURE_SSL_REDIRECT=1/' \
    -e 's/^DJANGO_SESSION_COOKIE_SECURE=.*/DJANGO_SESSION_COOKIE_SECURE=1/' \
    -e 's/^DJANGO_CSRF_COOKIE_SECURE=.*/DJANGO_CSRF_COOKIE_SECURE=1/' \
    "${DJANGO_ENV_FILE}" || true
  systemctl restart "${SERVICE_NAME}" || true
fi

echo "OK: SSL installed and HTTPS is healthy for ${DOMAIN_NAME}."
