# Implementation Plan Execution Log

Log operativo post–branch restore. Distingue **storico pre-restore** (lavoro perso col restore) da **stato attuale del codice**.

---

## Vincoli permanenti

### Sidebar freeze (non negoziabile)

- Zero modifiche a `radar/frontend/src/app/components/radar-sidebar/` (TS/HTML/SCSS/spec).
- Zero sostituzione `p-carousel` → `app-article-list`.
- Zero restyle / a11y / cleanup altezza carosello / ResizeObserver sul carosello.

### Bug aperti (fuori sidebar)

- [x] **Read/unread `.marker-read` no-op** — fix Phase 4: hybrid is_read in `state.service` + geometry fingerprint / `syncMarkerReadState` in `radar-map` (no cluster rebuild). Sidebar untouched.
- [x] **Read/unread collassa le icone a grafo espanse** — fix Phase 4: solo `is_read` non chiama `clearLayers`; spiderfy resta.

---

## A. Storico pre-restore (ARCHIVIO — non più nel codice)

> Prima del problema al carosello e del restore del branch, l’execution log dichiarava complete: Phase 0–5, remediation Phase 5, Phase 5.5 hardening. **Quel lavoro non è più nel tree sorgente** (restano al più `__pycache__` fantasma). Non spuntare di nuovo queste voci finché non sono ripristinate nel codice attuale.

| Area | Cosa c’era (claim pre-restore) | Stato dopo restore |
|------|--------------------------------|--------------------|
| Phase 0 | pytest markers, live gate, diagnostici fuori discovery | **Rifatta** nel codice attuale (sezione B) |
| Phase 1 | migrazioni SQL, outbox, vault atomico, yaml.safe_dump, path traversal SHA-256, Miniflux stream | **Persa** — di nuovo bootstrap `CREATE TABLE IF NOT EXISTS`, YAML f-string, MD5[:8], ecc. |
| Phase 2 | `radar-worker`, QuotaLedger, coda bounded, advisory lock | **Persa** — ingestione ancora in `main.py` + `TaskGroup` |
| Phase 3 | reti `edge`/`data`, `/health/live`+`/ready`, CSP, ops backup, hardening | **Persa** — rete unica, `/health` solo, porte `80`/`8080` aperte |
| Phase 4 | DestroyRef, XSS `textContent`, `MOCK_MODE`, a11y, spec map | **Persa** — XSS via string HTML, mock fallback silenzioso, no DestroyRef |
| Phase 5 | SQL senza Cartesian join, `article-list`, marker-read path | **Persa** — join+`array_agg` classico; `article-list` **non** va ripristinato (freeze) |
| Phase 5.5 | advisory lock, ready checks, reconcile outbox, CoT rimosso, leaflet stub spec | **Persa** (stub leaflet rifatto in Phase 0 attuale) |

---

## B. Stato attuale post-restore (sorgente di verità)

### Phase 0 — Test Environment Baseline — COMPLETATA (2026-07-14)

- [x] `radar/pytest.ini`: markers `unit` / `integration` / `live`; `addopts = -m "not live"`.
- [x] Live gate: `pytest_runtest_setup` fallisce senza `RUN_LIVE_TESTS=1`.
- [x] Diagnostici Gemini in `radar/backend/scripts/diagnostics/`; rimossi da `backend/app/test_*.py`.
- [x] Live E2E: ID run-unique + DB/Vault isolati; no delete su record produzione arbitrari.
- [x] Frontend: `leaflet.stub.ts` + spec; `app.spec.ts` behavior tests.
- [x] Scripts: `typecheck`, `test:ci`, `lint`, `build:ci`.
- [x] Fixture test allineati a schema `str` + Miniflux params + retry client.

**Gate regression**

```text
cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
# → typecheck OK; 10 passed; build:ci OK (budget warning ~978kB)

cd radar && backend\.venv\Scripts\python.exe -m pytest -m "not live" -q
# → 34 passed, 3 deselected
```

**Docker / smoke (2026-07-14)**

- [x] `docker compose down` + `up --build` — backend/frontend/db healthy; miniflux up.
- [x] HTTP `/`, `/health`, `/api/articles` 200.
- [x] Prova vault: 10 file eliminati + unread Miniflux (4 match) → pipeline **4 elaborati / 0 errori**, vault ricreato, entry di nuovo `read`.

---

### Phase 1 — Data Integrity & Boundaries — COMPLETATA (2026-07-14)

