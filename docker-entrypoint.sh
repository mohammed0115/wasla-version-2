#!/bin/sh
# Docker entrypoint script for WASLA backend

set -e

echo "🚀 Starting WASLA Backend..."

# Wait for database
echo "⏳ Waiting for PostgreSQL..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done
echo "✅ PostgreSQL is ready"

# Run migrations
echo "📦 Running migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📂 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create cache table (for database-backed cache)
echo "💾 Setting up cache..."
python manage.py createcachetable

# Create superuser if it doesn't exist
echo "👤 Checking for superuser..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@wasla.local',
        password='admin123'
    )
    print("✅ Created admin superuser (admin / admin123)")
else:
    print("⏺️ Admin user already exists")
END

# Start Gunicorn
echo "🚀 Starting Gunicorn..."
exec gunicorn \
    config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    "$@"
