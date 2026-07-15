# Audit Infra/DB — Radar Informativo Globale

**Data:** 2026-07-15  
**Checklist:** `scratch/infra_rules.md` (83 item)  
**Scope:** Compose (+ override), Dockerfile backend/frontend, `nginx.conf`, migrazioni `001`–`007`, `.dockerignore`, GeoJSON verify, `config.py`, logging, CI/runbook/ops correlati.  
**Metodo:** walk checklist → pass/fail con evidenza; solo FAIL in sezione Findings.

---

## Riepilogo esecutivo

| Metrica | Valore |
|---------|--------|
| Item checklist | 83 |
| PASS | 81 |
| FAIL | 2 |
| **P0** | **0** |
| **P1** | **1** |
| **P2** | **1** |
| Digest pin / drop `--legacy-peer-deps` | Deferred (non-fail, INF-IMG-03 / INF-OTH-09) |

Stack Compose allineato a edge/data, indici obbligatori presenti, GeoJSON fetch+verify in build, CMD `app.main:app`, volume `./data/postgres`, niente `:latest`. Unici gap: **URL-encoding credenziali** (P1) e **Nginx ancora root** senza user unprivileged documentato (P2).

---

## Inventario servizi / reti / volume (osservato)

| Servizio | Image / build | Networks | Ports host | USER / note | Healthcheck |
|----------|---------------|----------|------------|-------------|-------------|
| `radar-db` | `postgres:15-alpine` | `radar-data` | nessuna | (immagine postgres) | `pg_isready` |
| `radar-backend` | build `backend` → `production` | `radar-edge` + `radar-data` | nessuna | `USER radar` (uid 1000) | `curl …/health/live` |
| `radar-worker` | stessa immagine backend | `radar-data` | nessuna | eredita `radar`; `command: python -m app.worker` | `disable: true` |
| `radar-frontend` | build `frontend` → `production` | `radar-edge` | `80:80` | Nginx default **root** (no `USER`) | Compose: `wget …/health` |
| `radar-miniflux` | `miniflux/miniflux:2.3.2` | `radar-data` | nessuna (base) | n/a | `miniflux -healthcheck auto` |

**Override:** `docker-compose.hardened.yml` (FE `127.0.0.1:80`, Miniflux `127.0.0.1:8080`); `docker-compose.lan.yml` (Miniflux `8080:8080`).

**Volume DB:** `./data/postgres:/var/lib/postgresql/data` (bind-mount; nessun named volume).

**Networks:** `radar-edge` + `radar-data`, entrambe `driver: bridge`; `radar-data` senza `internal: true`.

---

## Pass/fail per dominio

| Dominio | Prefisso | N | PASS | FAIL | Note |
|---------|----------|---|------|------|------|
| Isolamento rete | INF-NET-* | 10 | 10 | 0 | edge/data + nomi immutabili OK |
| Non-root | INF-USER-* | 4 | 3 | 1 | FAIL: INF-USER-03 (Nginx root) |
| Healthcheck | INF-HC-* | 9 | 9 | 0 | live vs ready rispettato; wget FE / curl BE |
| Volume Postgres | INF-VOL-* | 3 | 3 | 0 | bind `./data/postgres` |
| Tag/digest | INF-IMG-* | 3 | 3 | 0 | no `:latest`; digest deferred |
| npm / multi-stage FE | INF-NPM-* | 4 | 4 | 0 | `npm ci --legacy-peer-deps`; prod default |
| GeoJSON | INF-GEO-* | 6 | 6 | 0 | gitignore + verify `--fetch` pre-build + CI |
| CMD / entrypoint | INF-CMD-* | 4 | 4 | 0 | `app.main:app`; worker `python -m app.worker` |
| Indici / schema | INF-IDX-* | 9 | 9 | 0 | 001+007 + UNIQUE + junction + asyncpg |
| Credenziali / URL | INF-CRED-* | 5 | 4 | 1 | FAIL: INF-CRED-04 (no quote_plus) |
| Nginx | INF-NGX-* | 8 | 8 | 0 | listen 80, SPA, resolver dinamico, headers |
| Migrazioni 001–007 | INF-MIG-* | 9 | 9 | 0 | file presenti; runner checksum |
| Altre regole | INF-OTH-* | 9 | 9 | 0 | dockerignore, vault, ops, CI, runbook |
| **TOTALE** | | **83** | **81** | **2** | |

