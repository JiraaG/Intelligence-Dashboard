#!/usr/bin/env bash
# sync-miniflux-seed.sh — overwrite config/ seed+OPML from live Miniflux (git SoT).
#
# Prerequisites: lan/hardened Miniflux on :8080, MINIFLUX_API_KEY in .env
#
# Uso (da radar/, Git Bash / WSL):
#   ./ops/sync-miniflux-seed.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RADAR_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${RADAR_ROOT}"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load_dotenv.sh"
radar_load_dotenv "${RADAR_ROOT}/.env"

if [[ -z "${MINIFLUX_API_KEY:-}" ]]; then
  echo "ERROR: MINIFLUX_API_KEY not set in .env" >&2
  exit 1
fi

ADMIN_URL="${MINIFLUX_ADMIN_URL:-http://localhost:8080}"
SEED="${RADAR_ROOT}/config/miniflux-feeds.seed.json"
OPML="${RADAR_ROOT}/config/miniflux-feeds.opml"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: python3/python required" >&2
  exit 1
fi

mkdir -p "${RADAR_ROOT}/config"

# Windows Git Bash → native Python needs Win paths (cygpath -w).
win_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
  else
    printf '%s' "$p"
  fi
}

"${PY}" "$(win_path "${SCRIPT_DIR}/miniflux_feeds_sync.py")" sync-seed \
  --url "${ADMIN_URL}" \
  --token "${MINIFLUX_API_KEY}" \
  --seed "$(win_path "${SEED}")" \
  --opml "$(win_path "${OPML}")"

echo "Commit these when ready: config/miniflux-feeds.seed.json config/miniflux-feeds.opml"
