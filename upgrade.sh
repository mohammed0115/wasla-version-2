#!/usr/bin/env bash
set -euo pipefail

# =============================
# CONFIG (عدلها حسب مشروعك)
# =============================
APP_NAME="w-sala"                 # اسم الخدمة/المشروع (للطباعة فقط)
REPO_DIR="/var/www/wasla-version-2/wasla"        # مسار الريبو على السيرفر
BRANCH="copilit"                  # الفرع الذي تريد التحديث منه
VENV_DIR="$REPO_DIR/.venv"        # مسار الـ venv
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# systemd services (عدلها حسب الموجود عندك)
DJANGO_SERVICE="w-sala-web"       # gunicorn/uwsgi service
CELERY_SERVICE="w-sala-celery"    # celery worker service (لو عندك)
CELERYBEAT_SERVICE="w-sala-beat"  # celery beat service (لو عندك)

# Django settings
DJANGO_MANAGE="$REPO_DIR/manage.py"
ENV_FILE="$REPO_DIR/.env"         # ملف env (اختياري لكن مفضل)
BACKUP_DIR="/var/backups/w-sala"
TS="$(date +%Y%m%d_%H%M%S)"

# =============================
# HELPERS
# =============================
log(){ echo -e "\n\033[1;34m[$(date +'%F %T')] $*\033[0m"; }
warn(){ echo -e "\n\033[1;33m[WARN] $*\033[0m"; }
die(){ echo -e "\n\033[1;31m[ERROR] $*\033[0m"; exit 1; }

need_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

# =============================
# PRECHECKS
# =============================
need_cmd git
need_cmd systemctl
need_cmd bash

log "Starting upgrade for $APP_NAME"
log "Repo: $REPO_DIR | Branch: $BRANCH | Backup: $BACKUP_DIR"

[ -d "$REPO_DIR" ] || die "REPO_DIR not found: $REPO_DIR"
[ -f "$DJANGO_MANAGE" ] || die "manage.py not found: $DJANGO_MANAGE"
[ -d "$VENV_DIR" ] || die "VENV_DIR not found: $VENV_DIR"
[ -x "$PYTHON" ] || die "Python not executable: $PYTHON"

mkdir -p "$BACKUP_DIR"

# =============================
# BACKUP (DB + current code ref)
# =============================
log "Saving current git ref + basic backup snapshot"
cd "$REPO_DIR"
CURRENT_REF="$(git rev-parse --short HEAD || true)"
echo "$CURRENT_REF" > "$BACKUP_DIR/prev_ref_$TS.txt"

# Optional: DB backup if using Postgres (requires DATABASE_URL in env)
if [ -f "$ENV_FILE" ] && grep -q "^DATABASE_URL=" "$ENV_FILE"; then
  warn "DATABASE_URL found in .env. If you want auto DB backup, install pg_dump and provide PG creds."
else
  warn "No DATABASE_URL in .env (or .env missing). Skipping DB backup."
fi

# =============================
# STOP SERVICES (graceful)
# =============================
log "Stopping services (if they exist)"
systemctl stop "$CELERYBEAT_SERVICE" 2>/dev/null || true
systemctl stop "$CELERY_SERVICE" 2>/dev/null || true
systemctl stop "$DJANGO_SERVICE" 2>/dev/null || true

# =============================
# GIT PULL
# =============================
log "Pulling latest code from GitHub"
git fetch --all --prune
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

NEW_REF="$(git rev-parse --short HEAD || true)"
log "Updated git ref: $CURRENT_REF -> $NEW_REF"

# =============================
# INSTALL / UPDATE DEPENDENCIES
# =============================
log "Installing dependencies"
$PIP install -U pip wheel setuptools
if [ -f "$REPO_DIR/requirements.txt" ]; then
  $PIP install -r "$REPO_DIR/requirements.txt"
elif [ -f "$REPO_DIR/pyproject.toml" ]; then
  $PIP install .
else
  warn "No requirements.txt or pyproject.toml found. Skipping pip install."
fi

# =============================
# DJANGO CHECKS + MIGRATIONS
# =============================
log "Running Django system checks"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

$PYTHON "$DJANGO_MANAGE" check --deploy || warn "check --deploy returned warnings (review output)"
$PYTHON "$DJANGO_MANAGE" migrate --noinput

# =============================
# STATIC FILES
# =============================
if $PYTHON "$DJANGO_MANAGE" help | grep -q collectstatic; then
  log "Collecting static files"
  $PYTHON "$DJANGO_MANAGE" collectstatic --noinput
fi

# =============================
# RESTART SERVICES
# =============================
log "Starting services"
systemctl start "$DJANGO_SERVICE" 2>/dev/null || die "Failed to start $DJANGO_SERVICE"
systemctl start "$CELERY_SERVICE" 2>/dev/null || warn "Could not start $CELERY_SERVICE (maybe not installed)"
systemctl start "$CELERYBEAT_SERVICE" 2>/dev/null || warn "Could not start $CELERYBEAT_SERVICE (maybe not installed)"

# =============================
# HEALTH CHECK
# =============================
log "Health check (local)"
if curl -fsS "http://127.0.0.1/healthz" >/dev/null 2>&1; then
  log "✅ Healthz OK"
else
  warn "Healthz failed. Check logs: journalctl -u $DJANGO_SERVICE -n 200 --no-pager"
fi

log "Upgrade finished ✅"
log "Rollback tip: git checkout $CURRENT_REF && rerun migrate/collectstatic then restart services."
