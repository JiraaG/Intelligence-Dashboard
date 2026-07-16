# Checklist regole Frontend — Radar Informativo Globale

> **STORICO (checklist 2026-07-15):** FE-CL-04 «cap 24» / `SPIDERFY_MAX_ICONS` è **stale** rispetto al runtime 2026-07-16 (tutte le icone; no hard cap). Aggiornare solo dopo riverifica SoT: `radar/.ecc/rules/frontend.md`. Non riscrivere l’intero audit grezzo.

> **Scopo:** consolidamento di ogni requisito FE enforceabile dalle governance docs/skills.  
> **Non è un audit del codice** — solo regole da verificare.  
> **Linguaggio:** italiano (termini tecnici in English dove standard).  
> **Scope path tipico:** `radar/frontend/src/app/` (salvo dove indicato altrimenti).

**Fonti consultate:**
- `.agents/AGENTS.md` (sezioni FE)
- `radar/.ecc/rules/frontend.md`
- `radar/.ecc/agents/angular-map-expert.md`
- `.agents/skills/radar-sidebar-freeze/SKILL.md`
- `.agents/skills/spatial-data-mocking/SKILL.md`
- `.agents/skills/radar-api-contract/SKILL.md` (parti FE)
- `.agents/skills/angular-developer/SKILL.md` (vincoli Angular 21 rilevanti)
- `.agents/skills/radar-geojson-assets/SKILL.md` (asset FE)
- Mirror `radar/.ecc/skills/` — **nessun delta normativo** rispetto a `.agents/skills/` per sidebar-freeze, spatial-data-mocking, radar-api-contract; `angular-developer.md` ECC rimanda alle `references/` sotto `.agents/`

---

## 1. Sidebar freeze

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-SB-01 | `.agents/AGENTS.md`; `radar/.ecc/rules/frontend.md`; `.agents/skills/radar-sidebar-freeze/SKILL.md`; `radar/.ecc/agents/angular-map-expert.md` | **Zero touch** su `radar-sidebar/**`: vietato modificare, restyle, refactor o sostituire TS/HTML/SCSS/spec. | `components/radar-sidebar/**` | `git diff --stat -- radar/frontend/src/app/components/radar-sidebar` resta vuoto in ogni PR/task non esplicitamente autorizzato a scongelare. |
| FE-SB-02 | stessi | Conservare `p-carousel` come unico carosello notizie; **vietato** `app-article-list`, infinite scroll, list custom. | `components/radar-sidebar/**` (osservazione only); shell che monta sidebar | Template usa `p-carousel`; nessun selettore/componente `app-article-list` / `article-list` introdotto. |
| FE-SB-03 | `.agents/skills/radar-sidebar-freeze/SKILL.md`; `radar/.ecc/rules/frontend.md` | Vietato ResizeObserver “migliorativo” sul carosello o sostituzione del polling altezza esistente. | `components/radar-sidebar/**` | Nessun `ResizeObserver` sul carosello; logica altezza invariata. |
| FE-SB-04 | `radar/.ecc/rules/frontend.md`; `angular-map-expert.md` | Phase 4/5 UI (mappa, toolbar, state, shell) **non** passa dalla sidebar. | `components/radar-map/**`, `components/radar-toolbar/**`, `services/state.service.ts`, `app.*` | Diff FE esclusi da `radar-sidebar/**`. |
| FE-SB-05 | `spatial-data-mocking/SKILL.md` | Validazione carosello in **sola osservazione** — non editare sidebar per “sistemare” UX. | checklist QA / mock | Test visivi senza modifiche a `radar-sidebar/**`. |

**Conteggio dominio 1:** 5

---

## 2. Carousel PrimeNG + `updateCarouselHeight`

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-CR-01 | `.agents/AGENTS.md` §5.8; `radar-sidebar-freeze`; `frontend.md` CRITICAL | Altezza dinamica via `document.getElementById('article-card-' + id)` (pattern `article-card-{id}`). | `components/radar-sidebar/**` (freeze — non modificare); verificabile in codice esistente | `updateCarouselHeight` (o equivalente) usa `article-card-` + id, **non** `.p-carousel-item-active`. |
| FE-CR-02 | `.agents/AGENTS.md` §5.8; `frontend.md` | Vietato affidarsi a `.p-carousel-item-active` (race DOM al primo avvio). | stesso | Nessun calcolo altezza basato su `.p-carousel-item-active`. |
| FE-CR-03 | `frontend.md` Regola 7; `spatial-data-mocking` | Nation open: carosello = **tutte** le notizie della nazione; vietato truncare a N arbitrario come regola UX. | consumer state / load nation (fuori sidebar); mock `getArticlesPage` | FE concatena pagine fino a esaurimento `next_cursor`; sidebar riceve lista completa. |
| FE-CR-04 | `frontend.md` Regola 7 | Sort categoria + pill `findIndex` restano invariati in sidebar (freeze). | `components/radar-sidebar/**` | Nessun cambiamento a sort/pill nella sidebar. |

