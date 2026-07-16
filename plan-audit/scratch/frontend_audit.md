# Frontend Code Audit — Radar Informativo Globale

> **STORICO (2026-07-15):** snapshot pre–fix map. Claim «cap 24» / `SPIDERFY_MAX_ICONS` **non è più runtime** (2026-07-16): spiderfy mostra tutte le icone categoria; size/distanza adattivi; restore hub on failure. SoT attuale: `radar/.ecc/rules/frontend.md`, `Implementation_Plan.md` Map UX. Non usare questo file come checklist operativa senza riverifica.

> **Scope:** `radar/frontend/src/app/` (+ `angular.json` / `package.json` / `Dockerfile` solo dove richiesto dalla checklist)  
> **Checklist:** `scratch/frontend_rules.md` (88 items, 16 domini)  
> **Data:** 2026-07-15  
> **Metodo:** walk checklist → pass/fail con evidenza; **nessuna modifica** al source app  
> **Conteggi FAIL:** **P0 = 0** · **P1 = 1** · **P2 = 4**

---

## Executive summary

Il frontend è **largamente conforme** alle governance rules: sidebar freeze rispettata nello stato attuale (`p-carousel`, no `article-list`), Leaflet via `window.L`, icone XSS-safe con `textContent`, day-view su `getMapSummary`, nation open con concatenazione cursor fino a `next_cursor == null`, overlay `100vw` + `invalidateSize`, bounds US/RU letterali, cluster `maxClusterRadius: 40` / `spiderfyOnMaxZoom: false`, spiderfy single-category ~~con cap 24~~ *(storico; runtime attuale = no hard cap)*.

L’unico scostamento **P1** è la superficie errore nation-fetch: fallimenti di `loadCountryArticles` non popolano `StateService.error` / banner toolbar. Il resto dei gap è igiene o difesa in profondità (**P2**).

---

## Matrice pass/fail per dominio

| # | Dominio | Items | Esito | Note |
|---|---------|------:|-------|------|
| 1 | Sidebar freeze | 5 | **PASS** | Codice corrente conforme; nessuna violazione architetturale |
| 2 | Carousel + `updateCarouselHeight` | 4 | **PASS** | `article-card-{id}`; no `.p-carousel-item-active` |
| 3 | Read / unread | 4 | **PASS** | Fingerprint senza `is_read` + `syncMarkerReadState` |
| 4 | Leaflet / `window.L` | 5 | **PASS** | `scripts[]` + `getLeaflet()`; solo `import type` |
| 5 | XSS-safe icons | 3 | **PASS** | DOM + `textContent`; emoji da `CATEGORY_ICONS` |
| 6 | API MapSummary / ArticlesPage | 10 | **PASS** | Envelope + `expand`/`reduce`; pin summary day-view |
| 7 | Overlay + `invalidateSize` | 6 | **PASS** | Shell `App`; ordine invalidate → spiderfy |
| 8 | MOCK_MODE | 4 | **FAIL parziale** | Token OK; **P1** nation error non in banner |
| 9 | Categorie (10) | 4 | **PASS** | 10 SoT; mock primary legali (`Chip`/`Acqua` solo come tags) |
| 10 | Bounding box US/RU | 3 | **PASS** | Literal esatti + bypass GeoJSON |
| 11 | Spiderfy / cluster | 11 | **PASS*** | *P2: filtro esplicito `primary_category` assente in `clusterclick` |
| 12 | Zoom / hatching / legenda | 7 | **PASS** | Soglia 5; owner `getOrCreateComboPattern`; no `appLeafletHatch` in uso |
| 13 | Stack Signals / Standalone | 9 | **PASS** | Standalone + signals; RxJS solo HTTP |
| 14 | GeoJSON / assets | 2 | **PASS** | `assets/data/countries.geo.json` via HttpClient |
| 15 | Palette / template | 3 | **PASS*** | *P2: alcuni `rgba` ciano hardcoded in TS/SCSS mappa |
| 16 | Misc | 8 | **PASS*** | *P2: `UI_OFFSETS` dead; cartella `shared/directives` vuota |

\* = dominio globalmente PASS con finding P2 minori elencati sotto.

---

## Sidebar freeze — verifica stato corrente

| Check | Esito | Evidenza |
|-------|-------|----------|
| `p-carousel` presente | **OK** | `radar-sidebar.component.html` L101–184 |
| Assenza `app-article-list` / `article-list` | **OK** | Grep su `src/app` negativo |
| `updateCarouselHeight` via `article-card-{id}` | **OK** | `radar-sidebar.component.ts` L66 |
| No `ResizeObserver` sul carosello | **OK** | Polling `setInterval` L62–86 |
| No `.p-carousel-item-active` per altezza | **OK** | Assente |
| Read toggle UI in sidebar → `StateService` | **OK** | UI freeze; mutazione in `state.service.ts` |
| Marker `.marker-read` fuori sidebar | **OK** | Solo `radar-map.component.ts` |

