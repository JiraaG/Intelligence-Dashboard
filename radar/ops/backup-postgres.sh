#!/usr/bin/env bash
# backup-postgres.sh — pg_dump (-Fc) + Miniflux feed snapshot + optional vault.
#
# Default: NO vault (markdown articles not needed for config restore).
# Crash-consistency: dump Postgres coerente; vault/outbox non atomici.
#
# Uso (da radar/, stack up; Git Bash / WSL — non PowerShell nativo):
#   ./ops/backup-postgres.sh              # dump + feed seed/OPML, no vault
#   ./ops/backup-postgres.sh --with-vault # include anche vault.tar.gz
#   SKIP_VAULT=0 ./ops/backup-postgres.sh # stesso di --with-vault
#   RETENTION_DAYS=14 BACKUP_ROOT=./backups ./ops/backup-postgres.sh
#
# Aggiorna anche config/miniflux-feeds.seed.json + .opml (SoT git) se Miniflux
# è raggiungibile su MINIFLUX_ADMIN_URL (default http://localhost:8080).
#
# Richiede: docker compose, sha256sum|shasum, python3, tar (solo con vault).
# @see ops/README.md; runbook backup.
set -euo pipefail

# Git Bash su Windows riscrive /tmp/... → %TEMP% prima di docker — blocca pg_dump.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RADAR_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${RADAR_ROOT}"

BACKUP_ROOT="${BACKUP_ROOT:-${RADAR_ROOT}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
COMPOSE="${COMPOSE:-docker compose}"
# Default: skip vault (config/feeds backup). Opt-in: --with-vault or SKIP_VAULT=0
SKIP_VAULT="${SKIP_VAULT:-1}"
SYNC_SEED="${SYNC_SEED:-1}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/${STAMP}"

for arg in "$@"; do
  case "${arg}" in
    --with-vault) SKIP_VAULT=0 ;;
    --no-vault) SKIP_VAULT=1 ;;
    --no-sync-seed) SYNC_SEED=0 ;;
    -h|--help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: ${arg}" >&2
      exit 2
      ;;
  esac
done

POSTGRES_USER="${POSTGRES_USER:-radar_user}"
POSTGRES_DB="${POSTGRES_DB:-radar_db}"

# Solo KEY=VALUE da .env (sicuro su Windows / commenti con parentesi)
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/_load_dotenv.sh"
radar_load_dotenv "${RADAR_ROOT}/.env"
POSTGRES_USER="${POSTGRES_USER:-radar_user}"
POSTGRES_DB="${POSTGRES_DB:-radar_db}"

mkdir -p "${DEST}"

echo "==> Backup destination: ${DEST}"
echo "    SKIP_VAULT=${SKIP_VAULT} SYNC_SEED=${SYNC_SEED}"

# ── Warn crash-consistency outbox (non abort) ────────────────────────────────
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

# Path host per `docker compose cp` sotto Git Bash (cygpath → Windows)
host_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
  else
    printf '%s' "$p"
  fi
}

pick_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo python3
  elif command -v python >/dev/null 2>&1; then
    echo python
  else
    echo ""
  fi
}

# Windows Git Bash: convert paths for native Windows Python (avoid C:\c\Users\...).
win_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$p"
  else
    printf '%s' "$p"
  fi
}

# ── Dump Postgres (custom format in-container: evita CRLF su pipe Windows) ───
DUMP_FILE="${DEST}/radar_${POSTGRES_DB}.dump"
echo "==> pg_dump → ${DUMP_FILE}"
$COMPOSE exec -T radar-db \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc -f /tmp/radar_backup.dump
$COMPOSE cp "radar-db:/tmp/radar_backup.dump" "$(host_path "${DUMP_FILE}")"
$COMPOSE exec -T radar-db rm -f /tmp/radar_backup.dump

# ── Miniflux feed SoT (seed + OPML) ──────────────────────────────────────────
SEED_SRC="${RADAR_ROOT}/config/miniflux-feeds.seed.json"
OPML_SRC="${RADAR_ROOT}/config/miniflux-feeds.opml"
ADMIN_URL="${MINIFLUX_ADMIN_URL:-http://localhost:8080}"
PY="$(pick_python)"