**Conteggio dominio 2:** 4

---

## 3. Read / unread (`.marker-read`)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-RU-01 | `.agents/AGENTS.md`; `radar-sidebar-freeze`; `frontend.md`; `angular-map-expert.md` | Fix letta/non letta **solo** in `state.service.ts` + `radar-map.component.ts` (e test correlati). | `services/state.service.ts`; `components/radar-map/radar-map.component.ts` | Diff read-state non tocca `radar-sidebar/**`. |
| FE-RU-02 | `frontend.md` Regola 7; `AGENTS.md` Phase 4 | Fingerprint geometry + `syncMarkerReadState` — **no** `clearLayers` / rebuild cluster su solo cambio `is_read`. | `components/radar-map/radar-map.component.ts` | Toggle `is_read` aggiorna classe `.marker-read` senza ricostruire i cluster. |
| FE-RU-03 | `angular-map-expert.md` XSS-safe icons | Classe `.marker-read` applicata sull’elemento icona quando `article.is_read`. | `radar-map.component.ts` (`createSafeMarkerIcon` o equivalente) | Marker letti hanno `.marker-read`; non letti no. |
| FE-RU-04 | `radar-sidebar-freeze` anti-pattern | Vietato spostare logica read-state dentro `radar-sidebar/`. | `components/radar-sidebar/**` | Nessuna logica `is_read` / marker-read nella sidebar. |

**Conteggio dominio 3:** 4

---

## 4. Leaflet via `window.L` (ESBuild)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-LL-01 | `.agents/AGENTS.md` §5 WARNING; `frontend.md` Regola 10; `angular-map-expert.md` | Caricare Leaflet + MarkerCluster come script globali in `angular.json` → `scripts[]`. | `radar/frontend/angular.json` | Presenti `leaflet/dist/leaflet.js` e `leaflet.markercluster/dist/leaflet.markercluster.js` in `scripts`. |
| FE-LL-02 | stessi | Accedere a Leaflet con `const L = (window as any).L` (o cast equivalente). | `components/radar-map/**`, altri consumer mappa | Runtime usa `window.L`; tipi `@types/leaflet*` solo compile-time. |
| FE-LL-03 | stessi | **Vietato** `import * as L from 'leaflet'` nel codice app componenti. | `src/app/**/*.ts` (grep) | Nessun import namespace Leaflet nei componenti/servizi app. |
| FE-LL-04 | stessi | **Vietato** `import 'leaflet.markercluster'` side-effect nei componenti. | `src/app/**/*.ts` | Nessun side-effect import markercluster nell’app. |
| FE-LL-05 | `angular-map-expert.md` / CLAUDE skill map | Test: stub Leaflet in `testing/leaflet.stub.ts` se presenti unit test mappa. | `src/app/testing/leaflet.stub.ts` | Stub disponibile e usato nei test che toccano L. |

**Conteggio dominio 4:** 5

---

## 5. XSS-safe icons / DOM

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-XSS-01 | `angular-map-expert.md`; `AGENTS.md` Phase 4 | Icone marker via DOM APIs + `textContent` (es. `createSafeMarkerIcon`), **non** stringhe HTML/`innerHTML` con titoli o dati untrusted. | `components/radar-map/radar-map.component.ts` | `L.divIcon({ html: Element })` con `el.textContent = emoji`; niente interpolazione titoli in HTML. |
| FE-XSS-02 | `angular-map-expert.md` clustering | Cluster count XSS-safe: `el.textContent = String(count)` (non HTML string). | stesso | `iconCreateFunction` usa DOM + `textContent`. |
| FE-XSS-03 | `angular-map-expert.md` | Emoji da mappa categorie fisse (`CATEGORY_ICONS`), non da payload grezzo non sanitizzato. | stesso | Solo emoji note per le 10 categorie (+ fallback `📍`). |

