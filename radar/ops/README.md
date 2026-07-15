# Ops — Radar Informativo Globale

> Companion operativo (EN). Manuali IT: [`docs/01_getting_started.md`](../../docs/01_getting_started.md), runbook: [`docs/runbook.md`](../docs/runbook.md).

## One-liner start (plug-and-play)

```bash
cd radar
cp .env.example .env   # set POSTGRES_PASSWORD, GEMINI_API_KEY, MINIFLUX_*
docker compose up -d --build
```

Open **http://localhost/** (port 80 on all interfaces).

Remote / internet exposure: put a TLS reverse proxy with auth and ACLs in front — do not publish `:80` raw to the public internet.

---

## Live vs ready

| Probe | Path | Meaning | Compose uses it? |
|-------|------|---------|------------------|
| **Liveness** | `GET /health/live` | Process up | Yes — `radar-backend` healthcheck; frontend `depends_on` this |
| **Readiness** | `GET /health/ready` | Pool + migrations (`004_+`) + worker heartbeat freshness; outbox counts are reported but non-gating | No — ops/load-balancer only |

On first boot, `/health/ready` may return **503** for ~30–90s until the worker leader writes a heartbeat. The UI on `:80` can still load; do not gate Nginx on ready.

---

## Miniflux admin (no host port by default)

Miniflux is on the **data** network only. Options:

1. **Hardened (loopback admin):**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d
   ```
   Then http://127.0.0.1:8080

2. **LAN publish:**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d
   ```
   Then http://localhost:8080

3. **Exec / one-off** (no long-lived publish): use Compose exec into `radar-miniflux` or a temporary `docker compose run` with `-p 127.0.0.1:8080:8080`.

Create an API key in Miniflux → Settings → API Keys, put it in `.env` as `MINIFLUX_API_KEY`.

---

## Hardened override (loopback FE)

```bash
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d
```

- Frontend: `127.0.0.1:80` only  
- Miniflux admin: `127.0.0.1:8080` only  

---

## Networks (Phase 3)

```
radar-edge:  radar-frontend ↔ radar-backend
radar-data:  radar-backend, radar-worker, radar-db, radar-miniflux
```

Frontend is **never** on `radar-data`. Worker is **only** on `radar-data`.

---

## Backup

```bash
# Git Bash / WSL / Linux (not raw PowerShell)
./ops/backup-postgres.sh
```

Produces `backups/<UTC-stamp>/`:

- `radar_<db>.dump` — `pg_dump -Fc`
- `vault.tar.gz` — Obsidian vault bind mount
- `SHA256SUMS` — checksums

Warns if `article_outbox` has `pending` / `writing` rows (crash-consistent, not cross-FS atomic). Retention: `RETENTION_DAYS` (default 7).

Env: `BACKUP_ROOT`, `RETENTION_DAYS`, `COMPOSE` (default `docker compose`).

---

## Restore drill

```bash
./ops/restore-postgres.sh ./backups/<stamp>
./ops/restore-postgres.sh ./backups/<stamp> --with-vault
```

Stops backend+worker, `pg_restore --clean --if-exists`, optional vault replace, restarts services. Prefer a disposable stack before production drills.

After restore, the worker reconciles remaining outbox rows on the next cycle.

---

## Windows / Git Bash note

- Run `ops/*.sh` from **Git Bash** or **WSL**, not PowerShell (line endings + bash).
- Vault path is a Docker bind mount (`./vault`); keep it inside the project tree for Desktop file sharing.
- Prefer `http://localhost` over exotic `127.0.0.1` vs hostname quirks unless using the hardened loopback bind.
- If scripts are checked out with CRLF, run `sed -i 's/\r$//' ops/*.sh` once or enable `core.autocrlf` appropriately.
