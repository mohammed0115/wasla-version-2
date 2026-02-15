#!/usr/bin/env bash
set -Eeuo pipefail

# 04_gunicorn_service.sh
# App service setup:
# - Runs Django migrations
# - Collects static files
# - Creates systemd service for Gunicorn (unix socket)
# - Auto-restart on failure
# - Proper logging via journald
# - Exports OCR environment

PROJECT_NAME="${PROJECT_NAME:-wasla}"
PROJECT_ROOT="${PROJECT_ROOT:-/opt/wasla}"
BACKEND_PATH="${BACKEND_PATH:-${PROJECT_ROOT}/app}"
VENV_PATH="${VENV_PATH:-${PROJECT_ROOT}/venv}"
DOMAIN_NAME="${DOMAIN_NAME:-76.13.143.149}"

ENV_DIR="/etc/${PROJECT_NAME}"
DJANGO_ENV_FILE="${ENV_DIR}/django.env"
OCR_ENV_FILE="${ENV_DIR}/ocr.env"

RUNTIME_DIR="/var/lib/${PROJECT_NAME}"
STATIC_DIR="${RUNTIME_DIR}/static"
MEDIA_DIR="${RUNTIME_DIR}/media"

SOCKET_PATH="/run/gunicorn-${PROJECT_NAME}.sock"
SERVICE_NAME="gunicorn-${PROJECT_NAME}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [[ "$(id -u)" -ne 0 ]]; then
  fail "Must run as root."
fi

if [[ ! -x "${VENV_PATH}/bin/python" ]]; then
  fail "Virtualenv not found at ${VENV_PATH}. Run deployment/02_system_setup.sh first."
fi

if [[ ! -f "${BACKEND_PATH}/manage.py" ]]; then
  fail "manage.py not found at ${BACKEND_PATH}. Run deployment/01_git_sync.sh first."
fi

if ! id "${PROJECT_NAME}" >/dev/null 2>&1; then
  useradd --system --home-dir "${PROJECT_ROOT}" --create-home --shell /usr/sbin/nologin "${PROJECT_NAME}"
fi

mkdir -p "${ENV_DIR}" "${RUNTIME_DIR}" "${STATIC_DIR}" "${MEDIA_DIR}"
chown -R "${PROJECT_NAME}:www-data" "${RUNTIME_DIR}"
chmod 02750 "${RUNTIME_DIR}" || true
chmod 02755 "${STATIC_DIR}" "${MEDIA_DIR}" || true

# Keep existing secret key stable across runs.
existing_secret=""
if [[ -f "${DJANGO_ENV_FILE}" ]]; then
  existing_secret="$(grep -E '^DJANGO_SECRET_KEY=' "${DJANGO_ENV_FILE}" | head -n1 | cut -d= -f2- || true)"
fi

if [[ -z "${existing_secret}" ]]; then
  existing_secret="$(openssl rand -base64 64 | tr -d '\n')"
fi

workers_default="$(( ( $(nproc 2>/dev/null || echo 1) * 2 ) + 1 ))"
if (( workers_default < 3 )); then
  workers_default=3
fi

allowed_hosts="localhost,127.0.0.1,[::1]"
csrf_trusted=""
if [[ -n "${DOMAIN_NAME}" ]]; then
  if [[ "${DOMAIN_NAME}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    allowed_hosts="${DOMAIN_NAME},localhost,127.0.0.1,[::1]"
    csrf_trusted="http://${DOMAIN_NAME},https://${DOMAIN_NAME}"
  else
    allowed_hosts="${DOMAIN_NAME},www.${DOMAIN_NAME}"
    csrf_trusted="http://${DOMAIN_NAME},http://www.${DOMAIN_NAME},https://${DOMAIN_NAME},https://www.${DOMAIN_NAME}"
  fi
fi

cat > "${DJANGO_ENV_FILE}" <<EOF
DJANGO_SETTINGS_MODULE=wasla_sore.settings
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=${existing_secret}
DJANGO_ALLOWED_HOSTS=${allowed_hosts}
DJANGO_CSRF_TRUSTED_ORIGINS=${csrf_trusted}
DJANGO_STATIC_ROOT=${STATIC_DIR}
DJANGO_MEDIA_ROOT=${MEDIA_DIR}
DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_SESSION_COOKIE_SECURE=0
DJANGO_CSRF_COOKIE_SECURE=0
GUNICORN_WORKERS=${workers_default}
EOF
chmod 0640 "${DJANGO_ENV_FILE}"

# Run migrations + collectstatic with the same environment the service will use.
set -a
# shellcheck disable=SC1090
source "${DJANGO_ENV_FILE}"
if [[ -f "${OCR_ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${OCR_ENV_FILE}"
fi
set +a

cd "${BACKEND_PATH}"
"${VENV_PATH}/bin/python" manage.py compilemessages || true
"${VENV_PATH}/bin/python" manage.py migrate --noinput
"${VENV_PATH}/bin/python" manage.py collectstatic --noinput

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Gunicorn service for ${PROJECT_NAME}
After=network.target

[Service]
Type=simple
User=${PROJECT_NAME}
Group=www-data
WorkingDirectory=${BACKEND_PATH}
EnvironmentFile=${DJANGO_ENV_FILE}
EnvironmentFile=-${OCR_ENV_FILE}
ExecStartPre=/usr/bin/rm -f ${SOCKET_PATH}
ExecStart=${VENV_PATH}/bin/gunicorn \\
  --workers \$GUNICORN_WORKERS \\
  --bind unix:${SOCKET_PATH} \\
  --umask 007 \\
  --access-logfile - \\
  --error-logfile - \\
  --capture-output \\
  wasla_sore.wsgi:application
UMask=007
Restart=on-failure
RestartSec=3
TimeoutStopSec=30
KillSignal=SIGQUIT
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

systemctl is-active --quiet "${SERVICE_NAME}.service" || fail "Gunicorn service is not active."

echo "OK: Gunicorn service installed and running (${SERVICE_NAME})."
