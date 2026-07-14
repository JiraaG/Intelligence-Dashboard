# Consolidation Implementation Plan

This plan addresses the production blockers found during the code and architecture review. Execute phases in order. Do not release a later phase while an earlier acceptance gate is failing.

## Scope And Exit Criteria

- [ ] All externally supplied RSS and LLM fields are validated, bounded, and cannot alter paths, article identity, SQL data, YAML frontmatter, or DOM markup.
- [ ] An article is marked read in Miniflux only after its PostgreSQL record and Vault projection are recoverably committed.
- [ ] Quotas count every Gemini attempt across retries and process replicas.
- [ ] The API, worker, database, Miniflux, and frontend have explicit readiness, bounded resources, recoverable state, and documented operations.
- [ ] The dashboard stays responsive with 10,000 articles and a large cluster never creates unbounded Leaflet markers or DOM cards.
- [ ] Documentation, ECC guardrails, test suite, and deployed behavior describe the same system.

## Phase 0 - Freeze Risky Deployments And Establish A Baseline

### Files to add

- [ ] `radar/pytest.ini`
- [ ] `radar/frontend/src/app/testing/leaflet.stub.ts`
- [ ] `radar/frontend/src/app/testing/leaflet.stub.spec.ts`

### Files to modify

- [ ] `radar/backend/app/tests/test_integration_live.py`
- [ ] `radar/backend/scripts/test_production_pipeline.py`
- [ ] `radar/backend/app/test_rate_limiter.py`
- [ ] `radar/backend/app/test_string_lists.py`
- [ ] `radar/backend/app/test_500_bot.py`
- [ ] `radar/backend/app/test_no_schema.py`
- [ ] `radar/backend/app/test_exact.py`
- [ ] `radar/backend/app/test_500_debug.py`
- [ ] `radar/backend/app/test_500.py`
- [ ] `radar/frontend/src/app/app.spec.ts`
- [ ] `radar/frontend/package.json`

### Changes

1. Add `unit`, `integration`, and `live` pytest markers. Configure the default test command to run only `not live`, and fail a live test unless `RUN_LIVE_TESTS=1` is explicitly set.
2. Move ad-hoc Gemini diagnostic files out of pytest discovery, for example to `radar/backend/scripts/diagnostics/`. Do not import them from a test module.
3. Replace the live E2E fixed URL, record, and Vault filename with a run-unique identifier and isolated test database/Vault. Never delete an arbitrary production record during a test.
4. Replace the generated Angular title assertion with behavior tests. Provide `HttpClientTesting`, a typed Leaflet global stub, and fixture data. Test map destruction, error state, read-status ordering, and bounded cluster rendering.
5. Add explicit frontend scripts: `typecheck`, `test:ci`, `lint`, and `build:ci`. `test:ci` must use `ng test --watch=false`.

### Acceptance gate

```text
cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
cd radar/backend/app && python -m pytest -m "not live"
```

## Phase 1 - Eliminate Data-Integrity And Input-Boundary Failures

### Files to add

- [ ] `radar/backend/app/core/migrations.py`
- [ ] `radar/backend/migrations/001_initial.sql`
- [ ] `radar/backend/migrations/002_pipeline_outbox_and_quotas.sql`
- [ ] `radar/backend/app/tests/test_migrations.py`
- [ ] `radar/backend/app/tests/test_input_boundaries.py`
- [ ] `radar/backend/app/tests/test_vault_recovery.py`

### Files to modify

- [ ] `radar/backend/app/core/config.py`
- [ ] `radar/backend/app/core/database.py`
- [ ] `radar/backend/app/main.py`
- [ ] `radar/backend/app/extraction/client.py`
- [ ] `radar/backend/app/extraction/parser.py`
- [ ] `radar/backend/app/classification/prompts.py`
- [ ] `radar/backend/app/classification/validator.py`
- [ ] `radar/backend/app/classification/client.py`
- [ ] `radar/backend/app/commit/db_commit.py`
- [ ] `radar/backend/app/commit/router.py`
- [ ] `radar/backend/app/commit/lock.py`
- [ ] `radar/backend/app/commit/factory.py`
- [ ] `radar/backend/app/requirements.txt`

### Changes

