# Consolidation Implementation Plan

This plan addresses the production blockers found during the code and architecture review. Execute phases in order. Do not release a later phase while an earlier acceptance gate is failing.

**Progress (2026-07-15):** Phase **0–5 DONE**. Phase **6 DONE / GATE VERDE** (`56c2eff` — docs, GeoJSON fetch+verify, CI, runbook, hooks). ECC remediation tip = commit successivo su questo branch. Sidebar remains frozen.

**Git restore points (branch `refactor/enterprise-consolidation`):**
| Tag semantico | Commit tipico | Contenuto |
|---------------|---------------|-----------|
| Phase 0 | `0189359` | pytest markers / frontend CI baseline |
| Phase 1 | `bff8abe` | migrations 001–002, outbox, Pydantic strict, vault atomico |
| Phase 2 | `72851d7` | `radar-worker`, coda bounded, `llm_request_ledger`, Gemini deadline/retry |
| Phase 3 | `19c67f0` | edge/data, live/ready+heartbeat, CSP, ops, soft hardening; schema Gemini sanificato |
| Phase 4 | `de9bd2f` | FE XSS/MOCK_MODE/DestroyRef; read-unread no cluster rebuild; hatch owner map; overlay full-bleed |
| Phase 5 | `1dfdf60` | map-summary + articles cursor/LATERAL; nation detail markers; spiderfy category-aligned |
| Phase 6 | `56c2eff` | governance: docs/README, GeoJSON pin+verify, ECC/hooks, CI, runbook |

## Scope And Exit Criteria

### Frozen: radar-sidebar (non-negotiable)

Do **not** modify, restyle, refactor, replace, or add specs for `radar/frontend/src/app/components/radar-sidebar/` (including `p-carousel`, `updateCarouselHeight`, markup, SCSS, or a11y inside the sidebar). Do **not** introduce `article-list` or infinite-scroll replacements for the carousel.

**Exception kept in scope:** read/unread sync (`.marker-read` no-op **and** expanded graph icons collapsing on toggle — see below). Fix only via `state.service.ts` and `radar-map.component.ts` — the sidebar already calls `toggleRead` → `StateService` and must keep working without editing sidebar files.

**Observed UI bug (2026-07-14) — FIXED Phase 4:** toggling *Segna come letta / non letta* while a category cluster is spiderfied/expanded made expanded graph icons disappear. Root cause was `toggleReadStatus` → new articles array → map `effect` → `clearLayers`. Phase 4: geometry fingerprint + `syncMarkerReadState` (`.marker-read` without rebuild).

### Exit criteria

- [ ] All externally supplied RSS and LLM fields are validated, bounded, and cannot alter paths, article identity, SQL data, YAML frontmatter, or DOM markup.
- [ ] An article is marked read in Miniflux only after its PostgreSQL record and Vault projection are recoverably committed.
- [ ] Quotas count every Gemini attempt across retries and process replicas.
- [ ] The API, worker, database, Miniflux, and frontend have explicit readiness, bounded resources, recoverable state, and documented operations.
- [ ] The dashboard stays responsive with 10,000 articles and a large cluster never creates unbounded Leaflet markers. (Sidebar DOM card bounding is out of scope.)
- [ ] Read-status toggles update map marker `.marker-read` without a full cluster rebuild (expanded spiderfy/graph icons must stay); concurrent toggles converge on the final server state.
- [x] Documentation, ECC guardrails, test suite, and deployed behavior describe the same system. *(Phase 6 `56c2eff` + ECC remediation tip)*

## Phase 0 - Freeze Risky Deployments And Establish A Baseline

**Status:** DONE (2026-07-14) on post-restore branch.

### Files to add

- [x] `radar/pytest.ini`
- [x] `radar/frontend/src/app/testing/leaflet.stub.ts`
- [x] `radar/frontend/src/app/testing/leaflet.stub.spec.ts`

### Files to modify

- [x] `radar/backend/app/tests/test_integration_live.py`
- [x] `radar/backend/scripts/test_production_pipeline.py`
- [x] Diagnostics moved to `radar/backend/scripts/diagnostics/` (removed from `radar/backend/app/test_*.py`)
- [x] `radar/frontend/src/app/app.spec.ts`
- [x] `radar/frontend/package.json`
- [x] Fixture alignment: `test_classification.py`, `test_commit.py`, `test_pipeline_smoke.py`, `test_extraction.py`

