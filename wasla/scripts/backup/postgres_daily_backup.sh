#!/usr/bin/env bash
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/wasla}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-wasla}"
DB_USER="${DB_USER:-wasla_user}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

DATE_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
DB_DIR="${BACKUP_ROOT}/db"
LOG_DIR="${BACKUP_ROOT}/logs"
mkdir -p "${DB_DIR}" "${LOG_DIR}"

OUT_FILE="${DB_DIR}/${DB_NAME}_${DATE_UTC}.sql.gz"
LOG_FILE="${LOG_DIR}/postgres_backup_${DATE_UTC}.log"
LATEST_LINK="${DB_DIR}/latest.sql.gz"

exec > >(tee -a "${LOG_FILE}") 2>&1

echo "[INFO] Starting PostgreSQL backup for ${DB_NAME} at ${DATE_UTC}"

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "[ERROR] pg_dump not found"
  exit 1
fi

if [[ -z "${DB_PASSWORD:-}" && -z "${PGPASSWORD:-}" ]]; then
  echo "[ERROR] DB_PASSWORD or PGPASSWORD must be set"
  exit 1
fi

export PGPASSWORD="${PGPASSWORD:-${DB_PASSWORD:-}}"

pg_dump \
  --host "${DB_HOST}" \
  --port "${DB_PORT}" \
  --username "${DB_USER}" \
  --format=plain \
  --no-owner \
  --no-privileges \
  "${DB_NAME}" | gzip -9 > "${OUT_FILE}"

if [[ ! -s "${OUT_FILE}" ]]; then
  echo "[ERROR] Backup output is empty: ${OUT_FILE}"
  exit 1
fi

gzip -t "${OUT_FILE}"
ln -sfn "${OUT_FILE}" "${LATEST_LINK}"

find "${DB_DIR}" -type f -name "*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete

SHA_FILE="${OUT_FILE}.sha256"
sha256sum "${OUT_FILE}" > "${SHA_FILE}"

echo "[OK] PostgreSQL backup complete: ${OUT_FILE}"
