# AGENTS.md — Radar Informativo Globale (ECC Native Guardrails)

Questo file definisce le regole operative globali, i vincoli architetturali e i guardrail per lo sviluppo del modulo Radar. Queste istruzioni sono immutabili e caricate nativamente ad ogni turno di chat.

---

## 1. Identità del Progetto & Stack Tecnologico

* **Nome:** Radar Informativo Globale (Intelligence Dashboard)
* **Obiettivo:** Applicazione web self-hosted, containerizzata e plug-and-play che aggrega feed RSS, li arricchisce semanticamente via LLM multi-provider (Gemini SDK e/o OpenAI-compat httpx) e li visualizza su una mappa 2D interattiva in stile Palantir (estetica scura, confini SVG nitidi, marker tematici per categoria geopolitica).

### Stack Tecnologico Ufficiale
* **Backend:** Python 3.12-slim (Docker) / 3.14 (locale). Demone asincrono con polling `WORKER_POLL_INTERVAL_SECONDS` (default 900).
* **LLM:** `google-genai` SDK + OpenAI-compat via httpx (`deepseek`/`openai`/`glm`/`grok`; no package `openai`); lane `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (limiti per-lane; soft-trim = `LLM_SIMPLE.rpd` se >0). **RPM/TPM pieni → attesa stessa lane; RPD/cooldown → residual cross-lane** (`QuotaDailyExceeded`). Dialect: deepseek=`thinking`; openai/glm/grok=stock (**Profilo F / Ollama reasoner:** `think=true` via `openai_compat_payload`; **vietato** SDK `ollama` / `ollama.chat`). `claude` = stub. Caps Studio Flash Lite tipici: RPM≤12 / TPM=250K / RPD=500. Ops: Profili **A–F** in `.env.example` (F = Local-Hybrid overlay `docker-compose.ollama-host.yml`) — non hardcodare chiavi.
* **Database:** PostgreSQL 15 (`radar-db`). Accesso tramite driver asincrono `asyncpg` puro.
* **Feed Source:** Miniflux REST API.
* **Frontend:** Angular 21 (Standalone Components).
* **Container:** Docker + docker-compose (servizi: `radar-db`, `radar-backend`, `radar-worker`, `radar-frontend`, `radar-miniflux`) su reti `radar-edge` + `radar-data` (Phase 3). Ingestione solo in `radar-worker`.
* **Web Server:** Nginx (Alpine) per servire Angular e proxying `/api/`.
* **Piani operativi:** [`plan_impl_phase_0_6.md`](../plan-audit/complete/plan_impl_phase_0_6.md) + [`plan_impl_phase_0_6_execution.md`](../plan-audit/complete/plan_impl_phase_0_6_execution.md). Post–branch restore (2026-07-15): **Phase 0–5 DONE**; Phase **6 DONE / GATE VERDE**. Final Release **F0–F4 COMPLETE** (2026-07-18; PR #1 merged); Fase 5 hardening **DEFERRED ACCETTATO** (non richiesto) — [`STATUS.md`](../plan-audit/STATUS.md).

---

## 2. Vincoli di Produzione Cruciali (Radar Specific)

> [!CRITICAL]
> ### ⛔ Sidebar freeze (non negoziabile)
> Non refactorare, restyle ampio o sostituire `radar/frontend/src/app/components/radar-sidebar/` (TS/HTML/SCSS/spec).
> Conservare `p-carousel` e `updateCarouselHeight` con `document.getElementById('article-card-' + id)`.
> Vietato introdurre `app-article-list`, infinite scroll o ResizeObserver “migliorativi” sul carosello.
> Bug **letta/non letta** (`.marker-read`) e logica **save**: fix in `state.service.ts` + `radar-map.component.ts` (sidebar solo delega click).
> **Eccezione mirata:** toggle **Salva / Rimuovi dai salvati** sulle card (binding `is_saved`) + sezione chip dei **paesi correlati** (`related_countries`) — vedi skill `radar-sidebar-freeze`.
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
   * Il loop di monitoraggio vive in `worker.py` (`while True` + `asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)`), cattura eccezioni a livello di ciclo/articolo, e **re-raise** `CancelledError`. Lo sleep di polling non sta in un `finally` di shutdown.
3. **Deduplicazione Pre-LLM:**
   * Controllare sempre l'esistenza dell'URL dell'articolo nel DB via query SQL prima di effettuare la chiamata all'LLM per ottimizzare i costi API.
4. **Gestione Errori a Tre Livelli:**
   * *Livello 1:* Demone principale (non deve morire).
   * *Livello 2:* Ciclo completo della pipeline (se fallisce un ciclo, il successivo parte).
   * *Livello 3:* Elaborazione del singolo articolo (se un articolo fallisce, si passa al successivo con log di warning/error).
5. **Type Hints & Logging:**
   * Type hints obbligatori su tutte le funzioni pubbliche.
   * Utilizzare il logger centralizzato configurato in `core/logging.py`, evitando categoricamente l'uso di `print()`.
6. **Rate Limiting & Rispetto delle Quote LLM:**
   * Quote durable via `llm_request_ledger` + `classification/quota.py` (reserve RPM/TPM/RPD **prima di ogni** tentativo provider, anche retry). Limiti **per lane**: `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (`0` = unmanaged). Legacy `LLM_RPM` / `DEEPSEEK_RPM` = alias fill-gap, non tetto globale. Soft-trim worker = solo `LLM_SIMPLE.rpd` se `> 0` — **bypass ibernazione** se residual COMPLEX distinto (failover per-articolo). **RPM/TPM pieni → sleep stessa lane**; **RPD esaurita → `QuotaDailyExceeded` + cooldown + residual altra lane**. Free → RPM/RPD(+TPM); paid → `*_BUDGET_USD_DAY` / 402. Spacing in-process con `time.monotonic()`; finestre giornaliere half-open su `RADAR_TIME_ZONE`. Rispettare `429` + `Retry-After`.
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
> ### ⚠️ Leaflet + ESBuild: Pattern di Importazione Obbligatorio
> `leaflet.markercluster` è una libreria UMD che richiede `window.L`. Con Angular 21 + ESBuild
> (`@angular/build:application`), un `import 'leaflet.markercluster'` come side-effect import
> in un componente TypeScript crea un namespace Leaflet **separato** che non si aggancia al plugin.
> **Soluzione:** caricare Leaflet e MarkerCluster come script globali in `angular.json` → `scripts[]`
> e accedere via `const L = (window as any).L` nel componente.
> Mai usare `import * as L from 'leaflet'` o `import 'leaflet.markercluster'` nei componenti.

