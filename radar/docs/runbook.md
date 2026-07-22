# Runbook — Radar Informativo Globale

Companion operativo a [`../ops/README.md`](../ops/README.md). Usa ops per overlay Compose, reti e script backup; questo file per incident e upgrade.

---

## Deploy

```bash
cd radar
cp .env.example .env   # POSTGRES_PASSWORD, LLM lane keys (Profili A–F), MINIFLUX_*
docker compose up -d --build
```

- UI: **http://localhost/** (porta **80** → Nginx FE **8080**).
- Non pubblicare `:80` grezzo su Internet — TLS reverse proxy + auth/ACL.
- Miniflux **senza** porte host di default (hardened / lan / exec: vedi ops README).
- Hardened: `docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d`
- Local-Hybrid (Profilo F): overlay `docker-compose.ollama-host.yml` — vedi sezione sotto.

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
- Failover S3: L1 `LLM_*_FALLBACKS` (CSV **stesso** provider) → L2 residual cross-lane → L3 fallback article. `*_FALLBACKS=` vuoto = nessun L1 (sostituto cross-provider = residual, non CSV).
- Cascata Gemini same-provider (opz.): `LLM_SIMPLE_FALLBACKS` o legacy `GEMINI_MODEL_FALLBACKS` solo se chiave lane assente
- Cooldown 24h hard-fail: tabella `llm_model_cooldown` (`LLM_MODEL_COOLDOWN_HOURS`) — **non** per 429 brevi con Retry-After
- Routing: `LLM_ROUTING_MODE=complexity` + lane env:
  - `LLM_SIMPLE_PROVIDER` / `LLM_SIMPLE_MODEL` (lane SIMPLE only — effort tipico `none`)
  - `LLM_COMPLEX_PROVIDER` / `LLM_COMPLEX_MODEL` (BORDERLINE + COMPLEX + escalate — effort tipico `high`)
  - Residual SIMPLE↔COMPLEX se identity diversa (**eccezione:** SIMPLE Ollama-think → **niente** residual/escalate verso cloud)
  - Complessità = rischio estrazione schema (G/E/X); **L sola → SIMPLE** (non eleva)
  - Swap provider: cambiare `PROVIDER`+`MODEL`+`API_KEY`+`BASE_URL`+limiti/budget; restart `radar-worker`; **un solo** blocco profilo attivo
  - Target hybrid (Profilo A): Gemini Flash Lite SIMPLE + DeepSeek COMPLEX; `*_FALLBACKS=`
  - OpenAI/GLM/Grok: dialect `openai` (niente `thinking` DeepSeek); ricette in `.env.example` Profili C/D/E + topologia 1–8
  - Local-Hybrid (Profilo F): Ollama host via `PROVIDER=openai` + `BASE_URL=http://host.docker.internal:11434/v1` — vedi sezione sotto; **vietato** SDK `ollama` / `ollama.chat`
  - Cloud-only: Profilo A/B; F commentato; compose **senza** `-f docker-compose.ollama-host.yml`
  - `claude` = stub (Messages API non implementata)
  - `LLM_ROUTING_SHADOW=true` = solo log lane (usa sempre SIMPLE)
  - Audit: [`audit_llm_lane_env_generalization.md`](../../plan-audit/complete/audit_llm_lane_env_generalization.md)
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

**Distruttivo / re-ingest:** marca unread le ultime N entry *già lette* in Miniflux (API paginata: Miniflux restituisce ≤50 entry/pagina), cancella le righe `articles` / `article_outbox` e i markdown vault corrispondenti (hash URL), e svuota `llm_model_cooldown`. Non è un reconcile outbox “gentile”.

**Prerequisiti:** stack up (`radar-worker` healthy-enough), `MINIFLUX_API_KEY` valida, vault montato sul worker.

```bash
# Preview only (nessuna mutazione Miniflux/DB/vault)
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 50 --dry-run

# Re-ingest reale (ultime N read)
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 50
docker compose restart radar-worker   # ciclo immediato (poll tipico 900s)

# Prova da zero (48h / full reset locale): wipe TUTTI i .md vault + DELETE tutte le articles
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 100 --purge-all --dry-run
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 100 --purge-all
docker compose restart radar-worker
```

Il worker fetch unread filtra già `published_after` ≈ 48h (`MINIFLUX` client). Entry unread più vecchie restano in coda Miniflux ma non entrano nel ciclo finché non rientrano nella finestra.

Poi nei log: `route lane=SIMPLE … effort=none` e/o `COMPLEX|BORDERLINE … effort=high`; gate: `Ciclo … 0 errori`.

---

## Local-Hybrid (Fase A / Profilo F)

Scenario ops: SIMPLE su **Ollama host** + COMPLEX cloud (tipico DeepSeek). Path HTTP OpenAI-compat già nel client (`PROVIDER=openai` + httpx) — **nessun** package/SDK `ollama`, **vietato** `ollama.chat`. Core shipped `54c8038`.

### Ricette profili (solo `.env` + overlay)

