# Regole Frontend — Path-Scope: `frontend/**`
> **Scope:** Queste regole si applicano ESCLUSIVAMENTE ai file in `frontend/`.
> Non caricare queste regole durante il lavoro su `backend/` o file Docker.
> **Priorità:** ALTA — questi vincoli sovrascrivono qualsiasi comportamento default dell'agente.

---

## Regola CRITICAL: Sidebar freeze (non negoziabile)

- **VIETATO** modificare `src/app/components/radar-sidebar/**` (TS/HTML/SCSS/spec), tranne per le due eccezioni mirate: il toggle Salva/Rimuovi e la sezione chip dei paesi correlati (`related_countries`).
- Conservare `p-carousel` e la logica esistente `updateCarouselHeight` / `article-card-{id}`.
- **VIETATO** introdurre `app-article-list`, infinite scroll, o sostituire il polling altezza con ResizeObserver.
- Fix **letta/non letta** (`.marker-read`): solo `services/state.service.ts` + `components/radar-map/**`.
- Phase 4/5/H UI: mappa, toolbar, state, shell — non la sidebar (tranne le eccezioni sopra indicate).

---

## Regola 0: Struttura Build Angular 21 — Cartella `browser/` Obbligatoria

> **⚠️ ATTENZIONE:** A partire da Angular 17+, il comando `ng build` produce un output **doppio livello**.
> La cartella `dist/` ha questa struttura:
> ```
> dist/
> └── [nome-progetto]/
>     ├── browser/    ← FILE STATICI da servire con Nginx (index.html, JS, CSS)
>     └── server/     ← Solo se SSR è abilitato (NON usato in questo progetto)
> ```

**OBBLIGATORIO:** Qualsiasi configurazione che copia o serve i file della build Angular DEVE
puntare a `dist/[nome-progetto]/browser/` e non alla cartella `dist/[nome-progetto]/` radice.

Esempi corretti:
```dockerfile
# Dockerfile: Stage 2 — copia dalla cartella browser/
COPY --from=builder /app/dist/radar-frontend/browser /usr/share/nginx/html
```
```nginx
# nginx.conf: root punta alla directory dove Nginx serve i file
root /usr/share/nginx/html;   # già pre-popolata con il contenuto di browser/
```

**VIETATO:**
```dockerfile
# SBAGLIATO: manca la sotto-cartella browser/
COPY --from=builder /app/dist/radar-frontend /usr/share/nginx/html
```

Quando Angular CLI inizializza un nuovo progetto (es. `ng new radar-frontend`), il nome del
proietto definisce il prefisso della cartella `dist/`. Verificare sempre `angular.json`
→ `projects.[nome].architect.build.options.outputPath` per il valore esatto.

---

## Stack Tecnologico Obbligatorio

| Componente          | Tecnologia Obbligatoria              | VIETATO                               |
|---------------------|--------------------------------------|---------------------------------------|
| Framework           | Angular 21 (Standalone Components)   | Angular < 17, Vue, React              |
| UI Library          | PrimeNG 17+                          | Angular Material, Ant Design, Bootstrap|
| Mappa (default)     | MapLibre GL 5.24 (3D-primary / globe)| Google Maps API, Mapbox a pagamento come default |
| Mappa (legacy)      | Leaflet 1.9.x via `MAP_RENDERER=leaflet` (LEGACY FREEZE) | Nuove feature sul path Leaflet        |
| Clustering / spider | MapLibre: fan custom (no MC); Leaflet legacy: leaflet.markercluster | Plugin cluster non ufficiali          |
| CSS                 | SCSS con variabili custom + CSS vars | TailwindCSS, Styled-Components        |
| Stato               | Angular Signals                      | NgRx, NGXS, Akita, BehaviorSubject   |
| HTTP                | HttpClient Angular                   | Axios, fetch() raw                    |

---

## Regola 1: Standalone Components Obbligatori

Angular 21 usa Standalone Components. Non creare mai `NgModule` tradizionali.

**OBBLIGATORIO:**
```typescript
@Component({
  selector: 'app-radar-map',
  standalone: true,
  imports: [CommonModule, SidebarModule, CarouselModule, CalendarModule],
  templateUrl: './radar-map.component.html',
  styleUrl: './radar-map.component.scss'
})
export class RadarMapComponent { }
```