**Conteggio dominio 5:** 3

---

## 6. API Phase 5 — MapSummary, ArticlesPage, cursor pagination

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-API-01 | `radar-api-contract`; `frontend.md` Regola 7; `AGENTS.md` §5.11; `spatial-data-mocking` | Day view: `getMapSummary` → `GET /api/map-summary` (righe `country_code × primary_category` + count/read + lat/lon finite). | `services/article.service.ts`; `models/map-summary.model.ts`; `models/article.dto.ts` | Nessun `Article[]` globale del giorno come SoT day-view. |
| FE-API-02 | stessi | Nation open: `getArticlesPage` → `GET /api/articles` envelope `{ items, next_cursor, total }`. | `services/article.service.ts`; `models/article.model.ts` | Tipo `ArticlesPage` / DTO parser allineati all’envelope. |
| FE-API-03 | stessi | Page size ≤ 100; FE **concatena** tutte le pagine finché `next_cursor` presente. | state / map load nation path; `article.service.ts` / mock | Loop (o equivalente) concatena `items`; non ferma a prima pagina. |
| FE-API-04 | `radar-api-contract`; `spatial-data-mocking` | Mock espone stessi metodi/contratto: `getMapSummary` + `getArticlesPage`. | `services/article-mock.service.ts` | Mock non è solo `getArticles`/`getCountries` deprecati. |
| FE-API-05 | `radar-api-contract` | FE post-API: `companies_involved` / `tags` / `infrastructural_entities` tipicamente `string[]` (dopo `array_agg`); non confondere con Pydantic CSV `str`. | `models/article.model.ts`; DTO parsers | Tipi FE coerenti con risposta API aggregata. |
| FE-API-06 | `frontend.md` Regola 7 | Day zoom ≥ 5: **un pin nazione** (conteggio + anello conic categorie), non pallini numerati per-categoria. | `radar-map.component.ts` | Day pins da map-summary; cluster per-categoria solo in nation open. |
| FE-API-07 | `frontend.md` Regola 7 | Click pin summary → nation fetch + sidebar con `preserveZoom: true` (no fitBounds/dezoom). | `radar-map.component.ts` | `armSkipCountryFit` / `preserveZoom` solo su pin summary. |
| FE-API-08 | `frontend.md` Regola 7; `AGENTS.md` §5.7 | Click poligono/toolbar → nation open + `fitBounds` con `maxZoom: 4` (o inferiore). | stesso | `fitBounds` maxZoom ≤ 4. |
| FE-API-09 | `frontend.md` Regola 7 | Ri-selezione stesso paese → `refocusCountry(code)` (signal non ri-triggera). | stesso | Secondo click stesso `focusCountryCode` richiama `refocusCountry`. |
| FE-API-10 | `frontend.md` HTTP stack | HTTP solo via `HttpClient` Angular — vietato Axios / `fetch()` raw per API Radar. | `services/**/*.ts` | Chiamate API usano `HttpClient`. |

**Conteggio dominio 6:** 10

---

## 7. Overlay full-bleed + `invalidateSize`

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-OV-01 | `.agents/AGENTS.md` §5.12; `frontend.md` Regola 6; `radar-sidebar-freeze` | Mappa sempre `100vw` / full-bleed; sidebar disegna **sopra** — **non** split 70/30 che restringe la mappa (`calc(100vw - sidebar)` vietato in Phase 4). | `app` shell SCSS/HTML; `radar-map` container styles | Idle e split-active: width mappa `100vw`; nessuna formula che sottrae sidebar. |
| FE-OV-02 | `frontend.md` Regola 6; `angular-map-expert.md` | Dopo open/close sidebar e su `window.resize`: `map.invalidateSize()` dal shell (`App`), senza editare sidebar. | `app.component.ts` (o shell); bridge verso map | Chiamate `invalidateSize` presenti su open/close/resize. |
| FE-OV-03 | `frontend.md` Regola 7 | Dopo open nazione: `invalidateSize` **prima** di `focusAndSpiderfyCategory`. | `radar-map.component.ts` | Ordine: invalidateSize → poi spiderfy/focus. |
| FE-OV-04 | `frontend.md` Regola 7 | `invalidateSize` con `pan: false`; `setView` solo se camera driftata (setView mid-spiderfy svuota pane MarkerCluster). | stesso | Nessun `setView` indiscriminato durante spiderfy. |
| FE-OV-05 | `frontend.md` Regola 6 | Vietato modal/tooltip al posto della sidebar split-screen per dettaglio notizie. | componenti UI | Dettaglio notizie via sidebar, non modal sostitutiva. |
| FE-OV-06 | `frontend.md` Regola 7 | Sidebar close: `App.closeSidebar()` → `mapComponent.collapseAllGraphs()` (senza editare sidebar). | `app.component.ts`; map public API | Close chiude grafi/spiderfy via map component. |