| # | Topologia | Blocco `.env.example` | Overlay ollama-host? |
|---|-----------|----------------------|----------------------|
| 1 | Gemini Lite + DeepSeek (TARGET) | Profilo A | No |
| 2 | Paid same/mix | B / C / D / E | No |
| 3 | SIMPLE locale + COMPLEX cloud | Profilo F | **Sì** |
| 4 | Dual-local | entrambe `openai` + BASE_URL host | **Sì** |
| 5 | SIMPLE cloud + COMPLEX locale | gemini + openai COMPLEX | **Sì** |
| 6 | Una lane effettiva | COMPLEX ≡ SIMPLE | No |
| 7 | L1 same-provider CSV | `LLM_*_FALLBACKS=model2` | — |
| 8 | Cloud-only | A o B; F commentato | **No** |

Dettaglio: [`audit_llm_lane_env_generalization.md`](../../plan-audit/complete/audit_llm_lane_env_generalization.md).

**Prerequisiti**

1. Ollama in esecuzione sull’host (es. `127.0.0.1:11434`).
2. Modello: ops default **`gemma4-radar`** (Modelfile host, non in git):
   ```text
   FROM gemma4:12b
   PARAMETER num_ctx 8192
   PARAMETER temperature 0.1
   ```
   `ollama create gemma4-radar -f Modelfile` (base pull: `gemma4:12b`).
3. In `.env` (non commit): attivare il blocco **Profilo F** da [`.env.example`](../.env.example) — spegnere A/B se confliggono.
4. Overlay Compose per risolvere `host.docker.internal` dal worker:

```bash
cd radar
docker compose -f docker-compose.yml -f docker-compose.ollama-host.yml up -d radar-worker
```

**Lane tipiche (Profilo F)**

| Lane | Provider | Model | `BASE_URL` |
|------|----------|-------|------------|
| SIMPLE | `openai` | `gemma4-radar` | `http://host.docker.internal:11434/v1` |
| COMPLEX | `deepseek` | `deepseek-v4-flash` | `https://api.deepseek.com` |

- `LLM_SIMPLE_API_KEY` dummy non vuota (es. `ollama`); RPM/TPM/RPD SIMPLE = `0` (unmanaged).
- `LLM_SIMPLE_REASONING_EFFORT=high` — su `gemma4*` / reasoner Ollama il client abilita **`think=true`**, `num_ctx`/`num_predict=8192`, estrae JSON da `content` o `reasoning` (`openai_compat_*`). Schema Radar senza campo CoT.
- **Nessun escalate** e **nessun residual** SIMPLE Ollama-think → DeepSeek/cloud: solo correction locale (`_MAX_ATTEMPTS_LOCAL=6`). Se Ollama è down sugli articoli SIMPLE → fallback article (non cloud). BORDERLINE/COMPLEX → DeepSeek.
- Pre-validate: `normalize_llm_json_dict` (liste→CSV, alias, coerenza geo/categoria/tag).
- Host: **`OLLAMA_NUM_PARALLEL=1`**; worker tipico `WORKER_ENTRY_CONCURRENCY=1`, `WORKER_DB_CONCURRENCY=1`, `WORKER_GEMINI_CONCURRENCY=1`.
- `LLM_SIMPLE_TIMEOUT`: `180` default esempio; `600` se load/think lenti.
- Non pubblicare host `:11434` su LAN di default; non combinare con un container ROCm Ollama sulla stessa GPU.
- **VRAM lifecycle (shipped):** durante classify SIMPLE il modello resta caldo (`keep_alive` busy sulle request `/v1`, best-effort). A fine ciclo worker + debounce (`OLLAMA_UNLOAD_DEBOUNCE_SECONDS`, default 60) il worker chiama unload nativo `POST /api/generate` con `keep_alive=0` (log `ollama_unload`). Gate: `OLLAMA_AUTO_UNLOAD=true` + modello SIMPLE think-protocol. Wake NOTIFY durante debounce → skip unload. Shutdown worker → unload best-effort.
- Env tipici (`.env.example`): `OLLAMA_AUTO_UNLOAD`, `OLLAMA_KEEP_ALIVE_BUSY=5m`, `OLLAMA_KEEP_ALIVE_IDLE=0`, `OLLAMA_UNLOAD_DEBOUNCE_SECONDS=60`.
- Checklist: [`ops/verify-ollama-vram.sh`](../ops/verify-ollama-vram.sh) — `ollama ps` + log `ollama_unload` / route / health.

**Verifica VRAM (ops)**

```bash
cd radar
ollama ps                                          # idle: vuoto / senza gemma
# … ciclo con unread SIMPLE …
ollama ps                                          # durante classify: gemma4-radar in GPU
# … fine ciclo + debounce …
ollama ps                                          # idle di nuovo
docker compose -f docker-compose.yml -f docker-compose.ollama-host.yml \
  logs --since=15m radar-worker | grep ollama_unload
./ops/verify-ollama-vram.sh
```

**Verifica / gate 48h**

