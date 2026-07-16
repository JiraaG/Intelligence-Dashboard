# Checklist Infra/DB — Radar Informativo Globale

> **Scopo:** consolidamento di requisiti **enforceable** da governance (AGENTS, `.ecc/rules/docker.md`, geo-data-architect, skill docker-ops / geojson-assets).  
> **Non è un audit del codice** — solo inventario regole.  
> **STORICO:** riferimenti «migrazioni 001–007» = snapshot checklist; tree attuale include `008_outbox_miniflux_marked_at.sql`.  
> **Delta skill ECC vs `.agents`:** `radar/.ecc/skills/radar-docker-ops.md` e `radar/.ecc/skills/radar-geojson-assets.md` sono **identici** alle skill `.agents` (nessun delta).

---

## 1. Isolamento di rete (edge vs data)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-NET-01 | `.agents/AGENTS.md` §4.3; `radar/.ecc/rules/docker.md` Regola 3; `.agents/skills/radar-docker-ops/SKILL.md` | Devono esistere due reti bridge: `radar-edge` e `radar-data`. | `radar/docker-compose.yml` → `networks:` | Presenti entrambe con `driver: bridge`. |
| INF-NET-02 | `radar/.ecc/rules/docker.md` Regola 3; AGENTS §4.3 | `radar-frontend` è **solo** su `radar-edge` (mai su `radar-data`). | Compose → service `radar-frontend.networks` | Solo `radar-edge`; nessuna membership a `radar-data`. |
| INF-NET-03 | `radar/.ecc/rules/docker.md` Regola 3 | `radar-backend` è su **entrambe** le reti (`radar-edge` + `radar-data`). | Compose → `radar-backend.networks` | Entrambe le reti elencate. |
| INF-NET-04 | `radar/.ecc/rules/docker.md` Regola 3 | `radar-worker`, `radar-db`, `radar-miniflux` sono **solo** su `radar-data`. | Compose → networks di ciascun servizio | Solo `radar-data`; nessuna membership a `radar-edge`. |
| INF-NET-05 | `radar/.ecc/rules/docker.md` Regola 3 | `radar-data` non deve essere `internal: true` (egress necessario per Gemini / fetch Miniflux). | Compose → `networks.radar-data` | Assente `internal: true` (o documentato come `internal: false`). |
| INF-NET-06 | AGENTS §4.3; `docker.md` principio | Default plug-and-play: frontend pubblica `80:8080` su tutte le interfacce. | Compose → `radar-frontend.ports` | Mapping `80:8080` (o equivalente host:80 → container:8080). |
| INF-NET-07 | AGENTS §4.3; `docker.md` principio | Miniflux **non** pubblica porte host di default. | Compose base (non override) → `radar-miniflux.ports` | Nessuna `ports:` nel compose base; override solo via `docker-compose.lan.yml` / `docker-compose.hardened.yml`. |
| INF-NET-08 | `docker.md` criteri accettazione | Porta PostgreSQL `5432` **non** esposta sull’host. | Compose → `radar-db.ports` | Assente pubblicazione `5432` verso host. |
| INF-NET-09 | AGENTS §4.3 | Loopback hardening / admin Miniflux LAN solo tramite override dedicati. | `docker-compose.hardened.yml`, `docker-compose.lan.yml` | File presenti e usati solo come override (non sostituiscono il default plug-and-play). |
| INF-NET-10 | AGENTS §1; `docker.md` Regola 1 | Nomi servizi immutabili: `radar-db`, `radar-backend`, `radar-worker`, `radar-frontend`, `radar-miniflux`. | `docker-compose.yml` | Esattamente questi cinque nomi servizio (nessun rename silenzioso). |

**Conteggio dominio rete: 10**

---

