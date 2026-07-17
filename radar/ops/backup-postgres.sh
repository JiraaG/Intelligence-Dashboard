#!/usr/bin/env bash
# backup-postgres.sh — pg_dump + vault tar with SHA-256 checksums and retention.
#
# Usage (from radar/ with stack running, or via Git Bash / WSL on Windows):
#   ./ops/backup-postgres.sh
#   RETENTION_DAYS=14 BACKUP_ROOT=./backups ./ops/backup-postgres.sh
#
# Requires: docker compose, sha256sum (or shasum), tar.
# Do NOT run from PowerShell directly — use Git Bash, WSL, or:
#   docker compose run --rm --entrypoint bash radar-backend -c '...'
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RADAR_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${RADAR_ROOT}"

BACKUP_ROOT="${BACKUP_ROOT:-${RADAR_ROOT}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
COMPOSE="${COMPOSE:-docker compose}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/${STAMP}"

POSTGRES_USER="${POSTGRES_USER:-radar_user}"
POSTGRES_DB="${POSTGRES_DB:-radar_db}"

# Load .env KEY=VALUE only (safe on Windows / comments with parentheses)
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load_dotenv.sh"
radar_load_dotenv "${RADAR_ROOT}/.env"
POSTGRES_USER="${POSTGRES_USER:-radar_user}"
POSTGRES_DB="${POSTGRES_DB:-radar_db}"

mkdir -p "${DEST}"

echo "==> Backup destination: ${DEST}"

# ── Outbox consistency warning ───────────────────────────────────────────────
warn_outbox() {
  local pending writing
  pending="$($COMPOSE exec -T radar-db \
    psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Atc \
    "SELECT COUNT(*) FROM article_outbox WHERE status = 'pending';" 2>/dev/null || echo "?")"
  writing="$($COMPOSE exec -T radar-db \
    psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Atc \
    "SELECT COUNT(*) FROM article_outbox WHERE status = 'writing';" 2>/dev/null || echo "?")"

  echo "    article_outbox pending=${pending} writing=${writing}"
  if [[ "${writing}" != "0" && "${writing}" != "?" ]]; then
    echo "WARN: outbox rows in 'writing' — vault may be mid-reconcile; dump is crash-consistent, not atomic with vault." >&2
  fi
  if [[ "${pending}" != "0" && "${pending}" != "?" ]]; then
    echo "WARN: outbox rows in 'pending' — after restore, worker reconcile should catch up." >&2
  fi
}

if $COMPOSE ps --status running --services 2>/dev/null | grep -qx radar-db; then
  echo "==> Checking article_outbox before dump..."
  warn_outbox
else
  echo "WARN: radar-db not running — cannot check outbox; aborting." >&2
  exit 1
fi

# ── PostgreSQL dump (custom format; file-in-container avoids Win CRLF on pipes) ─
DUMP_FILE="${DEST}/radar_${POSTGRES_DB}.dump"
echo "==> pg_dump → ${DUMP_FILE}"
$COMPOSE exec -T radar-db \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc -f /tmp/radar_backup.dump
$COMPOSE cp "radar-db:/tmp/radar_backup.dump" "${DUMP_FILE}"
$COMPOSE exec -T radar-db rm -f /tmp/radar_backup.dump

# ── Vault tar (same stamp) ───────────────────────────────────────────────────
VAULT_DIR="${RADAR_ROOT}/vault"
VAULT_TAR="${DEST}/vault.tar.gz"
if [[ -d "${VAULT_DIR}" ]]; then
  echo "==> tar vault → ${VAULT_TAR}"
  tar -C "${RADAR_ROOT}" -czf "${VAULT_TAR}" vault
else
  echo "WARN: vault/ missing — skipping vault archive." >&2
fi

# ── Checksums ────────────────────────────────────────────────────────────────
MANIFEST="${DEST}/SHA256SUMS"
echo "==> Writing ${MANIFEST}"
(
  cd "${DEST}"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum ./* > SHA256SUMS.tmp
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 ./* > SHA256SUMS.tmp
  else
    echo "ERROR: need sha256sum or shasum" >&2
    exit 1
  fi
  # Exclude the manifest itself from the listing
  grep -v 'SHA256SUMS' SHA256SUMS.tmp > SHA256SUMS || true
  rm -f SHA256SUMS.tmp
)

# ── Retention ────────────────────────────────────────────────────────────────
echo "==> Applying retention: keep last ${RETENTION_DAYS} days under ${BACKUP_ROOT}"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true

echo "==> Backup complete: ${DEST}"
ls -la "${DEST}"
