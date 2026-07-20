# Ops — Radar Informativo Globale

> Companion operativo (EN). Manuali IT: [`docs/01_getting_started.md`](../../docs/01_getting_started.md), runbook: [`docs/runbook.md`](../docs/runbook.md).

## One-liner start (plug-and-play)

```bash
cd radar
cp .env.example .env   # POSTGRES_PASSWORD, LLM lane keys (Profili A–F), MINIFLUX_*
docker compose up -d --build
```

Open **http://localhost/** (host port **80** → FE container **8080**).

LLM knobs / Profili A–F: [`.env.example`](../.env.example) + SoT [`sot_llm_multi_model_fallback.md`](../../plan-audit/complete/sot_llm_multi_model_fallback.md).  
**Profilo F (Local-Hybrid):** Ollama host + overlay [`docker-compose.ollama-host.yml`](../docker-compose.ollama-host.yml) — procedura in [`docs/runbook.md`](../docs/runbook.md) § Local-Hybrid.

Requeue / incident: [`docs/runbook.md`](../docs/runbook.md) (`python -m app.scripts.requeue_articles`; `--purge-all` = wipe vault + all articles).

### VRAM checklist (Profilo F)

```bash
cd radar
./ops/verify-ollama-vram.sh
```

Snapshot `ollama ps` + grep log worker (`ollama_unload`, route lane, errori). Dettaglio env unload: runbook § Local-Hybrid / `.env.example` (`OLLAMA_AUTO_UNLOAD`, `OLLAMA_KEEP_ALIVE_*`, debounce).

Few articles on the map? Check Miniflux feed count first (catalog: [`RSS.txt`](../../RSS.txt)) — ingest volume tracks subscribed feeds, not FE filters.

Remote / internet exposure: put a TLS reverse proxy with auth and ACLs in front — do not publish `:80` raw to the public internet.

---

## Smoke after deploy

```bash
curl -s http://localhost/health/live
curl -s "http://localhost/api/map-summary?date=$(date -I)"
curl -s "http://localhost/api/map-relations?date=$(date -I)"
curl -s http://localhost/api/saved-summary
curl -s "http://localhost/api/articles?saved=true&limit=10"
```

UI: toolbar **NOTIZIE SALVATE** + tooltip nazioni; card **Salva notizia** / **Rimuovi dai salvati**; click nazione → carousel + zoom + spiderfy. See [`docs/runbook.md`](../docs/runbook.md).

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

### Feed seed (OPML + scraper config)

Commit-ready list (from repo-root [`RSS.txt`](../../RSS.txt)):

- `config/miniflux-feeds.seed.json` — titles, categories, crawler, `user_agent`, `scraper_rules`
- `config/miniflux-feeds.opml` — portable OPML (categories only; full settings live in the seed)

```bash
# Publish admin UI, then import/update all feeds on a fresh PC:
docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d
./ops/import-miniflux-feeds.sh          # Git Bash / WSL
# → http://localhost:8080

# Optional: dump what is live now (not for commit — *.live.* gitignored):
./ops/export-miniflux-feeds.sh
```

Scripts load `MINIFLUX_API_KEY` via `ops/_load_dotenv.sh`. Override URL with `MINIFLUX_ADMIN_URL` if needed.

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
./ops/backup-postgres.sh              # recommended: dump + Miniflux seed, NO vault
./ops/backup-postgres.sh --with-vault # also archive vault markdown
./ops/sync-miniflux-seed.sh           # refresh config/* from live Miniflux (for git)
```

Scripts load `radar/.env` via `ops/_load_dotenv.sh` (KEY=VALUE only — safe if comments contain `()`). Defaults: `POSTGRES_USER=radar_user`, `POSTGRES_DB=radar_db`.

Produces `backups/<UTC-stamp>/` (gitignored):

- `radar_<db>.dump` — `pg_dump -Fc` (Radar + Miniflux tables)
- `miniflux/miniflux-feeds.seed.json` + `.opml` — feed config snapshot
- `BACKUP_INFO.txt` — restore hints
- `vault.tar.gz` — only with `--with-vault`
- `SHA256SUMS`

**Git SoT (clone → ready feeds):** `config/miniflux-feeds.seed.json` (+ `.opml`).  
Commit the seed after `./ops/sync-miniflux-seed.sh` or after a backup that syncs live Miniflux.  
Do **not** commit `backups/` or vault articles.

Fresh PC:

```bash
cp .env.example .env          # secrets + later MINIFLUX_API_KEY
./ops/bootstrap-miniflux.sh   # up + import seed (or import-miniflux-feeds.sh)
```

Warns if `article_outbox` has `pending` / `writing` rows (crash-consistent, not cross-FS atomic). Retention: `RETENTION_DAYS` (default 7).

Env: `BACKUP_ROOT`, `RETENTION_DAYS`, `COMPOSE`, `SKIP_VAULT`, `SYNC_SEED`, `MINIFLUX_ADMIN_URL`.

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
- Scripts export `MSYS_NO_PATHCONV=1` so Git Bash does **not** rewrite container paths like `/tmp/radar_backup.dump` to `%TEMP%` (otherwise `pg_dump` fails with “could not open output file … AppData/Local/Temp”).
- `docker compose cp` host paths use `cygpath -w` under Git Bash so the dest is `C:\Users\…` (not `C:\c\Users\…`).