**VIETATO:**
```typescript
// NO: NgModule obsoleto in Angular 21
@NgModule({
  declarations: [RadarMapComponent],
  imports: [BrowserModule]
})
export class AppModule { }
```

---

## Regola 2: Signals per lo Stato della Mappa

Non usare `BehaviorSubject`, `Subject` o `EventEmitter` per lo stato UI globale.
Usare esclusivamente `signal()`, `computed()` e `effect()` di Angular 21.

**Policy Phase 4 & Real-Time (Signals vs RxJS & SSE):**
- **Signals** possiedono lo stato UI (`StateService`, input/output componenti, filtri).
- **RxJS** è ammesso solo come adapter di trasporto HttpClient (`Observable`, `rxResource`, operatori HTTP).
- **Resilienza SSE Real-Time:** L'aggiornamento dello stato in tempo reale è pilotato dallo stream SSE in `StateService` (`initRealTimeConnection`). I timer di resilienza per il `metricsStatusResource` (Fix A open reload, Fix B retries 15s/45s su `degraded`, Fix C safety net 5m) vivono fuori dalla Zone Angular (`runOutsideAngular`) per non generare cicli Change Detection spuri. **Non modificare né rimuovere questi meccanismi di resilienza.**
- **Topbar FinOps/FONTI:** `.toolbar-left` = **STATUS** → **FONTI** → calendario; `.toolbar-right` termina con **COSTI**. Popover glass (`role="dialog"`), **no `p-dialog`**. FONTI Giorno = by-feed `published_at` (read-only); Catalogo = `GET/PATCH /api/feeds` (Miniflux `disabled` only). Errori feeds/by-feed **non** nel banner mappa. Dettaglio: `docs/03_frontend_and_ui.md` + skill `radar-api-contract` / `spatial-data-mocking` Test 8–9.
- Non introdurre `BehaviorSubject` per stato locale. Un eventuale passaggio a `httpResource` resta **deferred post–Phase 5 (D11)**; il trasporto attuale è `rxResource` + HttpClient.

**OBBLIGATORIO:**
```typescript
// Stato reattivo con Signals
selectedDate = signal<string>(new Date().toISOString().split('T')[0]);
articles = signal<Article[]>([]);
selectedArticle = signal<Article | null>(null);
isSidebarOpen = signal<boolean>(false);
currentZoomLevel = signal<number>(3);

// Computed derivati
isZoomedOut = computed(() => !this.pinModeActive()); // latch via resolvePinMode()
articlesByCountry = computed(() => groupArticlesByCountry(this.articles()));
```

**VIETATO:**
```typescript
// NO: RxJS subject per stato locale (usa Signals invece)
private selectedArticle$ = new BehaviorSubject<Article | null>(null);
```

---

## Regola 2b: MOCK_MODE esplicito (Phase 4) + errori API (T-P1-04)

Mock dati solo via injection token `MOCK_MODE` (`services/mock-mode.token.ts`).
Default produzione: `false`. **Vietato** `catchError` che attiva mock silenziosamente.

Errore API → `StateService.error` / banner toolbar (`app.html` `[apiError]="!!state.error()"`); data richiesta preservata.

**Nation-fetch (T-P1-04 DONE):** `detailError = signal<unknown>(null)`; `error = computed(() => mapSummaryResource.error() ?? savedSummaryResource.error() ?? detailError())`.
`loadCountryArticles` / `loadSavedCountryArticles` valorizzano `detailError` in catch. Sul fallimento, `App` chiama `closeSidebar(false)` così la UI si chiude ma il banner resta.
Close intenzionale utente (`closeSidebar()` / default `clearError: true`) azzera `detailError`. **Non** refactorare `radar-sidebar/**` (eccezione: toggle Salva).

**Notizie Salvate:** `savedSummaryResource` (no date); toolbar `NOTIZIE SALVATE` + tooltip nazioni; `sidebarMode: 'nation' | 'saved'`; click nazione salvata = stesso path di LETTE/TROVATE (`fitBounds` + `flyTo` 6 + spiderfy); save ⇒ read; unread ⇒ unsave.

---

## Regola 3: GeoJSON Esclusivamente Locale