**Conteggio dominio 7:** 6

---

## 8. MOCK_MODE esplicito

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-MK-01 | `frontend.md` Regola 2b; `spatial-data-mocking`; `radar-api-contract`; `angular-map-expert.md` | Toggle mock solo via injection token `MOCK_MODE` in `services/mock-mode.token.ts`. | `services/mock-mode.token.ts`; `app.config.ts` | Token esiste; default produzione `false`. |
| FE-MK-02 | stessi | **Vietato** `catchError` / fallback silenzioso che attiva mock su errore API. | `services/article.service.ts`; state loaders | Errore API → `StateService.error` / banner toolbar; data richiesta preservata. |
| FE-MK-03 | `spatial-data-mocking` | Offline/demo: `{ provide: MOCK_MODE, useValue: true }` esplicito. | `app.config.ts` / TestBed | Mock attivo solo se provider esplicito `true`. |
| FE-MK-04 | `spatial-data-mocking` | Tipi mock = tipi prod (`MapSummaryRow[]`, `ArticlesPage`). | `article-mock.service.ts` | Stesse firme di `ArticleService` per i metodi Phase 5. |

**Conteggio dominio 8:** 4

---

## 9. Categorie geopolitiche (10 SoT)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-CAT-01 | `spatial-data-mocking`; `radar-api-contract`; `frontend.md` palette; `angular-map-expert.md` | Exactamente 10 primary: Nucleare, Energia, Infrastrutture, Geopolitica, Economia, Tecnologia, Spazio, Ambiente, Salute, Sicurezza (`PRIMARY_CATEGORIES` / `CATEGORY_CSS_VARS`). | `models/**`; `radar-map.component.ts`; `styles.scss` | Liste/icone/CSS vars allineate alle 10. |
| FE-CAT-02 | `spatial-data-mocking`; `radar-api-contract` | **Vietato** come `primary_category`: `Chip`, `Acqua`, `Elettronica` (ok solo come tag testuali). | mock dataset; tipi `PrimaryCategory` | Nessun mock/prod FE con primary illegali. |
| FE-CAT-03 | `angular-map-expert.md` | Un `L.markerClusterGroup` per `primary_category` (fino a 10). | `radar-map.component.ts` | Map/gruppi = chiavi categorie valide. |
| FE-CAT-04 | `angular-map-expert.md` | Colori categoria da CSS vars runtime (`getComputedStyle`), non HEX hardcoded nel componente. | `radar-map.component.ts` hatching | Hatch/marker usano `--color-*` da `styles.scss`. |

**Conteggio dominio 9:** 4

---

## 10. Bounding box US / RU (antimeridiano)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-BB-01 | `.agents/AGENTS.md` §5.4; `frontend.md` Regola 11 | US mainland hardcoded: `L.latLngBounds(L.latLng(24.396308, -125.0), L.latLng(49.384358, -66.93457))`. | `components/radar-map/radar-map.component.ts` | Literal bounds US presenti e usati nel focus. |
| FE-BB-02 | stessi | RU mainland hardcoded: `L.latLngBounds(L.latLng(41.1856, 19.6389), L.latLng(81.8587, 169.0))`. | stesso | Literal bounds RU presenti e usati nel focus. |
| FE-BB-03 | stessi | Non calcolare bounds dinamici da geometria completa per US/RU (evita crash antimeridiano). | stesso | Path US/RU bypassa bounds GeoJSON “raw” a favore degli statici. |

**Conteggio dominio 10:** 3

---

