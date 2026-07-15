# Consolidation Implementation Plan

This plan addresses the production blockers found during the code and architecture review. Execute phases in order. Do not release a later phase while an earlier acceptance gate is failing.

**Progress (audit codice 2026-07-15, post–Phase 3):** Phase **0 DONE**. Phase **1 DONE**. Phase **2 DONE**. Phase **3 DONE** (stack secure/operate + fix Gemini `additional_properties` → no fallback spurio). Phases **4–6 NOT STARTED**. Resume at Phase 4. Sidebar remains frozen; read/unread `.marker-read` remains in scope via `state.service` + `radar-map` only.

**Git restore points (branch `refactor/enterprise-consolidation`):**
| Tag semantico | Commit tipico | Contenuto |
|---------------|---------------|-----------|
| Phase 0 | `0189359` | pytest markers / frontend CI baseline |
| Phase 1 | `bff8abe` | migrations 001–002, outbox, Pydantic strict, vault atomico |
| Phase 2 | `72851d7` | `radar-worker`, coda bounded, `llm_request_ledger`, Gemini deadline/retry |
| Phase 3 | *(SHA di questo commit feat(phase3) — pinnato subito dopo)* | edge/data, live/ready+heartbeat, CSP, ops, soft hardening; schema Gemini sanificato |

## Scope And Exit Criteria

### Frozen: radar-sidebar (non-negotiable)

Do **not** modify, restyle, refactor, replace, or add specs for `radar/frontend/src/app/components/radar-sidebar/` (including `p-carousel`, `updateCarouselHeight`, markup, SCSS, or a11y inside the sidebar). Do **not** introduce `article-list` or infinite-scroll replacements for the carousel.

**Exception kept in scope:** read/unread sync (`.marker-read` no-op **and** expanded graph icons collapsing on toggle — see below). Fix only via `state.service.ts` and `radar-map.component.ts` — the sidebar already calls `toggleRead` → `StateService` and must keep working without editing sidebar files.

**Observed UI bug (2026-07-14):** toggling *Segna come letta / non letta* while a category cluster is spiderfied/expanded makes the expanded graph icons disappear. Root cause is in the same Phase 4/5 path: `StateService.toggleReadStatus` replaces the articles array, `radar-map` rebuilds MarkerCluster layers, and spiderfy state is lost. Acceptance: read toggle must update `.marker-read` (and keep spiderfy/expanded icons) without a full cluster rebuild.

### Exit criteria

- [ ] All externally supplied RSS and LLM fields are validated, bounded, and cannot alter paths, article identity, SQL data, YAML frontmatter, or DOM markup.
- [ ] An article is marked read in Miniflux only after its PostgreSQL record and Vault projection are recoverably committed.
- [ ] Quotas count every Gemini attempt across retries and process replicas.
- [ ] The API, worker, database, Miniflux, and frontend have explicit readiness, bounded resources, recoverable state, and documented operations.
- [ ] The dashboard stays responsive with 10,000 articles and a large cluster never creates unbounded Leaflet markers. (Sidebar DOM card bounding is out of scope.)
- [ ] Read-status toggles update map marker `.marker-read` without a full cluster rebuild (expanded spiderfy/graph icons must stay); concurrent toggles converge on the final server state.
- [ ] Documentation, ECC guardrails, test suite, and deployed behavior describe the same system.

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

**Status:** NOT STARTED after restore — XSS HTML markers, in-place `is_read`, silent mock fallback, no DestroyRef / MOCK_MODE / map specs. Sidebar frozen (Change 5 cancelled). Read/unread fix remains mandatory (Change 7), including the observed collapse of expanded spiderfy/graph icons on letta/non-letta toggle.

### Files to add

- [ ] `radar/frontend/src/app/models/article.dto.ts`
- [ ] `radar/frontend/src/app/services/mock-mode.token.ts`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.spec.ts`

### Files to modify

- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.ts`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.html`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.scss`
- [ ] `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.html`
- [ ] `radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.scss`
- [ ] `radar/frontend/src/app/services/article.service.ts`
- [ ] `radar/frontend/src/app/services/article-mock.service.ts`
- [ ] `radar/frontend/src/app/services/state.service.ts`
- [ ] `radar/frontend/src/app/app.config.ts`
- [ ] `radar/frontend/src/app/app.scss`
- [ ] `radar/frontend/src/styles.scss`
- [ ] `radar/frontend/src/app/shared/directives/leaflet-hatch.directive.ts`

### Changes