> [!NOTE]
> ### 🗺️ Regole di Visualizzazione Mappa e Clustering
> 1. **Clustering per categoria**: un `L.markerClusterGroup` **per** `primary_category` raggruppa spazialmente gli articoli. Per forzare il corretto raggruppamento spaziale per nazione senza mostrare punti reali ridondanti, vengono impiegati marker invisibili (`isDummy: true`). Day-view: pin nazione da map-summary (non pallini per-categoria).
> 2. **Impostazioni MarkerCluster e Spiderfy Custom**: Il raggio di clusterizzazione è stretto (`maxClusterRadius: 40`). Lo spiderfy automatico è disabilitato (`spiderfyOnMaxZoom: false`). La frammentazione dei cluster avviene tramite una logica custom (click e flyTo allo zoom 6). Non “allineare” a valori legacy 200/true.
> 3. **Hub disco + fan emoji**: nation open usa hub compatto (`radar-spider-root`) e spiderfy emoji della categoria attiva (tutte le icone della categoria; size/distanza adattivi). Il root non deve sparire al cambio categoria (`unspiderfied` no-op se `restoreDetailHubOnUnspiderfy === false`). In caso di fallimento spiderfy, ripristinare sempre l’hub nazione. Con spider aperto: **non** auto-unspiderfy MarkerCluster su wheel/zoom; tenere fan + sidebar finché zoom ≥ 5; a zoom &lt; 5 (hatching) chiudere fan e sidebar (`collapseAllGraphs(true)` + `lastSpiderfy*`); su `zoomend` ≥ 5 re-spiderfy deferito per riallineare le gambe.
> 4. **Estensione Bounding Box per Stati Trans-Antimeridiano**: Nel calcolo dello zoom di focus per nazioni con territori oltre la linea di cambio data (Stati Uniti `US` e Russia `RU`), per garantire la validità del bounding box ed evitare comportamenti bloccanti, utilizzare bounding box statici Mainland hardcoded:
>    * `US`: `L.latLngBounds(L.latLng(24.396308, -125.0), L.latLng(49.384358, -66.93457))`
>    * `RU`: `L.latLngBounds(L.latLng(41.1856, 19.6389), L.latLng(81.8587, 169.0))`
> 5. **Legenda Colori**: Inserire una legenda glassmorphic orizzontale in assoluto in basso al centro della mappa (`bottom: 20px; left: 50%`) che mostri cerchi luminosi (`box-shadow` del colore di categoria) affiancati alle emoji e ai nomi delle categorie geopolitiche.
> 6. **Limitazioni Zoom Mappa**: Impedire lo zoom all'indietro infinito e lo scroll laterale al di fuori della terraferma configurando `minZoom: 2.2`, `maxBounds` impostati sui limiti del globo terrestre (`[-85, -180]` a `[85, 180]`) e `maxBoundsViscosity: 1.0`.
> 7. **Click e Zoom di Focus**: pin summary → `preserveZoom` (no fitBounds); poligono/toolbar → `fitBounds` con `maxZoom: 4`; ri-selezione stesso paese → `refocusCountry`. Zoom &lt; 5 (hatching): click nazione via map-click + `pickCountryCodeAt` (il canvas `relationsPane` blocca i click SVG). Hub/pin/spider e archi condividono l’anchor nazione (`getCountryCentroid`: US/RU mainland hardcoded) — **non** mediare lat/lng articolo (teatro estero sposterebbe il pallino in oceano).
> 8. **Gestione Dinamica Altezza Carosello**: Il ridimensionamento dinamico dell'altezza delle schede nel carosello laterale DEVE essere calcolato estraendo l'ID univoco dell'articolo corrente (`document.getElementById('article-card-' + id)`) anziché affidarsi alla classe `.p-carousel-item-active` di PrimeNG, la quale introduce race-condition nel DOM al primo avvio.
> 9. **Allineamento Flexbox e Troncamento Fonti**: Le sezioni di metadati contenenti stringhe potenzialmente lunghe (es. la fonte dell'articolo) e bottoni affiancati (es. `Leggi fonte →`) devono impiegare rigorosamente layout *Flexbox* (`flex: 1`, `min-width: 0` per il contenitore di testo e `flex-shrink: 0`, `white-space: nowrap` per il link).
> 10. **Pulizia Prefisso Feed**: I titoli dei feed provenienti da Miniflux devono essere processati in Angular tramite Regex (es. `.replace(/^Feed:\s*/i, '')`) per rimuovere la dicitura automatica "Feed: " prima del rendering.
> 11. **API Phase 5+:** day view via `GET /api/map-summary`; relations via `GET /api/map-relations` (archi Leaflet: pane `relationsPane`, click → carosello bilaterale); saved vault via `GET /api/saved-summary` (no date); nation open via `GET /api/articles` con envelope `{ items, next_cursor, total }` (page ≤ 100; FE concatena); saved open via `?saved=true` (ignora date). Mock solo con `MOCK_MODE`.
> 12. **Overlay full-bleed:** mappa sempre `100vw`; sidebar sopra — non split 70%/30% che restringe la mappa; `invalidateSize()` dopo open/close.
> 13. **Errori API / nation-fetch (T-P1-04):** `StateService.error` = `mapSummaryResource.error() ?? savedSummaryResource.error() ?? detailError()`. Fallimento `loadCountryArticles` / `loadSavedCountryArticles` → `detailError` + `closeSidebar(false)` (banner toolbar resta). Close utente → clear errore. Vietato fallback silenzioso a mock.
> 14. **Notizie Salvate:** contatore toolbar date-agnostic; tooltip nazioni; carosello multi-day in `sidebarMode='saved'`; click nazione = stesso path di LETTE/TROVATE (`fitBounds` + `flyTo` 6 + spiderfy); save ⇒ read; unread ⇒ unsave.

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