## 11. Spiderfy / cluster stability

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-CL-01 | `.agents/AGENTS.md` §5.2; `frontend.md` Regola 7 | `maxClusterRadius: 40` — non legacy 200/100. | `radar-map.component.ts` | Valore esatto 40. |
| FE-CL-02 | stessi | `spiderfyOnMaxZoom: false` — espansione custom, non spiderfy automatico. | stesso | `false`; non `true`. |
| FE-CL-03 | `frontend.md` Regola 7; `angular-map-expert.md` | Non reintrodurre `disableClusteringAtZoom: 18` come requisito ECC. | stesso | Assente come “requisito” / non allineare a legacy. |
| FE-CL-04 | `AGENTS.md` §5.3; `frontend.md` Regola 7 | Nation open: hub disco `radar-spider-root` + fan emoji categoria attiva; **storico:** max 24 / `SPIDERFY_MAX_ICONS` — **runtime attuale:** tutte le icone (no hard cap); size/distanza adattivi; restore hub on failure. | `radar-map.component.ts` | Nessun `SPIDERFY_MAX_ICONS`; helpers distanza/size per count. |
| FE-CL-05 | `frontend.md` Regola 7 | Spiderfy: **solo** categoria del pallino / pill / articolo attivo carosello — non tutte; scroll stessa categoria → solo highlight (`lastSpiderfyKey`). | stesso | Un fan per categoria attiva; no multi-cat spiderfy. |
| FE-CL-06 | `frontend.md` Regola 7; `AGENTS.md` §5.3 | Hub root lifecycle: su cambio categoria `collapseAllGraphs(false, false)` setta `restoreDetailHubOnUnspiderfy = false`; handler `unspiderfied` **non** deve `clearRootMarkers`/ripristinare hub in quel caso. | stesso | Root non sparisce al cambio categoria; solo chiusura reale (`restoreHub: true`) ripristina. |
| FE-CL-07 | `frontend.md` Regola 7 | Close/cambio paese: clear detail markers; tornano i pin summary. | stesso | Detail layer cleared; day pins restored. |
| FE-CL-08 | `angular-map-expert.md` | Offset marker per categoria in pixel/geo progressivo (`GEO_DIRECTIONS`), non solo CSS `iconAnchor` legacy come unica strategia. | stesso | Offset geografico progressivo presente. |
| FE-CL-09 | `angular-map-expert.md` | `clusterclick`: filtrare articoli esplicitamente per `primary_category` del gruppo. | stesso | Handler filtra `a.primary_category === cat`. |
| FE-CL-10 | `.agents/AGENTS.md` (nota clustering) | Day-view può usare marker invisibili `isDummy: true` per raggruppamento spaziale nazione senza punti ridondanti (dove ancora applicabile al design day pins). | `radar-map.component.ts` | Se presenti dummy, `isDummy: true` e non mostrati come pin reali. |
| FE-CL-11 | `frontend.md` accettazione | `showCoverageOnHover: false`, `zoomToBoundsOnClick: false` (pattern expert agent). | stesso | Allineato al pattern documentato in angular-map-expert. |

**Conteggio dominio 11:** 11

---

## 12. Zoom, hatching, legenda, focus camera

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-ZM-01 | `frontend.md` Regola 5; `angular-map-expert.md` | Zoom &lt; 5: hatching SVG nazioni, marker nascosti; zoom ≥ 5: hatching opacity 0, marker/pin visibili. | `radar-map.component.ts` + SCSS | Soglia 5 rispettata; transizione CSS `fill-opacity` / opacity. |
| FE-ZM-02 | `frontend.md` Regola 5 | Transizione CSS obbligatoria (~0.3–0.4s ease-in-out), non toggle istantaneo. | SCSS mappa / global | Regole transition presenti. |
| FE-ZM-03 | `angular-map-expert.md` Phase 4 | Hatch owner = `getOrCreateComboPattern` — niente direttiva `appLeafletHatch`. | `radar-map` / helpers hatch | Nessun `appLeafletHatch`; combo pattern owner corretto. |
| FE-ZM-04 | `.agents/AGENTS.md` §5.6; `frontend.md` Regola 11 | `minZoom: 2.2`, `maxBounds` `[-85,-180]`→`[85,180]`, `maxBoundsViscosity: 1.0`. | `radar-map.component.ts` init `L.map` | Opzioni mappa matchano. |
| FE-ZM-05 | `.agents/AGENTS.md` §5.5; `frontend.md` Regola 11 | Legenda glassmorphic monoriga in basso centro (`bottom: 20px; left: 50%`); `flex-wrap: nowrap` + `overflow-x: auto` + `max-width: 90vw`. | template/SCSS legenda mappa | Una riga; scroll orizzontale se serve; no wrap verticale. |
| FE-ZM-06 | `frontend.md` Regola 11 | Tooltip nazioni (`.tooltip-row`): allineamento flag/nome/badge (line-height comune, flex). | SCSS tooltip | Allineamento baseline/center coerente. |
| FE-ZM-07 | `angular-map-expert.md` | Tile CartoDB Dark Positron (estetica Palantir); zoomControl tipicamente off in init documentato. | init map | Tile dark_nolabels (o equivalente Carto dark documentato). |

