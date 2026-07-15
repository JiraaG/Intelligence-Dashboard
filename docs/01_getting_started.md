# Manuale operativo: installazione e avvio

Guida per portare su **Radar Informativo Globale** con Docker. Fonte knobs: [`radar/.env.example`](../radar/.env.example). Ops avanzate: [`radar/ops/README.md`](../radar/ops/README.md). Incident/upgrade: [`radar/docs/runbook.md`](../radar/docs/runbook.md).

---

## 1. Requisiti

- Docker + Docker Compose
- RAM consigliata ≥ 4 GB
- Porte host (compose base): **80** (frontend). Backend, DB e Miniflux restano interni.
- Accesso rete a: feed RSS, Google Gemini API, tile Carto

Miniflux UI su host solo con overlay:

- hardened: `http://127.0.0.1:8080`
- lan: `http://localhost:8080`

---

## 2. Configurazione `.env`

```bash
cd radar
cp .env.example .env
```

Compila almeno: `GEMINI_API_KEY` (o `GOOGLE_API_KEY`, che ha precedenza), `POSTGRES_PASSWORD`, credenziali Miniflux. **Non** usare `$` nelle password (interpolazione Compose).

Categorie principali (dettaglio in `.env.example`):

| Area | Esempi |
|------|--------|
| Runtime | `RADAR_ENV`, `RADAR_TIME_ZONE` |
| CORS | `CORS_ALLOW_ORIGINS` (vuoto in prod dietro Nginx; es. `http://localhost:4200` per `ng serve`) |
| LLM | `GEMINI_MODEL`, `LLM_RPM` / `LLM_TPM` / `LLM_RPD`, `GEMINI_REQUEST_TIMEOUT` |
| Worker | coda/concorrenza, `WORKER_POLL_INTERVAL_SECONDS`, heartbeat |
| Miniflux | URL interno, API key, limit, timeout/byte caps |
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
- Frontend: `npm ci --legacy-peer-deps` → fetch/verify GeoJSON → Nginx **1.27-alpine**

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
3. `docker compose up -d` (o restart `radar-worker` / stack) per rileggere l’env.
4. Aggiungi feed (catalogo: [RSS.txt](../RSS.txt)).

**Ciclo reale (worker, non API):**

- Servizio `radar-worker` (`python -m app.worker`), leadership via advisory lock
- Polling ~`WORKER_POLL_INTERVAL_SECONDS` (default 900)
- Entry **unread** ultime ~48h, dedup URL in PostgreSQL
- Classificazione Gemini → commit DB + outbox → vault atomico → mark-read Miniflux solo se completed
- Quote durable: `llm_request_ledger` (`LLM_RPM` / `LLM_TPM` / `LLM_RPD`)

Riavviare solo `radar-backend` **non** riavvia l’ingest: serve `radar-worker`.

---

## 7. Troubleshooting

| Sintomo | Cosa controllare |
|---------|------------------|
| `InvalidPasswordError` | `$` in password Compose |
| Miniflux exit | DB non ready → `docker compose restart radar-miniflux` |
| `/health/ready` 503 | Normale finché il worker non scrive heartbeat (~30–90s) |
| 429 Gemini | Ledger + Retry-After; verifica quote in AI Studio |
| Mappa senza confini | Manca o SHA errato su `countries.geo.json` → `npm run verify-geojson:fetch` |
| Nessun articolo nuovo | `MINIFLUX_API_KEY`, log `radar-worker`, `LLM_RPD` |

Backup/restore: [radar/ops/README.md](../radar/ops/README.md) (`radar/ops/backup-postgres.sh`, `restore-postgres.sh`). Persistenza: `radar/data/postgres/`, `radar/vault/`.
