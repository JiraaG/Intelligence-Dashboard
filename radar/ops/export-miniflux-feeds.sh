#!/usr/bin/env bash
# export-miniflux-feeds.sh — dump live Miniflux OPML + feeds JSON into config/.
#
# Prerequisites:
#   - stack up with Miniflux admin published, e.g.:
#       docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d
#   - MINIFLUX_API_KEY in radar/.env
#
# Uso (da radar/, Git Bash / WSL — non PowerShell nativo):
#   ./ops/export-miniflux-feeds.sh
#
# Override URL: MINIFLUX_ADMIN_URL=http://127.0.0.1:8080 ./ops/export-miniflux-feeds.sh
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

OPML_OUT="${RADAR_ROOT}/config/miniflux-feeds.live.opml"
JSON_OUT="${RADAR_ROOT}/config/miniflux-feeds.live.json"
ADMIN_URL="${MINIFLUX_ADMIN_URL:-http://localhost:8080}"

mkdir -p "${RADAR_ROOT}/config"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: python3/python required to run ops/miniflux_feeds_sync.py" >&2
  exit 1
fi

export MINIFLUX_API_KEY

win_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
  else
    printf '%s' "$p"
  fi
}

"${PY}" "$(win_path "${SCRIPT_DIR}/miniflux_feeds_sync.py")" export \
  --url "${ADMIN_URL}" \
  --token "${MINIFLUX_API_KEY}" \
  --opml "$(win_path "${OPML_OUT}")" \
  --json "$(win_path "${JSON_OUT}")"

echo "Note: commit-ready seed remains config/miniflux-feeds.seed.json (+ .opml)."
echo "      *.live.* are runtime dumps — usually gitignored / not for seed."
