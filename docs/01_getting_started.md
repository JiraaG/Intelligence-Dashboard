# Manuale operativo: installazione e avvio

Guida per portare su **Radar Informativo Globale** con Docker. Fonte knobs: [`radar/.env.example`](../radar/.env.example). Ops avanzate: [`radar/ops/README.md`](../radar/ops/README.md). Incident/upgrade: [`radar/docs/runbook.md`](../radar/docs/runbook.md).

---

## 1. Requisiti

- Docker + Docker Compose
- RAM consigliata ≥ 4 GB
- Porte host (compose base): **80** (frontend). Backend, DB e Miniflux restano interni.
- Accesso rete a: feed RSS, API LLM (Gemini e/o OpenAI-compat: DeepSeek / OpenAI / GLM / Grok), tile/style mappa (Carto / MapLibre — renderer default **MapLibre** 3D-primary; Leaflet solo via `MAP_RENDERER`)
- Ops tipico LLM: **Profilo B** in [`radar/.env.example`](../radar/.env.example) (DeepSeek-only) con `LLM_ROUTING_MODE=complexity` e `LLM_ROUTING_SHADOW=false`. Effort BORDERLINE: `LLM_BORDERLINE_REASONING_EFFORT` (example safe `high`; ops tipico post-GATE `none` + escalate `high`). **Profilo F (Local-Hybrid):** Ollama host + overlay `docker-compose.ollama-host.yml` — vedi [runbook § Local-Hybrid](../radar/docs/runbook.md) (include lifecycle VRAM / `OLLAMA_*` + `ops/verify-ollama-vram.sh`). Default codice boot-safe **senza** `.env`: `LLM_ROUTING_MODE=off` + `LLM_ROUTING_SHADOW=true` — copiare `.env.example` attiva già il profilo ops, non il default codice.

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
| LLM | Lane `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (provider=`gemini`\|`deepseek`\|`openai`\|`glm`\|`grok`\|`claude` **stub**; model/RPM/TPM/RPD/budget; `0`=unmanaged); BORDERLINE effort `LLM_BORDERLINE_REASONING_EFFORT` (default/ops tipico `high`; COMPLEX tipico `max` su Flash); dialect OpenAI-compat: deepseek=`thinking`, openai/glm/grok=stock; soft-trim = `LLM_SIMPLE.rpd` se >0; **RPM/TPM wait stessa lane**; **RPD/cooldown → residual cross-lane**; free=RPM/RPD(+TPM), paid=BUDGET; legacy fill-gap; Profili A–F in `.env.example` + SoT LLM (F = Local-Hybrid Ollama host) |
| Worker | coda/concorrenza, drain eager + settle `WORKER_REFRESH_SETTLE_SECONDS` (default 15), safety poll `WORKER_POLL_INTERVAL_SECONDS` (default 900), heartbeat |
| Miniflux | URL interno, API key, `MINIFLUX_LIMIT` (tipico **50**; `100` può superare `MAX_MINIFLUX_RESPONSE_BYTES=5MB`), timeout/byte caps |
| Postgres | user/password/db, `DATABASE_URL` (Compose la costruisce in container con image `pgvector/pgvector:0.8.0-pg15`) |
| Semantic Dedup | `SEMANTIC_DEDUP_ENABLED=true`, `SEMANTIC_DEDUP_SIMILARITY_THRESHOLD=0.80`, `SEMANTIC_DEDUP_LOOKBACK_HOURS=24`, `SEMANTIC_PREFILTER_LEN_RATIO=0.7`, `SEMANTIC_QUALITY_REPLACE_HINT_RATIO=1.25`, `SEMANTIC_DEDUP_DIRECT_SHADOW=false`, `CONTENT_HASH_DEDUP_ENABLED=true` |


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

# Map relations (bilateral arcs)
curl.exe -s "http://localhost/api/map-relations?date=2026-07-15"

# Saved vault (cross-day, no date)
curl.exe -s "http://localhost/api/saved-summary"
curl.exe -s "http://localhost/api/articles?saved=true&limit=10"

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

## 6. Miniflux: configurazione minima feed e ingest

Miniflux è l’unica sorgente RSS. **Di default non ha porte host** — per l’UI admin:

```bash
cd radar
docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d
# → http://localhost:8080
# (hardened: solo 127.0.0.1:8080)
```

### Configurazione minima (obbligatoria)

| Passo | Cosa fare |
|-------|-----------|
| 1. Admin | Login con `MINIFLUX_ADMIN_USERNAME` / `MINIFLUX_ADMIN_PASSWORD` da `.env` |
| 2. API key | **Settings → API Keys → Create** → copia in `.env` come `MINIFLUX_API_KEY` |
| 3. Rileggi env | `docker compose up -d` (preferire `up -d`, non `restart` parallelo di tutto lo stack) |
| 4. Feed | Importa lo seed versionato (non aggiungere i feed a mano se parti da zero) |

```bash
# Da radar/, Git Bash / WSL — applica categorie, URL, scraper CSS, crawler, User-Agent
./ops/import-miniflux-feeds.sh
# oppure one-shot dopo clone:
./ops/bootstrap-miniflux.sh
```

**SoT feed in Git** (non sostituibile da un dump Postgres “vecchio”):

| File | Contenuto |
|------|-----------|
| [`radar/config/miniflux-feeds.seed.json`](../radar/config/miniflux-feeds.seed.json) | Config completa: titolo, categoria, `feed_url`, `scraper_rules`, `crawler`, `user_agent`, `enabled?` (assente = **true**) |
| [`radar/config/miniflux-feeds.opml`](../radar/config/miniflux-feeds.opml) | OPML portabile (categorie/URL; le regole scraper vivono nello seed) |
| [`RSS.txt`](../RSS.txt) | Catalogo umano di riferimento (URL + selettori CSS) |

**UI FONTI vs CLI (add feed):**

| Azione | Dove |
|--------|------|
| Vedere chi ha prodotto articoli nel giorno calendario | Topbar **FONTI → Giorno** (`published_at`) |
| Spegnere / accendere un feed già importato | Topbar **FONTI → Catalogo** (toggle → Miniflux `disabled`; seed **non** riscritto) |
| Conteggio sorgenti attive | **STATUS → Sorgenti N/M** (read-only) |
| **Aggiungere un URL nuovo** | Edit seed (`enabled` opzionale, default true) + mirror `RSS.txt` → `./ops/import-miniflux-feeds.sh` → commit seed+OPML. **Non** da UI. |
| Gate mutazioni PATCH feed (opzionale) | `FEED_ADMIN_TOKEN` in `.env`; se valorizzato, header `X-Feed-Admin-Token` obbligatorio. **Caveat UI:** il toggle FONTI Catalogo **non** invia l’header (`article.service.ts`) → con token non vuoto il browser riceve 401 salvo proxy fidato; tipico LAN = token vuoto |

**Volume mappa:** dipende dai feed sottoscritti in Miniflux, non dal solo worker. Con 1–2 feed (es. BBC World + NASA) tipicamente ~40–60 articoli/48h; per ~centinaia di notizie/giorno importa lo seed completo (Guardian, BBC sezioni, NPR, DW, CNBC, …). Default catalogo: tutti abilitati (`enabled` assente = true); l’import applica `disabled = not enabled`.

Per ogni feed nello seed Radar usa tipicamente:

- **Fetch original content** (`crawler: true`) — tranne Hacker News
- **Scraper rules** CSS (es. `article`, `#main-content`, `.storytext`) come in `RSS.txt`
- **User-Agent** browser-like (campo nello seed / per-feed in Miniflux)
- **`enabled`** opzionale (default true) — import synca lo stato `disabled` su Miniflux