**Conteggio dominio 12:** 7

---

## 13. Stack Angular 21, Signals, Standalone

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-ST-01 | `frontend.md` Regola 1; `angular-map-expert.md` | Solo Standalone Components — **vietato** `NgModule` tradizionali per feature app. | `src/app/**/*.ts` | Componenti con `standalone: true` (o default Angular 21 standalone). |
| FE-ST-02 | `frontend.md` Regola 2 | Stato UI globale con Signals (`signal`/`computed`/`effect`) — **vietato** `BehaviorSubject` per stato UI. | `services/state.service.ts`; componenti | Nessun BehaviorSubject per selectedArticle/filters/sidebar. |
| FE-ST-03 | `frontend.md` Regola 2 policy Phase 4 | RxJS ammesso solo come adapter HttpClient (`Observable`, `rxResource`, operatori HTTP). | services HTTP | RxJS limitato al trasporto. |
| FE-ST-04 | `frontend.md` Regola 2 | Passaggio a `httpResource` **deferred** — trasporto attuale `rxResource` + HttpClient. | services | Non forzare migrazione httpResource come requisito corrente. |
| FE-ST-05 | `frontend.md` Stack table | UI: PrimeNG 17+; CSS: SCSS + CSS vars — **vietato** Tailwind/Bootstrap/Material/Styled-Components come stack UI. | `package.json`; styles | Dipendenze e stili allineati a PrimeNG + SCSS. |
| FE-ST-06 | `frontend.md` Stack | Mappa Leaflet 1.9.x + leaflet.markercluster ufficiale — no Google Maps / Mapbox a pagamento. | `package.json` | Solo Leaflet stack. |
| FE-ST-07 | `AGENTS.md` Phase 4; `angular-map-expert.md` | Usare `DestroyRef` per cleanup subscription/listener dove applicabile (Phase 4 DONE). | componenti long-lived (map, shell) | Cleanup via DestroyRef / takeUntilDestroyed, non leak ovvi. |
| FE-ST-08 | `.agents/skills/angular-developer/SKILL.md` | Seguire Angular 21: Signals per stato; non usare `effect()` per derived state che deve essere `computed()`. | nuovo codice FE | Pattern Signals corretto. |
| FE-ST-09 | `angular-developer` anti-patterns | Non chiamare `inject()` fuori injection context. | servizi/factory | `inject()` solo in context valido. |

**Conteggio dominio 13:** 9

---

## 14. GeoJSON locale / assets

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-GEO-01 | `frontend.md` Regola 3; `angular-map-expert.md`; `radar-geojson-assets` | Confini solo da asset locale `assets/data/countries.geo.json` (o equivalente) via HttpClient. | `radar-map` load GeoJSON | Path `assets/data/...` — nessun CDN/URL esterno a runtime. |
| FE-GEO-02 | `radar-geojson-assets` | Non committare dump GeoJSON enormi (gitignored); build Docker verifica/fetch via `verify-geojson.mjs`. | `frontend/src/assets/data/`; Dockerfile FE; scripts | Nessun fetch CDN nel browser; verify in build. |

**Conteggio dominio 14:** 2

---

## 15. Palette Palantir / template data

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-PAL-01 | `frontend.md` Regola 4 | Palette immutabile via CSS custom properties in `styles.scss` (`--color-bg-*`, `--color-text-*`, 10 `--color-*` categorie). | `src/styles.scss` | Vars presenti; UI non introduce HEX “random” fuori palette. |
| FE-PAL-02 | `frontend.md` accettazione | Vietati colori hardcoded tipo `#ff0000` fuori dalle CSS vars di progetto. | componenti SCSS/TS | Colori categoria/UI da vars. |
| FE-PAL-03 | `frontend.md` Regola 8 | Nessun dato placeholder hardcoded nei template HTML (titoli/summary statici finti). | template `*.html` | Binding a Signals/state. |