I confini geografici delle nazioni devono sempre essere caricati dal file statico locale.
Non usare CDN esterni, API di terze parti o URL dinamici.

**OBBLIGATORIO:**
```typescript
// Caricamento offline dal file locale in assets/
this.http.get<GeoJSON.FeatureCollection>('assets/data/countries.geo.json')
  .subscribe(geoData => {
    this.initializeCountryLayers(geoData);
  });
```

**VIETATO:**
```typescript
// NO: URL esterno per GeoJSON (rompe l'offline, crea dipendenza esterna)
this.http.get('https://cdn.jsdelivr.net/npm/world-atlas/countries-50m.json')
this.http.get('https://raw.githubusercontent.com/.../countries.geo.json')
```

---

## Regola 4: Palette Colori Palantir (Immutabile)

La palette cromatica dell'interfaccia è fissa e non negoziabile.
Usare sempre le CSS Custom Properties definite in `styles.scss`.

```scss
// frontend/src/styles.scss — Palette Palantir (definita una volta sola)
:root {
  // Sfondi
  --color-bg-primary:       #0a0a0f;   // Nero profondo mappa
  --color-bg-secondary:     #0d1117;   // Sidebar e pannelli
  --color-bg-card:          #161b22;   // Card notizie nella sidebar
  --color-bg-overlay:       rgba(10, 10, 15, 0.95);  // Overlay glassmorphism

  // Bordi e separatori
  --color-border-primary:   rgba(0, 212, 255, 0.15); // Ciano desaturato
  --color-border-accent:    rgba(0, 212, 255, 0.40); // Hover/focus

  // Testo
  --color-text-primary:     #e6edf3;   // Testo principale
  --color-text-secondary:   #8b949e;   // Testo secondario/metadata
  --color-text-accent:      #58a6ff;   // Link e accenti

  // Categorie (per hatching SVG e marker) — 10 categorie = styles.scss
  --color-nucleare:         #00E5FF;
  --color-energia:          #FFEA00;
  --color-infrastrutture:   #9E9E9E;
  --color-geopolitica:      #E040FB;
  --color-economia:         #00E676;
  --color-tecnologia:       #2979FF;
  --color-spazio:           #7C4DFF;
  --color-ambiente:         #8BC34A;
  --color-salute:           #FF1744;
  --color-sicurezza:        #FF9100;
}
```

---

## Regola 5: Logica Zoom — Hatching e Marker

### Soglia di Zoom

- Costante FE: `MAP_ZOOM_PIN_THRESHOLD` (= **4**) in `maplibre/great-circle.ts` (usata anche dal path Leaflet legacy).
- **Isteresi** `MAP_ZOOM_PIN_HYSTERESIS` (= **0.4**) + `resolvePinMode()`: entra in pin a zoom ≥ 4; esce solo sotto **3.6**. Evita flicker pin↔hatching quando il globo MapLibre aggiusta `getZoom()` in pan (latitudine).
- **Zoom / latch hatching**: Modalità macro — mostra hatching SVG sulle nazioni, nascondi marker / pin summary
- **Zoom / latch pin**: Modalità dettaglio — nascondi hatching (opacity 0), mostra marker/pin

```typescript
// Latch con isteresi (MapLibre + Leaflet)
this.pinModeActive.set(resolvePinMode(this.map.getZoom(), this.pinModeActive()));
if (this.pinModeActive()) {
  this.activateMarkerMode();
} else {
  this.activateHatchingMode();
}
```

### Nation open + spiderfy vs dezoom (obbligatorio)

Con nazione aperta e fan spiderfy attivo:

- **Zoom ≥ 4** (nessun hatching): lo spider **resta aperto**. MarkerCluster **non** deve auto-unspiderfy su wheel/zoom (`disableMarkerClusterMapClickUnspiderfy` rimuove anche `zoomstart` / `zoomanim` / `_noanimationUnspiderfy`). Su `zoomend`, re-spiderfy deferito (`lastSpiderfyCountry` + `lastSpiderfyCategory`) per riallineare le gambe.
- **Zoom < 4** (hatching / barre colorate): chiudere fan **e** sidebar via `collapseAllGraphs(true)` → `clusterClicked([])`. Guard: solo se `lastSpiderfyCategory` è settato (evita race `fitBounds(maxZoom:4)` all’open nazione).
- `emitClose` su `collapseAllGraphs` azzera `lastSpiderfyCountry` / `lastSpiderfyCategory`.

