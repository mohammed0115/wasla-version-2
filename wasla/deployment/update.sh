#!/bin/bash
set -e

echo "🚀 Starting deployment for WASLA..."

PROJECT_DIR="/var/www/wasla"
VENV="$PROJECT_DIR/venv"
PYTHON="$VENV/bin/python"

echo "📁 Go to project directory"
cd $PROJECT_DIR

echo "🔐 Mark repo as safe (git security)"
git config --global --add safe.directory $PROJECT_DIR

echo "📥 Pull latest code"
git pull origin main

echo "👤 Fix ownership (www-data)"
chown -R www-data:www-data $PROJECT_DIR

echo "🗄️ Fix database permissions"
chmod 664 $PROJECT_DIR/db.sqlite3 || true
chmod 775 $PROJECT_DIR

echo "🐍 Activate virtualenv"
source $VENV/bin/activate

echo "🧱 Apply migrations"
sudo -u www-data $PYTHON manage.py migrate --noinput

echo "🎨 Collect static files"
sudo -u www-data $PYTHON manage.py collectstatic --noinput

echo "🔁 Restart services"
systemctl restart gunicorn-wasla
systemctl restart nginx

echo "✅ Deployment finished successfully!"
