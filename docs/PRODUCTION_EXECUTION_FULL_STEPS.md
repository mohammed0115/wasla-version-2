# WASLA Production Execution (Full Steps)

## 0) Deployment Model
This runbook is for **traditional Linux deployment** (Nginx + Gunicorn + systemd + MySQL/PostgreSQL + Redis) for the Django app in `wasla/`.

---

## 1) Server Prerequisites
Run on Ubuntu 22.04+ as root/sudo user:

```bash
sudo apt update && sudo apt install -y \
  git curl unzip software-properties-common \
  python3 python3-venv python3-pip \
  nginx redis-server \
  mysql-server postgresql postgresql-contrib
```

Optional (for TLS):

```bash
sudo apt install -y certbot python3-certbot-nginx
```

---

## 2) Clone Project and Prepare Runtime

```bash
sudo mkdir -p /var/www
cd /var/www
sudo git clone https://github.com/mohammed0115/wasla-version-2.git wasla
cd wasla/wasla
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3) Create Production .env
Copy and edit:

```bash
cp .env.example .env
nano .env
```

Use these **required production keys** (matching current settings):

```env
ENVIRONMENT=production
DJANGO_SECRET_KEY=<strong-random-secret>
DJANGO_ALLOWED_HOSTS=w-sala.com,www.w-sala.com,.w-sala.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://w-sala.com,https://www.w-sala.com,https://*.w-sala.com

# DB selection: sqlite | mysql | postgresql
DJANGO_DB_DEFAULT=mysql

# MySQL
MYSQL_DB_HOST=127.0.0.1
MYSQL_DB_PORT=3306
MYSQL_DB_NAME=wasla
MYSQL_DB_USER=wasla_user
MYSQL_DB_PASSWORD=<strong-db-password>

# Or PostgreSQL (if selected)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=wasla
DB_USER=wasla_user
DB_PASSWORD=<strong-db-password>

# HTTPS cookies/security
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_SESSION_COOKIE_SECURE=1
DJANGO_CSRF_COOKIE_SECURE=1
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=1
DJANGO_SECURE_HSTS_PRELOAD=1

# Redis cache
CACHE_USE_REDIS=1
CACHE_REDIS_URL=redis://127.0.0.1:6379/1

# Celery
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# Domain behavior
WASSLA_BASE_DOMAIN=w-sala.com
DOMAIN_PROVISIONING_MODE=manual

# Language
DJANGO_LANGUAGE_CODE=ar
WASLA_ENABLE_AR=1
```

Generate secret quickly:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 4) Database Setup

### Option A: MySQL

```bash
sudo mysql -e "CREATE DATABASE IF NOT EXISTS wasla CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'wasla_user'@'localhost' IDENTIFIED BY 'ChangeMeStrong!123';"
sudo mysql -e "GRANT ALL PRIVILEGES ON wasla.* TO 'wasla_user'@'localhost'; FLUSH PRIVILEGES;"
```

### Option B: PostgreSQL

```bash
sudo -u postgres psql -c "CREATE DATABASE wasla;"
sudo -u postgres psql -c "CREATE USER wasla_user WITH PASSWORD 'ChangeMeStrong!123';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE wasla TO wasla_user;"
```

---

## 5) Django Initialization

```bash
cd /var/www/wasla/wasla
source .venv/bin/activate
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py seed_wasla
```

---

## 5.1) Superadmin and Admin-Portal Roles

Seed admin portal RBAC roles/permissions:

```bash
cd /var/www/wasla/wasla
source .venv/bin/activate
python manage.py seed_admin_portal_rbac
```

Create/update superadmin account for admin portal:

```bash
python manage.py create_admin_staff \
    --username superadmin \
    --email admin@w-sala.com \
    --password 'ChangeMeStrong!123'
```

Assign admin-portal role to the account:

```bash
python manage.py assign_admin_role superadmin SuperAdmin
```

Verify role assignment:

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; from apps.admin_portal.models import AdminUserRole; U=get_user_model(); u=U.objects.get(username='superadmin'); print(u.is_staff, u.is_superuser, AdminUserRole.objects.get(user=u).role.name)"
```

