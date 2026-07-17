# Runbook — Radar Informativo Globale

Companion operativo a [`../ops/README.md`](../ops/README.md). Usa ops per overlay Compose, reti e script backup; questo file per incident e upgrade.

---

## Deploy

```bash
cd radar
cp .env.example .env   # POSTGRES_PASSWORD, LLM lane keys (Profili A–E), MINIFLUX_*
docker compose up -d --build
```

- UI: **http://localhost/** (porta **80** → Nginx FE **8080**).
- Non pubblicare `:80` grezzo su Internet — TLS reverse proxy + auth/ACL.
- Miniflux **senza** porte host di default (hardened / lan / exec: vedi ops README).
- Hardened: `docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d`

API (`radar-backend`) ≠ ingest (`radar-worker`). Riavviare solo il backend **non** riparte il polling.

GeoJSON: in build Docker viene scaricato e verificato (`scripts/verify-geojson.mjs --fetch`). Locale: `npm run verify-geojson:fetch` in `radar/frontend`.

---

## Health: `/health/live` vs `/health/ready`

| Probe | Path | Meaning | Compose |
|-------|------|---------|---------|
| Liveness | `GET /health/live` | Processo API su | Sì — healthcheck backend; FE `depends_on` |
| Alias | `GET /health` | Come live | — |
| Readiness | `GET /health/ready` | Pool + migrazione heartbeat + freshness leader; report outbox | No — solo ops |

`/health/ready` può dare **503** per ~30–90s al boot finché il worker scrive heartbeat. Non usare ready per restartare l’API. Nginx FE non deve dipendere da ready.

```bash
docker compose exec radar-backend curl -sf http://localhost:8000/health/live
docker compose exec radar-backend curl -sf http://localhost:8000/health/ready
```

---

## Logs

```bash
cd radar
docker compose logs -f --tail=200 radar-backend
docker compose logs -f --tail=200 radar-worker
docker compose logs -f --tail=200 radar-frontend
docker compose logs -f --tail=200 radar-db
docker compose logs -f --tail=200 radar-miniflux
```

Ingest / LLM / outbox → **`radar-worker`**. API HTTP → `radar-backend`.

---

## Quota LLM esaurita

Sintomi: log worker con wait/`429`/`Retry-After`; pochi articoli nuovi; ready può restare 200 se heartbeat fresco.

- Ledger durable per **lane** (`classify:simple` / `classify:complex`): limiti da `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (RPM/TPM/RPD/budget; `0` = unmanaged); `PROVIDER` = gemini|deepseek|openai|glm|grok|claude; legacy `GEMINI_*`/`DEEPSEEK_*`/`LLM_RPM` = fill-gap (non tetto globale)
- Soft-trim worker: solo `LLM_SIMPLE.rpd` se `> 0`. Free tier → RPM/RPD `> 0`; paid → RPM/RPD `= 0` + `*_BUDGET_USD_DAY` / 402
- Cascata Gemini (lane SIMPLE se provider=gemini): `LLM_SIMPLE_MODEL` + `GEMINI_MODEL_FALLBACKS` (CSV)
- Cooldown 24h hard-fail: tabella `llm_model_cooldown` (`LLM_MODEL_COOLDOWN_HOURS`) — **non** per 429 brevi con Retry-After
- Routing: `LLM_ROUTING_MODE=complexity` + lane env:
  - `LLM_SIMPLE_PROVIDER` / `LLM_SIMPLE_MODEL` (lane SIMPLE only — effort tipico `none`)
  - `LLM_COMPLEX_PROVIDER` / `LLM_COMPLEX_MODEL` (BORDERLINE + COMPLEX + escalate — effort tipico `high`)
  - Residual SIMPLE↔COMPLEX se identity diversa
  - Complessità = rischio estrazione schema (G/E/X); **L sola → SIMPLE** (non eleva)
  - Swap provider: cambiare `PROVIDER`+`MODEL`+`API_KEY`+`BASE_URL`+limiti/budget; restart `radar-worker`
  - Esempio COMPLEX → Google: `LLM_COMPLEX_PROVIDER=gemini` + `LLM_COMPLEX_MODEL=gemini-3.5-flash`
  - OpenAI/GLM/Grok: dialect `openai` (niente `thinking` DeepSeek); ricette in `.env.example` Profili C/D/E
  - `claude` = stub (Messages API non implementata)
  - `LLM_ROUTING_SHADOW=true` = solo log lane (usa sempre SIMPLE)
- OpenAI-compat via httpx (`deepseek`/`openai`/`glm`/`grok`); effort: `*_REASONING_EFFORT` (DeepSeek dialect usa `thinking`)
- Periodicità ciclo: `WORKER_POLL_INTERVAL_SECONDS` (default 900)
- Senza `GEMINI_API_KEY`: API/FE avviano; worker degradato se tutte le lane richiedono Gemini
- Senza key OpenAI-compat con COMPLEX=deepseek/openai/glm/grok: warning (o fail se `LLM_ROUTING_STRICT=1`); COMPLEX usa SIMPLE

Azioni: verificare key/model in `.env` e restart `radar-worker`; controllare quote provider / AI Studio;  
`SELECT * FROM llm_model_cooldown;`; abbassare `MINIFLUX_LIMIT` se serve; **non** scalare worker multipli (single-leader).

```bash
docker compose exec radar-db psql -U radar_user -d radar_db \
  -c "SELECT provider, model, until_ts, reason FROM llm_model_cooldown;"