## 2. Esecuzione non-root

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-USER-01 | `docker.md` Regola 6 + criteri accettazione; AGENTS §3.7 | Backend production image esegue come user non-root (`USER radar`, uid tipico 1000). | `radar/backend/Dockerfile` | Presente `useradd` (o equivalente) + `USER radar` prima di HEALTHCHECK/CMD; nessun processo API come root. |
| INF-USER-02 | `docker.md` Regola 6; backend.md Regola 8 | Worker usa la stessa immagine backend → eredita user non-root; override solo comando (`python -m app.worker`). | Compose `radar-worker` + Dockerfile backend | Nessun `user: root` / `USER root` sul worker; comando override senza elevazione privilegi. |
| INF-USER-03 | `docker.md` criteri accettazione (“Container che gira come root”) | Frontend/Nginx non deve girare come root se evitabile; criterio di sicurezza Compose/Docker. | `radar/frontend/Dockerfile`, Compose | Nessun override esplicito a root; se l’immagine Nginx gira come root di default, documentare eccezione o applicare user unprivileged — **fail** se c’è `USER root` esplicito o capability elevazione non necessaria. |
| INF-USER-04 | AGENTS §3.7; `backend.md` Regola 10 | Logging file-based deve tollerare FS non scrivibile sotto non-root (`try/except` su `makedirs` / `RotatingFileHandler`; console handler obbligatorio). | `backend/app/core/logging.py` | Crash-free se `/app/logs` non scrivibile; console handler sempre attivo. |

**Conteggio dominio non-root: 4**

---

## 3. Healthcheck (Alpine/wget, live vs ready)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-HC-01 | AGENTS §4.4; `docker.md` Regola 4; skill docker-ops | Healthcheck Compose del backend = `GET /health/live` (**non** `/health/ready`). | Compose `radar-backend.healthcheck`; Dockerfile backend HEALTHCHECK | URL contiene `/health/live`; assente `/health/ready` nel test Compose/Dockerfile. |
| INF-HC-02 | AGENTS §4.4 | Readiness (`/health/ready`: pool, migrazioni, heartbeat) è ops-only e **non** deve far restartare l’API via Compose health. | Compose depends_on / healthcheck | Solo `live` usato per `depends_on`/`service_healthy` dell’API. |
| INF-HC-03 | AGENTS §4.4; `docker.md` Regola 4 | Frontend `depends_on` backend con condizione healthy (= live). | Compose `radar-frontend.depends_on` | `radar-backend` con `condition: service_healthy`. |
| INF-HC-04 | AGENTS §4.4; `docker.md` Regola 4 | Worker attende `radar-db` + `radar-miniflux` healthy. | Compose `radar-worker.depends_on` | Entrambi con `condition: service_healthy`. |
| INF-HC-05 | `docker.md` Regola 4 | Miniflux healthcheck: `["CMD", "/usr/bin/miniflux", "-healthcheck", "auto"]`. | Compose `radar-miniflux.healthcheck` | Comando esatto (o equivalente ufficiale documentato). |
| INF-HC-06 | AGENTS §4.10; `docker.md` Regola 4; skill docker-ops | Su immagini **Alpine** (Nginx frontend) usare `wget`, **non** `curl`. | Dockerfile frontend HEALTHCHECK; Compose FE healthcheck | `wget` presente; assente `curl` negli healthcheck Alpine. |
| INF-HC-07 | `docker.md` Regola 6 | Backend (Debian slim) può usare `curl` su `/health/live`; pacchetto `curl` installato nell’immagine production. | Dockerfile backend | `curl` installato + HEALTHCHECK con `curl -f .../health/live`. |
| INF-HC-08 | `docker.md` Regola 4 (esempio FE) | Frontend healthcheck tipico: `wget -qO-` su porta 8080 (`/` o `/health` secondo config reale). | Dockerfile/Compose FE | Healthcheck usa wget verso `127.0.0.1`/`localhost:8080`; interval/timeout/retries coerenti. |
| INF-HC-09 | `docker.md` criteri accettazione | `depends_on` senza healthcheck correlato è vietato dove richiesto (race all’avvio). | Compose depends_on di backend/worker/frontend | Dipendenze critiche usano `service_healthy`, non solo start order. |

**Conteggio dominio healthcheck: 9**

---

## 4. Volume PostgreSQL

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-VOL-01 | AGENTS §4.2; `docker.md` Regola 2; skill docker-ops | Persistenza DB = bind-mount host `./data/postgres:/var/lib/postgresql/data`. | Compose `radar-db.volumes` | Path esatto (o equivalente relativo da root compose) verso `/var/lib/postgresql/data`. |
| INF-VOL-02 | `docker.md` Regola 2 | Vietato volume anonimo solo-container senza path host. | Compose | Assente pattern `- /var/lib/postgresql/data` senza bind host. |
| INF-VOL-03 | `docker.md` Regola 2 | Vietato named volume + `driver_opts` bind indiretto come schema Compose attuale. | Compose `volumes:` top-level | Nessun named volume `radar-postgres-data` (o simile) al posto del bind `./data/postgres`, salvo eccezione **documentata**. |

