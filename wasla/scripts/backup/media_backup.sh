#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/wasla}"
MEDIA_DIR="${MEDIA_DIR:-/var/www/wasla/wasla/media}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

DATE_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
MEDIA_BACKUP_DIR="${BACKUP_ROOT}/media"
LOG_DIR="${BACKUP_ROOT}/logs"
mkdir -p "${MEDIA_BACKUP_DIR}" "${LOG_DIR}"

OUT_FILE="${MEDIA_BACKUP_DIR}/media_${DATE_UTC}.tar.gz"
LOG_FILE="${LOG_DIR}/media_backup_${DATE_UTC}.log"
LATEST_LINK="${MEDIA_BACKUP_DIR}/latest.tar.gz"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "[INFO] Starting media backup from ${MEDIA_DIR}"

if [[ ! -d "${MEDIA_DIR}" ]]; then
  echo "[ERROR] MEDIA_DIR does not exist: ${MEDIA_DIR}"
  exit 1
fi

tar -C "${MEDIA_DIR}" -czf "${OUT_FILE}" .

if [[ ! -s "${OUT_FILE}" ]]; then
  echo "[ERROR] Media backup output is empty: ${OUT_FILE}"
  exit 1
fi

tar -tzf "${OUT_FILE}" >/dev/null
ln -sfn "${OUT_FILE}" "${LATEST_LINK}"

find "${MEDIA_BACKUP_DIR}" -type f -name "*.tar.gz" -mtime +"${RETENTION_DAYS}" -delete

SHA_FILE="${OUT_FILE}.sha256"
sha256sum "${OUT_FILE}" > "${SHA_FILE}"

echo "[OK] Media backup complete: ${OUT_FILE}"
