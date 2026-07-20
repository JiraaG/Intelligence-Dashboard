#!/usr/bin/env bash
# import-miniflux-feeds.sh — create/update Miniflux feeds from config seed.
#
# Applies titles, categories, crawler, user_agent, scraper_rules from
# config/miniflux-feeds.seed.json (sourced from repo-root RSS.txt).
#
# Prerequisites:
#   docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d
#   MINIFLUX_API_KEY in radar/.env (Settings → API Keys)
#
# Uso (da radar/, Git Bash / WSL):
#   ./ops/import-miniflux-feeds.sh
#
# Also regenerates config/miniflux-feeds.opml from the seed.
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

SEED="${RADAR_ROOT}/config/miniflux-feeds.seed.json"
OPML="${RADAR_ROOT}/config/miniflux-feeds.opml"
ADMIN_URL="${MINIFLUX_ADMIN_URL:-http://localhost:8080}"

if [[ ! -f "${SEED}" ]]; then
  echo "ERROR: missing seed ${SEED}" >&2
  exit 1
fi

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

echo "==> Regenerating OPML from seed..."
"${PY}" "$(win_path "${SCRIPT_DIR}/miniflux_feeds_sync.py")" gen-opml \
  --seed "$(win_path "${SEED}")" \
  --opml "$(win_path "${OPML}")"

echo "==> Importing/updating feeds on ${ADMIN_URL} ..."
"${PY}" "$(win_path "${SCRIPT_DIR}/miniflux_feeds_sync.py")" import \
  --seed "$(win_path "${SEED}")" \
  --url "${ADMIN_URL}" \
  --token "${MINIFLUX_API_KEY}"

echo "==> Done. Open ${ADMIN_URL} to verify categories/feeds."
