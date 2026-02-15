#!/usr/bin/env bash
set -Eeuo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${here}/00_env_check.sh"
bash "${here}/01_git_sync.sh"
bash "${here}/02_system_setup.sh"
bash "${here}/03_ocr_setup.sh"
bash "${here}/04_gunicorn_service.sh"
bash "${here}/05_nginx_setup.sh"
#bash "${here}/06_ssl_setup.sh"
bash "${here}/07_monitoring.sh"
bash "${here}/08_notifications.sh"

echo "OK: Deployment completed successfully."
