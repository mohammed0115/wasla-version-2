#!/usr/bin/env bash
set -euo pipefail

# Non-destructive restore validation in a disposable local directory/database.
# Requires: psql, createdb/dropdb, gzip, tar

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/wasla}"
TEST_DB_NAME="${TEST_DB_NAME:-wasla_restore_test}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-wasla_user}"
RESTORE_WORKDIR="${RESTORE_WORKDIR:-/tmp/wasla_restore_test}"

DB_BACKUP="${BACKUP_ROOT}/db/latest.sql.gz"
MEDIA_BACKUP="${BACKUP_ROOT}/media/latest.tar.gz"

if [[ -z "${DB_PASSWORD:-}" && -z "${PGPASSWORD:-}" ]]; then
  echo "[ERROR] DB_PASSWORD or PGPASSWORD must be set"
  exit 1
fi
export PGPASSWORD="${PGPASSWORD:-${DB_PASSWORD:-}}"

mkdir -p "${RESTORE_WORKDIR}"
rm -rf "${RESTORE_WORKDIR:?}"/*

if [[ ! -f "${DB_BACKUP}" || ! -f "${MEDIA_BACKUP}" ]]; then
  echo "[ERROR] Missing latest backups in ${BACKUP_ROOT}"
  exit 1
fi

echo "[INFO] Recreating test database ${TEST_DB_NAME}"
dropdb --if-exists --host "${DB_HOST}" --port "${DB_PORT}" --username "${DB_USER}" "${TEST_DB_NAME}"
createdb --host "${DB_HOST}" --port "${DB_PORT}" --username "${DB_USER}" "${TEST_DB_NAME}"

echo "[INFO] Restoring DB backup"
gzip -dc "${DB_BACKUP}" | psql --host "${DB_HOST}" --port "${DB_PORT}" --username "${DB_USER}" --dbname "${TEST_DB_NAME}" >/dev/null

echo "[INFO] Running DB smoke checks"
psql --host "${DB_HOST}" --port "${DB_PORT}" --username "${DB_USER}" --dbname "${TEST_DB_NAME}" -c "SELECT COUNT(*) FROM django_migrations;" >/dev/null

echo "[INFO] Restoring media archive to ${RESTORE_WORKDIR}/media"
mkdir -p "${RESTORE_WORKDIR}/media"
tar -xzf "${MEDIA_BACKUP}" -C "${RESTORE_WORKDIR}/media"

if [[ -z "$(find "${RESTORE_WORKDIR}/media" -type f -print -quit)" ]]; then
  echo "[WARN] Media restore produced empty tree (verify if expected)."
else
  echo "[OK] Media restore validation passed"
fi

echo "[OK] Restore test completed successfully"
