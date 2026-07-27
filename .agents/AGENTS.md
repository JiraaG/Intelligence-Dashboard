# AGENTS.md — Radar Informativo Globale (ECC Native Guardrails)

Questo file definisce le regole operative globali, i vincoli architetturali e i guardrail per lo sviluppo del modulo Radar. Queste istruzioni sono immutabili e caricate nativamente ad ogni turno di chat.

---

## 1. Identità del Progetto & Stack Tecnologico

* **Nome:** Radar Informativo Globale (Intelligence Dashboard)
* **Obiettivo:** Applicazione web self-hosted, containerizzata e plug-and-play che aggrega feed RSS, li arricchisce semanticamente via LLM multi-provider (Gemini SDK e/o OpenAI-compat httpx) e li visualizza su una mappa **MapLibre** 3D-primary (globo; mercator+pitch contingency) in stile Palantir (estetica scura, confini nitidi, marker tematici per categoria geopolitica). Leaflet resta dormiente (LEGACY FREEZE) dietro `MAP_RENDERER`.

### Stack Tecnologico Ufficiale
* **Backend:** Python 3.12-slim (Docker) / 3.14 (locale). Demone asincrono: wake webhook/NOTIFY + eager drain-until-empty (settle `WORKER_REFRESH_SETTLE_SECONDS`); `WORKER_POLL_INTERVAL_SECONDS` (default 900) = safety net a coda vuota.
* **LLM:** `google-genai` SDK + OpenAI-compat via httpx (`deepseek`/`openai`/`glm`/`grok`; no package `openai`); lane `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (limiti per-lane + contatori per-model; soft-trim su catena SIMPLE se >0; override CSV `*_MODEL_LIMITS`). BORDERLINE: stessa catena COMPLEX con effort da `LLM_BORDERLINE_REASONING_EFFORT` (default safe `high`, target ops `none` + escalate `high` su ValidationError). **RPM/TPM pieni → attesa stessa lane; RPD/cooldown → failover L1 / residual cross-lane** (`QuotaDailyExceeded`). Dialect: deepseek=`thinking`; openai/glm/grok=stock (**Profilo F / Ollama reasoner:** `think=true` via `openai_compat_payload`; VRAM unload `ollama_lifecycle` + `OLLAMA_*`; **vietato** SDK `ollama` / `ollama.chat`). `claude` = stub. Caps Studio Flash Lite tipici: RPM≤12 / TPM=250K / RPD=500. Ops: Profili **A–F** in `.env.example` (F = Local-Hybrid overlay `docker-compose.ollama-host.yml`) — non hardcodare chiavi.
* **Database:** PostgreSQL 15 con estensione `pgvector` (`pgvector/pgvector:0.8.0-pg15`). Accesso tramite driver asincrono `asyncpg` puro.
* **Feed Source:** Miniflux REST API.
* **Frontend:** Angular 21 (Standalone Components).
* **Mappa:** MapLibre GL 5.24 (default) — facade `radar-map.component.ts` + host `maplibre/`; Leaflet 1.9 + MarkerCluster solo path legacy (`MAP_RENDERER=leaflet`, host `leaflet/`, LEGACY FREEZE). Token `services/map-renderer.token.ts`. Proiezione: `localStorage` `radar.mapProjection` = `globe`|`mercator`. Gate: `npm run verify-map-renderer`.
* **Container:** Docker + docker-compose (servizi: `radar-db`, `radar-backend`, `radar-worker`, `radar-frontend`, `radar-miniflux`) su reti `radar-edge` + `radar-data` (Phase 3). Ingestione solo in `radar-worker`.
* **Web Server:** Nginx (Alpine) per servire Angular e proxying `/api/`.
* **Piani operativi:** [`plan_impl_phase_0_6.md`](../plan-audit/complete/plan_impl_phase_0_6.md) + [`plan_impl_phase_0_6_execution.md`](../plan-audit/complete/plan_impl_phase_0_6_execution.md). Post–branch restore (2026-07-15): **Phase 0–5 DONE**; Phase **6 DONE / GATE VERDE**. Final Release **F0–F4 COMPLETE** (2026-07-18; PR #1 merged); Fase C Deduplicazione Semantica **DONE / GATE VERDE** (2026-07-22; `012_pgvector_article_embeddings.sql`); FinOps UI Metrics & Eager Drain **DONE / GATE VERDE** (2026-07-24); Fix STATUS Real-Time SSE **DONE / GATE VERDE** (2026-07-25); Distinzione BORDERLINE Carosello & Migration 017 **DONE / GATE VERDE** (2026-07-25); **FONTI feed management COMPLETE / GATE VERDE** (2026-07-27; topbar FONTI Giorno+Catalogo, `/api/feeds`, by-feed `date_field`); Fase 5 hardening **DEFERRED ACCETTATO** (non richiesto) — [`STATUS.md`](../plan-audit/STATUS.md). MapLibre 3D-primary: [`plan_impl_map_3d_globe.md`](../plan-audit/active/plan_impl_map_3d_globe.md) (+ globo J: [`plan_impl_map_globe_projection.md`](../plan-audit/active/plan_impl_map_globe_projection.md)).


---

## 2. Vincoli di Produzione Cruciali (Radar Specific)

> [!CRITICAL]
> ### ⛔ Sidebar freeze (non negoziabile)
> Non refactorare, restyle ampio o sostituire `radar/frontend/src/app/components/radar-sidebar/` (TS/HTML/SCSS/spec).
> Conservare `p-carousel` e `updateCarouselHeight` con `document.getElementById('article-card-' + id)`.
> Vietato introdurre `app-article-list`, infinite scroll o ResizeObserver “migliorativi” sul carosello.
> Bug **letta/non letta** (`.marker-read`) e logica **save**: fix in `state.service.ts` + `radar-map.component.ts` (sidebar solo delega click).
> **Eccezione mirata:** toggle **Salva / Rimuovi dai salvati** sulle card (binding `is_saved`) + sezione chip dei **paesi correlati** (`related_countries`) + blocco **ANALISI FINOPS & FONTE RSS** dopo Tag — vedi skill `radar-sidebar-freeze`.
> **Phase 4 DONE:** `MOCK_MODE` esplicito (no fallback silenzioso), marker XSS-safe, DestroyRef, fingerprint geometry (no rebuild cluster su solo `is_read`).
> **Notizie Salvate:** vault cross-day (`is_saved`, `/api/saved-summary`, `GET /api/articles?saved=true`); save ⇒ read; unread ⇒ unsave; click nazione = fitBounds + flyTo 6 + spiderfy (parity LETTE/TROVATE).

> [!CRITICAL]
> ### ⛔ Divieto Assoluto di Placeholder o "TODO"
> Il codice di produzione deve essere completo, tipizzato tramite Type Hinting, testato e privo di commenti `TODO`, `FIXME`, `HACK`, blocchi `pass` senza codice o sollevamenti di `NotImplementedError`. Ogni riga di codice deve essere pronta per il deployment.
>
> ### ⛔ Obbligo asyncpg Puro (No ORM / No SQLAlchemy)
> Tutte le interazioni con il database PostgreSQL devono avvenire tramite query SQL pure eseguite in modo asincrono con `asyncpg`. È severamente vietato l'uso di SQLAlchemy o altri ORM per garantire la massima efficienza e aderenza alle specifiche tecniche del modulo Radar.
>
> ### ⛔ Purgazione Rigida dei Tag Multimediali nel Parser
> Il modulo `extraction/parser.py` deve eliminare categoricamente tutti i tag HTML e purgare interamente i tag multimediali (`<img>`, `<video>`, `<audio>`, `<noscript>`, `<meta>`) e tutti i loro attributi (es. `src`, `href`, `style`, `alt`) per ottimizzare rigorosamente il consumo dei token dell'LLM.
>
> ### ⛔ Percorso di Fallback del Vault Obsidian
> Il percorso predefinito di fallback per l'inizializzazione del Vault di Obsidian deve essere impostato esplicitamente su `/app/vault`.

---

## 3. Regole di Codifica Backend (Path-Scope: `backend/**`)

1. **Versionamento Dipendenze (requirements.txt):**
   * Non bloccare mai le dipendenze con operatori `==`. Usare sempre `>=` per garantire compatibilità con Python 3.14 su sistemi Windows (es. `asyncpg>=0.31.0`, `pydantic>=2.10.0`).
2. **Il Demone Non Si Ferma Mai:**
   * Il loop di monitoraggio vive in `worker.py` (webhook/NOTIFY = wake primario; eager drain-until-empty all’avvio e post-wake con settle `WORKER_REFRESH_SETTLE_SECONDS`; `_wait_interval(WORKER_POLL_INTERVAL_SECONDS)` = safety net a coda vuota), cattura eccezioni a livello di ciclo/articolo, e **re-raise** `CancelledError`. L'attesa di polling non sta in un `finally` di shutdown.
3. **Deduplicazione Pre-LLM:**
   * Controllare sempre l'esistenza dell'URL dell'articolo nel DB via query SQL prima di effettuare la chiamata all'LLM per ottimizzare i costi API.
   * In aggiunta: (1) content hash pre-embed (`CONTENT_HASH_DEDUP_*`, `articles.content_sha256` / migrazione `014`); (2) dedup **semantica** via embeddings + `pgvector` (`SEMANTIC_DEDUP_*`); (3) high-sim direct bypass (`SEMANTIC_DEDUP_DIRECT_*`) keep/replace senza compare; (4) near-dup residuo → **1×** `quality:compare` su lane **COMPLEX** (effort `none`) decide keep vs replace in-place.
4. **Gestione Errori a Tre Livelli:**
   * *Livello 1:* Demone principale (non deve morire).
   * *Livello 2:* Ciclo completo della pipeline (se fallisce un ciclo, il successivo parte).
   * *Livello 3:* Elaborazione del singolo articolo (se un articolo fallisce, si passa al successivo con log di warning/error).
5. **Type Hints & Logging:**
   * Type hints obbligatori su tutte le funzioni pubbliche.
   * Utilizzare il logger centralizzato configurato in `core/logging.py`, evitando categoricamente l'uso di `print()`.
6. **Rate Limiting & Rispetto delle Quote LLM:**
   * Quote durable via `llm_request_ledger` + `classification/quota.py` (reserve RPM/TPM/RPD **prima di ogni** tentativo provider, anche retry). Limiti **per-lane e contatori per-modello**: `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (`0` = unmanaged; override CSV `*_MODEL_LIMITS`). BORDERLINE reasoning effort da `LLM_BORDERLINE_REASONING_EFFORT` (default safe `high`, target ops `none` con escalate `high` su `ValidationError`). Legacy `LLM_RPM` / `DEEPSEEK_RPM` = alias fill-gap, non tetto globale. Soft-trim worker = residuo catena SIMPLE — **bypass ibernazione** se residual COMPLEX distinto (failover per-articolo). **RPM/TPM pieni → sleep stessa lane**; **RPD esaurita su un modello → `QuotaDailyExceeded` + cooldown + failover L1 / residual altra lane**. Free → RPM/RPD(+TPM); paid → `*_BUDGET_USD_DAY` / 402. Spacing in-process con `time.monotonic()` per lane; finestre giornaliere half-open su `RADAR_TIME_ZONE`. Rispettare `429` + `Retry-After`.
7. **Architettura Modulare Backend (Path: `backend/app/`):**
   * Layer: `core/`, `extraction/`, `classification/` (incluso `quota.py`), `commit/`, più `worker.py` (ingest) separato da `main.py` (API).
   * `core/logging.py`: il `RotatingFileHandler` e `makedirs` per `logs/` DEVONO essere in `try/except` — il container non-root con `WORKDIR=/app` può non avere permessi. Il fallback deve mantenere attivo il console handler.

---

## 4. Regole di Containerizzazione (Docker & Compose)

1. **Nomi dei Servizi Immutabili:** `radar-db`, `radar-backend`, `radar-worker`, `radar-frontend`, `radar-miniflux`.
2. **Persistenza Dati:** PostgreSQL deve utilizzare un volume named bind-mounted locale (`./data/postgres`).
3. **Isolamento di Rete (Phase 3):** reti `radar-edge` (frontend ↔ backend) e `radar-data` (backend, worker, db, miniflux). Il frontend **non** sta su `radar-data`. Default plug-and-play: FE `80:8080 (tutte le interfacce)`; Miniflux **senza** porte host. Loopback: `docker-compose.hardened.yml`. Admin Miniflux LAN: `docker-compose.lan.yml`.
4. **Healthcheck & depends_on:** Compose healthcheck API = `GET /health/live` (non `/health/ready`). Frontend `depends_on` backend healthy (= live). Worker attende db + Miniflux healthy. Readiness (`/health/ready`: pool, migrazioni, heartbeat) è ops-only e non deve restartare l'API. **Nota:** `depends_on` healthy vale per `up`, non per `compose restart` parallelo → preferire `up -d` o restart ordinato; vedi `docker.md` Regola 4 / `CannotConnectNowError`.
5. **Password e Sicurezza:** 
   * Le credenziali reali vivono esclusivamente nel file `.env` (ignorato da Git).
   * È vietato l'uso del carattere `$` all'interno del valore delle password in quanto Docker Compose lo interpreta come interpolazione di variabili.
   * Ciascun Dockerfile deve contenere file `.dockerignore` per non includere cache locali o cartelle pesanti (`node_modules`, `.venv`).
6. **Workflow di Compilazione Frontend (Multi-Stage Build):**
   * Il Dockerfile del frontend DEVE utilizzare un approccio multi-stage per garantire una distribuzione totalmente plug-and-play. La fase `builder` (basata su `node`) compilerà il codice, mentre la fase finale copierà solo la cartella `dist/` compilata all'interno del web server Nginx. L'utente finale non dovrà mai installare Node.js né eseguire `npm run build` manualmente. Qualsiasi modifica al codice Angular del frontend richiede unicamente la ricostruzione del container (`docker compose up --build -d radar-frontend`) affinché Nginx possa servire la versione aggiornata.
7. **Risoluzione DNS Dinamica in Nginx (Prevenzione 502 Bad Gateway):**
   * Per evitare errori `502 Bad Gateway` a seguito di riavvii dei container o riassegnazioni di IP nella rete bridge, `nginx.conf` deve utilizzare un resolver interno (`resolver 127.0.0.11 valid=10s;`) ed una variabile locale per il `proxy_pass` (es. `set $backend_upstream http://radar-backend:8000; proxy_pass $backend_upstream$request_uri;`). Questo costringe Nginx a risolvere l'IP a runtime anziché solo all'avvio.
8. **Riproducibilità Frontend (`npm ci`):**
   * Nel `Dockerfile` del frontend Angular, l'installazione delle dipendenze nello stage builder deve avvenire tramite `npm ci --legacy-peer-deps`. È vietato l'uso di `npm install`. Drop di `--legacy-peer-deps` = **deferred accettato (Final Release Fase 5)** — **non** obbligatorio per release; solo con matrix Angular/CDK/PrimeNG allineata e decisione esplicita.
9. **Sicurezza Immagini (No `latest`):**
   * È severamente vietato l'utilizzo del tag `latest` per le immagini di base nei `docker-compose.yml` e nei `Dockerfile` (es. `miniflux/miniflux:latest`). Le versioni devono sempre essere bloccate (pinnate) a una major/minor specifica (es. `2.3.2`) per prevenire rotture distruttive da aggiornamenti silenti. Digest SHA: **deferred accettato (Final Release Fase 5)** — **non** richiesto per il path ready-to-run.
10. **Coerenza Healthcheck (Alpine Linux):**
    * Gli script di healthcheck definiti nei Dockerfile e nel docker-compose devono utilizzare eseguibili realmente disponibili nell'immagine di base. Ad esempio, per immagini basate su Alpine (come Nginx), è obbligatorio usare `wget` invece di `curl` per evitare che il container venga marchiato costantemente come `unhealthy`.
11. **CORS:** default allowlist vuota (same-origin via Nginx). Mai `allow_origins=["*"]`. Dev diretto: `CORS_ALLOW_ORIGINS=http://localhost:4200`.
12. **Ops:** backup/restore in `radar/ops/`; vedi `ops/README.md`.
13. **Phase 6 ops/CI:** `radar/frontend/scripts/verify-geojson.mjs` (+ `--fetch` in Docker FE); runbook `radar/docs/runbook.md`; CI `.github/workflows/ci.yml`.

---

## 5. Vincoli Frontend Angular 21

> [!WARNING]
> ### ⚠️ MapLibre primary + Leaflet legacy (ESBuild)
> **Default:** MapLibre GL (`radar-map/maplibre/`) via facade `radar-map.component.ts` + token `MAP_RENDERER` (`map-renderer.token.ts`; default `maplibre`). Gate: `npm run verify-map-renderer`.
> **Spiderfy path MapLibre:** fan custom HTML markers — **senza** MarkerCluster; n &lt; 9 cerchio, n ≥ 9 **spirale** (algoritmo MarkerCluster, offset in pixel).
> **Overlay:** dopo open/close sidebar → `map.resize()` (MapLibre). Legacy Leaflet: `invalidateSize()`.
> **Leaflet dormiente:** host `radar-map/leaflet/` (LEGACY FREEZE). `leaflet.markercluster` richiede `window.L`: caricare Leaflet e MarkerCluster come script globali in `angular.json` → `scripts[]` **solo per il path legacy**; accedere via `const L = (window as any).L`. Mai `import * as L from 'leaflet'` o `import 'leaflet.markercluster'` nei componenti.

> [!NOTE]
> ### 🗺️ Regole di Visualizzazione Mappa e Clustering
> 1. **Day-view / nation:** day-view = pin nazione da map-summary; nation open = hub `radar-spider-root` + spiderfy emoji della categoria attiva. Path MapLibre: spiderfy custom (no MC). Path Leaflet legacy: un `L.markerClusterGroup` **per** `primary_category` con marker invisibili (`isDummy: true`) dove ancora usati.
> 2. **Spiderfy policy (parity):** keep fan + sidebar finché **`pinModeActive`** (enter ≥ `MAP_ZOOM_PIN_THRESHOLD` **4**, exit &lt; **3.6** via `resolvePinMode` / isteresi — no flicker pan globo); latch hatching → chiudere fan e sidebar. Path MapLibre: **non** emettere `clusterClicked` da `spiderfyAndCreateRoot` (solo `[]` su collapse — altrimenti App riscrive carousel + auto-read). Path Leaflet: `maxClusterRadius: 40`, `spiderfyOnMaxZoom: false`; non auto-unspiderfy MC su wheel/zoom; su `zoomend` in pin mode re-spiderfy deferito.
> 3. **Hub disco + fan emoji**: tutte le icone della categoria attiva (size/distanza adattivi). Path Leaflet: root non deve sparire al cambio categoria (`unspiderfied` no-op se `restoreDetailHubOnUnspiderfy === false`); in caso di fallimento spiderfy, ripristinare sempre l’hub nazione.
> 4. **Estensione Bounding Box per Stati Trans-Antimeridiano**: Nel calcolo dello zoom di focus per nazioni con territori oltre la linea di cambio data (Stati Uniti `US` e Russia `RU`), utilizzare bounding box statici Mainland hardcoded (stesse costanti su MapLibre e Leaflet).
> 5. **Legenda Tipologie (Popover Grid 3 Colonne A-Z & Evidenziazione Mappa)**: Inserire un pulsante trigger compatto `🏷️ LEGENDA TIPOLOGIE 15` (o `N/15` se attiva un'evidenziazione bloccata) in basso al centro della mappa (`bottom: 20px; left: 50%`) che apre un popover glassmorphic in griglia a 3 colonne per tutte le 15 tipologie geopolitiche ordinate alfabeticamente A-Z (Ambiente 🌿 a Tecnologia 💻). Ogni card presenta il dot del colore tematico, l'emoji, la label ed il badge delle notizie disponibili `(14)`. Layout fluido con troncamento etichetta e badge `(14)` non clippato. L'hover o la selezione cliccata su una o più card illumina le rispettive campiture sulla mappa (`fill-opacity` = `0.85`) mantenendo le tipologie non selezionate alla loro opacità e tinta standard (`0.34`), senza oscurarle. All'avvicinamento/zoom in modalità marker (zoom >= 4 / `pinModeActive`), la legenda si chiude automaticamente. Il filtraggio effettivo dei dati articoli resta in toolbar nel selettore Tipologia.
> 6. **Limitazioni Zoom Mappa**: `minZoom: 2.2`. Path **Leaflet** legacy: `maxBounds` mondo + viscosity. Path **MapLibre globe**: **non** impostare `maxBounds` (clampa/blocca la rotazione) — solo `minZoom` + `renderWorldCopies: false`. Contingency mercator: `radar.mapProjection=mercator`.
> 7. **Click vs drag (MapLibre):** `clickTolerance: 12`; sopprimere country/relation click dopo `dragstart` / `rotatestart` / `pitchstart` / `map.isMoving()`.
> 8. **Centroidi MultiPolygon:** largest-area polygon + hardcode **US / RU / NL** mainland (Natural Earth NL → Caraibi altrimenti mid-Atlantic).
> 9. **Hatching day-view (latch hatching, enter/exit via `MAP_ZOOM_PIN_THRESHOLD=4` + isteresi 0.4):** path **MapLibre** = fasce soft O→E (1 colore × tipologia da `map-summary`; mainland US/RU; isole ≥0.5% area largest; clip terra∩strip via `polygon-clipping`; helper `maplibre/country-category-fills.ts`) — **non** `fill-pattern` barcode. Path **Leaflet** legacy = SVG combo pattern. Click nazione = `pickCountryCodeAt`.
> 10. **CSP Nginx:** `connect-src` / `img-src` = apex `https://basemaps.cartocdn.com` **e** `https://*.basemaps.cartocdn.com`; `worker-src`/`child-src` `blob:` per MapLibre workers.
> 11. **Click e Zoom di Focus**: pin summary → `preserveZoom` (no fitBounds); poligono/toolbar → `fitBounds` con `maxZoom: 4`; ri-selezione stesso paese → `refocusCountry`. Latch hatching: click nazione via map-click + `pickCountryCodeAt`. Hub/pin/spider e archi condividono l’anchor nazione (`getCountryCentroid`) — **non** mediare lat/lng articolo.
> 12. **Gestione Dinamica Altezza Carosello**: Il ridimensionamento dinamico dell'altezza delle schede nel carosello laterale DEVE essere calcolato estraendo l'ID univoco dell'articolo corrente (`document.getElementById('article-card-' + id)`) anziché affidarsi alla classe `.p-carousel-item-active` di PrimeNG, la quale introduce race-condition nel DOM al primo avvio.
> 13. **Allineamento Flexbox e Troncamento Fonti**: Le sezioni di metadati contenenti stringhe potenzialmente lunghe (es. la fonte dell'articolo) e bottoni affiancati (es. `Leggi fonte →`) devono impiegare rigorosamente layout *Flexbox* (`flex: 1`, `min-width: 0` per il contenitore di testo e `flex-shrink: 0`, `white-space: nowrap` per il link).
> 14. **Pulizia Prefisso Feed**: I titoli dei feed provenienti da Miniflux devono essere processati in Angular tramite Regex (es. `.replace(/^Feed:\s*/i, '')`) per rimuovere la dicitura automatica "Feed: " prima del rendering.
> 15. **API Phase 5+:** day view via `GET /api/map-summary`; relations via `GET /api/map-relations` (restituisce `source_country`, `target_country`, `primary_category`, `volume`, `article_ids`; archi MapLibre = macro multicolore solida; hover evidenzia tutte le linee collegate alla medesima notizia multi-paese; FE filtra con toolbar **RELAZIONI ATTIVE** → `visibleMapRelations`, default 0 archi; legacy Leaflet `relationsPane` = dash+fan ≥4; click → carosello bilaterale); saved vault via `GET /api/saved-summary` (no date); nation open via `GET /api/articles` con envelope `{ items, next_cursor, total }` (page ≤ 100; FE concatena); saved open via `?saved=true` (ignora date). Mock solo con `MOCK_MODE`.
> 16. **Overlay full-bleed:** mappa sempre `100vw`; sidebar sopra — non split 70%/30% che restringe la mappa; `map.resize()` (MapLibre) / `invalidateSize()` (Leaflet) dopo open/close.
> 17. **Errori API / nation-fetch (T-P1-04):** `StateService.error` = `mapSummaryResource.error() ?? savedSummaryResource.error() ?? detailError()`. Fallimento `loadCountryArticles` / `loadSavedCountryArticles` → `detailError` + `closeSidebar(false)` (banner toolbar resta). Close utente → clear errore. Vietato fallback silenzioso a mock.
> 18. **Notizie Salvate:** contatore toolbar date-agnostic; tooltip nazioni; carosello multi-day in `sidebarMode='saved'`; click nazione = stesso path di LETTE/TROVATE (`fitBounds` + `flyTo` 6 + spiderfy); save ⇒ read; unread ⇒ unsave.

---

## 6. Gestione Repository e Vault (Git)

> [!IMPORTANT]
> ### ⛔ Regole di Esclusione Vault
> La cartella radice `vault/` deve essere tracciata su Git unicamente tramite il file `.gitkeep`.
> Qualsiasi file markdown (`.md`) o sottocartella generata per categoria o nazione DEVE essere ignorato inserendo `vault/*` e `!vault/.gitkeep` all'interno del file `.gitignore` globale. 
> Non è necessario spingere la struttura ad albero su Git, in quanto il modulo di backend (`router.py`) si occupa di ricreare dinamicamente (`os.makedirs`) tutte le categorie e sottocartelle all'arrivo del primo articolo.

> [!IMPORTANT]
> ### Hook Cursor (auto) + fallback manuale
> **Default:** `.cursor/hooks.json` invoca adapter sottili in `.cursor/hooks/*-adapter.py` che delegano a `radar/.ecc/hooks/pre-tool-use.py` e `post-tool-use.py` (`preToolUse`, `postToolUse`, `afterFileEdit`). La logica security/lint resta solo in `radar/.ecc/hooks/*.py`.
> **Fallback manuale** (harness senza auto-hook, debug, CI locale):
> 1. **Pre-Tool-Use Scan:** [pre-tool-use.py](../radar/.ecc/hooks/pre-tool-use.py) — secret, path vietati, comandi pericolosi, domain whitelist.
> 2. **Post-Tool-Use Linting:** [post-tool-use.py](../radar/.ecc/hooks/post-tool-use.py) — ruff (`.py`), **prettier** (FE), placeholder soft-warn; fail-closed se il linter manca.