### Transizione CSS Obbligatoria

La transizione tra le due modalità DEVE essere fluida (non un toggle istantaneo):
```scss
.leaflet-overlay-pane svg path.country-fill {
  transition: fill-opacity 0.4s ease-in-out;
}
.leaflet-marker-pane {
  transition: opacity 0.3s ease-in-out;
}
```

---

## Regola 6: Layout Split-Screen (overlay full-bleed — Phase 4)

Il layout split-screen è obbligatorio per la visualizzazione delle notizie.
Non usare modal, overlay o tooltip: usare la sidebar laterale sinistra.

- **Stato idle**: mappa = 100% larghezza
- **Stato attivo** (marker cliccato): sidebar aperta **sopra** la mappa; la mappa resta **100vw** (overlay full-bleed). Non restringere la mappa con `calc(100vw - sidebar)` in Phase 4.
- Dopo open/close sidebar e su `window.resize`, chiamare `map.resize()` (MapLibre default) o `map.invalidateSize()` (Leaflet legacy) dal shell (`App`), senza modificare file sidebar.
- **Transizione sidebar**: cubic-bezier, durata ~350ms (stile esistente sidebar — freeze)

La sidebar è implementata con CSS puro + classe Angular attivata via Signal.
Il componente `p-sidebar` di PrimeNG può essere usato come wrapper UI.

---

## Regola 7: Clustering per categoria + map-summary (Phase 5+)

**Day open (Phase 5):** la mappa si dipinge da `GET /api/map-summary` (righe `country_code × primary_category` + count/read + lat/lon finite). Niente `Article[]` globale del giorno. Hatching zoom &lt; `MAP_ZOOM_PIN_THRESHOLD` (4): **MapLibre** = fasce soft O→E (1 colore × tipologia da `map-summary`; mainland US/RU; isole significative ≥0.5% area largest; clip terra∩strip via `polygon-clipping`, no fill in mare); **Leaflet** legacy = SVG combo. A zoom ≥ 4: **un pin nazione** (conteggio + anello conic categorie) — non pallini numerati per-categoria. Click pin → fetch nazione + sidebar (`preserveZoom: true`, niente dezoom). Click hatching (zoom &lt; 4) → map-click + `pickCountryCodeAt` (canvas `relationsPane` ruba i hit SVG) → stesso path toolbar. Click poligono/toolbar → nation open + `fitBounds` (`maxZoom: 4`). Hub/pin/spider e archi: anchor = `getCountryCentroid` (US/RU mainland), **non** media lat/lng articolo.

**Saved vault:** `GET /api/saved-summary` (no date) alimenta `NOTIZIE SALVATE` + tooltip nazioni; click → `loadSavedCountryArticles` + carosello multi-day con `sidebarMode='saved'`; **stesso path mappa di LETTE/TROVATE** (`fitBounds` + `flyTo` zoom 6 + spiderfy categoria + highlight). Card **Salva notizia** / **Rimuovi dai salvati**; save ⇒ read; unread ⇒ unsave.

**Nation open:** `GET /api/articles?date&country` (envelope `{items,next_cursor,total}`, page ≤100; FE concatena tutte le pagine) → carosello = **tutte** le notizie della nazione (sort categoria + pill `findIndex` invariati in sidebar). Sulla mappa: marker articolo **solo** per il paese aperto + **hub disco compatto** (`radar-spider-root`, stesso stile del root spiderfy). Spiderfy: sola categoria del pallino / pill / articolo attivo carosello — **non** tutte; allo scroll stessa categoria solo highlight (`lastSpiderfyKey`). Fan: **tutte** le icone della categoria (niente hard cap 24 / park extras); size emoji + `spiderfyDistanceMultiplier` adattivi al conteggio; restore hub se spiderfy fallisce. Close/cambio paese: clear detail markers; tornano i pin summary.

**InvalidateSize / spiderfy race:** dopo open nazione, `invalidateSize` **prima** di `focusAndSpiderfyCategory`; `invalidateSize` usa `pan: false` e `setView` solo se la camera è driftata (setView mid-spiderfy svuota il pane MarkerCluster).