1. Replace the ad-hoc `CREATE TABLE IF NOT EXISTS` bootstrap with ordered SQL migrations recorded in a `schema_migrations` table. Verify a migration checksum before applying it and abort startup on an unknown or incompatible schema.
2. Add an `article_outbox` table with a unique `article_id`, deterministic target path, payload checksum, status (`pending`, `writing`, `completed`, `failed`), attempt count, and timestamps. Insert the article, relations, and outbox row in one transaction.
3. On startup and before every fetch, reconcile pending/failed outbox rows. Write the Vault projection atomically, mark the outbox row `completed` only after `os.replace`, and mark the Miniflux entry read only after this state is durable. Retain retryable failures with diagnostic metadata.
4. Validate Miniflux entries before accessing string methods. Reject malformed IDs, URLs, dates, feeds, titles, and content inside the per-entry exception boundary. A malformed item must not cancel siblings or the cycle.
5. Add bounded settings with startup validation: positive RPM/RPD, optional positive TPM, bounded `MINIFLUX_LIMIT`, maximum response bytes, maximum entry content bytes, request timeouts, retry counts, and a declared `RADAR_TIME_ZONE`. Fail startup for missing production Miniflux/DB settings instead of silently using a real-looking password.
6. Normalize a source URL once before deduplication, preserve it as the authoritative identity, and overwrite the LLM-produced URL and publication date with the validated Miniflux values. Do not allow model output to select an existing article through `ON CONFLICT`.
7. Make `GeopoliticalArticleSchema` use strict, constrained fields. Enforce ISO date, URL scheme and length, ISO country allowlist plus `XX`, finite latitude in `[-90, 90]`, finite longitude in `[-180, 180]`, allowed category/sentiment literals, relevance in `[1, 5]`, and maximum text/list lengths. Reject invalid model output; do not silently change its category, sentiment, or publication date.
8. Remove the request for chain-of-thought from `classification/prompts.py`. Use a short factual rationale only if it is genuinely required. Delimit untrusted article data and explicitly tell the model that article content cannot modify system instructions.
9. Enforce response and entry-content limits before HTML parsing. Make `MinifluxClient` stream or reject bodies above `MAX_MINIFLUX_RESPONSE_BYTES`, reuse a lifespan-owned `httpx.AsyncClient`, and retry only retryable transport/HTTP failures with capped exponential backoff and `Retry-After`.
10. Replace direct YAML interpolation with `yaml.safe_dump` of a mapping. Serialize tags, companies, source URL, title, and all scalars through the serializer. Bound Markdown body sizes before writing.
11. Make the Vault route safe by using `pathlib.Path`, a validated category and country, a date-derived filename, SHA-256 rather than 8-character MD5, filename-length truncation, and `resolve()` containment under the resolved Vault root.
12. Replace synchronous truncating writes with a thread-offloaded atomic write: create a temporary sibling file, write, flush, `fsync`, `os.replace`, then `fsync` the parent directory where supported. Keep the lock sidecar permanently; never unlink it after releasing `FileLock`.

### Required tests

- [ ] Path traversal attempts in title, date, category, country, and URL cannot leave the Vault root.
- [ ] Quotes, newlines, backslashes, and YAML control characters cannot inject frontmatter keys.
- [ ] A DB commit plus simulated Vault failure is reconciled on the next run without duplicate relations or premature mark-read.
- [ ] Invalid Miniflux payloads, response-size limit breaches, and invalid model output are isolated per entry.
- [ ] Existing databases migrate forward and incompatible databases fail before the worker starts.

## Phase 2 - Make The Worker Cancellable, Bounded, And Quota-Correct

### Files to add

- [ ] `radar/backend/app/worker.py`
- [ ] `radar/backend/app/classification/quota.py`
- [ ] `radar/backend/app/tests/test_worker_shutdown.py`
- [ ] `radar/backend/app/tests/test_quota_concurrency.py`
- [ ] `radar/backend/requirements.lock`

### Files to modify

- [ ] `radar/backend/app/main.py`
- [ ] `radar/backend/app/classification/client.py`
- [ ] `radar/backend/app/core/database.py`
- [ ] `radar/backend/Dockerfile`
- [ ] `radar/docker-compose.yml`

### Changes