```

---

## Requeue articoli (ops / E2E)

**Distruttivo / re-ingest:** marca unread le ultime N entry *già lette* in Miniflux, cancella le righe `articles` / `article_outbox` e i markdown vault corrispondenti (hash URL), e svuota `llm_model_cooldown`. Non è un reconcile outbox “gentile”.

**Prerequisiti:** stack up (`radar-worker` healthy-enough), `MINIFLUX_API_KEY` valida, vault montato sul worker.

```bash
# Preview only (nessuna mutazione Miniflux/DB/vault)
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20 --dry-run

# Re-ingest reale
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20
docker compose restart radar-worker   # ciclo immediato (poll tipico 900s)
```

Poi nei log: `route lane=SIMPLE … effort=none` e/o `COMPLEX|BORDERLINE … effort=high`.

---

## Outbox pending / recovery

Stati: `pending` → `writing` → `completed` | `failed`. Mark-read Miniflux solo dopo `completed`.

Il worker chiama `reconcile_outbox` all’avvio e tra i cicli (stale `writing` → `pending`).

```bash
docker compose exec radar-backend curl -s http://localhost:8000/health/ready
docker compose exec radar-db psql -U radar_user -d radar_db \
  -c "SELECT status, COUNT(*) FROM article_outbox GROUP BY status;"
```

Su `failed` persistenti: `last_error`, mount `./vault`, permessi, poi restart worker.

---

## Backup / restore

Procedure e flag: **[ops/README.md](../ops/README.md)**.

```bash
./ops/backup-postgres.sh
./ops/restore-postgres.sh ./backups/<UTC-stamp>
./ops/restore-postgres.sh ./backups/<UTC-stamp> --with-vault
```

Windows: Git Bash / WSL. Preferire drill su stack usa-e-getta prima del restore prod.

---

## Rolling upgrade

1. Aggiorna codice; rivedi `.env.example` per nuovi knobs.
2. `docker compose up -d --build`.
3. Ricrea **`radar-backend`** per applicare migrazioni (`schema_migrations` — abort su checksum mismatch).
4. Ricrea **`radar-worker`** (uno solo); ready 503 breve fino a heartbeat.
5. Ricrea **`radar-frontend`** (depends on live).
6. Smoke: live, ready, `GET /api/articles?date=YYYY-MM-DD`, `GET /api/map-summary?date=…`, UI mappa.

Non puntare un load balancer a `/health/ready` se quello **riavvia** l’API su 503 transitori.

---

## Security boundary

| Rete | Membri |
|------|--------|
| `radar-edge` | frontend ↔ backend |
| `radar-data` | backend, worker, db, miniflux |

Frontend **mai** su data. CORS allowlist vuota in prod dietro Nginx. Secret solo in `.env`. Soft hardening: `no-new-privileges`, `cap_drop`, limiti risorse (vedi Compose).

---

## Escalation

| Sev | Trigger | Prima azione |
|-----|---------|--------------|
| P1 UI down | `:80` down | `docker compose ps`, log FE/backend, `/health/live` |
| P1 API live fail | restart loop backend | live + log + `pg_isready` — **non** cambiare healthcheck in ready |
| P2 ready stale | ready 503 > ~2 min | worker up? heartbeat? migrazione `004`+? |
| P2 ingest stuck | zero articoli | API key Miniflux/LLM lane, quota, outbox, log worker |
| P2 outbox backlog | `failed`/`pending` alti | vault mount, reconcile |
| P3 data | corruzione | restore drill ops su stack usa-e-getta |

Allega: `docker compose ps`, ultimi 200 log backend+worker, JSON `/health/ready`.
