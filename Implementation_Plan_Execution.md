# Implementation Plan Execution Log

Log operativo post–branch restore. Distingue **storico pre-restore** (lavoro perso col restore) da **stato attuale del codice**.

---

## Vincoli permanenti

### Sidebar freeze (non negoziabile)

- Zero modifiche a `radar/frontend/src/app/components/radar-sidebar/` (TS/HTML/SCSS/spec).
- Zero sostituzione `p-carousel` → `app-article-list`.
- Zero restyle / a11y / cleanup altezza carosello / ResizeObserver sul carosello.

### Bug aperti (fuori sidebar)

- [ ] **Read/unread `.marker-read` no-op** — mutazione in-place in `state.service.ts`; marker Leaflet senza path `.marker-read`. Fix in Phase 4 (Change 7) + Phase 5 (Change 4): update immutabile + DOM marker senza rebuild cluster. Non toccare i file sidebar.
- [ ] **Read/unread collassa le icone a grafo espanse (rilevato 2026-07-14)** — con un cluster/spiderfy già aperto sulla mappa, il bottone *Segna come letta / non letta* (sidebar → `toggleRead` → `StateService.toggleReadStatus`) fa sparire le icone espanse del grafo. Causa probabile: `toggleReadStatus` emette un nuovo array articoli (`return [...arts]`), l’`effect` in `radar-map` ricostruisce i layer MarkerCluster e perde lo stato spiderfy/espanso. Stesso filone del fix Phase 4/5: aggiornare solo lo stato letto sul marker DOM (`.marker-read`) **senza** `clearLayers` / rebuild cluster su cambio `is_read`. Non toccare i file sidebar.

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
- [x] Sidebar non toccata. Phase 1 verificata; Phase 2 completata — **in attesa test manuale UI/ops prima di Phase 3.**

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
- [x] Sidebar non toccata. **In attesa conferma UI/ops prima di Phase 3.**

---

### Phase 3 — Secure container stack — NON INIZIATA

- [ ] Bind loopback (o doc reverse-proxy); Miniflux non pubblico di default / loopback.
- [ ] CORS non `*`; reti `edge` + data; frontend solo su edge.
- [ ] Healthcheck Miniflux; `/health/live` + `/health/ready` (pool, migrazioni, heartbeat, outbox).
- [ ] Pin immagini digest; constraints Python; allineamento Angular peer deps.
- [ ] Runtime image senza test deps; `.dockerignore` rafforzati.
- [ ] Nginx unprivileged + CSP; `no-new-privileges` / caps / read-only / limiti risorse.
- [ ] Script `ops/backup-postgres.sh` + `restore-postgres.sh` + README; drill restore.

---

### Phase 4 — Frontend lifecycle & security — NON INIZIATA (sidebar frozen)

- [ ] Marker XSS-safe (`textContent` / DOM API, no HTML string da titolo).
- [ ] Guard tipizzato `window.L`; stato map-unavailable; metadata marker tipizzate.
- [ ] `DestroyRef` / `takeUntilDestroyed`; cancel frame/timeout/Leaflet su destroy; spiderfy idempotente.
- [ ] Hatch directive cleanup / SVG pattern owner.
- [ ] ~~Carousel height ResizeObserver~~ — **cancellato (sidebar freeze)**.
- [ ] `MOCK_MODE` injection token esplicito; errore API visibile, no fallback silenzioso a mock.
- [ ] **Read/unread**: mutation version + update immutabile in `state.service`; sync `.marker-read` in `radar-map` senza rebuild cluster; preservare spiderfy/icone a grafo espanse al toggle letta/non letta.
- [ ] Policy Signals vs RxJS documentata.
- [ ] Split-screen / `invalidateSize` / mobile **senza** toccare file sidebar; a11y toolbar/country solo fuori sidebar.
- [ ] Spec: `radar-map.component.spec.ts`, `article.dto.ts`, `mock-mode.token.ts` — **no** `radar-sidebar.component.spec.ts`.

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

## C. Scoreboard attuale (audit 2026-07-14, post–Phase 2)

| Phase | Pre-restore (storico) | Codice attuale | Prossimo lavoro |
|-------|----------------------|----------------|-----------------|
| 0 | Completata | **DONE** (`0189359`) | — |
| 1 | Completata (persa) | **DONE** (`bff8abe`) | — |
| 2 | Completata (persa) | **DONE** (`72851d7`) | Conferma UI/ops, poi Phase 3 |
| 3 | Completata (persa) | **NOT STARTED** | Dopo conferma UI Phase 2 |
| 4 | Completata (persa) | **NOT STARTED** | Include bug read/unread; no sidebar |
| 5 | Completata (persa) | **NOT STARTED** | No `article-list` |
| 5.5 | Completata (persa) | N/A nel piano master | Assorbita in 1–3 al ri-run |
| 6 | Non iniziata | **NOT STARTED** | Ultima |

**Ordine di ripresa:** Phase 3 → 4 → 5 → 6 (dopo conferma UI/ops Phase 2).

**Restore rapido a Phase 2:** `git checkout 72851d7` su `refactor/enterprise-consolidation` (messaggio: `feat(phase2): radar-worker...`).
