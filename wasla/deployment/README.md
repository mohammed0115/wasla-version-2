# Deployment (Ubuntu + Gunicorn + Nginx) | النشر (Ubuntu + Gunicorn + Nginx)

**AR:** هذه السكربتات تقوم بنشر مشروع Wasla (Django) على سيرفر Ubuntu باستخدام:  
- `systemd` + `gunicorn` (unix socket)  
- `nginx` كـ reverse proxy  
- SSL اختياري عبر `certbot` (يتطلب دومين حقيقي)

**EN:** These scripts deploy the Wasla Django app to an Ubuntu server using:
- `systemd` + `gunicorn` (unix socket)
- `nginx` reverse proxy
- optional `certbot` SSL (requires a real domain)

## Before you start

**AR:**
1) تأكد أن السيرفر Ubuntu 20.04+.
2) افتح المنافذ: `80` (HTTP) و (اختياري) `443` (HTTPS).
3) قرر كيف ستجلب الكود للسيرفر:
   - **مُوصى به:** ارفع المشروع على GitHub/GitLab واضبط `GIT_REPO_URL`.
   - أو ارفع الملفات يدويًا ثم تجاوز `01_git_sync.sh`.

**EN:**
1) Make sure the server has Ubuntu 20.04+.
2) Open firewall ports: `80` (HTTP) and optionally `443` (HTTPS).
3) Decide how you will get code onto the server:
   - **Recommended:** push your repo to GitHub/GitLab and set `GIT_REPO_URL`.
   - Otherwise: upload files manually, then skip `01_git_sync.sh`.

## Quick deploy (domain + SSL) | نشر سريع (دومين + SSL)

**AR:** على السيرفر (كمستخدم root):  
**EN:** On the server (as root):

```bash
export PROJECT_NAME=wasla
export PROJECT_ROOT=/opt/wasla
export BACKEND_PATH=/opt/wasla/app
export GIT_REPO_URL="https://github.com/<you>/<repo>.git"
export GIT_BRANCH=main
export DOMAIN_NAME="yourdomain.com"

bash deployment/00_env_check.sh
bash deployment/01_git_sync.sh
bash deployment/02_system_setup.sh
bash deployment/04_gunicorn_service.sh
bash deployment/05_nginx_setup.sh
bash deployment/06_ssl_setup.sh
```

**AR (ملاحظات):**
- خطوة `06_ssl_setup.sh` تقوم بتفعيل `DJANGO_SECURE_SSL_REDIRECT=1` وتفعيل secure cookies داخل `/etc/<project>/django.env`.
- SSL لن يعمل على IP فقط (Let's Encrypt لا يصدر شهادات لـ IP).

**EN (Notes):**
- Step `06_ssl_setup.sh` enables `DJANGO_SECURE_SSL_REDIRECT=1` and secure cookies in `/etc/<project>/django.env`.
- SSL will not work for a bare IP (Let's Encrypt does not issue certs for IPs).

## Deploy using server IP only (HTTP) | النشر باستخدام IP فقط (HTTP)

**AR:** إذا لديك IP فقط (مثال: `76.13.143.149`) بدون دومين:

**EN:** If you only have the server IP (example: `76.13.143.149`) and no domain yet:

```bash
export PROJECT_NAME=wasla
export PROJECT_ROOT=/opt/wasla
export BACKEND_PATH=/opt/wasla/app
export GIT_REPO_URL="https://github.com/<you>/<repo>.git"
export GIT_BRANCH=main
export DOMAIN_NAME="76.13.143.149"

bash deployment/00_env_check.sh
bash deployment/01_git_sync.sh
bash deployment/02_system_setup.sh
bash deployment/04_gunicorn_service.sh
bash deployment/05_nginx_setup.sh
```

Do **not** run `deployment/06_ssl_setup.sh` (it will fail without a real domain).

## Where config lives

**AR/EN:**
- Django runtime env: `/etc/<project>/django.env`
- OCR env (optional): `/etc/<project>/ocr.env`
- Static files: `/var/lib/<project>/static`
- Media uploads: `/var/lib/<project>/media`
- Gunicorn service: `gunicorn-<project>.service`
- Nginx logs: `/var/log/nginx/<project>.*.log`

## Custom domains (multi-tenant) | الدومينات الخاصة

**AR:**
- لتفعيل الربط الديناميكي للدومينات، اضبط المتغيرات التالية داخل `/etc/<project>/django.env`:
  - `WASSLA_BASE_DOMAIN`
  - `CUSTOM_DOMAIN_SERVER_IP`
  - `CUSTOM_DOMAIN_SSL_ENABLED=1`
  - `CUSTOM_DOMAIN_CERTBOT_WEBROOT=/var/www/certbot`
  - `CUSTOM_DOMAIN_NGINX_ENABLED=1`
  - `CUSTOM_DOMAIN_NGINX_DOMAINS_DIR=/etc/nginx/wassla/domains`
- تأكد من أن Nginx يحتوي على include لهذه المسارات:
  - `/etc/nginx/wassla/domains/*.conf`

**EN:**
- Enable dynamic custom domains by setting in `/etc/<project>/django.env`:
  - `WASSLA_BASE_DOMAIN`
  - `CUSTOM_DOMAIN_SERVER_IP`
  - `CUSTOM_DOMAIN_SSL_ENABLED=1`
  - `CUSTOM_DOMAIN_CERTBOT_WEBROOT=/var/www/certbot`
  - `CUSTOM_DOMAIN_NGINX_ENABLED=1`
  - `CUSTOM_DOMAIN_NGINX_DOMAINS_DIR=/etc/nginx/wassla/domains`
- Ensure Nginx includes:
  - `/etc/nginx/wassla/domains/*.conf`

## Useful commands

**AR/EN:**
```bash
systemctl status gunicorn-wasla --no-pager
journalctl -u gunicorn-wasla -n 200 --no-pager
nginx -t
systemctl reload nginx
```
