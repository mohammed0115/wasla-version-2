#!/usr/bin/env bash
set -euo pipefail

# =========================
# CONFIG (edit these)
# =========================
APP_NAME="wassla"
DOMAIN="example.com"                 # e.g. wassla.sa or store.example.com
EMAIL="admin@example.com"            # certbot email
DJANGO_SETTINGS_MODULE="config.settings.production"  # adjust if needed

# Repo / code
REPO_URL=""                          # optional: https://github.com/you/repo.git
BRANCH="main"

# Paths
APP_USER="wassla"
APP_DIR="/var/www/${APP_NAME}"
VENV_DIR="${APP_DIR}/.venv"
SRC_DIR="${APP_DIR}/app"             # where Django manage.py will live

# Gunicorn
GUNICORN_WORKERS="3"
GUNICORN_BIND="unix:/run/${APP_NAME}.sock"

# Database (choose one)
DB_ENGINE="sqlite"                   # sqlite | postgres
POSTGRES_DB="wassla"
POSTGRES_USER="wassla"
POSTGRES_PASSWORD="CHANGE_ME"
POSTGRES_HOST="127.0.0.1"
POSTGRES_PORT="5432"

# Django secrets
DJANGO_SECRET_KEY="CHANGE_ME_TO_A_LONG_RANDOM_VALUE"
DJANGO_ALLOWED_HOSTS="${DOMAIN}"
DJANGO_DEBUG="0"

# =========================
# Helpers
# =========================
log(){ echo -e "\n\033[1;32m==> $*\033[0m"; }
need_root(){
  if [[ "$EUID" -ne 0 ]]; then
    echo "Run as root: sudo bash deploy.sh"
    exit 1
  fi
}

# =========================
# Start
# =========================
need_root

log "1) System packages"
apt-get update -y
apt-get install -y \
  python3 python3-venv python3-pip \
  nginx git \
  ufw \
  certbot python3-certbot-nginx

if [[ "$DB_ENGINE" == "postgres" ]]; then
  apt-get install -y postgresql postgresql-contrib libpq-dev
fi

log "2) Create app user and directories"
id -u "${APP_USER}" >/dev/null 2>&1 || useradd -m -s /bin/bash "${APP_USER}"
mkdir -p "${APP_DIR}" "${SRC_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

log "3) Get code (clone or assume already uploaded)"
if [[ -n "${REPO_URL}" ]]; then
  if [[ ! -d "${SRC_DIR}/.git" ]]; then
    sudo -u "${APP_USER}" bash -lc "git clone -b '${BRANCH}' '${REPO_URL}' '${SRC_DIR}'"
  else
    sudo -u "${APP_USER}" bash -lc "cd '${SRC_DIR}' && git fetch && git checkout '${BRANCH}' && git pull"
  fi
else
  echo "REPO_URL is empty. Assuming your Django project already exists in: ${SRC_DIR}"
fi

log "4) Create venv and install requirements"
sudo -u "${APP_USER}" bash -lc "python3 -m venv '${VENV_DIR}'"
sudo -u "${APP_USER}" bash -lc "'${VENV_DIR}/bin/pip' install --upgrade pip wheel"

if [[ -f "${SRC_DIR}/requirements.txt" ]]; then
  sudo -u "${APP_USER}" bash -lc "'${VENV_DIR}/bin/pip' install -r '${SRC_DIR}/requirements.txt'"
else
  echo "WARNING: requirements.txt not found at ${SRC_DIR}/requirements.txt"
fi

log "5) Create .env (do not commit this)"
ENV_FILE="${SRC_DIR}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<EOF
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=${DJANGO_DEBUG}
DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS}
DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}

# Multi-tenancy
TENANT_HEADER_NAME=X-Tenant

# Database
DB_ENGINE=${DB_ENGINE}
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_HOST=${POSTGRES_HOST}
POSTGRES_PORT=${POSTGRES_PORT}

# Security (recommended)
CSRF_TRUSTED_ORIGINS=https://${DOMAIN}
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
EOF
  chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
else
  echo ".env already exists, leaving it unchanged: ${ENV_FILE}"
fi

log "6) (Optional) Setup PostgreSQL"
if [[ "$DB_ENGINE" == "postgres" ]]; then
  sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';"

  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"
fi

log "7) Django migrate + collectstatic"
# Expect manage.py in SRC_DIR. Adjust if it's in another folder.
if [[ -f "${SRC_DIR}/manage.py" ]]; then
  sudo -u "${APP_USER}" bash -lc "
    set -a
    source '${ENV_FILE}'
    set +a
    cd '${SRC_DIR}'
    '${VENV_DIR}/bin/python' manage.py migrate --noinput
    '${VENV_DIR}/bin/python' manage.py collectstatic --noinput
  "
else
  echo "ERROR: manage.py not found at ${SRC_DIR}/manage.py"
  echo "Fix SRC_DIR or your repo layout, then re-run."
  exit 1
fi

log "8) Create systemd service for Gunicorn"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Gunicorn for ${APP_NAME}
After=network.target

[Service]
User=${APP_USER}
Group=www-data
WorkingDirectory=${SRC_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn \\
  --workers ${GUNICORN_WORKERS} \\
  --bind ${GUNICORN_BIND} \\
  config.wsgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

log "9) Create systemd socket (optional but recommended)"
SOCKET_FILE="/etc/systemd/system/${APP_NAME}.socket"
cat > "${SOCKET_FILE}" <<EOF
[Unit]
Description=Gunicorn socket for ${APP_NAME}

[Socket]
ListenStream=/run/${APP_NAME}.sock

[Install]
WantedBy=sockets.target
EOF

systemctl daemon-reload
systemctl enable --now "${APP_NAME}.socket"
systemctl restart "${APP_NAME}.service"

log "10) Nginx site config"
NGINX_SITE="/etc/nginx/sites-available/${APP_NAME}"
cat > "${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 25M;

    location /static/ {
        alias ${SRC_DIR}/staticfiles/;
        access_log off;
        expires 30d;
    }

    location /media/ {
        alias ${SRC_DIR}/media/;
        access_log off;
        expires 30d;
    }

    location / {
        include proxy_params;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header Host \$host;
        proxy_pass http://unix:/run/${APP_NAME}.sock;
    }
}
EOF

ln -sf "${NGINX_SITE}" "/etc/nginx/sites-enabled/${APP_NAME}"
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl reload nginx

log "11) Firewall (UFW) allow Nginx"
ufw allow 'Nginx Full' || true
ufw --force enable || true

log "12) SSL with Let's Encrypt (certbot)"
# This will update nginx config automatically to https
certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" --redirect

log "13) Final restart"
systemctl restart "${APP_NAME}.service"
systemctl reload nginx

log "✅ DONE"
echo "Your app should be live at: https://${DOMAIN}"
echo "Service status:"
systemctl --no-pager status "${APP_NAME}.service" | sed -n '1,12p'