if [[ "${SYNC_SEED}" == "1" && -n "${MINIFLUX_API_KEY:-}" && -n "${PY}" ]]; then
  echo "==> Syncing commit-ready seed from Miniflux (${ADMIN_URL})..."
  if "${PY}" "$(win_path "${SCRIPT_DIR}/miniflux_feeds_sync.py")" sync-seed \
    --url "${ADMIN_URL}" \
    --token "${MINIFLUX_API_KEY}" \
    --seed "$(win_path "${SEED_SRC}")" \
    --opml "$(win_path "${OPML_SRC}")"; then
    :
  else
    echo "WARN: Miniflux seed sync failed — copying existing config/ if present." >&2
  fi
elif [[ "${SYNC_SEED}" == "1" ]]; then
  echo "WARN: skip live seed sync (need MINIFLUX_API_KEY + python)." >&2
fi

mkdir -p "${DEST}/miniflux"
if [[ -f "${SEED_SRC}" ]]; then
  cp -f "${SEED_SRC}" "${DEST}/miniflux/miniflux-feeds.seed.json"
  echo "==> Copied seed → ${DEST}/miniflux/"
fi
if [[ -f "${OPML_SRC}" ]]; then
  cp -f "${OPML_SRC}" "${DEST}/miniflux/miniflux-feeds.opml"
fi

# Manifest leggibile (no secrets)
cat > "${DEST}/BACKUP_INFO.txt" <<EOF
Radar backup ${STAMP}
SKIP_VAULT=${SKIP_VAULT}
POSTGRES_DB=${POSTGRES_DB}
Includes:
  - radar_${POSTGRES_DB}.dump (Postgres Fc; Miniflux feeds/entries + Radar articles)
  - miniflux/miniflux-feeds.seed.json (commit-ready feed config)
  - miniflux/miniflux-feeds.opml
$([ "${SKIP_VAULT}" = "0" ] && echo "  - vault.tar.gz" || echo "  - (vault omitted)")

Fresh PC (config, no article restore):
  1. cp .env.example .env  # fill secrets + MINIFLUX_API_KEY after first Miniflux login
  2. docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d --build
  3. ./ops/import-miniflux-feeds.sh

Optional full DB restore: ./ops/restore-postgres.sh ${DEST#$RADAR_ROOT/}
EOF

# ── Vault tar (opt-in) ───────────────────────────────────────────────────────
VAULT_DIR="${RADAR_ROOT}/vault"
VAULT_TAR="${DEST}/vault.tar.gz"
if [[ "${SKIP_VAULT}" == "0" ]]; then
  if [[ -d "${VAULT_DIR}" ]]; then
    echo "==> tar vault → ${VAULT_TAR}"
    tar -C "${RADAR_ROOT}" -czf "${VAULT_TAR}" vault
  else
    echo "WARN: vault/ missing — skipping vault archive." >&2
  fi
else
  echo "==> Skipping vault (use --with-vault to include)."
fi

# ── Checksums (manifest escluso da se stesso) ────────────────────────────────
MANIFEST="${DEST}/SHA256SUMS"
echo "==> Writing ${MANIFEST}"
(
  cd "${DEST}"
  # Portable: hash files in dest (incl. miniflux/); exclude SHA256SUMS itself.
  if command -v sha256sum >/dev/null 2>&1; then
    HASH_CMD=(sha256sum)
  elif command -v shasum >/dev/null 2>&1; then
    HASH_CMD=(shasum -a 256)
  else
    echo "ERROR: need sha256sum or shasum" >&2
    exit 1
  fi
  : > SHA256SUMS.tmp
  while IFS= read -r -d '' f; do
    rel="${f#./}"
    [[ "${rel}" == "SHA256SUMS" || "${rel}" == "SHA256SUMS.tmp" ]] && continue
    "${HASH_CMD[@]}" "${rel}" >> SHA256SUMS.tmp
  done < <(find . -type f -print0 | sort -z)
  mv SHA256SUMS.tmp SHA256SUMS
)

# ── Retention distruttiva: rimuove directory stamp più vecchie di N giorni ───
echo "==> Applying retention: keep last ${RETENTION_DAYS} days under ${BACKUP_ROOT}"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true

echo "==> Backup complete: ${DEST}"
ls -laR "${DEST}"