**Verdetto freeze:** il codice sidebar **non viola** le regole di freeze. Non è necessario (né consentito) riscrivere l’architettura sidebar per conformità. Eventuali fix read/unread restano in `state.service.ts` + `radar-map.component.ts`.

---

## Note spiderfy / cluster

- **Day view (zoom ≥ 5):** un pin nazione in `summaryMarkerGroup` con anello conic; `iconCreateFunction` dei cluster di categoria restituisce icona `hidden` (pallini per-categoria deprecati).
- **Nation open:** marker dettaglio per categoria + hub `radar-spider-root`; spiderfy **una sola** categoria attiva (`focusAndSpiderfyCategory` / `lastSpiderfyKey` in `App`).
- **Cap:** `SPIDERFY_MAX_ICONS = 24` con park/restore dei layer in eccesso.
- **Opzioni cluster:** `maxClusterRadius: 40`, `spiderfyOnMaxZoom: false`, `zoomToBoundsOnClick: false`, `showCoverageOnHover: false`; **nessun** `disableClusteringAtZoom: 18`.
- **Lifecycle hub:** `collapseAllGraphs(false, false)` setta `restoreDetailHubOnUnspiderfy = false`; handler `unspiderfied` non ripristina hub in quel caso.
- **Dummy:** `isDummy: true` per raggruppamento spaziale nation (non interattivi).
- **Offset:** `UI_OFFSETS` dichiarato ma **non applicato** (marker dettaglio condividono il centroide; lo spread è dello spiderfy) → finding P2-01.

---

## Findings FAIL

### [FE-AUD-001] Errore nation-fetch non arriva al banner toolbar
- **Priorità:** P1
- **Checklist:** FE-MK-02
- **File e Range Righe:** `radar/frontend/src/app/services/state.service.ts#L110-L127`, `radar/frontend/src/app/app.ts#L122-L125`, `radar/frontend/src/app/app.html#L6-L7`
- **Casistica Rilevata & Rischio:** `StateService.error` espone solo `mapSummaryResource.error()`. Un fallimento di `loadCountryArticles` logga, svuota `detailArticles`, rilancia; `App.onCountryClick` cattura e chiude la sidebar **senza** impostare uno stato errore. L’utente vede chiusura silenziosa (o paese “vuoto”) invece del banner `apiError` della toolbar. Non c’è fallback mock (conforme), ma manca la metà “Errore API → banner”.
- **Evidenza (snippet attuale):**
```typescript
// state.service.ts
} catch (err) {
  console.error('[StateService] Impossibile caricare articoli nazione:', err);
  this.detailArticles.set([]);
  throw err;
}

// app.ts
} catch {
  if (gen !== this.nationOpenGeneration) return;
  this.closeSidebar();
}

// state.service.ts — solo summary
readonly error = computed(() => this.mapSummaryResource.error());
```
- **Codice Correttivo (Diff):**
```diff
--- a/radar/frontend/src/app/services/state.service.ts
+++ b/radar/frontend/src/app/services/state.service.ts
@@
-  readonly error = computed(() => this.mapSummaryResource.error());
+  /** Nation-open fetch error (separate from day-view rxResource). */
+  readonly detailError = signal<unknown>(null);
+
+  readonly error = computed(
+    () => this.mapSummaryResource.error() ?? this.detailError(),
+  );
@@
   async loadCountryArticles(countryCode: string): Promise<Article[]> {
     const f = this.filters();
     this.detailLoading.set(true);
+    this.detailError.set(null);
     try {
       const all = await firstValueFrom(
         this.articleService.getAllArticlesForCountry(f.date, countryCode.toUpperCase()),
       );
       const filtered = all.filter((art) => this.matchesClientFilters(art, f));
       this.detailArticles.set(filtered);
       return filtered;
     } catch (err) {
       console.error('[StateService] Impossibile caricare articoli nazione:', err);
       this.detailArticles.set([]);
+      this.detailError.set(err);
       throw err;
     } finally {
       this.detailLoading.set(false);
     }
   }
```
```diff
--- a/radar/frontend/src/app/app.ts
+++ b/radar/frontend/src/app/app.ts
@@
   closeSidebar(): void {
     this.nationOpenGeneration++;
     this.lastSpiderfyKey = null;
     this.isSidebarOpen.set(false);
     this.selectedArticle.set(null);
     this.clusterArticles.set([]);
     this.focusCountryCode.set(null);
     this.state.clearDetailArticles();
+    this.state.detailError.set(null);
     this.mapComponent()?.collapseAllGraphs();
     this.scheduleInvalidateSize();
   }
```

---

