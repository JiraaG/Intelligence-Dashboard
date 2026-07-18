# Frontend e UI

SPA Angular 21 (standalone + signals). Codice: `radar/frontend/`.  
Stack allineato a Phase **6 DONE / GATE VERDE**.  
**Freeze:** non modificare `radar/frontend/src/app/components/radar-sidebar/**` (niente `article-list` / infinite scroll / restyle carousel) tranne per le due eccezioni mirate: il toggle Salva/Rimuovi e la sezione chip dei paesi correlati (`related_countries`).

---

## Stack

| Layer | Scelta |
|-------|--------|
| Core | Angular 21.2 standalone, Signals, ESBuild |
| Mappa | Leaflet 1.9.4 + markercluster 1.5.3 via `angular.json` `scripts[]` → `window.L` |
| UI | PrimeNG 17 + Angular CDK 17 (peer mismatch → `npm ci --legacy-peer-deps`) |
| Stile | SCSS (design system in `styles.scss`) |

Script utili (`package.json`): `start`, `verify-geojson`, `verify-geojson:fetch`, `typecheck`, `test:ci`, `build:ci`, `lint`. **Non esiste** runner `ng e2e` in questo repo.

---

## Albero componenti

```text
App
├── RadarToolbarComponent     # data, filtri, LETTE/TROVATE, NOTIZIE SALVATE
├── RadarMapComponent         # GeoJSON, hatching, cluster, pallini, spiderfy
└── RadarSidebarComponent     # p-carousel (FROZEN; eccezione toggle Salva)

Servizi:
├── StateService              # SoT signals + map-summary + saved-summary + nation/saved pages
├── ArticleService            # HTTP / mock gated
├── MOCK_MODE token           # default false — no silent fallback
└── ArticleMockService        # solo se MOCK_MODE=true
```

Hatching SVG: owner in `radar-map.component.ts` (`getOrCreateComboPattern`) — non una directive separata obbligatoria.

---

## Contratto dati (Phase 5+)

**Day open**

1. `GET /api/map-summary?date=…` → hatching per paese + a zoom ≥ 5 **un pin grande per nazione** (conteggio + anello conic colori categorie)
2. Niente `Article[]` globale del giorno in memoria mappa

**Nation open (day)**

1. `GET /api/articles?date&country` con envelope `{items,next_cursor,total}`; FE concatena pagine (`limit` ≤ 100) finché `next_cursor` è null
2. Carosello = tutte le notizie della nazione (sort categoria; pill `findIndex` invariato in sidebar)
3. Marker: **hub compatto** (`radar-spider-root`, stesso stile del root spiderfy — non il pin alto day-view) + spiderfy a **icone emoji** della sola categoria attiva
4. Fan spiderfy: **tutte** le icone della categoria (niente hard cap 24 / park extras); dimensione icone e `spiderfyDistanceMultiplier` **adattivi** al conteggio; se spiderfy fallisce → restore hub nazione
5. Spiderfy allineato alla **categoria attiva** (pill / slide carosello). Stessa categoria allo scroll → solo highlight (`lastSpiderfyKey`). Cambio categoria: non cancellare il root su `unspiderfied` asincrono (`restoreDetailHubOnUnspiderfy === false` → no-op)
6. **Dezoom:** spider + sidebar restano aperti a zoom ≥ 5; a zoom &lt; 5 (hatching) → collapse spiderfy / chiusura grafo dettaglio
7. Focus camera: pin summary → `preserveZoom` + `armSkipCountryFit`; poligono/toolbar → `fitBounds` (`maxZoom: 4`); ri-click stessa nazione → `refocusCountry`

**Saved vault (Notizie Salvate)**

1. Contatore toolbar date-agnostic da `GET /api/saved-summary` (no date) + tooltip **Nazioni Salvate**
2. Click nazione → `loadSavedCountryArticles` → `GET /api/articles?saved=true&country=` (ignora date; carosello multi-day)
3. **Stesso path mappa di LETTE/TROVATE:** `fitBounds` + `flyTo` zoom 6 + spiderfy categoria (`App.onToolbarSavedCountrySelect` → `scheduleCategorySpiderfy`)
4. Card: **Salva notizia** / **Rimuovi dai salvati** (delega a `StateService`)
5. Coupling: save ⇒ `is_read=true`; unread ⇒ `is_saved=false`

**Close / cambio paese:** clear detail markers; tornano i pin summary.

---

## MOCK_MODE

```typescript
// app.config.ts
{ provide: MOCK_MODE, useValue: false }
```

Offline: `{ provide: MOCK_MODE, useValue: true }`. Errori API restano visibili — **vietato** fallback silenzioso a mock.

### Errori nation/saved-fetch (T-P1-04)

- `StateService.detailError` + `error = mapSummaryResource.error() ?? savedSummaryResource.error() ?? detailError()`
- Wiring toolbar: `[apiError]="!!state.error()"`
- Fallimento `loadCountryArticles` / `loadSavedCountryArticles` → set `detailError` → `closeSidebar(false)` (UI chiusa, banner visibile)
- Close intenzionale → `closeSidebar()` / `clearError: true` azzera l’errore
- Test: `app.spec.ts` + `state.service.spec.ts`

---

## Leaflet + ESBuild