Login URL:
- https://w-sala.com/admin-portal/login/

---

## 6) Gunicorn Service (systemd)
Create `/etc/systemd/system/gunicorn-wasla.service`:

```ini
[Unit]
Description=Gunicorn for WASLA
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/wasla/wasla
Environment="PATH=/var/www/wasla/wasla/.venv/bin"
ExecStart=/var/www/wasla/wasla/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 4 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo chown -R www-data:www-data /var/www/wasla
sudo systemctl daemon-reload
sudo systemctl enable gunicorn-wasla
sudo systemctl restart gunicorn-wasla
sudo systemctl status gunicorn-wasla --no-pager
```

---

## 7) Optional Celery Services (recommended)
Create worker service `/etc/systemd/system/celery-wasla.service`:

```ini
[Unit]
Description=Celery Worker for WASLA
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/wasla/wasla
Environment="PATH=/var/www/wasla/wasla/.venv/bin"
ExecStart=/var/www/wasla/wasla/.venv/bin/celery -A config worker --loglevel=INFO
Restart=always

[Install]
WantedBy=multi-user.target
```

Create beat service `/etc/systemd/system/celery-beat-wasla.service`:

```ini
[Unit]
Description=Celery Beat for WASLA
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/wasla/wasla
Environment="PATH=/var/www/wasla/wasla/.venv/bin"
ExecStart=/var/www/wasla/wasla/.venv/bin/celery -A config beat --loglevel=INFO
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-wasla celery-beat-wasla
sudo systemctl restart celery-wasla celery-beat-wasla
```

---

## 8) Nginx Reverse Proxy
Create `/etc/nginx/sites-available/wasla`:

```nginx
server {
    listen 80;
    server_name w-sala.com www.w-sala.com *.w-sala.com;

    client_max_body_size 20m;

    location /static/ {
        alias /var/www/wasla/wasla/static/;
    }

    location /media/ {
        alias /var/www/wasla/wasla/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:

```bash
sudo ln -sf /etc/nginx/sites-available/wasla /etc/nginx/sites-enabled/wasla
sudo nginx -t
sudo systemctl restart nginx
```

---

## 9) Enable HTTPS (Production Mandatory)

```bash
sudo certbot --nginx -d w-sala.com -d www.w-sala.com
sudo systemctl reload nginx
```

Confirm auto-renew:

```bash
sudo systemctl status certbot.timer --no-pager
```

---

## 10) Firewall and Basic Hardening

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
```

Also ensure:
- DB ports are not publicly exposed.
- Redis bound to localhost/private network.
- `.env` permissions are strict.

```bash
sudo chown www-data:www-data /var/www/wasla/wasla/.env
sudo chmod 640 /var/www/wasla/wasla/.env
```

---

## 11) Validation Checklist (Go-Live)

```bash
# Services
sudo systemctl is-active gunicorn-wasla nginx redis-server

# App check
curl -I https://w-sala.com/

# Django checks
cd /var/www/wasla/wasla
source .venv/bin/activate
python manage.py check --deploy
python manage.py showmigrations | grep '\[ \]' || echo "All migrations applied"
```

Functional smoke tests:
- Admin portal login works.
- Merchant onboarding works with manual payment approval flow.
- Store resolution/subdomain routing works.
- Static/media assets load via HTTPS.

---

## 12) Zero-Downtime Update Procedure

```bash
cd /var/www/wasla
sudo git fetch origin
sudo git checkout main
sudo git pull --ff-only origin main
cd /var/www/wasla/wasla
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-wasla celery-wasla celery-beat-wasla nginx
```

Rollback quick path:

```bash
cd /var/www/wasla
sudo git log --oneline -n 5
sudo git reset --hard <previous_commit>
cd /var/www/wasla/wasla
source .venv/bin/activate
python manage.py migrate --noinput
sudo systemctl restart gunicorn-wasla nginx
```

---

## 13) Project-Specific Note (Important)
Current `config/settings.py` contains a hardcoded `DEBUG = True` later in the file. Before strict production rollout, update settings so `DEBUG` is fully environment-driven, then re-run:

```bash
python manage.py check --deploy
```

Without this fix, production security posture is not complete.
