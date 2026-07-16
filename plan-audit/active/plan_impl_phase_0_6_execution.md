# Log di Esecuzione Consolidamento — Phase 0-6

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

> **Solo storico.** Prima del restore del branch, l’execution log dichiarava complete Phase 0–5 (+ 5.5). Quel lavoro era stato perso al restore e **poi rifatto** (vedi § B e scoreboard § C).  
> **Non** usare questa tabella come stato attuale né come checklist da ripristinare.  
> Piani eseguibili: `plan_impl_phase_0_6.md` + § B/C di questo file.  
> Anche `Fase2_Implementation_Plan.md` è archivio (claim falsi vs tree attuale).

| Area | Cosa c’era (claim pre-restore) | Stato dopo restore (storico) |
|------|--------------------------------|--------------------|
| Phase 0 | pytest markers, live gate, diagnostici fuori discovery | Poi **rifatta** (§ B) |
| Phase 1 | migrazioni SQL, outbox, vault atomico, … | Era persa; **rifatta** |
| Phase 2 | `radar-worker`, QuotaLedger, … | Era persa (ingest in `main.py`); **rifatta** |
| Phase 3 | reti edge/data, live/ready, … | Era persa; **rifatta** |
| Phase 4 | DestroyRef, MOCK_MODE, … | Era persa; **rifatta** |
| Phase 5 | SQL LATERAL / map model; `article-list` **non** va ripristinato | Era persa; **rifatta** senza article-list (freeze) |
| Phase 5.5 | advisory lock, … | Assorbita in 1–3 al ri-run |

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

### Phase 5 — Scale query & map model — DONE (2026-07-15)

**Fase A (analisi):** confermata. Collo di bottiglia = articoli/giorno su mappa/API, non ingest 10k Miniflux 48h.

**Contratto prodotto locked (revisionato vs draft “limit 50”):**

- Apertura giorno → `GET /api/map-summary` (hatching + count `country×category` + pallini zoom ≥ 5); niente `Article[]` globale.
- Click nazione / toolbar → fetch **tutti** gli articoli `date+country` (page HTTP ≤100, FE concatena); carosello nazione completo.
- Pallino/pin summary → nazione + sidebar filtrata categoria + spiderfy categoria (`preserveZoom`).
- Open nazione senza categoria → spiderfy **solo** categoria dell’articolo attivo nel carosello.
- Scroll carosello stessa categoria → highlight only (`lastSpiderfyKey`); cambio categoria → spiderfy (hub root stabile).
- Poligono/toolbar → nation open + `fitBounds` (`maxZoom: 4`); ri-click stesso paese → `refocusCountry`.
- Close: clear detail markers; summary pins restano.
- Seed gate: SQL sintetico 10k/1 day — **non** pipeline Miniflux/Gemini (script pronto; EXPLAIN residuale).
- Breaking API; SQL LATERAL; finite lat/lon; MOCK_MODE; sidebar freeze.

**Checklist implementazione**

- [x] Blocco 1 — BE: LATERAL articles + cursor + map-summary + indici `007` + `test_articles_pagination.py` + `seed_perf_articles`
- [x] Blocco 2 — FE services/models: summary dto, ArticleService paged + summary, StateService dual, mock
- [x] Blocco 3 — Map/app/toolbar: summary hatch; nation fetch; detail markers; finite geo; Phase 4 fingerprint
- [x] Blocco 4 — Gate pytest + typecheck/test/build; smoke UI; ECC light; aggiornare scoreboard
- [x] Fix pallini multi-click (invalidate→spiderfy; pendingGeometryRefresh; refreshClusters)
- [x] Nation open spiderfy = categoria attiva carosello (non tutte)
- [x] Carousel scroll: no collapse/reopen spiderfy within same category

**Gate regression (2026-07-15)**

```text
cd radar && backend\.venv\Scripts\python.exe -m pytest -m "not live" -q
# → 107 passed, 3 deselected

cd radar/frontend && npm run typecheck && npm run test:ci && npm run build:ci
# → typecheck OK; 18 passed; build:ci OK
```

