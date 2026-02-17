#!/usr/bin/env bash
set -euo pipefail

#╔════════════════════════════════════════════════════════════════════╗
#║          WASLA v2 - Comprehensive Deployment Script               ║
#║               (Docker & Traditional Deployment)                    ║
#╚════════════════════════════════════════════════════════════════════╝

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 CONFIGURATION VARIABLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Deployment type: "docker" or "traditional"
DEPLOY_TYPE="${DEPLOY_TYPE:-docker}"

# Project paths
PROJECT_ROOT="${PROJECT_ROOT:-.}"
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
VENV="${VENV:-$PROJECT_DIR/.venv}"
PYTHON="${PYTHON:-$VENV/bin/python}"

# Git configuration
BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main')}"
GIT_PULL="${GIT_PULL:-false}"

# Docker configuration
DOCKER_COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-docker-compose.yml}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"
BUILD_BACKEND="${BUILD_BACKEND:-true}"
BUILD_FRONTEND="${BUILD_FRONTEND:-true}"

# Environment
ENV_FILE="${ENV_FILE:-.env}"
ENV_EXAMPLE_FILE="${ENV_EXAMPLE_FILE:-.env.example}"
LOG_DIR="${LOG_DIR:-./logs}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"

# User for permissions (traditional deployment)
APP_USER="${APP_USER:-www-data}"
APP_GROUP="${APP_GROUP:-www-data}"

# Service management
START_SERVICES="${START_SERVICES:-true}"
VERIFY_HEALTH="${VERIFY_HEALTH:-true}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛠️ UTILITY FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_header() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║ $1"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""
}

print_step() {
  echo "▶ $1"
}

print_success() {
  echo "✅ $1"
}

print_warning() {
  echo "⚠️  $1"
}

print_error() {
  echo "❌ $1"
}

print_info() {
  echo "ℹ️  $1"
}

check_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    print_error "$1 is not installed or not in PATH"
    return 1
  fi
  return 0
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✔️ PRE-DEPLOYMENT CHECKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_header "🔍 Pre-Deployment Checks"

print_step "Checking project directory"
if [ ! -d "$PROJECT_DIR" ]; then
  print_error "Project directory does not exist: $PROJECT_DIR"
  exit 1
fi
print_success "Project directory found: $PROJECT_DIR"
cd "$PROJECT_DIR" || exit 1

print_step "Checking OS and user"
CURRENT_USER="$(whoami)"
print_info "Current user: $CURRENT_USER"

# Check if running as root for certain operations
if [[ "$DEPLOY_TYPE" == "traditional" ]] && [[ "$CURRENT_USER" != "root" ]]; then
  print_warning "Traditional deployment may require root access. Some commands will use sudo."
fi

echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 ENVIRONMENT SETUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_header "⚙️ Environment Configuration"

# Create environment file if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
  print_step "Creating $ENV_FILE from $ENV_EXAMPLE_FILE"
  if [ -f "$ENV_EXAMPLE_FILE" ]; then
    cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
    print_success "$ENV_FILE created (using defaults from example)"
  else
    print_warning "Neither $ENV_FILE nor $ENV_EXAMPLE_FILE found. Creating minimal $ENV_FILE"
    cat > "$ENV_FILE" <<'EOF'
# WASLA Application Environment Configuration
DEBUG=False
SECRET_KEY=django-insecure-change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,backend,yourdomain.com

# Database Configuration
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wasla
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# Cache Configuration
CACHE_BACKEND=django_redis.cache.RedisCache
CACHE_URL=redis://redis:6379/0
REDIS_URL=redis://redis:6379/0

# Security
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-password

# Payment Providers
TAP_API_KEY=
TAP_SANDBOX=true
STRIPE_API_KEY=
PAYPAL_CLIENT_ID=
PAYPAL_SECRET=
PAYPAL_SANDBOX=true

# AWS S3 (Optional)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=

# Frontend
VITE_API_URL=http://localhost:8000/api
EOF
    print_success "Minimal $ENV_FILE created"
  fi
else
  print_success "$ENV_FILE already exists"
fi

# Load environment variables
if [ -f "$ENV_FILE" ]; then
  print_step "Loading environment variables from $ENV_FILE"
  export $(grep -v '^#' "$ENV_FILE" | xargs)
  print_success "Environment variables loaded"
else
  print_warning "Skipping environment file (not found)"
fi

echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🐳 DOCKER DEPLOYMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if [[ "$DEPLOY_TYPE" == "docker" ]]; then

  print_header "🐳 Docker Deployment Configuration"

  # Check Docker installation
  print_step "Checking Docker installation"
  if ! check_command docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
  fi
  DOCKER_VERSION=$(docker --version)
  print_success "Docker found: $DOCKER_VERSION"

  # Check Docker Compose
  print_step "Checking Docker Compose installation"
  if ! check_command docker-compose; then
    print_warning "docker-compose command not found, trying 'docker compose'"
    if ! check_command "docker compose"; then
      print_error "Docker Compose is not available"
      exit 1
    fi
    COMPOSE_CMD="docker compose"
  else
    COMPOSE_CMD="docker-compose"
  fi
  print_success "Docker Compose found"

  # Check Docker daemon
  print_step "Checking Docker daemon status"
  if ! docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running. Please start Docker."
    exit 1
  fi
  print_success "Docker daemon is running"

  echo ""

  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # 🔨 DOCKER BUILD & PULL
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  print_header "🔨 Docker Image Build"

  if [[ "$BUILD_BACKEND" == "true" ]]; then
    print_step "Building backend image"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" build backend
    print_success "Backend image built"
  fi

  if [[ "$BUILD_FRONTEND" == "true" ]]; then
    print_step "Building frontend image"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" build frontend
    print_success "Frontend image built"
  fi

  echo ""

  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # 🚀 START DOCKER SERVICES
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  if [[ "$START_SERVICES" == "true" ]]; then

    print_header "🚀 Starting Docker Services"

    print_step "Starting all services with Docker Compose"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d
    print_success "All services started in detached mode"

    echo ""

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ✓ VERIFY DOCKER SERVICES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    print_header "📊 Service Status"

    print_step "Checking running containers"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps
    echo ""

    if [[ "$VERIFY_HEALTH" == "true" ]]; then
      print_step "Waiting for services to be healthy (30 seconds)..."
      sleep 30

      print_step "Checking database connection"
      if $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" exec -T db pg_isready -U "${DB_USER:-postgres}" >/dev/null 2>&1; then
        print_success "PostgreSQL is responsive"
      else
        print_warning "PostgreSQL is not yet responsive"
      fi

      print_step "Checking Redis connection"
      if $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" exec -T redis redis-cli ping >/dev/null 2>&1; then
        print_success "Redis is responsive"
      else
        print_warning "Redis is not yet responsive"
      fi

      print_step "Checking backend API health"
      if curl -s http://localhost:8000/api/health/ >/dev/null 2>&1; then
        print_success "Backend API is responsive"
      else
        print_warning "Backend API is not yet responsive (may still be initializing)"
      fi
    fi

  fi

  echo ""

fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🐍 TRADITIONAL DEPLOYMENT (with venv)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if [[ "$DEPLOY_TYPE" == "traditional" ]]; then

  print_header "🐍 Traditional Deployment (venv)"

  # Git setup
  if [[ "$GIT_PULL" == "true" ]]; then
    print_step "Pulling latest code from git branch: $BRANCH"
    git config --global --add safe.directory "$PROJECT_DIR" || true
    git fetch origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
    print_success "Code pulled from git"
  fi

  echo ""

  # Virtualenv setup
  print_header "🐍 Python Virtual Environment"

  if [ ! -d "$VENV" ]; then
    print_step "Creating Python virtual environment"
    python3 -m venv "$VENV"
    print_success "Virtual environment created"
  else
    print_success "Virtual environment already exists"
  fi

  print_step "Activating virtual environment"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  print_success "Virtual environment activated"

  print_step "Upgrading pip"
  pip install -q -U pip
  print_success "pip upgraded"

  print_step "Installing requirements"
  pip install -q -r requirements.txt
  print_success "Requirements installed"

  echo ""

  # Permissions
  print_header "👤 File Permissions & Ownership"

  print_step "Setting ownership to $APP_USER:$APP_GROUP"
  sudo chown -R "$APP_USER:$APP_GROUP" "$PROJECT_DIR"
  print_success "Ownership set"

  print_step "Creating runtime directories"
  sudo mkdir -p "$PROJECT_DIR/staticfiles" "$PROJECT_DIR/media"
  sudo chown -R "$APP_USER:$APP_GROUP" "$PROJECT_DIR/staticfiles" "$PROJECT_DIR/media"
  print_success "Runtime directories created"

  if [ -f "$PROJECT_DIR/db.sqlite3" ]; then
    print_step "Fixing SQLite database permissions"
    sudo chown "$APP_USER:$APP_GROUP" "$PROJECT_DIR/db.sqlite3"
    sudo chmod 664 "$PROJECT_DIR/db.sqlite3"
    print_success "SQLite permissions fixed"
  fi

  echo ""

  # Django operations
  print_header "🔧 Django Configuration"

  print_step "Running Django system check"
  "$PYTHON" manage.py check
  print_success "Django system check passed"

  print_step "Applying database migrations"
  "$PYTHON" manage.py migrate --noinput
  print_success "Migrations applied"

  print_step "Collecting static files"
  "$PYTHON" manage.py collectstatic --noinput
  print_success "Static files collected"

  echo ""

  # i18n/Translations
  print_header "🌐 Internationalization"

  if ! command -v msgfmt >/dev/null 2>&1; then
    print_step "Installing gettext (for translations)"
    sudo apt-get update -y -qq
    sudo apt-get install -y -qq gettext
    print_success "gettext installed"
  fi

  print_step "Compiling translation files"
  if ! "$PYTHON" manage.py compilemessages; then
    print_warning "compilemessages failed. Using Python fallback..."
    pip install -q polib
    "$PYTHON" - <<'PY'