### Changes

1. [x] Add `unit`, `integration`, and `live` pytest markers. Configure the default test command to run only `not live`, and fail a live test unless `RUN_LIVE_TESTS=1` is explicitly set.
2. [x] Move ad-hoc Gemini diagnostic files out of pytest discovery, for example to `radar/backend/scripts/diagnostics/`. Do not import them from a test module.
3. [x] Replace the live E2E fixed URL, record, and Vault filename with a run-unique identifier and isolated test database/Vault. Never delete an arbitrary production record during a test.
4. [x] Replace the generated Angular title assertion with behavior tests. Provide `HttpClientTesting`, a typed Leaflet global stub, and fixture data. Test map destruction, error state, read-status ordering, and bounded cluster rendering.
5. [x] Add explicit frontend scripts: `typecheck`, `test:ci`, `lint`, and `build:ci`. `test:ci` must use `ng test --watch=false`.

### Acceptance gate

```text
cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
cd radar && python -m pytest -m "not live"
```

**Status (2026-07-14):** gate verde — frontend 10 passed; backend 34 passed / 3 live deselected. Docker smoke + prova vault/Miniflux (4 unread) OK.

## Phase 1 - Eliminate Data-Integrity And Input-Boundary Failures

**Status:** DONE (2026-07-14) on post-restore branch.

### Files to add

- [x] `radar/backend/app/core/migrations.py`
- [x] `radar/backend/migrations/001_initial.sql`
- [x] `radar/backend/migrations/002_pipeline_outbox_and_quotas.sql`
- [x] `radar/backend/app/tests/test_migrations.py`
- [x] `radar/backend/app/tests/test_input_boundaries.py`
- [x] `radar/backend/app/tests/test_vault_recovery.py`

### Files to modify

- [x] `radar/backend/app/core/config.py`
- [x] `radar/backend/app/core/database.py`
- [x] `radar/backend/app/main.py`
- [x] `radar/backend/app/extraction/client.py`
- [x] `radar/backend/app/extraction/parser.py`
- [x] `radar/backend/app/classification/prompts.py`
- [x] `radar/backend/app/classification/validator.py`
- [x] `radar/backend/app/classification/client.py`
- [x] `radar/backend/app/commit/db_commit.py`
- [x] `radar/backend/app/commit/router.py`
- [x] `radar/backend/app/commit/lock.py`
- [x] `radar/backend/app/commit/factory.py`
- [x] `radar/backend/app/requirements.txt`

### Changes