- [x] `core/migrations.py` + `migrations/001_*.sql` / `002_*.sql` + tabella `schema_migrations` (checksum); conversione legacy `name` → `version` su DB esistenti.
- [x] Tabella `article_outbox` + insert atomico articolo/relazioni/outbox; reconcile vault; mark-read Miniflux solo dopo commit durable; upgrade shape pre-restore (`payload`, `id`, `last_error`, `miniflux_entry_id`).
- [x] Validazione entry Miniflux; settings bounded + fail startup produzione (`RADAR_ENV`).
- [x] URL source autoritativo; schema Pydantic strict (reject, non coerce silenzioso); rimossi CoT/`reasoning` da prompt/schema.
- [x] Limiti byte response/content; `httpx` lifespan + stream/reject; retry solo errori retryable.
- [x] Frontmatter con `yaml.safe_dump`; vault `pathlib` + SHA-256 + containment; write atomica (`tmp` → `fsync` → `os.replace`); lock sidecar permanente.
- [x] Test: `test_migrations.py`, `test_input_boundaries.py`, `test_vault_recovery.py`.

**Gate regression**

```text
cd radar && backend\.venv\Scripts\python.exe -m pytest -m "not live" -q
# → 74 passed, 3 deselected
```

**Docker / smoke (2026-07-14)**

- [x] `docker compose up -d --build radar-backend` — healthy; migrazioni 001+002 applicate.
- [x] HTTP `/`, `/health`, `/api/articles` 200.
- [x] Sidebar non toccata. Phase 1 verificata; Phase 2/3 completate.

---

### Phase 2 — Worker cancellabile / quota — COMPLETATA (2026-07-14)

- [x] `worker.py` separato da FastAPI; Compose `radar-worker` (uno solo, stessa immagine backend, `python -m app.worker`).
- [x] Advisory lock session-level (`pg_try_advisory_lock`) + retry non-leader senza exit/flap.
- [x] Coda bounded (`WORKER_QUEUE_DEPTH`) + N consumer; semafori PARSE/DB/GEMINI.
- [x] `CancelledError` re-raise; shutdown ordinato bounded; chiusura httpx → unlock → pool.
- [x] Migrazione `003_quota_ledger.sql` + `QuotaLedger` (RPM/TPM/RPD durable, half-open TZ).
- [x] Client Gemini: reserve prima di ogni tentativo; deadline async SDK; retry classificato; `429`+Retry-After.
- [x] Test: `test_worker_shutdown.py`, `test_quota_concurrency.py`; `requirements.lock`.
- [x] Soft-trim RPD ciclo su ledger (non più `date(created_at)=CURRENT_DATE` su `articles`).
- [x] `setup_logging`: fallback se `logs/` non scrivibile (WORKDIR `/app`).

**Gate regression**

```text
cd radar && backend\.venv\Scripts\python.exe -m pytest -m "not live" -q
# → 95 passed, 3 deselected
```

**Docker / smoke (2026-07-14)**

- [x] `docker compose up -d --build` — backend/frontend/db healthy; `radar-worker` up; leadership acquisita.
- [x] Migrazione `003_quota_ledger` applicata; schema_migrations 001+002+003.
- [x] HTTP `/`, `/health`, `/api/articles` 200.
- [x] Sidebar non toccata. Phase 2 verificata; Phase 3 completata.

---

### Phase 3 — Secure container stack — COMPLETATA (2026-07-15)

- [x] Default FE `80:80` (0.0.0.0) plug-and-play; Miniflux unpublished; `docker-compose.hardened.yml` (loopback) + `docker-compose.lan.yml` (Miniflux :8080).
- [x] CORS allowlist env (default vuota, mai `*`); reti `radar-edge` + `radar-data`; frontend solo edge.
- [x] Healthcheck Miniflux; worker `depends_on` db+miniflux healthy; `/health/live` + `/health/ready` + migrazione `004_worker_heartbeat`.
- [x] Runtime image senza pytest (`requirements-dev.txt`); `.dockerignore` rafforzati. Digest pin / Angular matrix / drop legacy-peer-deps **deferred**.
- [x] Soft hardening (no-new-privileges, caps, limits, log rotation, FE read_only+tmpfs); CSP Nginx; no X-XSS-Protection.
- [x] Script `ops/backup-postgres.sh` + `restore-postgres.sh` + README (Windows/Git Bash, live vs ready, Miniflux admin).
- [x] **Fix Gemini:** `build_gemini_response_schema()` rimuove `additionalProperties`/`additional_properties` (400 INVALID_ARGUMENT → fallback “Errore di elaborazione…”). Verificato con reset vault/DB/Miniflux unread del giorno e re-ingest (categorie/paesi reali; 429 Retry-After OK).

**Gate regression**

```text
cd radar && backend\.venv\Scripts\python.exe -m pytest -m "not live" -q
# → 100+ passed, 3 deselected (include test_gemini_response_schema_strips_additional_properties)
cd radar && docker compose config -q   # (+ hardened, lan)
```

**Docker / smoke (2026-07-15):**