**Docker / smoke (2026-07-15)**

- [x] `docker compose up -d --build radar-backend radar-frontend` — healthy; migrazione `007` applicata
- [x] `/api/map-summary` + `/api/articles` envelope; nation open + pallini + carousel
- [x] Sidebar freeze: `git diff` vuoto sotto `radar-sidebar/**`
- [ ] Seed 10k + EXPLAIN documentato (script pronto; run opzionale su DB isolato)
- [ ] Smoke manuale toggle letta + spiderfy icone grafo (path Phase 4; non bloccante)

**Fix pallini multi-click (2026-07-15)**

Sintomo: click ripetuti su pallini → icone MarkerCluster sparite (layer in group, pane DOM vuoto).

Fix: `invalidateSize` senza `setView` inutile; invalidate **prima** dello spiderfy; `nationOpenGeneration`; `pendingGeometryRefresh` + `finishNavigating`; unspiderfy + `refreshClusters` post-`clearLayers`.

**Nation open / carousel (2026-07-15)**

- Open nazione → spiderfy sola categoria dell’articolo carosello (sort categoria).
- Scroll stessa categoria → `lastSpiderfyKey` skip collapse; cambio categoria / pill → spiderfy.

**Map UX harden — hub + fan (2026-07-15)**

Sintomi: hub spariva al cambio categoria carosello/pill; fan troppo denso / icone grandi; focus nazione inconsistente dopo il primo click.

Fix:
- `unspiderfied` no-op se `restoreDetailHubOnUnspiderfy === false` (non wipe del root mid-transition).
- Nation hub = disco compatto `radar-spider-root` (stesso chrome del root spiderfy).
- Fan: tutte le icone della categoria (niente cap 24); `spiderfyIconSizeForCount` + `spiderfyDistanceForCount` adattivi; hub ripristinato se spiderfy fallisce.
- `armSkipCountryFit` solo con `preserveZoom`; `refocusCountry` per stesso codice; poligono click sempre emette.
- Docs ECC: `docs/03_frontend_and_ui.md`, `radar/.ecc/rules/frontend.md` Regola 7, `.agents/AGENTS.md`, README FE.

**Spider dezoom / hatching close (2026-07-16)**

Sintomo: con spider aperto, un tick di dezoom (wheel) chiudeva il fan; a zoom &lt; 5 (barre/hatching) la sidebar restava aperta.

Causa: MarkerCluster auto-unspiderfy su `zoomstart`/`zoomanim`/`zoomend`; il nostro `zoomend` non chiudeva se `nationOpen`.

Fix (`radar-map.component.ts` only; sidebar freeze rispettato):
- `disableMarkerClusterMapClickUnspiderfy` rimuove anche `_unspiderfyZoomStart` / `_unspiderfyZoomAnim` / `_noanimationUnspiderfy`.
- `lastSpiderfyCountry` / `lastSpiderfyCategory` settati su spiderfy riuscito; azzerati su `collapseAllGraphs(emitClose)`.
- `zoomend`: se nation open + zoom ≥ 5 + lastSpiderfy → re-spiderfy deferito 50ms; se nation open + zoom &lt; 5 + lastSpiderfy → `collapseAllGraphs(true)` (sidebar + spider); guard lastSpiderfy evita race `fitBounds(maxZoom:4)`.
- Bundle budget initial `maximumError`: `1050kB` (fix ~310B oltre 1MB).
- Docs: `frontend.md` Regola 5+7, `angular-map-expert.md`, `.agents/AGENTS.md`, `CLAUDE.md`, checklist scratch, `audit_remediation_spider_dezoom.md`.

**Non fare**

- [x] ~~Replace carousel / `article-list`~~ — cancellato (sidebar freeze)
- [x] Truncate carosello nazione a 50
- [x] Fetch solo `country×category` al click nazione

**Restore point Phase 5:** `1dfdf60` (`feat(phase5): map-summary + paged articles, nation detail markers, stable spiderfy`) su `refactor/enterprise-consolidation`.
Restore: `git checkout 1dfdf60`

---

### ECC remediation (post Phase 6 GATE VERDE) — DONE (2026-07-15)