1. [x] Replace the ad-hoc `CREATE TABLE IF NOT EXISTS` bootstrap with ordered SQL migrations recorded in a `schema_migrations` table. Verify a migration checksum before applying it and abort startup on an unknown or incompatible schema.
2. [x] Add an `article_outbox` table with a unique `article_id`, deterministic target path, payload checksum, status (`pending`, `writing`, `completed`, `failed`), attempt count, and timestamps. Insert the article, relations, and outbox row in one transaction.
3. [x] On startup and before every fetch, reconcile pending/failed outbox rows. Write the Vault projection atomically, mark the outbox row `completed` only after `os.replace`, and mark the Miniflux entry read only after this state is durable. Retain retryable failures with diagnostic metadata.
4. [x] Validate Miniflux entries before accessing string methods. Reject malformed IDs, URLs, dates, feeds, titles, and content inside the per-entry exception boundary. A malformed item must not cancel siblings or the cycle.
5. [x] Add bounded settings with startup validation: positive RPM/RPD, optional positive TPM, bounded `MINIFLUX_LIMIT`, maximum response bytes, maximum entry content bytes, request timeouts, retry counts, and a declared `RADAR_TIME_ZONE`. Fail startup for missing production Miniflux/DB settings instead of silently using a real-looking password.
6. [x] Normalize a source URL once before deduplication, preserve it as the authoritative identity, and overwrite the LLM-produced URL and publication date with the validated Miniflux values. Do not allow model output to select an existing article through `ON CONFLICT`.
7. [x] Make `GeopoliticalArticleSchema` use strict, constrained fields. Enforce ISO date, URL scheme and length, ISO country allowlist plus `XX`, finite latitude in `[-90, 90]`, finite longitude in `[-180, 180]`, allowed category/sentiment literals, relevance in `[1, 5]`, and maximum text/list lengths. Reject invalid model output; do not silently change its category, sentiment, or publication date.
8. [x] Remove the request for chain-of-thought from `classification/prompts.py`. Use a short factual rationale only if it is genuinely required. Delimit untrusted article data and explicitly tell the model that article content cannot modify system instructions.
9. [x] Enforce response and entry-content limits before HTML parsing. Make `MinifluxClient` stream or reject bodies above `MAX_MINIFLUX_RESPONSE_BYTES`, reuse a lifespan-owned `httpx.AsyncClient`, and retry only retryable transport/HTTP failures with capped exponential backoff and `Retry-After`.
10. [x] Replace direct YAML interpolation with `yaml.safe_dump` of a mapping. Serialize tags, companies, source URL, title, and all scalars through the serializer. Bound Markdown body sizes before writing.
11. [x] Make the Vault route safe by using `pathlib.Path`, a validated category and country, a date-derived filename, SHA-256 rather than 8-character MD5, filename-length truncation, and `resolve()` containment under the resolved Vault root.
12. [x] Replace synchronous truncating writes with a thread-offloaded atomic write: create a temporary sibling file, write, flush, `fsync`, `os.replace`, then `fsync` the parent directory where supported. Keep the lock sidecar permanently; never unlink it after releasing `FileLock`.

### Required tests

- [x] Path traversal attempts in title, date, category, country, and URL cannot leave the Vault root.
- [x] Quotes, newlines, backslashes, and YAML control characters cannot inject frontmatter keys.
- [x] A DB commit plus simulated Vault failure is reconciled on the next run without duplicate relations or premature mark-read.
- [x] Invalid Miniflux payloads, response-size limit breaches, and invalid model output are isolated per entry.
- [x] Existing databases migrate forward and incompatible databases fail before the worker starts.

### Acceptance gate

```text
cd radar && python -m pytest -m "not live"
```

**Status (2026-07-14):** gate verde — 74 passed / 3 live deselected. Docker rebuild: migrations 001+002 applied (legacy `schema_migrations` converted); `/`, `/health`, `/api/articles` 200. Sidebar untouched.

## Phase 2 - Make The Worker Cancellable, Bounded, And Quota-Correct

**Status:** DONE (2026-07-14) on post-restore branch.

### Files to add

- [x] `radar/backend/app/worker.py`
- [x] `radar/backend/app/classification/quota.py`
- [x] `radar/backend/app/tests/test_worker_shutdown.py`
- [x] `radar/backend/app/tests/test_quota_concurrency.py`
- [x] `radar/backend/requirements.lock`
- [x] `radar/backend/migrations/003_quota_ledger.sql`

### Files to modify

- [x] `radar/backend/app/main.py`
- [x] `radar/backend/app/classification/client.py`
- [x] `radar/backend/app/core/config.py`
- [x] `radar/backend/app/core/logging.py` (makedirs fallback — WORKDIR `/app`)
- [x] `radar/backend/Dockerfile`
- [x] `radar/docker-compose.yml`
- [x] `radar/.env.example`

### Changes