---

## Inventario indici (migrazioni)

| Indice / vincolo | Migrazione | Definizione | Checklist |
|------------------|------------|-------------|-----------|
| `articles.source_url` UNIQUE | `001_initial.sql` L9 | `source_url TEXT NOT NULL UNIQUE` | INF-IDX-06 |
| `idx_articles_published_at` | `001` L58 | `(published_at DESC)` | INF-IDX-01 |
| `idx_articles_geo_date` | `001` L59 | `(published_at, latitude, longitude)` | INF-IDX-02 |
| `idx_articles_country_date` | `001` L60 | `(country_code, published_at DESC)` | INF-IDX-03 |
| `idx_articles_category` | `001` L61 | `(primary_category, published_at DESC)` | INF-IDX-04 |
| `idx_articles_published_id` | `007` L3 | `(published_at DESC, id DESC)` | INF-IDX-05 |
| `idx_articles_pub_country_cat` | `007` L4 | `(published_at, country_code, primary_category)` | INF-IDX-05 |
| Junction `article_companies` | `001` L46–50 | PK composta + FK CASCADE | INF-IDX-07 |
| Junction `article_tags` | `001` L52–56 | PK composta + FK CASCADE | INF-IDX-07 |
| `idx_article_outbox_status` | `002` | outbox status | (pipeline) |
| `idx_article_outbox_miniflux_entry` | `002` | Miniflux entry | (pipeline) |
| `idx_llm_request_ledger_created_at` | `003` / `005` | ledger | (quota) |
| `idx_llm_request_ledger_created_status` | `003` / `005` | ledger | (quota) |

**File migrazioni:** `001_initial` … `007_articles_query_indexes` tutti presenti (INF-MIG-01…07). Runner: `schema_migrations` + SHA-256 in `core/migrations.py` (INF-MIG-08). `004` fa `DROP TABLE worker_heartbeat` solo dentro `DO $$` dopo check esistenza + commento legacy (INF-MIG-09 OK).

---

## Evidenza sintetica PASS (per dominio)

### 1. Rete (INF-NET-01…10) — PASS

```237:244:radar/docker-compose.yml
networks:
  radar-edge:
    driver: bridge
    name: radar-edge
  radar-data:
    driver: bridge
    name: radar-data
    # internal: false (default) — backend/worker need egress for Gemini / Miniflux fetch
```

- FE solo `radar-edge` (L165–166); backend entrambe (L84–86); worker/db/miniflux solo `radar-data`.
- FE ports `"80:80"` (L159–161); Miniflux senza `ports` nel base; DB senza `5432` host.
- Override `hardened` / `lan` presenti; nomi servizio esatti.

### 2. Non-root (INF-USER-01/02/04) — PASS; INF-USER-03 — FAIL (sotto)

```28:45:radar/backend/Dockerfile
RUN useradd -m -u 1000 -s /bin/sh radar
...
USER radar
```

Worker: nessun `user: root`; `command: ["python", "-m", "app.worker"]`.  
Logging: `try/except OSError` su `makedirs`/`RotatingFileHandler` + console sempre attivo (`logging.py` L29–54).

### 3. Healthcheck (INF-HC-01…09) — PASS