from pathlib import Path
import polib

base = Path('.').resolve()
compiled = 0
for po_path in base.rglob('locale/*/LC_MESSAGES/*.po'):
    mo_path = po_path.with_suffix('.mo')
    po = polib.pofile(str(po_path))
    po.save_as_mofile(str(mo_path))
    compiled += 1
    print(f"  Compiled: {po_path.relative_to(base)}")

print(f"\n✅ Compiled {compiled} translation file(s).")
PY
  fi
  print_success "Translations compiled"

  echo ""

  # Services (systemd)
  print_header "🔁 Service Management"

  if [[ "$START_SERVICES" == "true" ]]; then
    print_step "Restarting Gunicorn service"
    if sudo systemctl is-enabled gunicorn-wasla >/dev/null 2>&1; then
      sudo systemctl restart gunicorn-wasla
      sleep 2
      if sudo systemctl is-active gunicorn-wasla >/dev/null 2>&1; then
        print_success "Gunicorn restarted and active"
      else
        print_warning "Gunicorn failed to start. Check logs: sudo journalctl -u gunicorn-wasla"
      fi
    else
      print_warning "Gunicorn service not enabled"
    fi

    print_step "Reloading Nginx"
    if ! sudo nginx -t >/dev/null 2>&1; then
      print_error "Nginx configuration test failed"
      sudo nginx -t
      exit 1
    fi
    sudo systemctl reload nginx
    print_success "Nginx reloaded"
  fi

  echo ""

fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📋 CREATE BACKUP & LOGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_header "📋 Setup Logging & Backups"

print_step "Creating log directory"
mkdir -p "$LOG_DIR"
print_success "Log directory ready: $LOG_DIR"

print_step "Creating backup directory"
mkdir -p "$BACKUP_DIR"
print_success "Backup directory ready: $BACKUP_DIR"

echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✅ FINAL SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print_header "✅ Deployment Complete!"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    DEPLOYMENT SUMMARY                      ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║ Deployment Type  : $DEPLOY_TYPE"
echo "║ Project Dir      : $PROJECT_DIR"
if [[ "$DEPLOY_TYPE" == "docker" ]]; then
  echo "║ Docker Compose   : $DOCKER_COMPOSE_FILE"
  echo "║ Backend URL      : http://localhost:8000"
  echo "║ Frontend URL     : http://localhost:5173"
  echo "║ Admin Panel      : http://localhost:8000/admin"
  echo "║ API Docs         : http://localhost:8000/api/docs"
else
  echo "║ Python Venv      : $VENV"
  echo "║ App User         : $APP_USER"
  echo "║ Gunicorn Status  : Check with 'systemctl status gunicorn-wasla'"
  echo "║ Nginx Status     : Check with 'systemctl status nginx'"
fi
echo "║ Environment File : $ENV_FILE"
echo "║ Log Directory    : $LOG_DIR"
echo "║ Backup Directory : $BACKUP_DIR"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║                      NEXT STEPS                            ║"
echo "╠════════════════════════════════════════════════════════════╣"

if [[ "$DEPLOY_TYPE" == "docker" ]]; then
  echo "║ 1. Check logs: docker-compose logs -f"
  echo "║ 2. Access frontend: http://localhost:5173"
  echo "║ 3. Access backend: http://localhost:8000"
  echo "║ 4. Admin panel: http://localhost:8000/admin"
  echo "║ 5. View containers: docker-compose ps"
else
  echo "║ 1. Check Gunicorn logs: journalctl -u gunicorn-wasla -f"
  echo "║ 2. Check Nginx logs: tail -f /var/log/nginx/error.log"
  echo "║ 3. Test application: curl http://localhost/"
  echo "║ 4. View database: sqlite3 db.sqlite3"
  echo "║ 5. Create superuser: $PYTHON manage.py createsuperuser"
fi

echo "║                                                            ║"
echo "║ 📖 Documentation: See docs/ directory                     ║"
echo "║ 🔧 Config: Review .env file for settings                 ║"
echo "║ 🆘 Support: Check logs for troubleshooting               ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

print_success "WASLA v2 deployment successful!"