**Hub root lifecycle:** su cambio categoria, `collapseAllGraphs(false, false)` setta `restoreDetailHubOnUnspiderfy = false`. Il handler `unspiderfied` **non** deve `clearRootMarkers` / ripristinare hub in quel caso (altrimenti l’`unspiderfy` asincrono del fan precedente cancella il nuovo root). Solo chiusura reale (`restoreHub: true`) ripristina l’hub.

**Zoom / wheel con spider aperto:** disabilitare auto-unspiderfy MarkerCluster su click **e** su zoom (`_unspiderfyWrapper`, `_unspiderfyZoomStart`, `_unspiderfyZoomAnim`, `_noanimationUnspiderfy`). Tenere il fan finché **`pinModeActive`** (latch isteresi, non raw `getZoom()`); a latch hatching → `collapseAllGraphs(true)` (sidebar + spider). Tracciare `lastSpiderfyCountry` / `lastSpiderfyCategory`; su `zoomend` in pin mode re-spiderfy deferito (~50ms) per refresh posizioni.

**Focus camera:** `armSkipCountryFit` **solo** con `preserveZoom` (pin summary). Poligono/toolbar: `fitBounds`. Stesso `focusCountryCode` di nuovo → `refocusCountry(code)` (il signal non ri-triggera).

**VIETATO:** `article-list` / infinite scroll in sidebar; truncare il carosello nazione a N arbitrario come regola UX; modificare `radar-sidebar/**`.

Il clustering utilizza un **`L.markerClusterGroup` per `primary_category`** (fino a 10 categorie) sui marker del paese aperto.
Parametri obbligatori (da `radar-map.component.ts`):

```typescript
const cg = L.markerClusterGroup({
  maxClusterRadius: 40,
  spiderfyOnMaxZoom: false,
  // iconCreateFunction: hidden 0×0 — day pins + nation hub disc own the chrome
});
```

Non reintrodurre raggio 200, `spiderfyOnMaxZoom: true`, o `disableClusteringAtZoom: 18` come requisiti ECC.

**Regole di calibrazione:**
- `maxClusterRadius`: **40px** (allineato a `radar-map.component.ts` post-restore)
- `spiderfyOnMaxZoom`: **false** (espansione custom, non spiderfy automatico)
- Spiderfy fan: **tutte** le icone della categoria attiva (niente hard cap 24 / niente `SPIDERFY_MAX_ICONS`); distanza/size adattivi (`spiderfyDistanceForCount` / `spiderfyIconSizeForCount`); restore hub nazione se spiderfy fallisce
- **Focus:** pin summary = preserveZoom; poligono/toolbar = `fitBounds` maxZoom 4; US/RU bounds hardcoded; hub/pin/spider = `getCountryCentroid` (no avg article coords); hatching click = `pickCountryCodeAt`
- **Sidebar close**: `App.closeSidebar()` → `mapComponent.collapseAllGraphs()` (senza editare file sidebar)
- **Read/unread**: fingerprint + `syncMarkerReadState` — no `clearLayers` su solo `is_read`

---

## Regola 8: Nessun Dato Hardcoded in Template HTML

I dati visualizzati nella sidebar e nelle card devono provenire esclusivamente
dallo stato Angular (Signals). Non inserire testo statico nei template HTML.

**OBBLIGATORIO:**
```html
<h2 class="article-title">{{ selectedArticle()?.title }}</h2>
<p class="article-summary">{{ selectedArticle()?.summary }}</p>
```

**VIETATO:**
```html
<!-- NO: dato hardcoded nel template -->
<h2>Notizia di esempio</h2>
<p>Questo è un placeholder in attesa dei dati reali.</p>
```

---

## Regola 9: Installazione dei Pacchetti tramite NPM (--legacy-peer-deps)

A causa dei potenziali conflitti di compatibilità delle dipendenze tra Angular 21, PrimeNG e Leaflet (in particolare per pacchetti legacy o librerie secondarie come `@angular/cdk`), è **obbligatorio** utilizzare sempre il flag `--legacy-peer-deps` durante l'installazione di qualsiasi pacchetto npm per garantire la coerenza della build e prevenire errori di installazione.