- Backend Compose + Dockerfile: `curl …/health/live` (non ready).
- FE `depends_on` backend `service_healthy`; worker `radar-db` + `radar-miniflux` healthy.
- Miniflux: `["CMD", "/usr/bin/miniflux", "-healthcheck", "auto"]`.
- FE Alpine: `wget` (Compose L168; Dockerfile L28–29); assente `curl` negli HC Alpine.
- Backend Debian: `curl` installato (Dockerfile L25) + HC curl.

### 4–6. Volume / immagini / npm — PASS

- Volume: `./data/postgres:/var/lib/postgresql/data` (compose L33–34).
- Tag pinnati; **nessun** `:latest` sotto `radar/`. Digest = deferred.
- FE: `npm ci --legacy-peer-deps`; multi-stage Node→Nginx; `COPY --from=builder …/dist/…`; `angular.json` `defaultConfiguration: production`.

### 7. GeoJSON — PASS

- `.gitignore` L47 ignora `countries.geo.json`; `ASSET_LICENSE.md` whitelisted.
- Dockerfile FE: `node scripts/verify-geojson.mjs --fetch` **prima** di `npm run build`.
- Script legge SHA da `ASSET_LICENSE.md`; map carica `assets/data/countries.geo.json` (no CDN GeoJSON).
- CI: `.github/workflows/ci.yml` esegue `verify-geojson:fetch`; runbook + script path OK.

### 8. CMD — PASS