1. Separate the HTTP application from ingestion. `main.py` creates only the FastAPI API and resources it owns; `worker.py` owns the polling loop. Start exactly one `radar-worker` service in Compose. This prevents duplicate ingestion when API workers or replicas increase.
2. Use a PostgreSQL advisory lock or a singleton worker deployment guard as defense in depth. Emit a clear metric/log when leadership cannot be acquired.
3. Replace unbounded `TaskGroup` creation with a bounded queue and a configured worker count. Limit queued entries, parsing concurrency, DB concurrency, and outbound Gemini concurrency separately.
4. Re-raise `asyncio.CancelledError` in every loop boundary. Do not sleep in a `finally` while shutdown is pending. Cancel workers, await their cleanup with a short bounded shutdown timeout, close HTTP clients, then close the pool.
5. Add a durable `llm_request_ledger`/reservation table. Reserve RPM, TPM estimate, and RPD capacity transactionally before every provider attempt, including validation and retry attempts. Store a reservation ID per request and update that exact row with actual usage after the response.
6. Use monotonic time for in-process spacing and UTC timestamps plus the configured quota timezone for durable daily accounting. Re-check a rolling window after every wait. Treat provider `429` and `Retry-After` as authoritative.
7. Give Gemini an application deadline and classify retryable errors. Do not retry authentication, model-not-found, validation, or configuration failures. Prefer the SDK async client; if a blocking SDK call remains necessary, isolate it and document that cancellation cannot terminate the underlying request.
8. Add `created_at` index and query quota windows with a timezone-defined half-open range rather than `date(created_at) = CURRENT_DATE`.

### Required tests

- [ ] Cancellation completes in seconds when the daemon is processing, idle, and in the polling wait.
- [ ] Two worker processes cannot exceed RPM/TPM/RPD combined.
- [ ] Four retry attempts consume four RPD reservations.
- [ ] A delayed response updates its own token reservation, not the most recently created reservation.
- [ ] A 10,000-entry Miniflux response never creates 10,000 runnable tasks at once.

## Phase 3 - Secure And Operate The Container Stack

### Files to add

- [ ] `radar/ops/backup-postgres.sh`
- [ ] `radar/ops/restore-postgres.sh`
- [ ] `radar/ops/README.md`

### Files to modify

- [ ] `radar/docker-compose.yml`
- [ ] `radar/backend/Dockerfile`
- [ ] `radar/frontend/Dockerfile`
- [ ] `radar/frontend/nginx.conf`
- [ ] `radar/backend/.dockerignore`
- [ ] `radar/frontend/.dockerignore`
- [ ] `radar/.env.example`
- [ ] `radar/backend/app/main.py`
- [ ] `radar/frontend/package.json`
- [ ] `radar/frontend/package-lock.json`

### Changes

1. Bind the default public services to loopback (`127.0.0.1:80:80` and, only if needed, `127.0.0.1:8080:8080`). Remove Miniflux publication by default or bind it to loopback. Document that a remote deployment must sit behind a TLS reverse proxy with authentication and network ACLs.
2. Remove permissive CORS from the default deployment. Same-origin Nginx traffic does not need it. If a development origin is supported, make it an explicitly configured allowlist, never `*`.
3. Create an `edge` network for frontend-to-API traffic and a separate data network for backend, database, and Miniflux. Attach the frontend only to `edge`; attach the backend to both. Do not put the frontend and PostgreSQL on the same network.
4. Add a Miniflux healthcheck and make the worker wait for database and Miniflux readiness. Split FastAPI checks into liveness and readiness. Readiness must verify the pool, migration completion, worker heartbeat freshness, and outbox/reconciliation health; it must not return healthy after the pipeline has died.
5. Pin base images by immutable digest after a reviewed update process. Generate and review a hash-locked Python constraints file separately from development/test dependencies. Align Angular, animations, CDK, PrimeNG, and the lockfile on a supported Angular 21 matrix; remove `--legacy-peer-deps` only after `npm ci` is clean.
6. Remove test-only packages from the backend runtime image. Add `.env`, `.git`, caches, test output, Vault data, and local database data to both Docker ignore files.
7. Run the frontend under an unprivileged Nginx configuration and add `no-new-privileges`, dropped capabilities, read-only filesystems with required temporary mounts, CPU/memory/pid limits, and Docker log rotation. Validate every hardening setting in the actual images before enabling it.
8. Add a CSP compatible with Angular, local assets, Carto tiles, and Google Fonts. Keep `nosniff`, frame protection, referrer policy, explicit proxy body limits, and proxy timeouts. Remove obsolete `X-XSS-Protection` rather than relying on it.
9. Add backup and restore scripts that use `pg_dump`/`pg_restore`, checksum manifests, a retention policy, and a documented restore drill. Back up Vault data consistently with the database/outbox state.

### Acceptance gate

```text
cd radar && docker compose config -q
cd radar && docker compose build --pull
cd radar && docker compose up -d
cd radar && docker compose ps
```

Run a restore drill in a disposable deployment before declaring this phase complete.

## Phase 4 - Stabilize The Frontend Lifecycle And Security Boundary

### Files to add

