#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/wasla}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-26}"

DB_LATEST="${BACKUP_ROOT}/db/latest.sql.gz"
MEDIA_LATEST="${BACKUP_ROOT}/media/latest.tar.gz"

check_file_age() {
  local file="$1"
  local label="$2"

  if [[ ! -f "$file" ]]; then
    echo "[ERROR] Missing ${label} backup: ${file}"
    return 1
  fi

  local now epoch age_seconds age_hours
  now="$(date +%s)"
  epoch="$(stat -c %Y "$file")"
  age_seconds=$(( now - epoch ))
  age_hours=$(( age_seconds / 3600 ))

  if (( age_hours > MAX_AGE_HOURS )); then
    echo "[ERROR] ${label} backup too old: ${age_hours}h > ${MAX_AGE_HOURS}h"
    return 1
  fi

  echo "[OK] ${label} backup age: ${age_hours}h"
  return 0
}

check_db_integrity() {
  gzip -t "${DB_LATEST}"
  echo "[OK] DB latest backup gzip integrity"
}

check_media_integrity() {
  tar -tzf "${MEDIA_LATEST}" >/dev/null
  echo "[OK] Media latest backup tar integrity"
}

status=0
check_file_age "${DB_LATEST}" "DB" || status=1
check_file_age "${MEDIA_LATEST}" "MEDIA" || status=1

if [[ -f "${DB_LATEST}" ]]; then
  check_db_integrity || status=1
fi
if [[ -f "${MEDIA_LATEST}" ]]; then
  check_media_integrity || status=1
fi

exit ${status}
