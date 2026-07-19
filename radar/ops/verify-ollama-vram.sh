#!/usr/bin/env bash
# verify-ollama-vram.sh — checklist ops Profilo F (VRAM load/unload).
# Non sostituisce requeue_articles. Exit non-zero solo su prereq falliti o
# errori critici nei log recenti. Snapshot ollama ps è informativo (timing GPU
# non assertabile rigidamente).
#
# Usage (from radar/):
#   ./ops/verify-ollama-vram.sh
#   COMPOSE_FILES="-f docker-compose.yml -f docker-compose.ollama-host.yml" ./ops/verify-ollama-vram.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.ollama-host.yml}"
# shellcheck disable=SC2086
dc() { docker compose $COMPOSE_FILES "$@"; }

OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
LOG_SINCE="${LOG_SINCE:-15m}"
fail=0

echo "=== verify-ollama-vram ==="
echo "cwd=$ROOT compose=$COMPOSE_FILES"

echo
echo "--- prereq: Ollama host ---"
if ! curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null; then
  echo "FAIL: Ollama non raggiungibile su ${OLLAMA_HOST}/api/tags"
  exit 1
fi
echo "OK: ${OLLAMA_HOST}/api/tags"

echo
echo "--- prereq: compose worker ---"
if ! dc ps --status running --services 2>/dev/null | grep -qx radar-worker; then
  echo "FAIL: radar-worker non in running (avviare con overlay ollama-host)"
  exit 1
fi
echo "OK: radar-worker running"

echo
echo "--- health backend ---"
if ! dc exec -T radar-backend curl -sf http://localhost:8000/health/live >/dev/null; then
  echo "FAIL: /health/live"
  fail=1
else
  echo "OK: /health/live"
fi

echo
echo "--- ollama ps (host) ---"
if command -v ollama >/dev/null 2>&1; then
  ollama ps || true
else
  echo "(ollama CLI assente; uso /api/ps)"
  curl -s "${OLLAMA_HOST}/api/ps" || true
  echo
fi

echo
echo "--- worker logs (since ${LOG_SINCE}) — lifecycle / route ---"
dc logs --since="$LOG_SINCE" radar-worker 2>/dev/null \
  | grep -E 'ollama_unload|ollama_ps|route lane=|openai-compat|Ciclo della pipeline' \
  | tail -n 40 || echo "(nessun match lifecycle/route)"

echo
echo "--- worker logs — errori critici ---"
err_lines="$(
  dc logs --since="$LOG_SINCE" radar-worker 2>/dev/null \
    | grep -E 'ValidationError|DeepSeekError|ERROR|Traceback|Ciclo .* [1-9][0-9]* errori' \
    | tail -n 30 || true
)"
if [[ -n "${err_lines}" ]]; then
  echo "$err_lines"
  # Soft: segnala ma non fallisce solo per ValidationError isolati (gate qualità KPI).
  if echo "$err_lines" | grep -qE 'Traceback|DeepSeekError'; then
    echo "WARN: Traceback/DeepSeekError nei log recenti — investigare"
    fail=1
  else
    echo "NOTE: match errori/warning presenti (revisione ops / KPI %XX)"
  fi
else
  echo "OK: nessun pattern errore critico recente"
fi

echo
if [[ "$fail" -ne 0 ]]; then
  echo "=== RESULT: FAIL (vedi sopra) ==="
  exit 1
fi
echo "=== RESULT: OK (checklist stampata; conferma VRAM idle con ollama ps dopo debounce) ==="
exit 0