1. [x] Separate the HTTP application from ingestion. `main.py` creates only the FastAPI API and resources it owns; `worker.py` owns the polling loop. Start exactly one `radar-worker` service in Compose. This prevents duplicate ingestion when API workers or replicas increase.
2. [x] Use a PostgreSQL advisory lock or a singleton worker deployment guard as defense in depth. Emit a clear metric/log when leadership cannot be acquired.
3. [x] Replace unbounded `TaskGroup` creation with a bounded queue and a configured worker count. Limit queued entries, parsing concurrency, DB concurrency, and outbound Gemini concurrency separately.
4. [x] Re-raise `asyncio.CancelledError` in every loop boundary. Do not sleep in a `finally` while shutdown is pending. Cancel workers, await their cleanup with a short bounded shutdown timeout, close HTTP clients, then close the pool.
5. [x] Add a durable `llm_request_ledger`/reservation table. Reserve RPM, TPM estimate, and RPD capacity transactionally before every provider attempt, including validation and retry attempts. Store a reservation ID per request and update that exact row with actual usage after the response.
6. [x] Use monotonic time for in-process spacing and UTC timestamps plus the configured quota timezone for durable daily accounting. Re-check a rolling window after every wait. Treat provider `429` and `Retry-After` as authoritative.
7. [x] Give Gemini an application deadline and classify retryable errors. Do not retry authentication, model-not-found, validation, or configuration failures. Prefer the SDK async client; if a blocking SDK call remains necessary, isolate it and document that cancellation cannot terminate the underlying request.
8. [x] Add `created_at` index and query quota windows with a timezone-defined half-open range rather than `date(created_at) = CURRENT_DATE`.

### Required tests

- [x] Cancellation completes in seconds when the daemon is processing, idle, and in the polling wait.
- [x] Two worker processes cannot exceed RPM/TPM/RPD combined.
- [x] Four retry attempts consume four RPD reservations.
- [x] A delayed response updates its own token reservation, not the most recently created reservation.
- [x] A 10,000-entry Miniflux response never creates 10,000 runnable tasks at once.

### Acceptance gate

```text
cd radar && python -m pytest -m "not live"
cd radar && docker compose up -d --build
```

**Status (2026-07-14):** gate verde — 95 passed / 3 live deselected. Docker: migrazione 003 applicata; `radar-worker` leader (advisory lock); API healthy; `/` `/health` `/api/articles` 200. Sidebar untouched.

## Phase 3 - Secure And Operate The Container Stack

**Status:** DONE (2026-07-15) — plug-and-play ports `80:80`; Miniflux unpublished; `radar-edge`/`radar-data`; `/health/live`+`/ready` + heartbeat `004`; CSP; ops backup; soft hardening; **Gemini structured output** via `build_gemini_response_schema()` (strip `additionalProperties` — evita 400 → summary fallback). Deferred: image digest pin, Angular peer-deps matrix, drop `--legacy-peer-deps`.

### Files to add

- [x] `radar/ops/backup-postgres.sh`
- [x] `radar/ops/restore-postgres.sh`
- [x] `radar/ops/README.md`
- [x] `radar/docker-compose.hardened.yml`
- [x] `radar/docker-compose.lan.yml`
- [x] `radar/backend/migrations/004_worker_heartbeat.sql`
- [x] `radar/backend/app/core/heartbeat.py`
- [x] `radar/backend/app/requirements-dev.txt`

### Files to modify

- [x] `radar/docker-compose.yml`
- [x] `radar/backend/Dockerfile`
- [x] `radar/frontend/nginx.conf`
- [x] `radar/backend/.dockerignore`
- [x] `radar/frontend/.dockerignore`
- [x] `radar/.env.example`
- [x] `radar/backend/app/main.py`
- [x] `radar/backend/app/worker.py`
- [x] `radar/backend/app/core/config.py`
- [ ] `radar/frontend/package.json` / `package-lock.json` — **deferred** (legacy-peer-deps retained)

### Changes

1. [x] Default FE `80:80` (0.0.0.0) for ready-to-run; Miniflux unpublished; hardened loopback via `docker-compose.hardened.yml`; lan Miniflux via `docker-compose.lan.yml`. Document TLS reverse-proxy for remote.
2. [x] CORS allowlist env (`CORS_ALLOW_ORIGINS`); default empty; never `*`.
3. [x] Networks `radar-edge` + `radar-data`; frontend only edge; backend both; worker/db/miniflux data only.
4. [x] Miniflux healthcheck; worker waits db+Miniflux healthy; `/health/live` + `/health/ready` (pool, migration 004, heartbeat freshness, outbox counts). Compose uses live only.
5. [x] Tag pins retained; digest pin + Angular matrix + drop legacy-peer-deps **deferred**. Runtime image without pytest (`requirements-dev.txt`).
6. [x] Strengthened `.dockerignore`; test deps out of runtime image.
7. [x] Soft hardening: no-new-privileges, cap_drop, resource limits, log rotation; FE read_only+tmpfs. Aggressive backend/db read-only deferred.
8. [x] CSP (Angular, Carto, Google Fonts); nosniff/frame/referrer; remove X-XSS-Protection; proxy body/timeouts.
9. [x] Backup/restore scripts + checksum + retention + drill docs; vault consistent with dump.