- [x] `docker compose config -q` (base + hardened + lan)
- [x] `docker compose build --pull` + `up -d` — backend/frontend/db/miniflux healthy; worker up; FE `0.0.0.0:80`; Miniflux unpublished
- [x] `/health/live` 200; `/health/ready` 200 (heartbeat fresco); `/` + `/api/articles` 200
- [x] Migrazioni `004`–`006` applicate (heartbeat + allineamento ledger legacy pre-restore)
- [x] Worker leader + ingest OK (commit+outbox). Sidebar non toccata.
- [x] Riavvio verificato (`compose down` + `up -d`): tutti healthy; `/health/live`+`/ready` 200; Traceback=0; Miniflux unpublished.
- [x] Re-ingest post-fix schema: niente fallback spurio su lotto di prova; Miniflux fetch 48h + classificazione IT OK.

**Restore point Phase 3:** `19c67f0` (`feat(phase3): secure Compose stack...`) su `refactor/enterprise-consolidation`.
Restore: `git checkout 19c67f0`

---

### Phase 4 — Frontend lifecycle & security — COMPLETATA (2026-07-15)

- [x] Marker XSS-safe (`textContent` / DOM API; `article.dto.ts` runtime guard).
- [x] Guard tipizzato `window.L`; stato map-unavailable; metadata marker tipizzate.
- [x] `DestroyRef` / `takeUntilDestroyed`; cancel GeoJSON/rAF/timeout; spiderfy generation idempotente.
- [x] Hatch: directive `appLeafletHatch` rimossa; owner unico `getOrCreateComboPattern` (typo i===5 fix + pattern cat. 7–10).
- [x] ~~Carousel height ResizeObserver~~ — cancellato (sidebar freeze).
- [x] `MOCK_MODE` injection token; errore API banner toolbar; no fallback silenzioso a mock.
- [x] **Read/unread**: mutation version FE + hybrid is_read; `.marker-read` senza rebuild cluster; spiderfy preservato.
- [x] Policy Signals vs RxJS documentata in `radar/.ecc/rules/frontend.md`.
- [x] Overlay full-bleed + `invalidateSize` su open/close/resize; a11y toolbar (button + focus-visible).
- [x] Spec: `radar-map.component.spec.ts` — **no** touch `radar-sidebar/**`.

**Gate regression**

```text
cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
# → typecheck OK; 14 passed; build:ci OK (budget warning ~982kB)
```

**Note:** Restore point Phase 4: `de9bd2f`. Restore: `git checkout de9bd2f` su `refactor/enterprise-consolidation`. Sidebar freeze verificato.

---

### Phase 5 — Scale query & map model — NON INIZIATA (no article-list)

- [ ] Endpoint articoli cursor-based (`items`, `next_cursor`, `total`) + filtri.
- [ ] Endpoint map-summary (aggregati paese/categoria + coordinate validate).
- [ ] Rewrite SQL `/api/articles` (no Cartesian join); indici + `EXPLAIN (ANALYZE)`.
- [ ] Marker aggregati bounded; `addLayers` / `chunkedLoading` se MarkerCluster resta; **no rebuild** su solo `is_read`.
- [ ] ~~Replace carousel / `article-list`~~ — **cancellato (sidebar freeze)**.
- [ ] Contratto geografico (finite bounds, non truthiness su lat/lon).
- [ ] Performance gate 10k articoli (path Leaflet; DOM sidebar out of scope).

---

### Phase 6 — Governance, docs, ops — NON INIZIATA

- [ ] GeoJSON asset versionato + license + verify script.
- [ ] README frontend/progetto allineati al comportamento reale.
- [ ] Docs / ECC / AGENTS / Fase2 archive coerenti col codice post-fasi.
- [ ] Hook CI reali; secret scanning; runbook ops.

---

## C. Scoreboard attuale (audit 2026-07-15, post–Phase 4)

| Phase | Pre-restore (storico) | Codice attuale | Prossimo lavoro |
|-------|----------------------|----------------|-----------------|
| 0 | Completata | **DONE** (`0189359`) | — |
| 1 | Completata (persa) | **DONE** (`bff8abe`) | — |
| 2 | Completata (persa) | **DONE** (`72851d7`) | — |
| 3 | Completata (persa) | **DONE** (`19c67f0`) | — |
| 4 | Completata (persa) | **DONE** (`de9bd2f`) | — |
| 5 | Completata (persa) | **NOT STARTED** | No `article-list` |
| 5.5 | Completata (persa) | N/A nel piano master | Assorbita in 1–3 al ri-run |
| 6 | Non iniziata | **NOT STARTED** | Ultima |

**Ordine di ripresa:** Phase 5 → 6.

**Restore rapido a Phase 4:** `git checkout de9bd2f` su `refactor/enterprise-consolidation`.
**Restore rapido a Phase 3:** `git checkout 19c67f0` su `refactor/enterprise-consolidation`.
**Restore a Phase 2:** `git checkout 72851d7`.
