#!/usr/bin/env bash
set -Eeuo pipefail

# 00_env_check.sh
# Preflight checks for Ubuntu deployment (fail-fast).
# Safe to run multiple times (read-only checks).

min_disk_mb=5120
min_ram_mb=2048

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

if [[ "$(id -u)" -ne 0 ]]; then
  fail "Must run as root."
fi

if [[ ! -r /etc/os-release ]]; then
  fail "/etc/os-release not found."
fi

# shellcheck disable=SC1091
. /etc/os-release

if [[ "${ID:-}" != "ubuntu" ]]; then
  fail "Unsupported OS: ${ID:-unknown}. Ubuntu 20.04+ is required."
fi

if [[ -z "${VERSION_ID:-}" ]]; then
  fail "Unable to detect Ubuntu version."
fi

if ! dpkg --compare-versions "${VERSION_ID}" ge "20.04"; then
  fail "Ubuntu ${VERSION_ID} detected; Ubuntu 20.04+ is required."
fi

avail_mb="$(df -Pm / | awk 'NR==2 {print $4}')"
if [[ -z "${avail_mb}" ]] || ! [[ "${avail_mb}" =~ ^[0-9]+$ ]]; then
  fail "Unable to determine available disk space."
fi
if (( avail_mb < min_disk_mb )); then
  fail "Insufficient disk space: ${avail_mb}MB available (need >= ${min_disk_mb}MB)."
fi

ram_mb="$(awk '/MemTotal:/ {print int($2/1024)}' /proc/meminfo || true)"
if [[ -z "${ram_mb}" ]] || ! [[ "${ram_mb}" =~ ^[0-9]+$ ]]; then
  fail "Unable to determine system RAM."
fi
if (( ram_mb < min_ram_mb )); then
  fail "Insufficient RAM: ${ram_mb}MB detected (need >= ${min_ram_mb}MB)."
fi

# Internet connectivity (DNS + HTTPS)
if command -v curl >/dev/null 2>&1; then
  timeout 8 curl -fsSL "https://github.com" >/dev/null || fail "No internet connectivity (HTTPS to github.com failed)."
elif command -v wget >/dev/null 2>&1; then
  timeout 8 wget -qO- "https://github.com" >/dev/null || fail "No internet connectivity (HTTPS to github.com failed)."
else
  getent hosts github.com >/dev/null 2>&1 || fail "No internet connectivity (DNS lookup for github.com failed)."
fi

echo "OK: Environment checks passed (Ubuntu ${VERSION_ID}, disk=${avail_mb}MB free, RAM=${ram_mb}MB)."

