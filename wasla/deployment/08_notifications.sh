#!/usr/bin/env bash
set -Eeuo pipefail

# 08_notifications.sh
# Notifications (email) based on health.status:
# - Reads health.status
# - Sends a single email alert with logs + timestamp
# - Avoids spamming using a cooldown marker
# - Cleans health.status after a successful send

PROJECT_NAME="${PROJECT_NAME:-wasla}"
DOMAIN_NAME="${DOMAIN_NAME:-$(hostname -f)}"

STATUS_DIR="/var/lib/${PROJECT_NAME}"
STATUS_FILE="${STATUS_DIR}/health.status"
LAST_SENT_FILE="${STATUS_DIR}/health.last_sent"

ALERT_EMAIL_TO="${ALERT_EMAIL_TO:-}"
ALERT_EMAIL_FROM="${ALERT_EMAIL_FROM:-monitor@${DOMAIN_NAME}}"

SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASS="${SMTP_PASS:-}"
SMTP_SCHEME="${SMTP_SCHEME:-smtp}" # smtp or smtps
SMTP_USE_TLS="${SMTP_USE_TLS:-1}" # 1 to require TLS

COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-3600}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [[ ! -f "${STATUS_FILE}" ]]; then
  exit 0
fi

if [[ -z "${ALERT_EMAIL_TO}" ]]; then
  fail "ALERT_EMAIL_TO is required."
fi

if [[ -z "${SMTP_HOST}" ]] || [[ -z "${SMTP_USER}" ]] || [[ -z "${SMTP_PASS}" ]]; then
  fail "SMTP_HOST/SMTP_USER/SMTP_PASS are required to send email."
fi

now_epoch="$(date +%s)"
last_sent_epoch="0"
if [[ -f "${LAST_SENT_FILE}" ]]; then
  last_sent_epoch="$(cat "${LAST_SENT_FILE}" 2>/dev/null || echo 0)"
fi

if [[ "${last_sent_epoch}" =~ ^[0-9]+$ ]] && (( now_epoch - last_sent_epoch < COOLDOWN_SECONDS )); then
  exit 0
fi

tmp_email="$(mktemp)"
trap 'rm -f "${tmp_email}"' EXIT

subject="[${PROJECT_NAME}] Health Alert - $(date -Is)"

{
  echo "Subject: ${subject}"
  echo "From: ${ALERT_EMAIL_FROM}"
  echo "To: ${ALERT_EMAIL_TO}"
  echo "Date: $(date -R)"
  echo "MIME-Version: 1.0"
  echo "Content-Type: text/plain; charset=UTF-8"
  echo
  echo "Host: $(hostname -f)"
  echo "Project: ${PROJECT_NAME}"
  echo "Timestamp: $(date -Is)"
  echo
  echo "==== health.status ===="
  cat "${STATUS_FILE}"
} > "${tmp_email}"

smtp_url="${SMTP_SCHEME}://${SMTP_HOST}:${SMTP_PORT}"

curl_args=(
  --silent --show-error --fail
  --url "${smtp_url}"
  --user "${SMTP_USER}:${SMTP_PASS}"
  --mail-from "${ALERT_EMAIL_FROM}"
  --upload-file "${tmp_email}"
)

IFS=',' read -r -a recipients <<< "${ALERT_EMAIL_TO}"
for rcpt in "${recipients[@]}"; do
  rcpt_trimmed="$(echo "${rcpt}" | xargs)"
  [[ -n "${rcpt_trimmed}" ]] && curl_args+=( --mail-rcpt "${rcpt_trimmed}" )
done

if [[ "${SMTP_USE_TLS}" == "1" ]]; then
  curl_args+=( --ssl-reqd )
fi

curl "${curl_args[@]}"

echo "${now_epoch}" > "${LAST_SENT_FILE}"
chmod 0640 "${LAST_SENT_FILE}" || true

rm -f "${STATUS_FILE}"