### Acceptance gate

```text
cd radar && docker compose config -q
cd radar && docker compose build --pull
cd radar && docker compose up -d
cd radar && docker compose ps
cd radar && python -m pytest -m "not live"
```

**Status (2026-07-15):** pytest 100+ passed / 3 live deselected. Compose smoke verde: live/ready 200, FE `:80`, Miniflux unpublished, worker ingest OK. Migrazioni `004`–`006`. Fix Gemini schema verificato (re-ingest oggi: summary reali, non fallback; 429 gestiti con Retry-After).

## Phase 4 - Stabilize The Frontend Lifecycle And Security Boundary

**Status:** DONE (2026-07-15) — XSS-safe markers; `MOCK_MODE` token (no silent fallback); DestroyRef lifecycle; geometry fingerprint + `.marker-read` without cluster rebuild; hatch owner = `getOrCreateComboPattern` (directive removed); toolbar a11y; overlay full-bleed + `invalidateSize`. Sidebar untouched.

### Files to add

- [x] `radar/frontend/src/app/models/article.dto.ts`
- [x] `radar/frontend/src/app/services/mock-mode.token.ts`
- [x] `radar/frontend/src/app/components/radar-map/radar-map.component.spec.ts`

### Files to modify

- [x] `radar/frontend/src/app/components/radar-map/radar-map.component.ts`
- [x] `radar/frontend/src/app/components/radar-map/radar-map.component.html`
- [x] `radar/frontend/src/app/components/radar-map/radar-map.component.scss`
- [x] `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.html`
- [x] `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.scss`
- [x] `radar/frontend/src/app/services/article.service.ts`
- [x] `radar/frontend/src/app/services/article-mock.service.ts` *(unchanged dataset; consumed only via MOCK_MODE)*
- [x] `radar/frontend/src/app/services/state.service.ts`
- [x] `radar/frontend/src/app/app.config.ts`
- [x] `radar/frontend/src/app/app.scss`
- [x] `radar/frontend/src/styles.scss`
- [x] `radar/frontend/src/app/shared/directives/leaflet-hatch.directive.ts` — **removed** (owner = map combo patterns)

### Changes

1. [x] Never concatenate article data into `L.divIcon().html`. DOM + `textContent` / `title` property; runtime DTO validation.
2. [x] Typed `window.L` guard; map-unavailable state; typed marker metadata.
3. [x] `DestroyRef` / `takeUntilDestroyed`; cancel GeoJSON, rAF, timeouts; spiderfy generation idempotent.
4. [x] Hatch: directive removed; single owner `getOrCreateComboPattern`; fixed 6th-line typo; patterns for categories 7–10.
5. ~~Carousel-height ResizeObserver~~ — **cancelled (sidebar freeze).**
6. [x] `MOCK_MODE` injection token; API errors visible; no silent mock fallback.
7. [x] Read-status mutation version; hybrid is_read (in-place object + new array); `.marker-read` without MarkerCluster rebuild / spiderfy preserved.
8. [x] Signals vs RxJS policy documented in `radar/.ecc/rules/frontend.md` (doc-only).
9. [x] Overlay full-bleed + `invalidateSize()` on open/close/resize; focus-visible on non-sidebar surfaces.
10. [x] Toolbar country/count controls → `button` (sidebar untouched).

### Required tests

- [x] A malicious title cannot create attributes, elements, or executable DOM.
- [x] Destroying a map cancels GeoJSON work and removes the map.
- [x] Read toggles update `.marker-read` without `clearLayers`; spiderfy retained; rapid sync converges.
- [x] Keyboard-ready toolbar country controls (button elements + focus-visible).

### Acceptance gate

```text
cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
```