**Conteggio dominio 15:** 3

---

## 16. Altre regole FE hard (feed, flex, npm, build path)

| ID | Source | Requirement | Where to verify | Pass criteria |
|----|--------|-------------|-----------------|---------------|
| FE-MISC-01 | `.agents/AGENTS.md` §5.10 | Pulizia prefisso feed: `.replace(/^Feed:\s*/i, '')` sui titoli Miniflux prima del render. | pipe/util o map component / card data prep (fuori freeze se possibile) | Prefisso `Feed: ` rimosso. |
| FE-MISC-02 | `.agents/AGENTS.md` §5.9 | Metadati lunghi (fonte) + link `Leggi fonte →`: Flexbox `flex: 1` + `min-width: 0` sul testo; `flex-shrink: 0` + `white-space: nowrap` sul link. | SCSS card (sidebar freeze: non modificare se già conforme) | Layout non overflowa/tronca correttamente. |
| FE-MISC-03 | `frontend.md` Regola 9; `AGENTS.md` Docker FE | Install npm: `npm ci --legacy-peer-deps` in Docker; locale `--legacy-peer-deps` quando richiesto. **Vietato** `npm install` in Dockerfile builder. | `radar/frontend/Dockerfile`; docs | Dockerfile usa `npm ci --legacy-peer-deps`. |
| FE-MISC-04 | `frontend.md` Regola 0 | Build Angular: output servito da `dist/[nome]/browser/` (non radice progetto senza `/browser`). | Dockerfile FE `COPY`; `angular.json` outputPath | Nginx riceve contenuto `browser/`. |
| FE-MISC-05 | `AGENTS.md` | Produzione FE: no `TODO`/`FIXME`/`HACK`/placeholder incompleti nel codice deployato. | `src/app/**` | Nessun TODO di produzione nei file shippati. |
| FE-MISC-06 | `angular-map-expert.md` | Output events mappa: `markerClicked` / `clusterClicked` / `countryClicked` (nation open carica articles paged). | `radar-map.component.ts` | Eventi presenti e wiring verso state/shell. |
| FE-MISC-07 | `frontend.md` lint note / angular-map-expert comandi | Lint FE = **prettier** (non eslint come gate documentato). | `package.json` scripts | `npm run lint` = prettier path. |
| FE-MISC-08 | `spatial-data-mocking` mock fields | Mock articoli devono includere `infrastructural_entities` (obbligatorio nello skill dataset). | `article-mock.service.ts` | Campo presente su ogni mock article. |

**Conteggio dominio 16:** 8

---

## Riepilogo conteggi per dominio

| # | Dominio | Items |
|---|---------|------:|
| 1 | Sidebar freeze | 5 |
| 2 | Carousel PrimeNG + `updateCarouselHeight` | 4 |
| 3 | Read / unread | 4 |
| 4 | Leaflet / `window.L` | 5 |
| 5 | XSS-safe icons | 3 |
| 6 | API MapSummary / ArticlesPage / cursor | 10 |
| 7 | Overlay full-bleed + `invalidateSize` | 6 |
| 8 | MOCK_MODE | 4 |
| 9 | Categorie (10) | 4 |
| 10 | Bounding box US/RU | 3 |
| 11 | Spiderfy / cluster | 11 |
| 12 | Zoom / hatching / legenda | 7 |
| 13 | Stack Signals / Standalone | 9 |
| 14 | GeoJSON / assets | 2 |
| 15 | Palette / template | 3 |
| 16 | Misc (feed, flex, npm, browser/, …) | 8 |
| | **TOTALE** | **88** |

---

## Note mirror ECC

- `radar/.ecc/skills/radar-sidebar-freeze.md`, `spatial-data-mocking.md`, `radar-api-contract.md`: **allineati** alle skill `.agents/` (nessun requisito FE aggiuntivo).
- `radar/.ecc/skills/angular-developer.md`: stesso corpo + nota SoT `references/` sotto `.agents/skills/angular-developer/references/` — nessun vincolo Radar-specifico extra oltre anti-pattern Angular generici già catturati in FE-ST-08/09.
- `radar/.ecc/skills/radar-geojson-assets.md`: requisiti asset FE consolidati in FE-GEO-*.