Dopo smoke, re-ingest nella finestra worker ≈ 48h con lo script ufficiale (dry-run prima): sezione **Requeue articoli** sopra (`requeue_articles` / `--purge-all` + `restart radar-worker`). Log attesi: `route lane=SIMPLE … openai / gemma4-radar` e COMPLEX/BORDERLINE DeepSeek; `ollama ps` durante classify mostra il modello in GPU; dopo idle+debounce `ollama_unload` e VRAM libera.

**Rollback → Profilo B**

1. Ripristinare in `.env` il blocco **Profilo B** (DeepSeek-only).
2. `docker compose up -d radar-worker` **senza** `-f docker-compose.ollama-host.yml`.

Piano: [`plan_impl_fase_A_local_amd_ollama.md`](../../plan-audit/complete/plan_impl_fase_A_local_amd_ollama.md). SoT lane: [`sot_llm_multi_model_fallback.md`](../../plan-audit/complete/sot_llm_multi_model_fallback.md).

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

Procedure complete: **[ops/README.md](../ops/README.md)**. Guida utente Miniflux (feed minimi + seed): [`docs/01_getting_started.md`](../../docs/01_getting_started.md) §6.

```bash
# Config-first (no vault markdown) — dump DB + snapshot seed/OPML in backups/
./ops/backup-postgres.sh
./ops/backup-postgres.sh --with-vault   # include vault/

# Aggiorna SoT git da Miniflux live (poi commit config/)
./ops/sync-miniflux-seed.sh

# Fresh PC: API key in .env, poi
./ops/import-miniflux-feeds.sh
# oppure
./ops/bootstrap-miniflux.sh

# Restore DB completo (opzionale; include articoli Postgres)
./ops/restore-postgres.sh ./backups/<UTC-stamp>
./ops/restore-postgres.sh ./backups/<UTC-stamp> --with-vault
```

Windows: Git Bash / WSL. Preferire drill su stack usa-e-getta prima del restore prod.  
`backups/` è gitignored; i feed da riprodurre su un clone sono `config/miniflux-feeds.seed.json` (+ `.opml`).

---

## Rolling upgrade

1. Aggiorna codice; rivedi `.env.example` per nuovi knobs.
2. `docker compose up -d --build`.
3. Ricrea **`radar-backend`** per applicare migrazioni (`schema_migrations` — abort su checksum mismatch; include `012_pgvector_article_embeddings.sql`).
4. Ricrea **`radar-worker`** (uno solo); ready 503 breve fino a heartbeat.
5. Ricrea **`radar-frontend`** (depends on live).
6. Smoke: live, ready, `GET /api/articles?date=YYYY-MM-DD`, `GET /api/map-summary?date=…`, `GET /api/map-relations?date=…`, `GET /api/saved-summary`, `GET /api/articles?saved=true`, `PATCH /api/articles/{id}/saved_status` (save⇒read), UI mappa **MapLibre** (default) + toolbar **NOTIZIE SALVATE** (tooltip → zoom + spiderfy). Verifica renderer: confini + pin/archi su MapLibre; `npm run verify-map-renderer` in `radar/frontend` se rebuild FE.

### Verifica Deduplicazione Semantica (pgvector)

```bash
# Test embedder all-MiniLM-L6-v2 in isolamento (dry-run)
Soglia default: `SEMANTIC_DEDUP_SIMILARITY_THRESHOLD=0.80` (distanza ≤ 0.20).

docker compose exec -T radar-worker python -m app.scripts.verify_semantic_dedup --dry-run

# Test live DB (estensione pgvector, tabella article_embeddings, cerca vicino-duplicato)
docker compose exec -T radar-worker python -m app.scripts.verify_semantic_dedup
```

### Verifica Metriche FinOps & Diagnostica (Fase 013)

```bash
# Script di verifica live DB e tabelle metriche/ledger/dedup (GATE 013)
docker compose exec -T radar-worker python -m app.scripts.verify_metrics_013

# Test live degli endpoint REST di diagnostica
curl -s http://localhost/api/metrics/summary
curl -s http://localhost/api/metrics/by-feed
curl -s http://localhost/api/metrics/dedup
```


### Forzare Leaflet legacy (ops / debug)

Default = MapLibre (`MAP_RENDERER`). Per attivare il path dormiente:

```js
// DevTools console, poi reload
localStorage.setItem('radar.mapRenderer', 'leaflet');
// oppure prima del bootstrap:
window.__RADAR_MAP_RENDERER__ = 'leaflet';
```

Ripristino default: rimuovere la chiave / `localStorage.setItem('radar.mapRenderer', 'maplibre')` + reload. Proiezione MapLibre: `localStorage` key `radar.mapProjection` = `globe` \| `mercator`.

**CSP / basemap:** se la console blocca `basemaps.cartocdn.com/.../style.json`, in `radar/frontend/nginx.conf` `connect-src` deve includere l’**apex** `https://basemaps.cartocdn.com` oltre a `https://*.basemaps.cartocdn.com` (il solo wildcard non basta). Rebuild FE dopo cambio CSP.

Re-ingest Miniflux (distruttivo): sezione **Requeue** sopra + skill [`.agents/skills/radar-requeue-ops/SKILL.md`](../../.agents/skills/radar-requeue-ops/SKILL.md).

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