### [FE-AUD-002] `UI_OFFSETS` dichiarato ma mai usato
- **Priorità:** P2
- **Checklist:** FE-CL-08
- **File e Range Righe:** `radar/frontend/src/app/components/radar-map/radar-map.component.ts#L144-L159`, `radar/frontend/src/app/components/radar-map/radar-map.component.ts#L1258-L1286`
- **Casistica Rilevata & Rischio:** Il commento cita offset legacy; `renderDetailMarkers` posiziona tutti i marker sul centroide nazione senza applicare `UI_OFFSETS` né un `GEO_DIRECTIONS` progressivo. Lo spread effettivo è solo via spiderfy (design attuale OK), ma il campo morto confonde futuri interventi e i test che leggono `UI_OFFSETS` danno falsa sicurezza.
- **Evidenza (snippet attuale):**
```typescript
private readonly UI_OFFSETS: Record<string, [number, number]> = {
  'Nucleare': [34, 0],
  // ...
};

// renderDetailMarkers — nessun uso di UI_OFFSETS:
const marker = L.marker([baseLat, baseLng], { icon }) as ArticleMarker;
```
- **Codice Correttivo (Diff):**
```diff
--- a/radar/frontend/src/app/components/radar-map/radar-map.component.ts
+++ b/radar/frontend/src/app/components/radar-map/radar-map.component.ts
@@
-  /**
-   * Pixel offsets kept for legacy cluster math; day/detail pins no longer
-   * use CSS rings (they drift into neighbouring countries).
-   */
-  private readonly UI_OFFSETS: Record<string, [number, number]> = {
-    'Nucleare':       [34, 0],
-    'Energia':        [28, 20],
-    'Infrastrutture': [11, 32],
-    'Geopolitica':    [-11, 32],
-    'Economia':       [-28, 20],
-    'Tecnologia':     [-34, 0],
-    'Spazio':         [-28, -20],
-    'Ambiente':       [-11, -32],
-    'Salute':         [11, -32],
-    'Sicurezza':      [28, -20],
-  };
-
   private map: Leaflet.Map | null = null;
```
*(In alternativa, se si reintroduce ring geografico pre-spiderfy: applicare offset lat/lng progressivi da una mappa `GEO_DIRECTIONS` in `renderDetailMarkers`.)*

---

### [FE-AUD-003] `clusterclick` senza filtro esplicito `primary_category === cat`
- **Priorità:** P2
- **Checklist:** FE-CL-09
- **File e Range Righe:** `radar/frontend/src/app/components/radar-map/radar-map.component.ts#L456-L494`
- **Casistica Rilevata & Rischio:** L’handler è chiuso sul loop `for (const cat of categories)` e i layer vivono già nel gruppo di quella categoria, quindi il filtro è **implicito**. La checklist richiede filtro esplicito `a.primary_category === cat` come difesa in profondità (regressioni / marker mal-tagged).
- **Evidenza (snippet attuale):**
```typescript
const articleMarkers = childMarkers.filter((m) => !m.isDummy && !m.isSummary && m.articleData);
const arts = articleMarkers
  .map((m) => m.articleData)
  .filter((a): a is Article => !!a);
// manca: a.primary_category === cat
```
- **Codice Correttivo (Diff):**
```diff
--- a/radar/frontend/src/app/components/radar-map/radar-map.component.ts
+++ b/radar/frontend/src/app/components/radar-map/radar-map.component.ts
@@
         const articleMarkers = childMarkers.filter((m) => !m.isDummy && !m.isSummary && m.articleData);
         const arts = articleMarkers
           .map((m) => m.articleData)
-          .filter((a): a is Article => !!a);
+          .filter((a): a is Article => !!a && a.primary_category === cat);
```

---

### [FE-AUD-004] Bordi GeoJSON con `rgba` ciano hardcoded
- **Priorità:** P2
- **Checklist:** FE-PAL-02
- **File e Range Righe:** `radar/frontend/src/app/components/radar-map/radar-map.component.ts#L711-L718`, `radar/frontend/src/app/components/radar-map/radar-map.component.ts#L775-L784`
- **Casistica Rilevata & Rischio:** I colori di categoria hatch usano `var(--color-*)`; i bordi nazione usano letterali `rgba(0, 212, 255, …)` fuori dalle CSS custom properties di progetto. Rischio basso (estetica), ma viola la regola “no HEX/rgba random fuori palette vars”.
- **Evidenza (snippet attuale):**
```typescript
style: () => ({
  color: 'rgba(0, 212, 255, 0.15)',
  weight: 0.5,
  fillOpacity: 0,
  fillColor: 'transparent',
  className: 'country-fill'
})
```
- **Codice Correttivo (Diff):**
```diff
--- a/radar/frontend/src/styles.scss
+++ b/radar/frontend/src/styles.scss
@@
   --color-text-accent:    #58a6ff;
+  --color-map-stroke:     rgba(0, 212, 255, 0.15);
+  --color-map-stroke-active: rgba(0, 212, 255, 0.25);

--- a/radar/frontend/src/app/components/radar-map/radar-map.component.ts
+++ b/radar/frontend/src/app/components/radar-map/radar-map.component.ts
@@
+    const stroke = getComputedStyle(document.documentElement)
+      .getPropertyValue('--color-map-stroke').trim() || 'rgba(0, 212, 255, 0.15)';
     const layer = L.geoJSON(feature, {
       style: () => ({
-        color: 'rgba(0, 212, 255, 0.15)',
+        color: stroke,
```

