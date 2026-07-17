#!/usr/bin/env bash
# restore-postgres.sh — restore drill for pg_dump custom format + optional vault.
#
# DANGER: replaces the live database. Use only on disposable stacks or after
# an explicit backup of the current state.
#
# Usage (Git Bash / WSL; from radar/):
#   ./ops/restore-postgres.sh ./backups/20260715T120000Z
#   ./ops/restore-postgres.sh ./backups/20260715T120000Z --with-vault
#
# Steps:
#   1. Verify SHA-256 (if SHA256SUMS present)
#   2. Stop worker (and optionally backend) to avoid writes
#   3. pg_restore --clean --if-exists into POSTGRES_DB
#   4. Optional: replace ./vault from vault.tar.gz
#   5. Start services; worker reconciles pending outbox
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RADAR_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${RADAR_ROOT}"

COMPOSE="${COMPOSE:-docker compose}"
POSTGRES_USER="${POSTGRES_USER:-radar_user}"
POSTGRES_DB="${POSTGRES_DB:-radar_db}"
WITH_VAULT=0

# Load .env KEY=VALUE only (safe on Windows / comments with parentheses)
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load_dotenv.sh"
radar_load_dotenv "${RADAR_ROOT}/.env"
POSTGRES_USER="${POSTGRES_USER:-radar_user}"
POSTGRES_DB="${POSTGRES_DB:-radar_db}"

usage() {
  echo "Usage: $0 <backup-dir> [--with-vault]" >&2
  echo "  backup-dir must contain radar_<db>.dump and optionally vault.tar.gz + SHA256SUMS" >&2
  exit 1
}

[[ $# -ge 1 ]] || usage
BACKUP_DIR="$1"
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-vault) WITH_VAULT=1 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
  shift
done

BACKUP_DIR="$(cd "${BACKUP_DIR}" && pwd)"
DUMP="$(ls -1 "${BACKUP_DIR}"/radar_*.dump 2>/dev/null | head -n1 || true)"
[[ -n "${DUMP}" && -f "${DUMP}" ]] || { echo "ERROR: no radar_*.dump in ${BACKUP_DIR}" >&2; exit 1; }

echo "==> Restore from ${BACKUP_DIR}"
echo "    dump: ${DUMP}"

# ── Verify checksums ─────────────────────────────────────────────────────────
if [[ -f "${BACKUP_DIR}/SHA256SUMS" ]]; then
  echo "==> Verifying SHA256SUMS"
  (
    cd "${BACKUP_DIR}"
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum -c SHA256SUMS
    elif command -v shasum >/dev/null 2>&1; then
      shasum -a 256 -c SHA256SUMS
    else
      echo "WARN: no sha256sum/shasum — skipping verify" >&2
    fi
  )
else
  echo "WARN: no SHA256SUMS — skipping integrity check" >&2
fi

echo ""
echo "WARNING: This will DROP/replace objects in database '${POSTGRES_DB}'."
echo "Press Enter to continue, or Ctrl-C to abort."
read -r _

# ── Quiesce writers ──────────────────────────────────────────────────────────
echo "==> Stopping radar-worker (and radar-backend) to freeze writes..."
$COMPOSE stop radar-worker radar-backend || true

# ── Copy dump into db container and restore ──────────────────────────────────
echo "==> pg_restore --clean --if-exists"
$COMPOSE cp "${DUMP}" "radar-db:/tmp/radar_restore.dump"
$COMPOSE exec -T radar-db \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  --clean --if-exists --no-owner --no-acl \
  /tmp/radar_restore.dump || {
    # pg_restore returns non-zero on some benign NOTICE/errors with --clean
    echo "WARN: pg_restore exited non-zero — inspect logs; continuing" >&2
  }
$COMPOSE exec -T radar-db rm -f /tmp/radar_restore.dump

# ── Optional vault ───────────────────────────────────────────────────────────
if [[ "${WITH_VAULT}" -eq 1 ]]; then
  VAULT_TAR="${BACKUP_DIR}/vault.tar.gz"
  if [[ -f "${VAULT_TAR}" ]]; then
    echo "==> Restoring vault from ${VAULT_TAR}"
    # Keep a safety copy of current vault
    if [[ -d "${RADAR_ROOT}/vault" ]]; then
      SAFETY="${RADAR_ROOT}/vault.pre-restore.$(date -u +%Y%m%dT%H%M%SZ)"
      mv "${RADAR_ROOT}/vault" "${SAFETY}"
      echo "    previous vault moved to ${SAFETY}"
    fi
    tar -C "${RADAR_ROOT}" -xzf "${VAULT_TAR}"
  else
    echo "ERROR: --with-vault set but vault.tar.gz missing" >&2
    exit 1
  fi
fi

# ── Restart ──────────────────────────────────────────────────────────────────
echo "==> Starting backend + worker"
$COMPOSE start radar-backend radar-worker
echo "==> Restore drill complete."
echo "    Check: docker compose ps"
echo "    Check: curl -sf http://localhost/api/articles?date=$(date -u +%Y-%m-%d) | head"
echo "    Check: curl -sf http://localhost:8000/health/live  # if backend published for debug"
echo "    Worker will reconcile pending outbox rows on next cycle."
