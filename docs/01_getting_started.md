# Manuale operativo: installazione e avvio

Guida per portare su **Radar Informativo Globale** con Docker. Fonte knobs: [`radar/.env.example`](../radar/.env.example). Ops avanzate: [`radar/ops/README.md`](../radar/ops/README.md). Incident/upgrade: [`radar/docs/runbook.md`](../radar/docs/runbook.md).

---

## 1. Requisiti

- Docker + Docker Compose
- RAM consigliata ≥ 4 GB
- Porte host (compose base): **80** (frontend). Backend, DB e Miniflux restano interni.
- Accesso rete a: feed RSS, API LLM (Gemini e/o OpenAI-compat: DeepSeek / OpenAI / GLM / Grok), tile Carto
- Ops tipico LLM: **Profilo B** in [`radar/.env.example`](../radar/.env.example) (DeepSeek-only) con `LLM_ROUTING_MODE=complexity` e `LLM_ROUTING_SHADOW=false`. Default codice boot-safe **senza** `.env`: `LLM_ROUTING_MODE=off` + `LLM_ROUTING_SHADOW=true` — copiare `.env.example` attiva già il profilo ops, non il default codice.

Miniflux UI su host solo con overlay:

- hardened: `http://127.0.0.1:8080`
- lan: `http://localhost:8080`

---

## 2. Configurazione `.env`

```bash
cd radar
cp .env.example .env
```

Compila almeno: key lane (`LLM_SIMPLE_API_KEY` / `LLM_COMPLEX_API_KEY` o legacy `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` a seconda del provider), `POSTGRES_PASSWORD`, credenziali Miniflux. **Non** usare `$` nelle password (interpolazione Compose).

Categorie principali (dettaglio in `.env.example`):

| Area | Esempi |
|------|--------|
| Runtime | `RADAR_ENV`, `RADAR_TIME_ZONE` |
| CORS | `CORS_ALLOW_ORIGINS` (vuoto in prod dietro Nginx; es. `http://localhost:4200` per `ng serve`) |
| LLM | Lane `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (provider=`gemini`\|`deepseek`\|`openai`\|`glm`\|`grok`\|`claude` **stub**; model/RPM/TPM/RPD/budget; `0`=unmanaged); dialect OpenAI-compat: deepseek=`thinking`, openai/glm/grok=stock; soft-trim = `LLM_SIMPLE.rpd` se >0; **RPM/TPM wait stessa lane**; **RPD/cooldown → residual cross-lane**; free=RPM/RPD(+TPM), paid=BUDGET; legacy fill-gap; Profili A–E in `.env.example` + SoT LLM |
| Worker | coda/concorrenza, `WORKER_POLL_INTERVAL_SECONDS` (default 900), heartbeat |
| Miniflux | URL interno, API key, `MINIFLUX_LIMIT` (tipico **50**; `100` può superare `MAX_MINIFLUX_RESPONSE_BYTES=5MB`), timeout/byte caps |
| Postgres | user/password/db, `DATABASE_URL` (Compose la costruisce in container) |

---

## 3. Asset GeoJSON

Path obbligatorio per la mappa:

`radar/frontend/src/assets/data/countries.geo.json`

Il file **non** è tracciato in Git (~14 MB). Pin, licenza e URL canonico: [`ASSET_LICENSE.md`](../radar/frontend/src/assets/data/ASSET_LICENSE.md).

```bash
cd radar/frontend
npm run verify-geojson:fetch
```

Senza asset valido, `npm run build` / la build Docker del frontend falliscono al passo verify (o la mappa non disegna i confini).

---

## 4. Avvio

```bash
cd radar
docker compose up --build -d
```

Servizi: `radar-frontend`, `radar-backend`, `radar-worker`, `radar-db`, `radar-miniflux` su reti `radar-edge` + `radar-data`.

Build note:

- Backend: Python **3.12-slim**, utente non-root `radar`
- Frontend: `npm ci --legacy-peer-deps` → fetch/verify GeoJSON → Nginx **1.27-alpine**, utente non-root `nginx`

### Overlay

```bash
# FE + Miniflux solo loopback
docker compose -f docker-compose.yml -f docker-compose.hardened.yml up -d --build

# Miniflux pubblicato su :8080
docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d --build
```

---

## 5. Validazione

```bash
# Health FE (Nginx :80) — non confondere con /health/live dell'API
curl.exe -sI http://localhost/health

# Probe API nel container backend
docker compose exec radar-backend curl -sf http://localhost:8000/health/live
docker compose exec radar-backend curl -sf http://localhost:8000/health/ready

# Articles (envelope, non array nudo) — usa una data ISO reale
curl.exe -s "http://localhost/api/articles?date=2026-07-15"

# Map summary
curl.exe -s "http://localhost/api/map-summary?date=2026-07-15"

