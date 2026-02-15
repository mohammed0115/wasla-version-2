#!/usr/bin/env bash
set -Eeuo pipefail

# 05_nginx_setup.sh
# Nginx setup (HTTP):
# - Installs Nginx
# - Serves static & media
# - Proxies to Gunicorn unix socket
# - Configures domain + www
# - Includes ACME webroot for certbot (SSL is done in step 06)

PROJECT_NAME="${PROJECT_NAME:-wasla}"
DOMAIN_NAME="${DOMAIN_NAME:-}"

RUNTIME_DIR="/var/lib/${PROJECT_NAME}"
STATIC_DIR="${RUNTIME_DIR}/static"
MEDIA_DIR="${RUNTIME_DIR}/media"
CERTBOT_WEBROOT="/var/www/certbot"

SOCKET_PATH="/run/gunicorn-${PROJECT_NAME}.sock"

HTTP_CONF="/etc/nginx/sites-available/${PROJECT_NAME}.http.conf"
HTTP_LINK="/etc/nginx/sites-enabled/${PROJECT_NAME}.http.conf"
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

if [[ -e "${SSL_LINK}" ]]; then
  echo "SSL config already enabled; skipping HTTP-only nginx config."
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends nginx

mkdir -p "${STATIC_DIR}" "${MEDIA_DIR}" "${CERTBOT_WEBROOT}"
chown -R "www-data:www-data" "${CERTBOT_WEBROOT}" || true

cat > "${HTTP_CONF}" <<EOF
upstream ${PROJECT_NAME}_gunicorn {
  server unix:${SOCKET_PATH};
}

server {
  listen 80;
  server_name ${DOMAIN_NAME} www.${DOMAIN_NAME};

  access_log /var/log/nginx/${PROJECT_NAME}.access.log;
  error_log  /var/log/nginx/${PROJECT_NAME}.error.log;

  client_max_body_size 25m;

  location ^~ /.well-known/acme-challenge/ {
    root ${CERTBOT_WEBROOT};
    default_type "text/plain";
  }

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

ln -sf "${HTTP_CONF}" "${HTTP_LINK}"
rm -f /etc/nginx/sites-enabled/default || true

nginx -t
systemctl enable --now nginx
systemctl reload nginx
systemctl is-active --quiet nginx || fail "Nginx is not active."

echo "OK: Nginx HTTP config enabled (${HTTP_CONF})."