1. JS Leaflet e MarkerCluster in `angular.json` `scripts[]` → `window.L`
2. CSS Leaflet/MarkerCluster via `@import` in `src/styles.scss` (incluso da `angular.json` `styles[]`)
3. Nel componente: `const L = (window as any).L`
4. Vietato `import 'leaflet.markercluster'` nei componenti
5. Test: stub `src/app/testing/leaflet.stub.ts`

---

## Clustering

Un `markerClusterGroup` **per ciascuna delle 10 categorie** (nation detail):

- `maxClusterRadius: 40`
- `spiderfyOnMaxZoom: false` (espansione custom / flyTo)
- `iconCreateFunction` → icona nascosta (0×0): day-view usa pin summary; nation open usa hub disco + fan emoji
- Non ripristinare raggio 200 o spiderfy automatico legacy

Read/unread/save: fingerprint geometria + `syncMarkerReadState` — toggle `is_read` **non** deve `clearLayers` (icone spiderfy restano). Logica in `state.service.ts` + `radar-map.component.ts`, non nella sidebar (sidebar solo delega click). Auto-mark come letta: in `app.ts` su `activeArticleChanged` se `!is_read`. Card **Salva notizia** / **Rimuovi dai salvati**. Coupling: save ⇒ read; unread ⇒ unsave.

PATCH read status: update ottimistico + rollback; risposta `{status, is_read, is_saved?}`.
PATCH saved status: update ottimistico + rollback; risposta `{status, is_saved, is_read?}`.

---

## Interazione split-screen

```mermaid
sequenceDiagram
  participant User as Utente
  participant MapUI as Mappa / Toolbar
  participant App as App
  participant State as StateService
  participant Sidebar as Sidebar
  participant Map as RadarMap

  User->>MapUI: click paese o pin summary
  MapUI->>App: country / cluster event
  App->>State: load nation articles (paged)
  App->>Sidebar: open carousel (frozen)
  App->>Map: hub disc + spiderfy categoria attiva
```

PATCH read status: update ottimistico + rollback su errore; risposta API `{status, is_read, is_saved?}`.
PATCH saved status: update ottimistico + rollback; risposta `{status, is_saved, is_read?}`.

GeoJSON locale: `assets/data/countries.geo.json` (no CDN in produzione; pin in `ASSET_LICENSE.md`). Bounding box speciali US/RU; `minZoom` ~2.2.

---

## Relazioni Geospaziali (Grafo — Fase H)

Per collegare le notizie multilaterali, la mappa disegna archi curvi bidirezionali (mediante interpolazione di punti tramite `L.polyline`) tra i centroidi dei paesi.

1. **Gestione dello Stato**: `StateService` espone `mapRelationsResource` sincronizzato con la data attiva e i filtri della toolbar. Al riceversi del segnale SSE `article_processed`, viene scatenato il reload atomico sia per il summary che per le relazioni.
2. **Visualizzazione e Zoom**:
   - Gli archi vengono disegnati in un `relationsLayerGroup` dedicato, posizionato sopra il layer dei confini nazionali.
   - **Zoom ≥ 5 (vista pin)**: gli archi sono divisi per categoria (1 linea per categoria geopolitica attiva per coppia paese), con spessore proporzionale al volume (`Math.min(6, 1 + volume * 0.5)`), opacity 0.8, e tratteggio **geometrico** (tratti solidi lat/lng + gap — niente `dashArray`/CSS, così non “scorre” a ogni pan). Se la stessa coppia ha più categorie, le Bézier usano un **offset di curvatura** (fan parallelo) così le linee non si sovrappongono.
   - **Zoom < 5 (vista hatching)**: gli archi vengono aggregati per coppia di paesi come una **singola linea multicolore** (spezzata in segmenti consecutivi proporzionali al volume di ciascuna categoria collegata, ordinata per volume decrescente). Hanno uno stile soft con spessore ridotto (`Math.min(3, 1 + totalVolume * 0.3)`), opacity ~0.45, classe `.relational-arc-flow--macro` (linea continua, senza dash) ed il tooltip mostra il breakdown delle categorie e del volume totale (es. `Sicurezza 5 · Economia 2 · n=7`).
   - Vengono nascosti se viene aperta la vista di dettaglio di una specifica nazione (per evitare sovrapposizioni visive con il ventaglio di spiderfy).
3. **Calcolo Centroidi**:
   - I centroidi vengono estratti dinamicamente dai confini GeoJSON caricati in cache.
   - Per gli Stati Uniti (`US`) e la Russia (`RU`), data la loro estensione trans-antimeridiana, si utilizzano coordinate statiche hardcoded per posizionare l'arco al centro della terraferma principale (mainland).
4. **Stile Visivo**:
   - Colore dell'arco allineato alle variabili di stile della categoria geopolitica (`CATEGORY_CSS_VARS`).
   - Spessore proporzionale al volume aggregato di notizie.
   - Zoom ≥ 5: tratteggio geometrico denso (sampling Bézier 60, tratti on/off 1/1 via `addGeometricDashedPolyline`); zoom &lt; 5: linea continua soft `.relational-arc-flow--macro`.

Dettaglio ops FE: [`radar/frontend/README.md`](../radar/frontend/README.md).