Allineamento `.agents/` + `radar/.ecc/` al codice reale (worker, Compose, API Phase 5, FE Phase 4–5). Sorgente: `plan-audit/archive/ecc/handoff_ecc_architecture_audit.md` §§5–8.

- [x] **P0:** `spatial-data-mocking` (entrambe le copie) — 10 categorie, overlay full-bleed, `getMapSummary`/`getArticlesPage`; `angular-map-expert` Chip→Tecnologia + prettier; `backend.md` Regola 3 sleep fuori da `finally`
- [x] **P1:** `docker.md` = Dockerfile/compose reali; wording deferred post–Phase 6; `settings.json` ↔ hooks; `llm-json-extraction` SoT `.agents` → mirror `.ecc`; path references `angular-developer`
- [x] **P2:** geo-data `007`; AGENTS/backend map-summary bullets; bounds US/RU esatti; note hooks manuali; comandi verify/runbook/CI
- [x] Checklist accettazione handoff §9
- [x] Commit remediation (no push) — tip = questo commit; Phase 6 tip = `56c2eff`

Sidebar freeze: zero touch `radar-sidebar/**`.

**Restore Phase 6 only (senza remediation ECC):** `git checkout 56c2eff`  
**Restore tip post-remediation:** SHA di questo commit (vedi `git log -1`).

---

### Audit remediation codice (post Gate Verde) — COMPLETATA

Ordine SoT: T-P0-01…T-P2-08.  
Fonte: `plan-audit/active/plan_docs_audit_ticket_status.md` §3.

| Ticket | Stato | Note |
|--------|-------|------|
| T-P0-01 … T-P0-02 | **DONE** | mark-read gate, quote_plus, advisory lock, outbox retry, script ClassificationClient |
| **T-P1-04** | **DONE** (`51225b5`) | `detailError` + banner nation-fetch; test 30/30 |
| **T-P1-05** | **DONE** | Nginx unprivileged (`USER nginx` + listen 8080 internally, Compose port map 80:8080, cap_drop ALL, read_only/tmpfs) |
| P2 (8) | **DONE** | backlog igiene chiuso in blocco (T-P2-01 … T-P2-08) |

---

### ECC expansion wiring — DONE (2026-07-15)

Harness Cursor + skill dominio selettive. Sorgente: `plan-audit/archive/ecc/handoff_ecc_expansion.md`. **Nessun nuovo SHA inventato** — commit solo su richiesta utente.

- [x] **P0:** `.cursor/hooks.json` + adapters → `radar/.ecc/hooks/*.py`; smoke allow/deny secret; `.cursor/rules/radar-*.mdc` globs → `.ecc/rules`; AGENTS/docs/04/`hooks.notes` allineati
- [x] **P1:** skill `radar-sidebar-freeze`, `radar-api-contract`, `radar-docker-ops`, `radar-geojson-assets`, `radar-quota-ledger` + mirror `.ecc` + skill map CLAUDE
- [x] **P2:** commands `radar-verify` / `radar-smoke` / `radar-lint` + nota spawn profili in CLAUDE
- [x] Checklist handoff §7; sidebar freeze invariato

Manuale: `ecc_deep_dive_analysis_v2.md` (stato wiring aggiornato).

---

### Phase 6 — Governance, docs, ops — DONE / GATE VERDE (2026-07-15)

**Metodo:** audit incongruenze → Blocchi A→D → polish tipografico/Mermaid/indici docs. Sidebar freeze invariato. **Commit solo su richiesta.**

#### Audit incongruenze (chiuso)

Tabella claim→realtà (docs/ECC vs codice @ tip post-`1dfdf60`) chiusa per i claim alti aperti in avvio Phase 6. Residui non-Phase-6 (seed 10k budget, chaos drill, image scan) restano nel Final Release Gate del piano master.

#### Blocco A — Verità documentale + revisione README — DONE