> **Nota Final Release (Fase 5):** il drop del flag resta **DEFERRED ACCETTATO** — non è un ticket OPEN. Si potrà rimuovere solo dopo upgrade coordinato CDK/PrimeNG compatibile con Angular 21, in branch dedicato, con smoke del carousel (sidebar freeze: sola osservazione).

**OBBLIGATORIO:**
```bash
# Dockerfile stage builder — OBBLIGATORIO riproducibile
RUN npm ci --legacy-peer-deps

# Locale: aggiunta pacchetto one-off
npm install <nome-pacchetto> --legacy-peer-deps
```

**VIETATO in Docker:**
```dockerfile
RUN npm install --legacy-peer-deps
```

**VIETATO senza `--legacy-peer-deps` quando richiesto dal lockfile:**
```bash
npm install <nome-pacchetto>
npm ci
```

Nel Dockerfile del frontend:
```dockerfile
RUN npm ci --legacy-peer-deps
```

**VIETATO:**
```bash
# NO: causa conflitti bloccanti di risoluzione peer dependencies
npm install <nome-pacchetto>
npm ci
```

---

## Regola 10: MapLibre primary + Leaflet legacy (ESBuild scripts)

> **Default:** MapLibre GL — host `components/radar-map/maplibre/`, facade `radar-map.component.ts`, token `MAP_RENDERER` (`services/map-renderer.token.ts`, default `maplibre`). Gate: `npm run verify-map-renderer`.
> Proiezione: `localStorage` `radar.mapProjection` = `globe` \| `mercator`.
> Spiderfy MapLibre: hub + fan HTML custom — **senza** MarkerCluster.
> Hatching MapLibre: fasce soft O→E (`country-category-fills.ts`; 1 colore × tipologia da `map-summary`; isole ≥0.5% largest; `polygon-clipping` terra∩strip) — **non** `fill-pattern` barcode.
> Resize overlay: `map.resize()` (non `invalidateSize`).

### Leaflet + ESBuild — solo host legacy (`MAP_RENDERER=leaflet`)

> **⚠️ GOTCHA (Angular 21 + @angular/build:application) — path Leaflet only:**
> `leaflet.markercluster` è UMD su `window.L`. Un `import 'leaflet.markercluster'` side-effect crea un namespace separato.
> Host: `components/radar-map/leaflet/` — **LEGACY FREEZE** (nessuna feature nuova salvo bug critici).

**SOLUZIONE (solo legacy):**

**1. `angular.json` → `scripts[]` (necessari al path Leaflet dormiente):**
```json
"scripts": [
  "node_modules/leaflet/dist/leaflet.js",
  "node_modules/leaflet.markercluster/dist/leaflet.markercluster.js"
]
```

**2. Accedere a Leaflet via `window` (NON `import * as L`):**
```typescript
const L = (window as any).L as typeof import('leaflet');
// VIETATO: import * as L from 'leaflet';
// VIETATO: import 'leaflet.markercluster';
```

**3. Types (devDependencies):** `@types/leaflet`, `@types/leaflet.markercluster` — compile-time only; runtime = `window.L`.

---

## Regola 11: Limitazioni Zoom, Bounding Box Focus e Legenda Monoriga

1. **Limitazioni Zoom all'indietro:** `minZoom: 2.2`. Path **Leaflet**: `maxBounds` globo + `maxBoundsViscosity: 1.0`. Path **MapLibre globe**: **non** usare `maxBounds` (blocca rotate / falsa nazione-open); usare `renderWorldCopies: false` + `clickTolerance: 12` + suppress click post-gesture.
2. **Focus Bounding Box (US & RU):** Per evitare crash o anomalie nel calcolo dinamico dei bounds derivati dall'antimeridiano, utilizzare bounding box statici hardcoded (literal da `radar-map.component.ts`):
   * Stati Uniti (`US`): `L.latLngBounds(L.latLng(24.396308, -125.0), L.latLng(49.384358, -66.93457))`
   * Russia (`RU`): `L.latLngBounds(L.latLng(41.1856, 19.6389), L.latLng(81.8587, 169.0))`