```55:55:radar/backend/Dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

`WORKDIR=/app`, `PYTHONPATH=/app`, `EXPOSE 8000`. API-only in `main.py`; ingest in worker.

### 9–10. Schema / credenziali (parziale)

Indici/UNIQUE/junction/asyncpg/bootstrap→`run_migrations` OK.  
Segreti via `env_file` + `${VAR}`; `.env.example` vieta `$` in password; CORS default vuoto + reject `*`.  
**FAIL URL-encoding:** vedi Findings.

### 11. Nginx — PASS

`listen 80`; `try_files … /index.html`; `resolver 127.0.0.11` + `$backend_upstream` + `$request_uri`; proxy headers; security headers + CSP; no `X-XSS-Protection`; gzip + `gzip_min_length 1000`; cache static 7d + `index.html` no-cache; Dockerfile `rm default.conf` + `COPY nginx.conf`.

### 12–13. Migrazioni / altre — PASS

`.dockerignore` backend+frontend; vault `/app/vault`; `vault/*` + `!vault/.gitkeep`; `radar/ops/` + README; CI + runbook; immagini ruoli allineati; no `radar-network` legacy.

---

## Findings (FAIL)

### [INF-AUD-01] DATABASE_URL senza URL-encoding delle credenziali
- **Priorità:** P1
- **Checklist:** INF-CRED-04
- **File e Range Righe:** `radar/backend/app/core/config.py#L91-L98`; `radar/docker-compose.yml#L76-L77` (e L122 worker); `radar/docker-compose.yml#L205` (Miniflux)
- **Casistica Rilevata & Rischio:** Username/password vengono interpolati grezzi nella connection string. Caratteri riservati URL (`@`, `:`, `/`, `#`, `%`, spazi, ecc.) spezzano il parser asyncpg / URL Miniflux → pool init fallisce o autenticazione errata. In Docker il path dominante è Compose `DATABASE_URL` (bypassa il fallback Python); anche il fallback locale in `config.py` non usa `urllib.parse.quote_plus`. La policy “niente `$`” (INF-CRED-02) non copre gli altri caratteri speciali.
- **Evidenza (snippet attuale):**
```python
pg_user = _env_str("POSTGRES_USER", "radar_user") or "radar_user"
pg_pass = _env_str("POSTGRES_PASSWORD", _DEFAULT_PG_PASSWORD) or _DEFAULT_PG_PASSWORD
pg_db = _env_str("POSTGRES_DB", "radar_db") or "radar_db"
pg_host = _env_str("POSTGRES_HOST", "localhost") or "localhost"
pg_port = _env_str("POSTGRES_PORT", "5432") or "5432"
_default_db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"

DATABASE_URL = _env_str("DATABASE_URL", _default_db_url) or _default_db_url
```
```yaml
DATABASE_URL: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}"
```
- **Codice Correttivo (Diff):**
```diff
--- a/radar/backend/app/core/config.py
+++ b/radar/backend/app/core/config.py
@@ -6,6 +6,7 @@ from __future__ import annotations
 import os
 from datetime import timezone as dt_timezone
 from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
+from urllib.parse import quote_plus
 
 from dotenv import load_dotenv
@@ -93,7 +94,10 @@ pg_user = _env_str("POSTGRES_USER", "radar_user") or "radar_user"
 pg_pass = _env_str("POSTGRES_PASSWORD", _DEFAULT_PG_PASSWORD) or _DEFAULT_PG_PASSWORD
 pg_db = _env_str("POSTGRES_DB", "radar_db") or "radar_db"
 pg_host = _env_str("POSTGRES_HOST", "localhost") or "localhost"
 pg_port = _env_str("POSTGRES_PORT", "5432") or "5432"
-_default_db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
+_default_db_url = (
+    f"postgresql://{quote_plus(pg_user)}:{quote_plus(pg_pass)}"
+    f"@{pg_host}:{pg_port}/{pg_db}"
+)
 
 DATABASE_URL = _env_str("DATABASE_URL", _default_db_url) or _default_db_url
```
```diff
--- a/radar/.env.example
+++ b/radar/.env.example
@@ -101,9 +101,12 @@ WORKER_ADVISORY_LOCK_BACKOFF_SECONDS=5
 # ─── PostgreSQL Database ──────────────────────────────────────────────────────
 POSTGRES_USER=radar_user
 # Dev ready-to-run default (change in production). No `$` in passwords (Compose interpolation).
+# Prefer alphanumerics, `-`, `_`. If password contains @ : / # % etc., either URL-encode
+# them in DATABASE_URL or omit DATABASE_URL and let config.py build it with quote_plus.
 POSTGRES_PASSWORD=radar_dev_password
 POSTGRES_DB=radar_db
-# DATABASE_URL è costruito automaticamente da docker-compose con le variabili sopra.
+# Prefer: leave DATABASE_URL unset in .env so backend/worker rebuild with quote_plus,
+# OR set an already-encoded URL. Compose interpolation does NOT percent-encode.
 # In sviluppo locale (fuori Docker), puoi impostarlo manualmente:
 # DATABASE_URL=postgresql://radar_user:TUA_PASSWORD@localhost:5432/radar_db
-DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}
+# DATABASE_URL=
```
```diff
--- a/radar/docker-compose.yml
+++ b/radar/docker-compose.yml
@@ -73,8 +73,10 @@ services:
     env_file:
       - .env
     environment:
-      # DATABASE_URL combines vars; $ in passwords must be escaped as $$ in Compose.
-      DATABASE_URL: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}"
+      # Prefer app-built URL (quote_plus). Only set DATABASE_URL in .env if pre-encoded.
+      # Fallback if unset: config.py builds from POSTGRES_* with URL-encoding.
+      POSTGRES_HOST: radar-db
+      POSTGRES_PORT: "5432"
       OBSIDIAN_VAULT_PATH: "/app/vault"
```
*(Applicare lo stesso `POSTGRES_HOST`/`PORT` al servizio `radar-worker`. Per Miniflux, che non usa `config.py`, documentare password alfanumeriche oppure un entrypoint/`DATABASE_URL` già percent-encoded.)*

---

### [INF-AUD-02] Frontend Nginx gira come root (nessun USER unprivileged)
- **Priorità:** P2
- **Checklist:** INF-USER-03
- **File e Range Righe:** `radar/frontend/Dockerfile#L16-L34`; `radar/docker-compose.yml#L174-L182`
- **Casistica Rilevata & Rischio:** Lo stage `production` basato su `nginx:1.27-alpine` non dichiara `USER` non-root e non documenta l’eccezione richiesta dalla checklist. Il master process resta root. Compose fa `cap_drop: ALL` poi `cap_add` (CHOWN/SETGID/SETUID/NET_BIND_SERVICE): con processo root, `NET_BIND_SERVICE` è ridondante; superficie privilegiata più ampia del necessario se un RCE colpisse Nginx.
- **Evidenza (snippet attuale):**
```dockerfile
FROM nginx:1.27-alpine AS production
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/radar-frontend/browser /usr/share/nginx/html
HEALTHCHECK ...
CMD ["nginx", "-g", "daemon off;"]
```
```yaml
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
      - NET_BIND_SERVICE
```
- **Codice Correttivo (Diff):**
```diff
--- a/radar/frontend/Dockerfile
+++ b/radar/frontend/Dockerfile
@@ -16,18 +16,28 @@ RUN npm run build
 FROM nginx:1.27-alpine AS production
 
 RUN rm /etc/nginx/conf.d/default.conf
+
+# Unprivileged Nginx: listen on 8080 inside container; compose maps host 80→8080
+# OR keep listen 80 with NET_BIND_SERVICE + USER nginx after fixing pid/cache paths.
 COPY nginx.conf /etc/nginx/conf.d/default.conf
 COPY --from=builder /app/dist/radar-frontend/browser /usr/share/nginx/html
+
+RUN chown -R nginx:nginx /usr/share/nginx/html \
+    && mkdir -p /var/cache/nginx /var/run \
+    && chown -R nginx:nginx /var/cache/nginx /var/run
+
+USER nginx
 
 HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
-    CMD wget -qO- http://localhost:80/ || exit 1
+    CMD wget -qO- http://127.0.0.1:8080/health || exit 1
 
-EXPOSE 80
+EXPOSE 8080
 
 CMD ["nginx", "-g", "daemon off;"]
```
```diff
--- a/radar/frontend/nginx.conf
+++ b/radar/frontend/nginx.conf
@@ -1,5 +1,5 @@
 server {
-    listen 80;
+    listen 8080;
     server_name localhost;
```
```diff
--- a/radar/docker-compose.yml
+++ b/radar/docker-compose.yml
@@ -157,8 +157,8 @@ services:
     restart: unless-stopped
     ports:
-      # Plug-and-play: all interfaces. Loopback-only → docker-compose.hardened.yml
-      - "80:80"
+      # Host 80 → container 8080 (nginx unprivileged)
+      - "80:8080"
     ...
     healthcheck:
-      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:80/health"]
+      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:8080/health"]
     ...
     cap_drop:
       - ALL
-    cap_add:
-      - CHOWN
-      - SETGID
-      - SETUID
-      - NET_BIND_SERVICE
+    # No cap_add needed if listening on 8080 as USER nginx
```
*(Allineare anche `docker-compose.hardened.yml` mapping `127.0.0.1:80:8080`. Alternativa minima P2: lasciare root ma aggiungere commento SoT “eccezione documentata: nginx official image master as root” — meno sicuro del path unprivileged.)*

---

## Deferred (non-fail)

| ID | Stato | Nota |
|----|-------|------|
| INF-IMG-03 | Deferred post–Phase 6 | Assenza digest SHA OK |
| INF-NPM-02 | Deferred | `--legacy-peer-deps` richiesto finché matrix Angular/CDK/PrimeNG non allineata |
| INF-OTH-09 | Informativo | Non trattare digest obbligatorio / drop legacy-peer-deps come DONE |

---

## Checklist walk (ID → esito)

| ID | Esito | Evidenza breve |
|----|-------|----------------|
| INF-NET-01 | PASS | `radar-edge` + `radar-data` bridge |
| INF-NET-02 | PASS | FE solo edge |
| INF-NET-03 | PASS | BE edge+data |
| INF-NET-04 | PASS | worker/db/miniflux solo data |
| INF-NET-05 | PASS | no `internal: true` |
| INF-NET-06 | PASS | `80:80` |
| INF-NET-07 | PASS | no ports Miniflux base |
| INF-NET-08 | PASS | no host 5432 |
| INF-NET-09 | PASS | hardened + lan override |
| INF-NET-10 | PASS | 5 nomi servizio immutabili |
| INF-USER-01 | PASS | `USER radar` |
| INF-USER-02 | PASS | worker eredita non-root |
| INF-USER-03 | **FAIL** | Nginx root — INF-AUD-02 |
| INF-USER-04 | PASS | logging try/except + console |
| INF-HC-01 | PASS | `/health/live` |
| INF-HC-02 | PASS | ready non in Compose HC |
| INF-HC-03 | PASS | FE depends backend healthy |
| INF-HC-04 | PASS | worker db+miniflux healthy |
| INF-HC-05 | PASS | miniflux healthcheck auto |
| INF-HC-06 | PASS | wget Alpine FE |
| INF-HC-07 | PASS | curl + package backend |
| INF-HC-08 | PASS | wget :80 (Compose `/health`) |
| INF-HC-09 | PASS | depends_on `service_healthy` |
| INF-VOL-01 | PASS | `./data/postgres` bind |
| INF-VOL-02 | PASS | no anonymous-only |
| INF-VOL-03 | PASS | no named volume DB |
| INF-IMG-01 | PASS | no `:latest` |
| INF-IMG-02 | PASS | pin major/minor |
| INF-IMG-03 | PASS | digest deferred |
| INF-NPM-01 | PASS | `npm ci --legacy-peer-deps` |
| INF-NPM-02 | PASS | legacy-peer-deps presente |
| INF-NPM-03 | PASS | multi-stage → Nginx |
| INF-NPM-04 | PASS | production default |
| INF-GEO-01 | PASS | gitignored GeoJSON |
| INF-GEO-02 | PASS | verify `--fetch` pre-build |
| INF-GEO-03 | PASS | ASSET_LICENSE SHA pin |
| INF-GEO-04 | PASS | asset locale in map |
| INF-GEO-05 | PASS | verify in Docker + CI |
| INF-GEO-06 | PASS | script + runbook |
| INF-CMD-01 | PASS | `app.main:app` |
| INF-CMD-02 | PASS | `python -m app.worker` |
| INF-CMD-03 | PASS | WORKDIR/PYTHONPATH/8000/workers 1 |
| INF-CMD-04 | PASS | ingest solo worker |
| INF-IDX-01…05 | PASS | indici 001+007 |
| INF-IDX-06 | PASS | UNIQUE source_url |
| INF-IDX-07 | PASS | junction FK CASCADE |
| INF-IDX-08 | PASS | asyncpg, no ORM |
| INF-IDX-09 | PASS | bootstrap → run_migrations |
| INF-CRED-01 | PASS | env_file, no secret in compose |
| INF-CRED-02 | PASS | doc no `$` in password |
| INF-CRED-03 | PASS | pattern radar-db:5432 |
| INF-CRED-04 | **FAIL** | no quote_plus — INF-AUD-01 |
| INF-CRED-05 | PASS | CORS default vuoto, no `*` |
| INF-NGX-01…08 | PASS | listen/SPA/resolver/headers/gzip/cache/conf |
| INF-MIG-01…09 | PASS | 001–007 + runner + DROP guarded |
| INF-OTH-01…09 | PASS | dockerignore, vault, ops, CI, stack, deferred |

---

## Conteggio priorità (return parent)

| Priorità | Count | ID finding |
|----------|-------|------------|
| P0 | **0** | — |
| P1 | **1** | INF-AUD-01 (INF-CRED-04) |
| P2 | **1** | INF-AUD-02 (INF-USER-03) |

**Output path:** `c:\Users\lucag\Documents\Dashboard finance\scratch\infra_audit.md`
