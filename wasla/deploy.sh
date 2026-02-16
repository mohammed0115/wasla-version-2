#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting deployment for WASLA (v2)..."

# -------- Paths (UPDATE ONLY IF NEEDED) --------
PROJECT_DIR="/var/www/wasla-version-2/wasla"
VENV="$PROJECT_DIR/venv"
PYTHON="$VENV/bin/python"

# Optional: branch name
BRANCH="resolve1"

# -------- Pre-checks --------
echo "📁 Go to project directory: $PROJECT_DIR"
cd "$PROJECT_DIR"

echo "🔐 Mark repo as safe (git security)"
git config --global --add safe.directory "$PROJECT_DIR" || true

echo "📥 Pull latest code"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

# -------- Ownership & Permissions --------
echo "👤 Fix ownership (www-data)"
sudo chown -R www-data:www-data "$PROJECT_DIR"

echo "📂 Ensure runtime dirs exist"
sudo mkdir -p "$PROJECT_DIR/static" "$PROJECT_DIR/media"
sudo chown -R www-data:www-data "$PROJECT_DIR/static" "$PROJECT_DIR/media"

# SQLite safe permissions (ONLY if SQLite file exists)
if [ -f "$PROJECT_DIR/db.sqlite3" ]; then
  echo "🗄️ SQLite detected -> fix db permissions"
  sudo chown www-data:www-data "$PROJECT_DIR/db.sqlite3"
  sudo chmod 664 "$PROJECT_DIR/db.sqlite3" || true
fi

# -------- Virtualenv --------
if [ ! -d "$VENV" ]; then
  echo "🐍 venv not found -> creating venv"
  python3 -m venv "$VENV"
fi

echo "🐍 Activate virtualenv"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "⬆️ Upgrade pip"
pip install -U pip

echo "📦 Install requirements"
pip install -r "$PROJECT_DIR/requirements.txt"

# -------- Django Checks --------
echo "✅ Django system check"
sudo -u www-data "$PYTHON" manage.py check

# -------- DB Migrations --------
echo "🧱 Apply migrations"
sudo -u www-data "$PYTHON" manage.py migrate --noinput

# -------- Static Files --------
echo "🎨 Collect static files"
sudo -u www-data "$PYTHON" manage.py collectstatic --noinput

# -------- Services --------
echo "🔁 Restart gunicorn"
sudo systemctl restart gunicorn-wasla
sudo systemctl status gunicorn-wasla --no-pager || true

echo "🧪 Test nginx config"
sudo nginx -t

echo "🔁 Reload nginx"
sudo systemctl reload nginx

echo "✅ Deployment finished successfully!"