3. **Legenda Tipologie (Popover Grid 3 Colonne A-Z & Evidenziazione Mappa):** La legenda in basso al centro della mappa usa il trigger compatto `🏷️ LEGENDA TIPOLOGIE 15` (o `N/15` se attiva un'evidenziazione bloccata) e gestisce l'illuminazione geospaziale sulla mappa. Mostra 15 card selezionabili A-Z (Ambiente 🌿 a Tecnologia 💻) con dot colorato, emoji, nome e badge conteggio notizie `(14)`. Layout fluido con troncamento etichetta e badge `(14)` sempre visibile. L'hover o la selezione cliccata illumina le campiture corrispondenti sulla mappa (`fill-opacity` = `0.85`), lasciando le altre tipologie al loro colore ed opacità standard (`0.34`), senza oscurarle. Si chiude automaticamente quando lo zoom raggiunge la modalità marker (zoom >= 4 / `pinModeActive`). Il filtraggio effettivo dei dati articoli risiede nel selettore Tipologia in toolbar.
4. **Allineamento Tooltip Nazioni:** La riga del tooltip delle nazioni (`.tooltip-row`) deve allineare perfettamente flag, nome e badge a livello di baseline/center impostando un `line-height` comune ed allineando i flex item.
5. **Livello di Zoom Massimo Focus:** Lo zoom durante l'azione di focus su nazione deve essere moderato (`maxZoom: 4` o inferiore nel `fitBounds`) per prevenire uno zoom-in troppo profondo che farebbe perdere il contesto.

---

## Regola 12: Relazioni Geospaziali (Grafo — Fase H)

1. **Gestione Stato e Risorsa**:
   - Utilizzare `StateService.mapRelationsResource` per caricare le relazioni bilaterali dal backend.
   - Esporre il segnale derivato `filteredMapRelations` che filtra le relazioni in base ai filtri Tipologia attivi (toolbar).
   - **Wave 1 — filtro nazioni MapLibre (DONE):** `relationCountriesEnabled` (default `Set` vuoto → **0 archi**), `relationCountryOptions`, `visibleMapRelations` (OR stella: arco se `source ∈ enabled` **oppure** `target ∈ enabled`). API: `toggleRelationCountry` / `selectAllRelationCountries` / `clearRelationCountries` + prune. Binding mappa: `[mapRelations]="state.visibleMapRelations()"` — **non** `filteredMapRelations()` diretto. Piano: `plan-audit/complete/plan_impl_map_relations_nation_filter.md`.
   - UI toolbar (pattern unificato, no `p-multiSelect`): **Sentiment**, **Tipologia** e **RELAZIONI ATTIVE** usano lo stesso tooltip — titolo `0.75rem` JetBrains Mono uppercase, **un solo** bottone full-width Seleziona tutto ↔ Deseleziona tutto, text box filtro, **toggle iOS a destra**. Relazioni: contatore `X/Y` + filtro nazione anche su Nazioni Coinvolte / Salvate. **VIETATO** toccare `radar-sidebar/**`. **VIETATO** ripristinare un pannello dock sinistro dedicato.
2. **Layer Dedicato sulla Mappa**:
   - **MapLibre (default):** archi great-circle / LineString su source layer dedicato (hit-buffer hover/click).
   - **Leaflet legacy:** `relationsLayerGroup` su pane `relationsPane` (z 550) con `L.polyline` Bézier — **VIETATO** `leaflet-curve`.
3. **Visibilità e Sincronizzazione**:
   - La visibilità del layer relazioni deve essere sincronizzata con la modalità Day View (`articles().length === 0`).
   - Gli archi devono essere nascosti automaticamente solo se una nazione è aperta (nation detail view).
   - **MapLibre:** stile archi indipendente dallo zoom (sempre macro multicolore solida) — niente ridisegno al crossing `MAP_ZOOM_PIN_THRESHOLD`. Filtro nazioni Wave 1 **non** cambia paint/hover/draw.
   - **Leaflet legacy:** su `zoomend` / attraversamento di `MAP_ZOOM_PIN_THRESHOLD` (4), ridisegnare gli archi passando da mode pin (zoom >= 4, dash+fan) a mode macro (zoom < 4) e viceversa.
4. **Fingerprint Geometria Mappa**:
   - Per ottimizzare le prestazioni, il ricalcolo degli elementi della mappa (inclusi gli archi) deve basarsi su un fingerprint che include lo stato delle relazioni, per evitare di ridisegnare la mappa inutilmente se non ci sono cambiamenti strutturali.
5. **Drawing degli Archi**:
   - **MapLibre (default):** una sola curva aggregata per coppia di nazioni, segmenti colore ∝ volume per categoria (`CATEGORY_CSS_VARS`), linea **continua** (no geometric dash, no fan parallelo), opacity ~0.45 — **a tutti i livelli di zoom**.
   - **Leaflet legacy — Zoom ≥ 4:** una curva per-categoria (`CATEGORY_CSS_VARS`), spessore `Math.min(6, 1 + volume * 0.5)`, opacity 0.8, tratteggio **geometric dash** (segmenti lat/lng + gap — **vietato** affidarsi a `line-dasharray` / CSS dash come unico tratteggio: scorre al pan). Multi-cat → fan parallelo.
   - **Leaflet legacy — Zoom < 4:** macro aggregata multicolore, spessore soft, opacity ~0.45.
   - Hover/click → `relationClicked` → `loadRelationArticles` (bilaterale A↔B).
   - **Fuori scope Wave 1 (chiuso):** soft-restyle archi / nation-hover preview. **Wave 2 (active):** archi elevati 3D — `plan-audit/active/plan_impl_map_relations_arcs_3d.md`.

---

## Criteri di Accettazione Automatici

| Pattern Vietato                                       | Motivo                                              |
|-------------------------------------------------------|-----------------------------------------------------|
| `NgModule` nei componenti Angular                     | Pattern obsoleto in Angular 21                      |
| URL CDN per GeoJSON                                   | Rompe l'offline, dipendenza esterna                 |
| `BehaviorSubject` per stato UI                        | Usare Signals invece                                |
| Colori hardcoded (es. `#ff0000`)                      | Devono usare CSS vars della palette                 |
| `maxClusterRadius` diverso da 40                      | Deve matchare `radar-map.component.ts`                             |
| `spiderfyOnMaxZoom` diverso da false                  | Espansione cluster custom; non spiderfy automatico legacy          |
| `npm install`/`npm ci` Docker senza `--legacy-peer-deps` | Peer deps Angular 21 / PrimeNG                                  |
| Modifiche a `radar-sidebar/**` o `app-article-list`   | Sidebar freeze — vedi Regola CRITICAL                              |
| Modal al posto della sidebar split-screen             | Specifica fissa del PRD                             |
| Testo placeholder statico in HTML                     | Viola la regola di completezza del codice           |
| `COPY dist/[nome]/` senza `/browser` nel Dockerfile   | Angular 21 genera `dist/[nome]/browser/` — path errata causa Nginx 404 |
| `npm install` o `npm ci` senza `--legacy-peer-deps`   | Causa fallimenti di installazione per conflitti di peer dependencies tra Angular 21 e librerie terze |
| `import * as L from 'leaflet'` nel componente legacy   | Con esbuild crea namespace separato, markercluster non funziona |
| `import 'leaflet.markercluster'` side-effect nel componente | Il plugin non trova `window.L` e lancia TypeError  |
| Nuove feature sul path `radar-map/leaflet/` (LEGACY FREEZE) | Sviluppo attivo solo su `maplibre/` + facade |
| `MAP_RENDERER` default diverso da `maplibre` senza decisione esplicita | Gate `verify-map-renderer` |
| `maxZoom` per fitBounds del focus maggiore di 4        | Lo zoom di focus risulterebbe troppo profondo        |
| Zoom all'indietro senza `minZoom` (Leaflet: anche senza `maxBounds`) | Consente navigazione verso aree nere / infinite |
| `maxBounds` su MapLibre **globe** | Clampa rotate → freeze percepito / click → fitBounds |
| Legenda con `flex-wrap: wrap` senza nowrap/scroll     | Rischia di spezzarsi verticalmente su schermi piccoli|
| Utilizzo di `leaflet-curve` o nuove dipendenze npm per archi Leaflet | Vietato sul path legacy; MapLibre usa LineString / style nativo |
| Archi relazioni visibili in nation detail o non aggiornati al cambio zoom | Vietato; devono essere nascosti in nation detail e ridisegnati tra macro/pin crossing `MAP_ZOOM_PIN_THRESHOLD` (4) |