**Status (2026-07-15):** gate verde — typecheck OK; 14 passed; build:ci OK (budget warning ~982kB). Sidebar freeze verified (no diff under `radar-sidebar/**`). Backend not touched.
**Restore point Phase 4:** `de9bd2f` (`feat(phase4): stabilize frontend lifecycle...`) su `refactor/enterprise-consolidation`.
Restore: `git checkout de9bd2f`

## Phase 5 - Scale The Query And Map Model

**Status:** DONE (2026-07-15) on post-restore branch.

**Bottleneck:** articles **per day** on map/API (not 10k via Miniflux 48h). DB ~1.5k total; peak day ~600. Miniflux `published_after=now-48h`, `MINIFLUX_LIMIT`≤500 — real ingest cannot be the 10k gate.

**Product contract (locked — overrides earlier “limit 50 detail” draft):**

```text
DAY OPEN     → GET /api/map-summary  → hatching + numbered pallini (zoom ≥ 5)
COUNTRY / TOOLBAR → ALL articles date+country → full-nation carousel
PALLINO summary (country×category) → nation fetch, sidebar filtered to category,
  spiderfy that category, no dezoom (armSkipCountryFit)
NATION OPEN (no category) → spiderfy only the carousel-active category
CAROUSEL SCROLL → highlight article; spiderfy only when category changes
CLOSE        → clear detailArticles → summary pallini return
```

Do **not** truncate the nation carousel at 50. HTTP page size may be ≤100 for transport; FE concatenates pages until `next_cursor` is null. Do **not** fetch only `country×category` on nation click (breaks category index). Sidebar freeze unchanged.

### Decisions (Fase A → B)

| ID | Choice |
|----|--------|
| D1 | Breaking FE+BE same phase; `/api/articles` returns `{items,next_cursor,total}` — no legacy bare array |
| D2 | Keyset cursor for single day: `id DESC`; cursor = article `id`; `total` = filtered `COUNT(*)`; max page `limit` 100 |
| D3 | map-summary aggregated by `country_code × primary_category` (+ finite representative lat/lon, counts, read/unread) |
| D4 | StateService: `mapSummaryResource` + `detailArticles` (nation scope); hybrid `toggleRead` on detail; toolbar/countries from summary |
| D5 | Nation click loads **all** nation articles; no infinite scroll / `article-list` |
| D6 | SQL: LATERAL/subselect for companies & tags — **no** double `LEFT JOIN` in one FROM |
| D7 | Geo: `Number.isFinite` + range; replace `latitude && longitude` |
| D8 | Perf gate: **synthetic SQL seed** 10k/1 day (≥100 country codes, 10 cats) — not Miniflux/Gemini |
| D9 | Phase 4 regression checklist mandatory (spiderfy + read toggle, XSS, MOCK_MODE, DestroyRef, sidebar diff empty) |
| D10 | ECC light (frontend.md map-summary + nation markers; CLAUDE API) — full docs Phase 6 |
| D11 | Defer: Playwright 10k, peer-deps matrix, `httpResource` migration, rigorous browser-memory CI |

### Files to add

- [x] `radar/backend/migrations/007_articles_query_indexes.sql`
- [x] `radar/backend/app/api/articles_query.py` (+ `api/__init__.py`)
- [x] `radar/backend/app/tests/test_articles_pagination.py`
- [x] `radar/backend/scripts/seed_perf_articles.py`
- [x] `radar/frontend/src/app/models/map-summary.model.ts` (+ dto guards)
- [x] Extended: `article.dto.ts`, `article-mock.service.ts`

### Files to modify

- [x] `radar/backend/app/main.py`
- [x] `radar/frontend/src/app/models/article.model.ts`
- [x] `radar/frontend/src/app/models/article.dto.ts`
- [x] `radar/frontend/src/app/services/article.service.ts`
- [x] `radar/frontend/src/app/services/article-mock.service.ts`
- [x] `radar/frontend/src/app/services/state.service.ts`
- [x] `radar/frontend/src/app/components/radar-map/radar-map.component.ts` (+ spec)
- [x] `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.ts`
- [x] `radar/frontend/src/app/app.ts` / `app.html` / `app.spec.ts`
- [x] `radar/.ecc/rules/frontend.md` + `radar/.ecc/CLAUDE.md` (ECC light)
- [x] **Never** `radar-sidebar/**` (verified empty diff)

