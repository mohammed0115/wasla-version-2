#!/usr/bin/env bash
set -Eeuo pipefail

# 02_system_setup.sh
# System base setup:
# - Installs OS packages (no OCR, no Nginx)
# - Installs Python 3.12
# - Creates a virtualenv
# - Upgrades pip, setuptools, wheel
# - Installs Python deps (requirements.txt if present; otherwise pinned minimal set)

PROJECT_NAME="${PROJECT_NAME:-wasla}"
PROJECT_ROOT="${PROJECT_ROOT:-/var/www/wasla}"
BACKEND_PATH="${BACKEND_PATH:-${PROJECT_ROOT}/app}"
VENV_PATH="${VENV_PATH:-${PROJECT_ROOT}/venv}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [[ "$(id -u)" -ne 0 ]]; then
  fail "Must run as root."
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y

apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gettext \
  git \
  openssl \
  build-essential \
  libpq-dev \
  libjpeg-dev \
  zlib1g-dev \
  libpng-dev \
  pkg-config \
  software-properties-common

if ! command -v python3.12 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -y
  apt-get install -y --no-install-recommends python3.12 python3.12-venv python3.12-dev
else
  apt-get install -y --no-install-recommends python3.12-venv python3.12-dev
fi

mkdir -p "${PROJECT_ROOT}"

if [[ ! -x "${VENV_PATH}/bin/python" ]]; then
  python3.12 -m venv "${VENV_PATH}"
fi

"${VENV_PATH}/bin/python" -m pip install --upgrade pip setuptools wheel

requirements_file=""
if [[ -f "${BACKEND_PATH}/requirements.txt" ]]; then
  requirements_file="${BACKEND_PATH}/requirements.txt"
elif [[ -f "${BACKEND_PATH}/requirements/production.txt" ]]; then
  requirements_file="${BACKEND_PATH}/requirements/production.txt"
fi

if [[ -n "${requirements_file}" ]]; then
  "${VENV_PATH}/bin/pip" install -r "${requirements_file}"
else
  # Minimal dependencies for this repository (use ranges to avoid broken pins).
  "${VENV_PATH}/bin/pip" install \
    "Django>=5.1,<5.3" \
    "djangorestframework>=3.15,<3.17" \
    "djangorestframework-simplejwt>=5.3,<6" \
    "celery>=5.4,<6" \
    "redis>=5,<6" \
    "cryptography>=42,<45" \
    "Pillow>=10,<13" \
    "requests>=2.31,<3" \
    "gunicorn>=21,<23" \
    "psycopg2-binary>=2.9,<3"
fi

"${VENV_PATH}/bin/python" -m pip check

echo "OK: System setup complete (venv=${VENV_PATH})."