**Conteggio dominio volume Postgres: 3**

---

## 5. Tag immagini e digest pin

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-IMG-01 | AGENTS §4.9; `docker.md`; skill docker-ops | Vietato tag `:latest` su immagini base in Compose e Dockerfile. | `docker-compose.yml`, tutti i Dockerfile, override | Nessuna occorrenza di `:latest`. |
| INF-IMG-02 | `docker.md` Regola 1 | Pin versioni note: es. `postgres:15-alpine`, `miniflux/miniflux:2.3.2`, `python:3.12-slim`, `node:22-alpine`, `nginx:1.27-alpine` (o pin equivalenti documentati). | Compose + Dockerfile | Ogni immagine ha major/minor (o patch) esplicita. |
| INF-IMG-03 | AGENTS §4.9; `docker.md` Phase 6 note; skill docker-ops Deferred | Digest pin SHA immagini = **deferred post–Phase 6** (opzionale prodotto; non richiesto per ready-to-run). | Checklist prodotto / runbook | Assenza di digest **non** è fail; presenza di digest è accettabile. Non inventare come requisito obbligatorio già attivo. |

**Conteggio dominio immagini: 3**

---

## 6. Build frontend — `npm ci` e multi-stage

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-NPM-01 | AGENTS §4.8; `docker.md` Regola 7; skill docker-ops | Nello stage builder: `npm ci --legacy-peer-deps` (**vietato** `npm install`). | `radar/frontend/Dockerfile` | Comando `npm ci --legacy-peer-deps`; assente `npm install`. |
| INF-NPM-02 | AGENTS §4.8; skill docker-ops Deferred | Drop di `--legacy-peer-deps` = **deferred** finché matrix Angular/CDK/PrimeNG non allineata. | Dockerfile + note Phase 6 | Presenza di `--legacy-peer-deps` è **pass** oggi; rimozione senza allineamento matrix = fail di processo. |
| INF-NPM-03 | AGENTS §4.6; `docker.md` Regola 7 | Dockerfile FE multi-stage: builder Node → production Nginx; solo `dist/` copiato; zero Node richiesto sull’host utente. | Dockerfile FE | ≥2 stage; stage finale basato su Nginx; `COPY --from=builder` di `dist/...`. |
| INF-NPM-04 | `docker.md` criteri accettazione | Build Angular di produzione (`--configuration=production` / script `build` di produzione). | Dockerfile FE `npm run build` / `angular.json` | Bundle production (non solo development). |

**Conteggio dominio npm/build FE: 4**

---

## 7. GeoJSON assets

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-GEO-01 | skill `radar-geojson-assets`; AGENTS §4.13 | `countries.geo.json` (o equivalente) è **gitignored** — non committare dump enormi. | `.gitignore`, git status sotto `frontend/src/assets/data/` | Pattern ignore presente; file pesante non tracciato. |
| INF-GEO-02 | skill geojson; `docker.md` Regola 7; skill docker-ops | Build Docker **deve** eseguire `node scripts/verify-geojson.mjs --fetch` **prima** di `npm run build`. | `radar/frontend/Dockerfile` | Ordine: verify `--fetch` → poi build; comando non omesso. |
| INF-GEO-03 | skill geojson; script verify | Pin/licenza da `ASSET_LICENSE` (SoT: `src/assets/data/ASSET_LICENSE.md` con SHA-256 pinnato). | `ASSET_LICENSE.md`, `verify-geojson.mjs` | Script legge pin da ASSET_LICENSE; verify fallisce se SHA non matcha. |
| INF-GEO-04 | skill geojson | Vietato scaricare GeoJSON da CDN arbitrarie **a runtime** nel browser/componente mappa. | FE map components / services | Solo asset locale sotto `frontend/src/assets/data/`. |
| INF-GEO-05 | skill geojson Anti-pattern | Vietato saltare verify in CI/Docker “per velocità”. | Dockerfile FE; `.github/workflows/ci.yml` | Verify presente in path build/CI documentato. |
| INF-GEO-06 | AGENTS §4.13 | Script e runbook: `radar/frontend/scripts/verify-geojson.mjs`; runbook `radar/docs/runbook.md`. | Path file | File script e runbook esistono e sono referenziati. |

**Conteggio dominio GeoJSON: 6**

---