### Changes

1. [x] Paginated `/api/articles` with filters `date` (required), `country`, `category`, `sentiment`, `relevance_level`, `cursor`, `limit` (cap 100). Response `{ items, next_cursor, total }`. Companies/tags via LATERAL.
2. [x] `GET /api/map-summary?date=…` → rows `country_code × primary_category` with counts + finite lat/lon.
3. [x] Indexes migration `007`; seed script `seed_perf_articles.py` (EXPLAIN residual / optional on isolated DB).
4. [x] **Map UX:** day = summary hatching + numbered pallini; nation open = detail markers only for that country; category pallino / pill / active carousel category → `focusAndSpiderfyCategory`; carousel same-category scroll does **not** collapse/reopen spiderfy (`lastSpiderfyKey`); multi-pallino race fixed (`invalidateSize` before spiderfy, `pendingGeometryRefresh`).
5. [x] ~~`article-list`~~ — **cancelled (sidebar freeze).**
6. [x] Geographic contract: finite bounds BE+FE.
7. [x] Seed script isolated to DB — no vault write, no Miniflux mark-read.
8. [x] `MOCK_MODE`: mock summary + mock paged articles; no silent fallback.

### Performance gate

- [x] Seed script ready (10k SQL); EXPLAIN documentato come residuale opzionale su DB isolato.
- [x] pytest coverage for pagination + map-summary.
- [x] FE typecheck / test:ci / build:ci; map specs cover fingerprint, invalidateSize, spiderfy generation.
- [x] Browser smoke: summary load, nation open, pallini multi-click, carousel scroll no flicker; sidebar `git diff` empty under `radar-sidebar/**`.
- [ ] Long-task / memory budgets: deferred (Playwright not required to close Phase 5).
- [ ] Smoke manuale toggle letta + spiderfy (residual; path Phase 4 preserved).

### Acceptance gate

```text
cd radar && python -m pytest -m "not live"
cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
# Docker rebuild FE+BE; /health/live+/ready; smoke UI above
```

**Status (2026-07-15):** gate verde locale — pytest `not live` OK; FE typecheck + test:ci (18) + build:ci OK; Docker FE/BE healthy; migrazione `007` applicata. Residuali non bloccanti: seed EXPLAIN su DB isolato, smoke toggle letta manuale.
**Restore point Phase 5:** `1dfdf60` (`feat(phase5): map-summary + paged articles...`) su `refactor/enterprise-consolidation`.
Restore: `git checkout 1dfdf60`

## Phase 6 - Align Governance, Documentation, And Operations

**Status:** DONE / GATE VERDE (2026-07-15) — Blocchi A–D + polish README/docs.  
**Gate locale:** pytest `not live` 107 passed; FE typecheck + test:ci (18) + build:ci + verify-geojson PASS; sidebar diff vuoto.  
**Commit/pin restore SHA:** solo su richiesta esplicita (nessun push finché non chiesto).

### Files to modify

- [x] `README.md` *(indice 01–04, Mermaid edge/data, restore SHA, mappa piani→codice; polish tipografia/link)*
- [x] `docs/01_getting_started.md`
- [x] `docs/02_architecture_and_backend.md`
- [x] `docs/03_frontend_and_ui.md`
- [x] `docs/04_ecc_framework.md`
- [x] `Fase2_Implementation_Plan.md` *(ARCHIVIO — non eseguibile)*
- [x] `radar/frontend/README.md`
- [x] `radar/ops/README.md` *(cross-link IT docs/runbook)*
- [x] `radar/.env.example` *(già allineato Phase 3–5 — verificato, nessuna modifica necessaria)*
- [x] `.gitignore` *(no più `data/` su assets FE; solo postgres/host data)*
- [x] `radar/.gitignore` *(geojson ignorato; license/README tracciabili)*
- [x] `.agents/AGENTS.md`
- [x] `radar/.ecc/CLAUDE.md`
- [x] `radar/.ecc/settings.json` *(allowlist ECC invariata; alias Cursor nel post-hook)*
- [x] `radar/.ecc/rules/backend.md` *(già allineato — audit-only)*
- [x] `radar/.ecc/rules/frontend.md`
- [x] `radar/.ecc/rules/docker.md` *(già allineato — audit-only)*
- [x] `radar/.ecc/agents/pipeline-engineer.md` *(già allineato — audit-only)*
- [x] `radar/.ecc/agents/angular-map-expert.md`
- [x] `radar/.ecc/hooks/pre-tool-use.py`
- [x] `radar/.ecc/hooks/post-tool-use.py`
- [x] `.agents/skills/llm-json-extraction/SKILL.md` + `radar/.ecc/skills/llm-json-extraction.md`