1. Never concatenate article data into `L.divIcon().html`. Create a DOM element, assign `title` through the property, and assign visible text through `textContent`. Add runtime validation for every API DTO before it reaches map or template code.
2. Retrieve `window.L` only after browser initialization through a typed guard. Present a controlled map-unavailable state if global scripts fail. Remove `any` marker extensions in favor of a typed marker metadata interface.
3. Use `DestroyRef`/`takeUntilDestroyed` for the GeoJSON request. Retain and cancel every animation frame, timeout, interval, and Leaflet callback during destroy. Make navigation completion idempotent: one terminal event, one fallback timer, listener removal before delayed spiderfy, and reconciliation of deferred article/focus updates.
4. Remove the redundant hatch directive or add a stored `MutationObserver` and destroy cleanup. Keep a single SVG-pattern owner and correct the sixth-line typo plus the representation of categories seven through ten.
5. ~~Carousel-height ResizeObserver~~ — **cancelled (sidebar freeze).**
6. Make mock data an explicit development-only injection token. An API error must remain visible to the user, preserve the requested date, and never silently switch a production session to synthetic data.
7. Serialize read-status writes per article with a mutation version. Apply a response or rollback only if it belongs to the most recent mutation. Return the canonical article ID/state/version from the backend. Use immutable article updates in `state.service` so map markers receive `.marker-read` without editing the sidebar. A read-status-only update must **not** rebuild MarkerCluster layers or clear an open spiderfy — expanded graph icons must remain visible after *Segna come letta / non letta*.
8. Choose and document one state policy: Signals own UI state; RxJS may exist only at the `HttpClient` transport adapter, or replace GET resources with Angular `httpResource`. The current claim of no RxJS is false because `Observable`, `catchError`, and `rxResource` are used.
9. Restore a single responsive split-screen rule via shell/map (`map.invalidateSize()` after transitions) and provide mobile layouts **without modifying `radar-sidebar` files**. Remove desktop-only minimum widths and focus-outline removal without a `:focus-visible` replacement on non-sidebar surfaces.
10. Replace clickable `div`/`span` controls with buttons on toolbar / country UI / map chrome only — **not** inside the frozen sidebar.

### Required tests

- [ ] A malicious title cannot create attributes, elements, or executable DOM.
- [ ] Destroying a map cancels GeoJSON, animation frames, timeouts, and spiderfy work.
- [ ] Two rapid read toggles converge on the final server state; toggling read updates `.marker-read` on the map marker without a full cluster rebuild; an already-expanded spiderfy/graph stays visible after letta/non-letta.
- [ ] Keyboard-only users can open/close the country UI and activate toolbar category controls (sidebar controls out of scope).

## Phase 5 - Scale The Query And Map Model

**Status:** NOT STARTED after restore — unpaginated `/api/articles`, Cartesian join + `array_agg`, one marker per article. Change 5 (`article-list`) cancelled — keep `p-carousel`.

### Files to add

- [ ] `radar/backend/app/tests/test_articles_pagination.py`
- [ ] `radar/frontend/src/app/models/map-summary.model.ts`

### Files to modify