# DB
docker compose exec radar-db psql -U radar_user -d radar_db -c "\dt"
```

| Probe | Significato | Compose |
|-------|-------------|---------|
| `GET /health` (host `:80`) | Healthcheck Nginx frontend | Sì (container FE) |
| `GET /health/live` (API) | Processo API su | Sì (healthcheck backend) |
| `GET /health/ready` (API) | Pool + migrazioni + heartbeat worker | No (ops; 503 tipico ai primi secondi) |
| `GET /health` (API, solo in-container `:8000`) | Alias di live | — |

---

## 6. Miniflux e ingest

1. Pubblica Miniflux (lan/hardened) e apri l’UI admin.
2. **Settings → API Keys → Create** → copia in `.env` come `MINIFLUX_API_KEY`.
3. `docker compose up -d` (rispetta `depends_on` healthy) per rileggere l’env. Evitare `docker compose restart` su tutti i servizi insieme: Postgres può essere ancora in recovery mentre backend/worker aprono il pool (`CannotConnectNowError`). Preferire `up -d` o restart ordinato (`radar-db` → wait healthy → resto); `init_pool` ritenta errori transienti di startup.
4. Aggiungi feed (catalogo: [RSS.txt](../RSS.txt)).

Con unread Miniflux alti, tenere `MINIFLUX_LIMIT` ≤ ~50 sotto il cap `MAX_MINIFLUX_RESPONSE_BYTES` (5MB). Se Gemma 31b restituisce HTTP 500 in classificazione, impostare in `.env` `GEMINI_MODEL=gemini-3.1-flash-lite` (o altro modello supportato) e riavviare solo `radar-worker` — **non** commitare `.env`.

**Ciclo reale (worker, non API):**

- Servizio `radar-worker` (`python -m app.worker`), leadership via advisory lock
- Polling `WORKER_POLL_INTERVAL_SECONDS` (default **900** = 15 min)
- Entry **unread** ultime ~48h, dedup URL in PostgreSQL
- Complexity v2.2 → QuotaLedger reserve → classificazione multi-provider (lane SIMPLE / COMPLEX) → eventuale cooldown modello → commit DB + outbox → vault atomico → mark-read Miniflux solo se completed
- Quote durable per lane: `llm_request_ledger` (`LLM_SIMPLE_*` / `LLM_COMPLEX_*`; soft-trim = `LLM_SIMPLE.rpd` se >0; RPM/TPM=attesa stessa lane; RPD/cooldown=`QuotaDailyExceeded` → residual altra lane; free=RPM/RPD(+TPM), paid=budget)
- Requeue ops (re-ingest distruttivo: unread Miniflux + purge articoli/vault/outbox + clear cooldown): comando canonico nel [runbook](../radar/docs/runbook.md) — `docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20` poi `docker compose restart radar-worker`

Riavviare solo `radar-backend` **non** riavvia l’ingest: serve `radar-worker`.

---

## 7. Troubleshooting

| Sintomo | Cosa controllare |
|---------|------------------|
| `InvalidPasswordError` | `$` in password Compose |
| Miniflux exit | DB non ready → attendere `radar-db` healthy, poi `docker compose up -d radar-miniflux` (evitare `restart` di tutto lo stack in parallelo; vedi [`radar/.ecc/rules/docker.md`](../radar/.ecc/rules/docker.md) Regola 4) |
| `/health/ready` 503 | Normale finché il worker non scrive heartbeat (~30–90s) |
| 429 / rate limit LLM | Ledger + Retry-After; quote lane (`LLM_SIMPLE_*` / `LLM_COMPLEX_*`); Studio / dashboard provider |
| Auth / key LLM | Key lane o legacy (`GEMINI_*` / `DEEPSEEK_*` / `OPENAI_*`) allineate al `PROVIDER` della lane |
| Articoli bloccati / requeue | [runbook](../radar/docs/runbook.md) — `docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20` (+ restart worker) |
| Mappa senza confini | Manca o SHA errato su `countries.geo.json` → `npm run verify-geojson:fetch` |
| Nessun articolo nuovo | `MINIFLUX_API_KEY`, log `radar-worker`, quote lane (`LLM_SIMPLE_RPD` / budget), cooldown |
| Payload Miniflux troppo grande / log 5MB | Abbassare `MINIFLUX_LIMIT` (tipico 50); non alzare cieco il cap |
| Classificazione → fallback / HTTP 500 modello | Verificare `LLM_*_MODEL` / legacy `GEMINI_MODEL` in `.env`; riavviare `radar-worker` — **non** commitare `.env` |

Backup/restore: [radar/ops/README.md](../radar/ops/README.md) (`radar/ops/backup-postgres.sh`, `restore-postgres.sh`). Persistenza: `radar/data/postgres/`, `radar/vault/`.