- [ ] `radar/frontend/src/app/models/article.dto.ts`
- [ ] `radar/frontend/src/app/services/mock-mode.token.ts`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.spec.ts`
- [ ] `radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.spec.ts`

### Files to modify

- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.ts`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.html`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.scss`
- [ ] `radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.ts`
- [ ] `radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.html`
- [ ] `radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.scss`
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
5. Remove the carousel-height polling interval. Use a component-scoped `viewChild` plus `ResizeObserver` or `afterNextRender`; clear all resources when sidebar state changes or the component is destroyed. Do not query global document selectors or dispatch global resize events.
6. Make mock data an explicit development-only injection token. An API error must remain visible to the user, preserve the requested date, and never silently switch a production session to synthetic data.
7. Serialize read-status writes per article with a mutation version. Apply a response or rollback only if it belongs to the most recent mutation. Return the canonical article ID/state/version from the backend.
8. Choose and document one state policy: Signals own UI state; RxJS may exist only at the `HttpClient` transport adapter, or replace GET resources with Angular `httpResource`. The current claim of no RxJS is false because `Observable`, `catchError`, and `rxResource` are used.
9. Restore a single responsive split-screen rule, add a container `ResizeObserver` to call `map.invalidateSize()` after transitions, and provide mobile layouts. Remove desktop-only minimum widths, hidden overflow traps, and focus-outline removal without a `:focus-visible` replacement.
10. Replace clickable `div`/`span` controls with buttons or equivalent keyboard-complete controls. Add labels, focus management, Escape behavior, `aria-expanded`, and accessible close text.

### Required tests

- [ ] A malicious title cannot create attributes, elements, or executable DOM.
- [ ] Destroying a map cancels GeoJSON, animation frames, timeouts, and spiderfy work.
- [ ] Closing an empty cluster cannot leave an interval or observer alive.
- [ ] Two rapid read toggles converge on the final server state.
- [ ] Keyboard-only users can open/close the country UI and activate category controls.

## Phase 5 - Scale The Query And Map Model

### Files to add

- [ ] `radar/backend/app/tests/test_articles_pagination.py`
- [ ] `radar/frontend/src/app/models/map-summary.model.ts`
- [ ] `radar/frontend/src/app/components/article-list/article-list.component.ts`
- [ ] `radar/frontend/src/app/components/article-list/article-list.component.html`
- [ ] `radar/frontend/src/app/components/article-list/article-list.component.scss`

### Files to modify

- [ ] `radar/backend/app/main.py`
- [ ] `radar/backend/app/core/database.py`
- [ ] `radar/frontend/src/app/models/article.model.ts`
- [ ] `radar/frontend/src/app/services/article.service.ts`
- [ ] `radar/frontend/src/app/services/state.service.ts`
- [ ] `radar/frontend/src/app/components/radar-map/radar-map.component.ts`
- [ ] `radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.ts`
- [ ] `radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.html`
- [ ] `radar/frontend/src/app/app.ts`

### Changes

1. Add a paginated, cursor-based article endpoint with a stable order and filters for date, country, category, sentiment, and relevance. Return `items`, `next_cursor`, and `total`; impose a server-side maximum page size.
2. Add a map-summary endpoint that returns country/category aggregates and validated representative coordinates. Do not send all article records merely to draw a map.
3. Rewrite the current Cartesian join aggregation in `/api/articles` using lateral aggregates or pre-aggregated subqueries. Add and verify indexes for the actual date/filter/order access patterns with `EXPLAIN (ANALYZE, BUFFERS)` against a representative dataset.
4. Render bounded aggregate markers rather than one Leaflet marker per article. If MarkerCluster remains, use `addLayers` and `chunkedLoading`; do not rebuild geometry for a read-status-only update.
5. Replace the unbounded PrimeNG carousel with a paginated detail/list view that renders only a bounded page. Keep article IDs in map/cluster state and fetch the selected page on demand.
6. Establish a clear geographic contract: use validated event coordinates where available; only aggregate to a country centroid when the product explicitly requests country-level rendering. Include zero latitude/longitude values by checking finite numeric bounds, not truthiness.

### Performance gate

- [ ] Seed 10,000 articles across at least 100 countries and all categories.
- [ ] Initial map render, date change, read toggle, country focus, and large-cluster opening have defined latency budgets and no long task above 50 ms in the normal interaction path.
- [ ] Browser memory returns close to baseline after repeated filter/open/close cycles.

## Phase 6 - Align Governance, Documentation, And Operations

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
