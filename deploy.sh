#!/usr/bin/env bash
set -euo pipefail

# ==========================
# Wasla One-File Deploy Script
# ==========================
APP_DIR="/var/www/wasla-version-2/wasla"
VENV_DIR="$APP_DIR/venv"

# Django project module (settings + wsgi)
DJANGO_PROJECT_MODULE="config"              # -> config.settings / config.wsgi:application
DJANGO_SETTINGS_MODULE="${DJANGO_PROJECT_MODULE}.settings"
DJANGO_WSGI_APP="${DJANGO_PROJECT_MODULE}.wsgi:application"

# Domain / Nginx
DOMAIN_1="w-sala.com"
DOMAIN_2="www.w-sala.com"
NGINX_SITE_NAME="wasla"
NGINX_AVAILABLE="/etc/nginx/sites-available/${NGINX_SITE_NAME}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"

# Gunicorn
GUNICORN_SERVICE="/etc/systemd/system/gunicorn-wasla.service"
GUNICORN_SOCK="/run/gunicorn/gunicorn-wasla.sock"
GUNICORN_WORKERS="3"
GUNICORN_TIMEOUT="300"

# Backup dir
BACKUP_DIR="/root/wasla_backup_deploy/$(date +%Y%m%d_%H%M%S)"

echo "==> Starting Wasla deploy"
echo "==> APP_DIR: $APP_DIR"
echo "==> DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "==> DJANGO_WSGI_APP: $DJANGO_WSGI_APP"
echo "==> Backup dir: $BACKUP_DIR"

# --------------------------
# 0) Sanity checks
# --------------------------
if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR does not exist"
  exit 1
fi

if [ ! -f "$APP_DIR/manage.py" ]; then
  echo "ERROR: manage.py not found in $APP_DIR"
  echo "Make sure your Django project root is /var/www/wasla"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

# --------------------------
# 1) Backup old deployment files
# --------------------------
echo "==> Backing up existing deployment files (if any)"
sudo mkdir -p "$BACKUP_DIR"

sudo cp -a "$GUNICORN_SERVICE" "$BACKUP_DIR/" 2>/dev/null || true
sudo cp -a "$NGINX_AVAILABLE" "$BACKUP_DIR/" 2>/dev/null || true
sudo cp -a "$NGINX_ENABLED" "$BACKUP_DIR/" 2>/dev/null || true

# --------------------------
# 2) Create/ensure venv
# --------------------------
echo "==> Ensuring venv exists: $VENV_DIR"
cd "$APP_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "==> Python: $(which python)"
echo "==> Pip:    $(which pip)"

echo "==> Upgrading pip"
pip install -U pip

# --------------------------
# 3) Install requirements
# --------------------------
if [ -f "$APP_DIR/requirements.txt" ]; then
  echo "==> Installing requirements.txt"
  pip install -r "$APP_DIR/requirements.txt"
else
  echo "WARN: requirements.txt not found, installing minimal packages"
  pip install "Django>=5.2" gunicorn
fi

# Ensure gunicorn exists
echo "==> Ensuring gunicorn is installed"
pip install -U gunicorn

echo "==> gunicorn path: $(command -v gunicorn)"
gunicorn --version || true

# --------------------------
# 4) Write/Update Gunicorn systemd service
# --------------------------
echo "==> Writing systemd service: $GUNICORN_SERVICE"

sudo tee "$GUNICORN_SERVICE" >/dev/null <<EOF
[Unit]
Description=gunicorn-wasla
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR

Environment="DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"
Environment="PATH=$VENV_DIR/bin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"

RuntimeDirectory=gunicorn
RuntimeDirectoryMode=0755

ExecStart=$VENV_DIR/bin/gunicorn \\
  --workers $GUNICORN_WORKERS \\
  --timeout $GUNICORN_TIMEOUT \\
  --bind unix:$GUNICORN_SOCK \\
  $DJANGO_WSGI_APP

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# --------------------------
# 5) Write/Update Nginx site
# --------------------------
echo "==> Writing nginx site: $NGINX_AVAILABLE"

sudo tee "$NGINX_AVAILABLE" >/dev/null <<EOF
server {
    server_name $DOMAIN_1 $DOMAIN_2;

    client_max_body_size 50M;
    server_tokens off;

    access_log /var/log/nginx/wasla.access.log;
    error_log  /var/log/nginx/wasla.error.log;

    location /static/ {
        alias $APP_DIR/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    location /media/ {
        alias $APP_DIR/media/;
        expires 30d;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:$GUNICORN_SOCK;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/$DOMAIN_1/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_1/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    listen 80;
    server_name $DOMAIN_1 $DOMAIN_2;
    return 301 https://\$host\$request_uri;
}
EOF

echo "==> Enabling nginx site"
sudo ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"

# --------------------------
# 6) Django commands
# --------------------------
echo "==> Django check"
python manage.py check || true

echo "==> Migrate"
python manage.py migrate --noinput

echo "==> Collectstatic"
python manage.py collectstatic --noinput

# Permissions (safe)
echo "==> Setting ownership"
sudo chown -R www-data:www-data "$APP_DIR" || true

# --------------------------
# 7) Restart services
# --------------------------
echo "==> Restarting gunicorn"
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-wasla >/dev/null 2>&1 || true
sudo systemctl restart gunicorn-wasla

echo "==> Checking gunicorn status"
sudo systemctl --no-pager status gunicorn-wasla || true

echo "==> Testing nginx config"
sudo nginx -t

echo "==> Reloading nginx"
sudo systemctl reload nginx

echo "✅ Deploy completed successfully."
echo "If you still see 502, run:"
echo "  sudo journalctl -u gunicorn-wasla -n 120 --no-pager"