## 8. Entrypoint / CMD module path

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-CMD-01 | `docker.md` Regola 6; `backend.md` Regola 8 | API: `uvicorn app.main:app` (**non** `main:app`). | Dockerfile backend `CMD`; Compose command | Modulo `app.main:app`; assente `main:app` senza package. |
| INF-CMD-02 | `docker.md` Regola 6; `backend.md` Regola 8 | Worker Compose override: `python -m app.worker` (ingest solo nel worker). | Compose `radar-worker.command` | Comando `python -m app.worker`; ingest assente dal lifespan API. |
| INF-CMD-03 | `docker.md` Regola 6 | Backend: `WORKDIR=/app`, `PYTHONPATH=/app`, expose `8000`, workers uvicorn `1`. | Dockerfile backend | ENV/WORKDIR/EXPOSE/CMD allineati. |
| INF-CMD-04 | AGENTS §1; `docker.md` | Ingestione **solo** in `radar-worker`, non nel processo API. | `main.py` vs `worker.py`; Compose | API API-only; worker esegue pipeline. |

**Conteggio dominio CMD/entrypoint: 4**

---

## 9. Indici DB obbligatori e schema

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-IDX-01 | `geo-data-architect.md` Indici obbligatori | `idx_articles_published_at` su `articles (published_at DESC)`. | `backend/migrations/*.sql` (tipicamente 001) + `\d` in DB | Indice presente in migrazioni e applicato. |
| INF-IDX-02 | `geo-data-architect.md` | `idx_articles_geo_date` su `(published_at, latitude, longitude)`. | Migrazioni SQL | Indice definito con `CREATE INDEX IF NOT EXISTS`. |
| INF-IDX-03 | `geo-data-architect.md` | `idx_articles_country_date` su `(country_code, published_at DESC)`. | Migrazioni SQL | Indice presente. |
| INF-IDX-04 | `geo-data-architect.md` | `idx_articles_category` su `(primary_category, published_at DESC)`. | Migrazioni SQL | Indice presente. |
| INF-IDX-05 | `geo-data-architect.md`; `backend.md` Phase 5 | Migrazione `007_articles_query_indexes.sql` con indici keyset/map-summary: `idx_articles_published_id (published_at DESC, id DESC)` e `idx_articles_pub_country_cat (published_at, country_code, primary_category)`. | `007_articles_query_indexes.sql` | Entrambi gli indici presenti. |
| INF-IDX-06 | `geo-data-architect.md` criteri | `articles.source_url` deve avere vincolo **UNIQUE**. | `001_initial.sql` / schema | UNIQUE su `source_url`. |
| INF-IDX-07 | `geo-data-architect.md` | Junction tables `article_companies` e `article_tags` (niente M:N senza junction). | Migrazioni 001+ | Tabelle junction con PK composta e FK CASCADE. |
| INF-IDX-08 | `geo-data-architect.md`; AGENTS §2 | Accesso DB solo via **asyncpg** puro (no SQLAlchemy/ORM). | `backend/app/**`, requirements | Nessun ORM; SQL async asyncpg. |
| INF-IDX-09 | `geo-data-architect.md` | Schema SoT = file in `backend/migrations/`; vietato DDL ad-hoc solo in bootstrap Python. | `core/migrations.py`, `core/database.py` | `bootstrap_database()` → `run_migrations()`; no `CREATE TABLE` sparsi nel bootstrap. |

**Conteggio dominio indici/schema: 9**

---

## 10. Credenziali DB e connection string (URL-encoding)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-CRED-01 | AGENTS §4.5; `docker.md` Regola 5 | Credenziali reali solo in `.env` (gitignored); Compose usa `env_file` + `${VAR}` — **vietato** hardcode secret in compose. | `.env`, `.gitignore`, `docker-compose.yml` | Nessuna password/API key in chiaro nel compose committed. |
| INF-CRED-02 | AGENTS §4.5; `docker.md` Warning | Vietato carattere `$` nei valori password (Compose interpolazione). Usare alfanumerici, `-`, `_`. | `.env` / `.env.example` docs | Nessun `$` non escapato in password; doc allineata. |
| INF-CRED-03 | `docker.md` Regola 5 | `DATABASE_URL` costruita da variabili (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) verso host `radar-db:5432`. | Compose environment backend/worker | Pattern `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}` (o equivalente sicuro). |
| INF-CRED-04 | Dominio audit richiesto; implicito da parsing URL asyncpg / costruzione `DATABASE_URL` | Username e password in connection string devono essere **URL-encoded** (percent-encoding; es. `urllib.parse.quote_plus`) se contengono `@`, `:`, `/`, `#`, ecc. | `backend/app/core/config.py` (fallback URL); eventuali builder Compose/docs | Credenziali speciali non spezzano il parser asyncpg; encoding applicato prima dell’interpolazione. |
| INF-CRED-05 | AGENTS §4.11 | CORS: allowlist default vuota (same-origin via Nginx); mai `allow_origins=["*"]`. | `config.py` / CORS setup; `.env.example` | Default vuoto; wildcard assente in prod. |

