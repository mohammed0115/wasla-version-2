#!/usr/bin/env bash
set -Eeuo pipefail

# 07_monitoring.sh
# Monitoring checks (no notifications here):
# - Checks systemd services (gunicorn + nginx)
# - Scans logs for 500/502/403 patterns
# - Writes health.status if issues detected

PROJECT_NAME="${PROJECT_NAME:-wasla}"
SERVICE_NAME="gunicorn-${PROJECT_NAME}.service"
NGINX_SERVICE="nginx.service"

STATUS_DIR="/var/lib/${PROJECT_NAME}"
STATUS_FILE="${STATUS_DIR}/health.status"

ACCESS_LOG="/var/log/nginx/${PROJECT_NAME}.access.log"
ERROR_LOG="/var/log/nginx/${PROJECT_NAME}.error.log"

mkdir -p "${STATUS_DIR}"

issues=0
report="$(mktemp)"
trap 'rm -f "${report}"' EXIT

{
  echo "timestamp=$(date -Is)"
  echo "project=${PROJECT_NAME}"
  echo
} >> "${report}"

if ! systemctl is-active --quiet "${NGINX_SERVICE}"; then
  issues=$((issues + 1))
  echo "[ISSUE] nginx is not active" >> "${report}"
  systemctl status "${NGINX_SERVICE}" --no-pager >> "${report}" || true
  echo >> "${report}"
fi

if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
  issues=$((issues + 1))
  echo "[ISSUE] gunicorn is not active (${SERVICE_NAME})" >> "${report}"
  systemctl status "${SERVICE_NAME}" --no-pager >> "${report}" || true
  echo >> "${report}"
fi

if [[ -f "${ACCESS_LOG}" ]]; then
  if tail -n 400 "${ACCESS_LOG}" | grep -E " (500|502|403) " >/dev/null 2>&1; then
    issues=$((issues + 1))
    echo "[ISSUE] nginx access log contains 500/502/403" >> "${report}"
    tail -n 80 "${ACCESS_LOG}" | grep -E " (500|502|403) " | tail -n 40 >> "${report}" || true
    echo >> "${report}"
  fi
fi

if [[ -f "${ERROR_LOG}" ]]; then
  if tail -n 200 "${ERROR_LOG}" | grep -E "error|crit|alert|emerg" >/dev/null 2>&1; then
    issues=$((issues + 1))
    echo "[ISSUE] nginx error log has recent errors" >> "${report}"
    tail -n 120 "${ERROR_LOG}" >> "${report}" || true
    echo >> "${report}"
  fi
fi

if journalctl -u "${SERVICE_NAME}" -n 200 --no-pager 2>/dev/null | grep -E "Traceback|ERROR|Exception" >/dev/null 2>&1; then
  issues=$((issues + 1))
  echo "[ISSUE] gunicorn logs contain errors" >> "${report}"
  journalctl -u "${SERVICE_NAME}" -n 120 --no-pager >> "${report}" || true
  echo >> "${report}"
fi

if (( issues > 0 )); then
  mv "${report}" "${STATUS_FILE}"
  chmod 0640 "${STATUS_FILE}" || true
  echo "HEALTH: issues detected (${issues}). Wrote ${STATUS_FILE}"
else
  rm -f "${STATUS_FILE}" || true
  echo "HEALTH: OK (no issues)."
fi