---

### [FE-AUD-005] Cartella `shared/directives` vuota (residuo hatch)
- **Priorità:** P2
- **Checklist:** FE-ZM-03
- **File e Range Righe:** `radar/frontend/src/app/shared/directives/` (directory vuota)
- **Casistica Rilevata & Rischio:** Hatch owner corretto = `getOrCreateComboPattern` in `radar-map` (**PASS** funzionale). Resta una cartella `shared/directives` vuota, tipico residuo di `appLeafletHatch` rimosso: rumore strutturale, rischio che qualcuno reintroduca la direttiva.
- **Evidenza (snippet attuale):** directory presente, nessun file; nessun import `appLeafletHatch` nel tree.
- **Codice Correttivo (Diff):**
```diff
# rimuovere la directory vuota
- radar/frontend/src/app/shared/directives/
```

---

## Checklist critiche — evidenza PASS (sintesi)

| ID | Esito | Evidenza chiave |
|----|-------|-----------------|
| FE-SB-02 | PASS | `p-carousel` in sidebar HTML; no `article-list` |
| FE-CR-01/02 | PASS | `getElementById('article-card-' + currentArt.id)` |
| FE-CR-03 | PASS | `getAllArticlesForCountry` → `expand` finché `next_cursor != null` |
| FE-RU-02/03 | PASS | fingerprint senza `is_read`; `syncMarkerReadState` + `.marker-read` |
| FE-LL-01..04 | PASS | `angular.json` scripts; `getLeaflet()` / `(window).L`; `import type` only |
| FE-LL-05 | PASS | `testing/leaflet.stub.ts` + setupFiles in `angular.json` |
| FE-XSS-01..03 | PASS | `createSafeMarkerIcon` / pin core via `textContent` + `CATEGORY_ICONS` |
| FE-API-01/02/03 | PASS | `getMapSummary`, `ArticlesPage`, concat pages limit ≤ 100 |
| FE-API-06/07/08/09 | PASS | pin summary; `preserveZoom`/`armSkipCountryFit`; `fitBounds maxZoom: 4`; `refocusCountry` |
| FE-API-10 | PASS | solo `HttpClient` |
| FE-OV-01..06 | PASS | `100vw` split-active; invalidate su resize/open/close; collapse su close |
| FE-MK-01/03/04 | PASS | token default `false`; mock stesse firme Phase 5 |
| FE-BB-01..03 | PASS | US/RU literal bounds esatti |
| FE-CL-01..07,10,11 | PASS | 40 / false / cap 24 / hub lifecycle / dummy / coverage flags |
| FE-ZM-01..07 | PASS | zoom&lt;5 hatch; transition 0.3–0.4s; Carto dark; legenda monoriga |
| FE-ST-* | PASS | Standalone, signals, PrimeNG+SCSS, Leaflet 1.9.x, DestroyRef |
| FE-GEO-* | PASS | asset locale + verify in Docker/`prebuild` |
| FE-MISC-01/02/03/04/07/08 | PASS | Feed: strip in sidebar; flex meta; `npm ci --legacy-peer-deps`; `dist/.../browser`; prettier lint; `infrastructural_entities` in mock |

---

## Rischi residuali non elevati a FAIL

1. **`iconCreateFunction` nascosto:** non usa più `textContent` per count (day pins sostituiscono i pallini categoria) — allineato al design Phase 5, non XSS.
2. **Hatch SVG con `var(--color-*)`:** pass criteria FE-CAT-04 soddisfatto; `getComputedStyle` sarebbe più robusto cross-browser (miglioria opzionale, non FAIL).
3. **`navigatingTargetZoom` scritto e mai letto** — dead field minore (non mappato a ID checklist dedicato).
4. **Path `clusterclick` summary (`arts.length === 0`)** probabilmente morto dopo i country pins; codice difensivo innocuo.

---

## Deliverable per parent agent

| Campo | Valore |
|-------|--------|
| **Path audit** | `c:\Users\lucag\Documents\Dashboard finance\scratch\frontend_audit.md` |
| **P0** | **0** |
| **P1** | **1** (FE-AUD-001 / FE-MK-02) |
| **P2** | **4** (FE-AUD-002..005) |
| **Source app modificato** | No |
