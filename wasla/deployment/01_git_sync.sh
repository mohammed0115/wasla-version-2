#!/usr/bin/env bash
set -Eeuo pipefail

# 01_git_sync.sh
# Sync project source code from GitHub (GitHub is source of truth).
# - Clones repo if missing
# - Hard-resets to origin branch on every run (conflicts are discarded)
# - Uses flock to prevent concurrent sync
# - Logs to /var/log/project-git.log

PROJECT_NAME="${PROJECT_NAME:-wasla}"
PROJECT_ROOT="${PROJECT_ROOT:-/opt/wasla}"
BACKEND_PATH="${BACKEND_PATH:-${PROJECT_ROOT}/app}"
GIT_REPO_URL="${GIT_REPO_URL:-https://github.com/mohammed0115/wasla.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"

LOG_FILE="/var/log/project-git.log"
LOCK_FILE="/var/lock/${PROJECT_NAME}-git.lock"

log() {
  echo "$(date -Is) $*" | tee -a "${LOG_FILE}" >/dev/null
}

fail() {
  log "ERROR: $*"
  exit 1
}

if [[ "$(id -u)" -ne 0 ]]; then
  fail "Must run as root."
fi

mkdir -p "$(dirname "${LOCK_FILE}")" "${PROJECT_ROOT}" "$(dirname "${BACKEND_PATH}")"
touch "${LOG_FILE}"
chmod 0640 "${LOG_FILE}" || true

exec 9>"${LOCK_FILE}"
flock -x 9

log "=== Git sync started (repo=${GIT_REPO_URL}, branch=${GIT_BRANCH}, path=${BACKEND_PATH}) ==="

if [[ ! -d "${BACKEND_PATH}" ]]; then
  log "Cloning repository..."
  git clone --branch "${GIT_BRANCH}" --single-branch "${GIT_REPO_URL}" "${BACKEND_PATH}" 2>&1 | tee -a "${LOG_FILE}" >/dev/null
else
  if [[ ! -d "${BACKEND_PATH}/.git" ]]; then
    fail "BACKEND_PATH exists but is not a git repo: ${BACKEND_PATH}"
  fi
fi

cd "${BACKEND_PATH}"

git remote set-url origin "${GIT_REPO_URL}" 2>&1 | tee -a "${LOG_FILE}" >/dev/null || true

log "Fetching latest..."
git fetch --prune origin 2>&1 | tee -a "${LOG_FILE}" >/dev/null

log "Resetting to origin/${GIT_BRANCH}..."
git checkout -B "${GIT_BRANCH}" "origin/${GIT_BRANCH}" 2>&1 | tee -a "${LOG_FILE}" >/dev/null
git reset --hard "origin/${GIT_BRANCH}" 2>&1 | tee -a "${LOG_FILE}" >/dev/null
git clean -fd 2>&1 | tee -a "${LOG_FILE}" >/dev/null

log "Git sync completed: $(git rev-parse --short HEAD)"
log "=== Git sync finished ==="