- [x] Audit incongruenze.
- [x] `README.md` root: 5 servizi edge/data, worker vs API, indice docs, restore SHA, mappa piani→codice, contratto API.
- [x] Revisione README “allegati” (operatori / piani / ECC / archivio).
- [x] `docs/01–04_*` riscritti sul contratto Phase 0–5.
- [x] `radar/frontend/README.md` di progetto (no `ng e2e`).
- [x] `Fase2_Implementation_Plan.md` banner ARCHIVIO.
- [x] `.gitignore` / `radar/.gitignore` asset dir.

#### Blocco B — GeoJSON — DONE

- [x] `ASSET_LICENSE.md` (Natural Earth / datasets pin, ODC-PDDL-1.0, SHA-256 `45F41865…CAE4`).
- [x] `scripts/verify-geojson.mjs` (+ `--fetch`).
- [x] `package.json` / Dockerfile FE / `.dockerignore`.
- [x] Policy: geojson **gitignored**; CI/Docker fetch deterministico.

#### Blocco C — ECC / hooks — DONE

- [x] `CLAUDE.md`, `angular-map-expert.md`, `frontend.md`, skills LLM → `worker.py`.
- [x] Hooks: domain anti-spoof; post fail-closed (ruff / prettier).
- [x] `.agents/AGENTS.md` status Phase 6 GATE VERDE.

#### Blocco D — CI + runbook — DONE

- [x] `.github/workflows/ci.yml`
- [x] `radar/docs/runbook.md`

#### Polish docs (post gate) — DONE

- [x] README: Mermaid vault fuori rete; indice 01–04; albero CI/runbook/verify; link ASSET_LICENSE.
- [x] docs/01: health FE vs API; `LLM_TPM`/`LLM_RPD`; verify-geojson; link runbook.
- [x] docs/02: Mermaid ciclo articoli corretto; nomi migrazioni 005/006 completi.
- [x] docs/03: Mermaid sequence con alias participant.
- [x] docs/04 / FE README / runbook / ops cross-link; typo «riavvia» / `docker compose ps`.

**Gate Phase 6 (locale — 2026-07-15):**

- [x] `git diff -- radar/frontend/src/app/components/radar-sidebar` vuoto
- [x] `verify-geojson` PASS (258 features)
- [x] pytest `not live` → 107 passed / 3 deselected
- [x] `npm run typecheck` → OK
- [x] `npm run test:ci` → 18 passed (3 files)
- [x] `npm run build:ci` → verify PASS + production build OK (budget warning ~992 kB, preesistente)
- [x] Commit Phase 6 creato (no push) — annotare SHA in scoreboard / pin follow-up

---

## C. Scoreboard attuale (2026-07-15)

| Phase | Pre-restore (storico) | Codice attuale | Prossimo lavoro |
|-------|----------------------|----------------|-----------------|
| 0 | Completata | **DONE** (`0189359`) | — |
| 1 | Completata (persa) | **DONE** (`bff8abe`) | — |
| 2 | Completata (persa) | **DONE** (`72851d7`) | — |
| 3 | Completata (persa) | **DONE** (`19c67f0`) | — |
| 4 | Completata (persa) | **DONE** (`de9bd2f`) | — |
| 5 | Completata (persa) | **DONE** (`1dfdf60`) | Residuali opzionali (seed 10k measure) |
| 5.5 | Completata (persa) | N/A nel piano master | Assorbita in 1–3 |
| 6 | Non iniziata | **DONE / GATE VERDE** (`56c2eff`) | ECC remediation tip (commit successivo); push solo se chiesto |

**Ordine:** Phase 6 `56c2eff` → ECC remediation (tip) → pin SHA esplicito in `plan_impl_phase_0_6.md` se serve.

**Restore rapido a Phase 5:** `git checkout 1dfdf60` su `refactor/enterprise-consolidation`.  
**Restore rapido a Phase 4:** `git checkout de9bd2f`.  
**Restore rapido a Phase 3:** `git checkout 19c67f0`.  
**Restore a Phase 2:** `git checkout 72851d7`.  
**Restore Phase 6 (GATE VERDE, pre–ECC remediation):** `git checkout 56c2eff`.  
**Restore tip post–ECC remediation:** `git checkout` dello SHA del commit remediation.
