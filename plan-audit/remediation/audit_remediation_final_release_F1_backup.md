# Final Release — Fase 1 Backup / restore drill

**Stato:** PASS  
**Data:** 2026-07-17  
**Branch:** `refactor/testing` @ `7472acd`  
**Ambiente:** stack Compose dev (Windows + Docker Desktop)

---

## Procedura eseguita

1. Backup primario `radar/backups/20260717T064518Z/`
   - `radar_radar_db.dump` (~54 MB)
   - `vault.tar.gz` (~1 MB)
   - `SHA256SUMS` (dump + vault)
2. Outbox pre-dump: `completed=2018`, `pending/writing=0`
3. Safety backup pre-restore: `radar/backups/20260717T064736Z/`
4. Restore **DB-only** (senza `--with-vault`) da `20260717T064518Z`
   - stop `radar-worker` + `radar-backend`
   - `pg_restore --clean --if-exists --no-owner --no-acl` → exit **0**
   - start backend + worker
5. Smoke post-restore

---

## Criteri PASS

| Check | Esito |
|-------|-------|
| Directory backup con dump + SHA256SUMS (+ vault) | PASS |
| Restore senza errore fatale | PASS (`pg_restore` 0) |
| Servizi healthy / worker running | PASS |
| `/health/live` backend | PASS `{"status":"ok"}` |
| FE `/health` | PASS `ok` |
| `GET /api/map-summary` | PASS (payload day-view) |
| `articles` count post-restore | 2893 |
| outbox `pending`/`writing` post-smoke | 0 |

---

## Note operative

- Gli script `ops/*.sh` su questa macchina **non** partono con `source .env` diretto: `.env` locale provoca `syntax error near unexpected token '('` in bash. Drill eseguito con equivalenti Compose (`pg_dump`/`pg_restore`/`docker compose cp`) + Git Bash solo per `tar`/`sha256sum`. Follow-up consigliato: source `.env` più robusto (solo `KEY=VALUE`) negli script ops.
- Dump/vault **non** committati (`backups/` gitignored).
- Vault replace non eseguito (gate minimo = DB restore).

---

## Decisione

**Fase 1 PASS** — proseguire a Fase 2 (seed 10k su data dedicata).