**Conteggio dominio credenziali/URL: 5**

---

## 11. Nginx (SPA, security headers, listen, DNS dinamico)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-NGX-01 | `docker.md` Regola 8 | `listen 8080;` — porta HTTP container. | `radar/frontend/nginx.conf` | `listen 8080` (o 8080 default conf.d). |
| INF-NGX-02 | `docker.md` Regola 8 | SPA fallback: `try_files $uri $uri/ /index.html;`. | `nginx.conf` `location /` | Presente try_files verso `index.html`. |
| INF-NGX-03 | AGENTS §4.7; `docker.md` Regola 8; skill docker-ops | DNS dinamico anti-502: `resolver 127.0.0.11 valid=10s;` + variabile `$backend_upstream` + `proxy_pass $backend_upstream$request_uri`. | `nginx.conf` `location /api/` | Resolver + `set $backend_upstream` + `$request_uri`; **vietato** proxy_pass statico solo-resolve-at-start. |
| INF-NGX-04 | `docker.md` Regola 8; criteri accettazione | Proxy `/api/` verso `http://radar-backend:8000`. | `nginx.conf` | Location `/api/` con proxy headers Host/X-Real-IP/X-Forwarded-*. |
| INF-NGX-05 | `docker.md` Regola 8 | Security headers: `X-Frame-Options SAMEORIGIN`, `X-Content-Type-Options nosniff`, `Referrer-Policy strict-origin-when-cross-origin`; **no** `X-XSS-Protection` (obsoleto); CSP per Angular + Carto + Google Fonts. | `nginx.conf` | Headers richiesti con `always`; CSP presente; assente X-XSS-Protection. |
| INF-NGX-06 | `docker.md` Regola 8 | Gzip on per tipi testo/css/json/js; `gzip_min_length 1000`. | `nginx.conf` | Direttive gzip presenti. |
| INF-NGX-07 | `docker.md` Regola 8 | Cache assets statici (`expires 7d`); `index.html` con `Cache-Control: no-cache, no-store, must-revalidate`. | `nginx.conf` | Location static + `location = /index.html` corretti. |
| INF-NGX-08 | `docker.md` Regola 7 | Rimuovere default conf Nginx; copiare `nginx.conf` custom in conf.d. | Dockerfile FE | `rm .../default.conf` + `COPY nginx.conf`. |

**Conteggio dominio Nginx: 8**

---

## 12. Inventario migrazioni 001→007

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-MIG-01 | `geo-data-architect.md` | Deve esistere `001_initial.sql`. | `radar/backend/migrations/` | File presente. |
| INF-MIG-02 | `geo-data-architect.md` | Deve esistere `002_pipeline_outbox_and_quotas.sql` (`article_outbox`). | migrations/ | File presente; definisce outbox. |
| INF-MIG-03 | `geo-data-architect.md` | Deve esistere `003_quota_ledger.sql`. | migrations/ | File presente. |
| INF-MIG-04 | `geo-data-architect.md` | Deve esistere `004_worker_heartbeat.sql`. | migrations/ | File presente. |
| INF-MIG-05 | `geo-data-architect.md` | Deve esistere `005_quota_ledger_align.sql`. | migrations/ | File presente. |
| INF-MIG-06 | `geo-data-architect.md` | Deve esistere `006_quota_ledger_legacy_nulls.sql`. | migrations/ | File presente. |
| INF-MIG-07 | `geo-data-architect.md`; `backend.md` | Deve esistere `007_articles_query_indexes.sql` (indici Phase 5). | migrations/ | File presente con indici keyset/map-summary. |
| INF-MIG-08 | `geo-data-architect.md` | Runner: tabella `schema_migrations` + checksum SHA-256; nuove modifiche solo con nuovo file numerato. | `core/migrations.py` | Applicazione ordinata; checksum; no edit silenzioso di SQL già applicati senza nuova migrazione. |
| INF-MIG-09 | `geo-data-architect.md` criteri | Vietato `DROP TABLE`/`TRUNCATE` senza `IF EXISTS` e senza commento di migrazione. | Nuove migrazioni SQL | Pattern sicuro rispettato. |

