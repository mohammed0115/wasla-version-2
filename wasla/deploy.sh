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

# -------- Language / i18n --------
if ! command -v msgfmt >/dev/null 2>&1; then
  echo "🛠️ msgfmt not found -> installing gettext"
  sudo apt-get update -y
  sudo apt-get install -y gettext
fi

echo "🌐 Compile translation files (.po -> .mo)"
if ! sudo -u www-data "$PYTHON" manage.py compilemessages; then
  echo "⚠️ compilemessages failed (likely missing msgfmt). Using Python fallback..."
  pip install -q polib
  sudo -u www-data "$PYTHON" - <<'PY'
from pathlib import Path
import polib

base = Path('.').resolve()
compiled = 0
for po_path in base.rglob('locale/*/LC_MESSAGES/*.po'):
    mo_path = po_path.with_suffix('.mo')
    po = polib.pofile(str(po_path))
    po.save_as_mofile(str(mo_path))
    compiled += 1

print(f"✅ Fallback compiled {compiled} locale file(s).")
PY
fi

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
