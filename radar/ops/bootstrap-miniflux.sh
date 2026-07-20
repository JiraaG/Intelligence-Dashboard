#!/usr/bin/env bash
# bootstrap-miniflux.sh — after clone: publish Miniflux admin + import seed feeds.
#
# Does NOT copy .env secrets. Create API key in Miniflux UI first if missing.
#
# Uso (da radar/, Git Bash / WSL):
#   cp .env.example .env   # fill secrets
#   ./ops/bootstrap-miniflux.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RADAR_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${RADAR_ROOT}"

COMPOSE="${COMPOSE:-docker compose -f docker-compose.yml -f docker-compose.lan.yml}"

echo "==> Starting stack (lan Miniflux :8080)..."
$COMPOSE up -d

echo "==> Waiting for Miniflux..."
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:8080" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load_dotenv.sh"
radar_load_dotenv "${RADAR_ROOT}/.env"

if [[ -z "${MINIFLUX_API_KEY:-}" ]]; then
  echo ""
  echo "MINIFLUX_API_KEY missing."
  echo "1) Open http://localhost:8080  (admin from .env MINIFLUX_ADMIN_*)"
  echo "2) Settings → API Keys → create key → put in .env as MINIFLUX_API_KEY"
  echo "3) Re-run: ./ops/import-miniflux-feeds.sh"
  exit 0
fi

"${SCRIPT_DIR}/import-miniflux-feeds.sh"
echo "==> Bootstrap done. UI http://localhost/  Miniflux http://localhost:8080"