**Conteggio dominio migrazioni: 9**

---

## 13. Altre regole infra hard

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| INF-OTH-01 | AGENTS §4.5; `docker.md` Regola 9 | `.dockerignore` obbligatorio per backend e frontend (`node_modules`, `.venv`, `.angular`, cache, `.env`, ecc.). | `radar/backend/.dockerignore`, `radar/frontend/.dockerignore` | Entrambi presenti con esclusioni pesanti. |
| INF-OTH-02 | AGENTS §2; vault path | Fallback vault Obsidian = `/app/vault`. | `config.py` / env default; Compose volumes vault | Default path `/app/vault`. |
| INF-OTH-03 | AGENTS §6 | Vault git: tracciare solo `.gitkeep`; `vault/*` + `!vault/.gitkeep` in `.gitignore`. | `.gitignore` | Pattern vault corretto; nessun dump `.md` vault committed intenzionalmente. |
| INF-OTH-04 | AGENTS §4.12 | Ops backup/restore in `radar/ops/`; vedi `ops/README.md`. | `radar/ops/` | Directory e README presenti. |
| INF-OTH-05 | AGENTS §4.13 | Phase 6: CI `.github/workflows/ci.yml` + runbook `radar/docs/runbook.md`. | Path CI/docs | Workflow e runbook esistono. |
| INF-OTH-06 | `docker.md` Regola 1 | Immagini/ruoli: db=`postgres:15-alpine`; backend=Python 3.12 custom; worker=stessa immagine; FE=Node+Nginx; miniflux pin `2.3.2`. | Compose | Allineamento ruoli/immagini. |
| INF-OTH-07 | AGENTS §1 stack | DB ufficiale: PostgreSQL **15** (`radar-db`); driver asyncpg. | Compose image tag; codice | `postgres:15-*`; asyncpg in uso. |
| INF-OTH-08 | `geo-data-architect.md` AVVISA | Non assumere rete unica legacy `radar-network` né solo `/health` aggregato (Phase 3 = edge/data + live/ready). | Compose + health endpoints | Nessun ritorno a `radar-network` unica; endpoint live/ready distinti. |
| INF-OTH-09 | Implementation_Plan / docker.md Deferred | Non trattare come DONE: digest SHA obbligatorio; drop `--legacy-peer-deps`. | Docs/checklist audit | Marcati deferred, non fail di conformità ready-to-run. |

**Conteggio dominio altre regole: 9**

---

## Riepilogo conteggi per dominio

| Dominio | Prefisso ID | N. item |
|---------|-------------|---------|
| 1. Isolamento rete | INF-NET-* | **10** |
| 2. Non-root | INF-USER-* | **4** |
| 3. Healthcheck | INF-HC-* | **9** |
| 4. Volume Postgres | INF-VOL-* | **3** |
| 5. Tag/digest immagini | INF-IMG-* | **3** |
| 6. npm ci / multi-stage FE | INF-NPM-* | **4** |
| 7. GeoJSON | INF-GEO-* | **6** |
| 8. CMD / entrypoint | INF-CMD-* | **4** |
| 9. Indici / schema DB | INF-IDX-* | **9** |
| 10. Credenziali / URL-encoding | INF-CRED-* | **5** |
| 11. Nginx | INF-NGX-* | **8** |
| 12. Migrazioni 001→007 | INF-MIG-* | **9** |
| 13. Altre regole infra | INF-OTH-* | **9** |
| **TOTALE** | | **83** |

---

## Fonti consultate

1. `.agents/AGENTS.md` (sezioni stack, §4 Docker, vault, CORS, logging non-root)
2. `radar/.ecc/rules/docker.md` (SoT containerizzazione)
3. `radar/.ecc/agents/geo-data-architect.md` (schema, indici, migrazioni 001–008)
4. `.agents/skills/radar-docker-ops/SKILL.md`
5. `.agents/skills/radar-geojson-assets/SKILL.md`
6. Skim: `radar/.ecc/skills/radar-docker-ops.md` + `radar/.ecc/skills/radar-geojson-assets.md` → **nessun delta**
7. Cross-ref supportiva: `radar/.ecc/rules/backend.md` (entrypoint `app.main:app`, migrazione 007, logging non-root)
