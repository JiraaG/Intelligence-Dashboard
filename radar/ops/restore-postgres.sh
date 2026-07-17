#!/usr/bin/env bash
# restore-postgres.sh — drill di restore da pg_dump custom + vault opzionale.
#
# PERICOLO: sostituisce il database live. Solo su stack usa-e-getta o dopo
# backup esplicito dello stato corrente.
#
# Uso (Git Bash / WSL; da radar/):
#   ./ops/restore-postgres.sh ./backups/20260715T120000Z
#   ./ops/restore-postgres.sh ./backups/20260715T120000Z --with-vault
#
# Passi:
#   1. Verifica SHA-256 se esiste SHA256SUMS (altrimenti WARN e continua)
#   2. Conferma interattiva Enter (Ctrl-C abort)
#   3. Stop worker+backend per congelare scritture
#   4. pg_restore --clean --if-exists in POSTGRES_DB
#      (exit nonzero di pg_restore: WARN e continua — NOTICE tipici con --clean)
#   5. Opzionale: sposta vault corrente in vault.pre-restore.<UTC>, poi tar -xzf
#   6. Start backend+worker; il worker riconcilia outbox pending al ciclo successivo
#
# @see ops/README.md; docs/runbook.md (restore).
set -euo pipefail

# Git Bash su Windows riscrive path tipo /tmp/foo → %TEMP%/foo prima di docker.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RADAR_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${RADAR_ROOT}"

COMPOSE="${COMPOSE:-docker compose}"
POSTGRES_USER="${POSTGRES_USER:-radar_user}"
POSTGRES_DB="${POSTGRES_DB:-radar_db}"
WITH_VAULT=0

# Carica solo KEY=VALUE da .env (sicuro su Windows / commenti con parentesi)
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

# ── Verifica checksum (opzionale) ────────────────────────────────────────────
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

# ── Quiesce writer ───────────────────────────────────────────────────────────
echo "==> Stopping radar-worker (and radar-backend) to freeze writes..."
$COMPOSE stop radar-worker radar-backend || true

# Path host per `docker compose cp` sotto Git Bash (cygpath → path Windows)
host_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
  else
    printf '%s' "$p"
  fi
}

# ── Copia dump nel container db e restore ────────────────────────────────────
echo "==> pg_restore --clean --if-exists"
$COMPOSE cp "$(host_path "${DUMP}")" "radar-db:/tmp/radar_restore.dump"
$COMPOSE exec -T radar-db \
  pg_restore -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  --clean --if-exists --no-owner --no-acl \
  /tmp/radar_restore.dump || {
    # pg_restore può uscire nonzero su NOTICE/error benigni con --clean
    echo "WARN: pg_restore exited non-zero — inspect logs; continuing" >&2
  }
$COMPOSE exec -T radar-db rm -f /tmp/radar_restore.dump

# ── Vault opzionale (safety copy prima di sostituire) ────────────────────────
if [[ "${WITH_VAULT}" -eq 1 ]]; then
  VAULT_TAR="${BACKUP_DIR}/vault.tar.gz"
  if [[ -f "${VAULT_TAR}" ]]; then
    echo "==> Restoring vault from ${VAULT_TAR}"
    # Copia di sicurezza del vault corrente
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