Opzionale ma utile: in Miniflux **Settings → Integrations → Webhook** punta a  
`http://radar-backend:8000/api/webhooks/miniflux` con lo stesso secret di `MINIFLUX_WEBHOOK_SECRET`.

Knobs worker: `MINIFLUX_LIMIT` tipico **50** (sotto `MAX_MINIFLUX_RESPONSE_BYTES=5MB`). Se un modello Gemini/Gemma dà HTTP 500 in classificazione, cambia `LLM_*_MODEL` / legacy `GEMINI_MODEL` in `.env` e riavvia solo `radar-worker` — **non** commitare `.env`.

### Backup feed / config (senza articoli vault)

```bash
cd radar
# Dump Postgres + snapshot seed/OPML; vault markdown OMESSO di default
./ops/backup-postgres.sh              # Git Bash / WSL
./ops/backup-postgres.sh --with-vault # solo se serve anche vault/

# Aggiorna i file in config/ da Miniflux live (poi commit)
./ops/sync-miniflux-seed.sh
```

- Output locale (gitignored): `radar/backups/<UTC-stamp>/` con `radar_*.dump`, `miniflux/*.seed.json`, `BACKUP_INFO.txt`
- **Da commitare** dopo sync: `config/miniflux-feeds.seed.json` + `.opml`
- Su un PC nuovo: `.env` → stack up → API key → `./ops/import-miniflux-feeds.sh` (il restore del dump è opzionale e include anche articoli DB)