- [ ] `radar/backend/app/main.py`
- [ ] `radar/backend/app/core/database.py`
- [ ] `radar/frontend/src/app/models/article.model.ts`
- [ ] `radar/frontend/src/app/services/article.service.ts`
- [ ] `radar/frontend/src/app/services/state.service.ts`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.ts`
- [ ] `radar/frontend/src/app/app.ts`

### Changes

1. Add a paginated, cursor-based article endpoint with a stable order and filters for date, country, category, sentiment, and relevance. Return `items`, `next_cursor`, and `total`; impose a server-side maximum page size.
2. Add a map-summary endpoint that returns country/category aggregates and validated representative coordinates. Do not send all article records merely to draw a map.
3. Rewrite the current Cartesian join aggregation in `/api/articles` using lateral aggregates or pre-aggregated subqueries. Add and verify indexes for the actual date/filter/order access patterns with `EXPLAIN (ANALYZE, BUFFERS)` against a representative dataset.
4. Render bounded aggregate markers rather than one Leaflet marker per article. If MarkerCluster remains, use `addLayers` and `chunkedLoading`; do not rebuild geometry for a read-status-only update (supports the read/unread marker fix).
5. ~~Replace PrimeNG carousel with `article-list`~~ — **cancelled (sidebar freeze).** Keep existing `p-carousel`.
6. Establish a clear geographic contract: use validated event coordinates where available; only aggregate to a country centroid when the product explicitly requests country-level rendering. Include zero latitude/longitude values by checking finite numeric bounds, not truthiness.

### Performance gate

- [ ] Seed 10,000 articles across at least 100 countries and all categories.
- [ ] Initial map render, date change, read toggle, country focus, and large-cluster opening have defined latency budgets and no long task above 50 ms in the normal interaction path (Leaflet path; sidebar DOM out of scope).
- [ ] Browser memory returns close to baseline after repeated filter/open/close cycles.

## Phase 6 - Align Governance, Documentation, And Operations

**Status:** NOT STARTED — run only after Phases 1–5 gates are green on the post-restore codebase.

### Files to modify

- [ ] `README.md`
- [ ] `docs/01_getting_started.md`
- [ ] `docs/02_architecture_and_backend.md`
- [ ] `docs/03_frontend_and_ui.md`
- [ ] `docs/04_ecc_framework.md`
- [ ] `Fase2_Implementation_Plan.md`
- [ ] `radar/frontend/README.md`
- [ ] `radar/.env.example`
- [ ] `.gitignore`
- [ ] `radar/.gitignore`
- [ ] `.agents/AGENTS.md`
- [ ] `radar/.ecc/CLAUDE.md`
- [ ] `radar/.ecc/settings.json`
- [ ] `radar/.ecc/rules/backend.md`
- [ ] `radar/.ecc/rules/frontend.md`
- [ ] `radar/.ecc/rules/docker.md`
- [ ] `radar/.ecc/agents/pipeline-engineer.md`
- [ ] `radar/.ecc/agents/angular-map-expert.md`
- [ ] `radar/.ecc/hooks/pre-tool-use.py`
- [ ] `radar/.ecc/hooks/post-tool-use.py`

### Files to add or track

- [ ] `radar/frontend/src/assets/data/countries.geo.json`
- [ ] `radar/frontend/src/assets/data/ASSET_LICENSE.md`
- [ ] `radar/frontend/scripts/verify-geojson.mjs`
- [ ] `radar/docs/runbook.md`
- [ ] `.github/workflows/ci.yml`

### Changes

1. Version the licensed GeoJSON asset or fetch it deterministically during a controlled build. Record origin, license, version, and SHA-256. Add a prebuild check that fails when the asset is missing or malformed. Exempt only this asset directory from the broad root `data/` ignore rule.
2. Replace the stale frontend README with project-specific build, test, development, asset, and deployment instructions. Remove the nonexistent `ng e2e` command unless an actual e2e runner is added.
3. Correct all claims that conflict with code: Vault fallback, current RPM/TPM defaults and algorithm, retry behavior, category fallback, PATCH response, cluster architecture, exposed ports, and real health semantics. Document the current limitations only until the related phase is complete.
4. Update `Fase2_Implementation_Plan.md` as archived historical material or delete claims about Python 3.11, Miniflux `latest`, CORS GET-only, and old cluster rules. It must not remain an apparently executable plan with false facts.
5. Reconcile global AGENTS, local ECC rules, CLAUDE instructions, profiles, and skills with the chosen architecture. Remove stale six-category/list-schema/mock-toggle/cluster examples. Do not preserve contradictory rules as alternatives.
6. Make hooks real gates in CI. The post hook must target the actual edit tools, run from the project root, fail on a missing linter rather than silently succeeding, and run typecheck/test/build as appropriate. Add secret scanning, dependency/image vulnerability scanning, migration verification, and documentation link checks to CI.
7. Correct pre-hook domain matching to accept only `domain == allowed` or `domain.endswith('.' + allowed)`. Expand secret detection to all project keys and avoid relying on regexes as the only secret-control mechanism.
8. Write a runbook covering deploy, health meanings, logs, quota exhaustion, pending outbox recovery, backup/restore, rolling upgrade, security boundary, and incident escalation.

## Final Release Gate

- [ ] Unit, integration, and opt-in live tests pass in isolated environments.
- [ ] A clean checkout builds without manually supplied untracked assets.
- [ ] Compose validation, container health, readiness degradation, backup, and restore are tested.
- [ ] A kill/restart during DB commit, Vault write, Miniflux mark-read, Gemini timeout, and polling wait leaves no lost or prematurely acknowledged article.
- [ ] SAST, dependency/image scans, CSP validation, and a manual XSS regression test pass.
- [ ] The 10,000-article performance test meets the agreed budgets.
- [ ] Every public document and ECC rule has been reviewed against the deployed configuration.