### Files to add or track

- [x] `radar/frontend/src/assets/data/countries.geo.json` *(policy: gitignored + fetch deterministico; non tracciato in Git)*
- [x] `radar/frontend/src/assets/data/ASSET_LICENSE.md`
- [x] `radar/frontend/scripts/verify-geojson.mjs`
- [x] `radar/docs/runbook.md`
- [x] `.github/workflows/ci.yml`

### Changes

1. [x] GeoJSON: pin SHA-256 + license (Natural Earth / datasets/geo-countries, ODC-PDDL-1.0); `verify-geojson.mjs` fail se missing/malformed/SHA errato; `--fetch` URL commit-pinned; Docker + `build:ci` eseguono fetch/verify. Asset resta gitignored.
2. [x] Frontend README di progetto; rimosso `ng e2e` fantasma; script `typecheck` / `test:ci` / `build:ci` / verify documentati.
3. [x] Docs 01–04 + README allineati al codice Phase 0–5 (worker vs API, edge/data, live/ready, envelope articles, map-summary, MOCK_MODE, ledger, porte Miniflux).
4. [x] `Fase2_Implementation_Plan.md` archiviato (banner non eseguibile; claim 3.11 / `latest` / CORS GET-only non più presentati come vivi).
5. [x] ECC/AGENTS: una verità architetturale; rimossi cluster 6-categorie / spiderfy contradittorio / ingest in `main.py` nei punti toccati; skill LLM → `worker.py`.
6. [x] CI: `.github/workflows/ci.yml` (FE verify+typecheck+test+build; pytest `not live`; secret grep best-effort). Hook post fail-closed (ruff/prettier). Migration verify = `test_migrations.py` nella suite pytest. Image/vuln scan e doc-link check: **deferred** (non bloccanti per chiudere Phase 6).
7. [x] Pre-hook: domain `==` o `.endswith('.'+allowed)`; secret patterns ampliati (Gemini/Postgres/Miniflux).
8. [x] Runbook: deploy, live/ready, logs, quota, outbox, backup/restore, rolling upgrade, security, escalation.

### Acceptance gate

```text
cd radar && python -m pytest -m "not live" -q
cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
# verify-geojson incluso in build:ci; sidebar: git diff vuoto sotto radar-sidebar/**
```

**Status (2026-07-15):** gate verde — 107 passed / 3 live deselected; FE 18 passed; build:ci + verify GeoJSON PASS. Sidebar untouched. Restore: `git checkout 56c2eff` (pre–ECC remediation).

## Final Release Gate

- [x] Unit + integration (`pytest -m "not live"`) pass; live resta opt-in (`RUN_LIVE_TESTS=1`).
- [x] Clean checkout buildable senza asset untracked manuali *(GeoJSON via `verify-geojson --fetch` / Docker)*.
- [ ] Compose validation, container health, readiness degradation, backup, and restore are tested. *(ops scripts presenti; drill Compose end-to-end — ops manuale / residuale)*
- [ ] A kill/restart during DB commit, Vault write, Miniflux mark-read, Gemini timeout, and polling wait leaves no lost or prematurely acknowledged article. *(design Phase 1–2; chaos drill residuale)*
- [ ] SAST, dependency/image scans, CSP validation, and a manual XSS regression test pass. *(CSP Phase 3; CI secret grep; image/SAST deferred)*
- [ ] The 10,000-article performance test meets the agreed budgets. *(seed script presente; budget measure residuale Phase 5)*
- [x] Every public document and ECC rule has been reviewed against the deployed configuration. *(Phase 6 + polish tipografico/Mermaid/indici)*