Dettaglio script: [`radar/ops/README.md`](../radar/ops/README.md).

### Ciclo ingest (worker, non API)

- Servizio `radar-worker` (`python -m app.worker`), leadership via advisory lock
- Webhook/NOTIFY = wake primario; drain-until-empty all’avvio (con sosta settle `WORKER_REFRESH_SETTLE_SECONDS`, default 15s) e post-wake; `WORKER_POLL_INTERVAL_SECONDS` (default **900** = 15 min) = safety net a coda vuota
- Entry **unread** ultime ~48h (`published_after`), dedup URL in PostgreSQL; Miniflux ricontrolla i feed tipicamente ~ogni ora
- Complexity v2.2 → QuotaLedger reserve → classificazione multi-provider (lane SIMPLE / COMPLEX) → eventuale cooldown modello → commit DB + outbox → vault atomico → mark-read Miniflux solo se completed
- Quote durable per lane: `llm_request_ledger` (`LLM_SIMPLE_*` / `LLM_COMPLEX_*`; soft-trim = `LLM_SIMPLE.rpd` se >0; RPM/TPM=attesa stessa lane; RPD/cooldown=`QuotaDailyExceeded` → residual altra lane; free=RPM/RPD(+TPM), paid=budget)
- Requeue ops (re-ingest distruttivo): [runbook](../radar/docs/runbook.md) — preview `docker compose exec -T radar-worker python -m app.scripts.requeue_articles 50 --dry-run`; reale senza `--dry-run`; **prova da zero** `… requeue_articles 100 --purge-all` (wipe vault + DELETE tutte le `articles`) poi `docker compose restart radar-worker`

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
| Articoli bloccati / requeue | [runbook](../radar/docs/runbook.md) — `--dry-run` poi `requeue_articles`; prova da zero `--purge-all` |
| Poche notizie in mappa (~decine vs ~centinaia) | Contare i feed in Miniflux UI (`GET /v1/feeds`); importare lo seed (`./ops/import-miniflux-feeds.sh`) / [RSS.txt](../RSS.txt). Non è un bug FE se Miniflux ha solo 1–2 feed |
| Mappa senza confini | Manca o SHA errato su `countries.geo.json` → `npm run verify-geojson:fetch` |
| Nessun articolo nuovo | `MINIFLUX_API_KEY`, seed importato?, log `radar-worker`, quote lane (`LLM_SIMPLE_RPD` / budget), cooldown; attendere poll 15 min + refresh feed ~1h |
| Payload Miniflux troppo grande / log 5MB | Abbassare `MINIFLUX_LIMIT` (tipico 50); non alzare cieco il cap |
| Classificazione → fallback / HTTP 500 modello | Verificare `LLM_*_MODEL` / legacy `GEMINI_MODEL` in `.env`; riavviare `radar-worker` — **non** commitare `.env` |
| Soft-news → `Tecnologia`/`XX` eccessivo | Prompt + soft-remap in `classification/` (anti-XX, sport→Geopolitica); requeue mirato |
| Solo 2 feed / config “vuota” dopo restore | Il dump Postgres non è il SoT feed: rieseguire `./ops/import-miniflux-feeds.sh` dallo seed in `config/` |
| FONTI / STATUS: **N/N attive · N con errori** (tutti ERR, `no such host`) | DNS Docker/host flaky al poll Miniflux → `parsing_error_count` sticky. Compose: `dns:` su `radar-miniflux` (1.1.1.1/8.8.8.8); `docker compose up -d radar-miniflux radar-worker`; poi `ops/verify_miniflux_egress.py` (refresh + assert `error_count`). Worker skippa `refresh_all_feeds` se DNS canary non pronto. |

Backup/restore e seed Miniflux: [radar/ops/README.md](../radar/ops/README.md) + §6 sopra. Persistenza DB: `radar/data/postgres/` (gitignored); vault: `radar/vault/` (solo `.gitkeep` in Git).
