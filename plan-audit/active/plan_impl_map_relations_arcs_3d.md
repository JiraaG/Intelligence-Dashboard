# Piano — Archi relazioni elevati 3D MapLibre (Wave 2)

**Stato:** ACTIVE — **analisi / spike**; prerequisito Wave 1 = **GATE VERDE** ([`../complete/plan_impl_map_relations_nation_filter.md`](../complete/plan_impl_map_relations_nation_filter.md))  
**Data:** 2026-07-20  
**Branch:** `feature/upgrades`

**Prerequisito obbligatorio:** [`../complete/plan_impl_map_relations_nation_filter.md`](../complete/plan_impl_map_relations_nation_filter.md) (Wave 1 — filtri nazioni) — **COMPLETE**  
**Motore mappa Phase I:** [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md)  
**Follow-up globo §3.J (separato):** [`plan_impl_map_globe_projection.md`](plan_impl_map_globe_projection.md)  
**Archi UI storici:** [`../complete/plan_archi_hatching_multicolor.md`](../complete/plan_archi_hatching_multicolor.md)  
**Quadro:** [`../STATUS.md`](../STATUS.md)

---

## 1. Obiettivo

Far sì che le relazioni MapLibre non appaiano più come linee **draped** sulla superficie del globo (“disegnate sulla mappa”), ma come archi **elevati** (flying / above-surface) a pitch tipico 3D, mantenendo:

- 1 arco aggregato per coppia (macro multicolore — AS-IS post-`0d942ed`)
- hover thicken + Popup + `relationClicked` (comportamento prodotto)
- filtro nazioni Wave 1 (solo archi `visibleMapRelations`)
- sidebar freeze; path Leaflet invariato

---

## 2. Relazione con Wave 1 (dettaglio)

| Aspetto | Wave 1 (filtri) | Wave 2 (questo piano) |
|---------|-----------------|------------------------|
| Densità spaghetti | Controllata da flag (default OFF) | Non risolve densità; assume W1 già live |
| Paint 2D attuale | **Invariato** | **Sostituisce** il layer visuale flat con path 3D |
| Hit-test / click | Layer `RELATIONS_HIT` 2D | Da riprogettare o mantenere shadow 2D |
| File State / pannello | Toolbar **RELAZIONI ATTIVE** + State | **Non** ritoccare salvo wiring se serve |
| `great-circle.ts` | Non toccare | Estendere a 3D (`[lng,lat,alt]`) o helper gemello |
| Dipendenze npm | Nessuna nuova | Possibile `deck.gl` se si sceglie opzione C |

**Ordine vincolante:** GATE W1 (**DONE**) → spike W2 → implementazione W2.

---

## 3. Diagnosi AS-IS (perché sembrano piatte)

| Pezzo | Dove | Comportamento |
|-------|------|----------------|
| Geometria | [`great-circle.ts`](../../radar/frontend/src/app/components/radar-map/maplibre/great-circle.ts) | Bézier su lat/lng → `[lng, lat][]` **senza altitudine** |
| Draw | [`radar-map-maplibre.component.ts`](../../radar/frontend/src/app/components/radar-map/maplibre/radar-map-maplibre.component.ts) `buildMacroRelationFeatures` | `LineString` 2D; segmenti colore ∝ volume |
| Layer visual | `RELATIONS_LINE` `type: 'line'` | Draped su ellissoide / globo |
| Layer hit | `RELATIONS_HIT` opacity 0 | Hover/click affidabile |

Con `projection: globe` + pitch, le linee restano sulla superficie → lettura “ink on map”, non “cable in air”.

---

## 4. Vincoli tecnici MapLibre 5.24 (repo)

**Verificato nel frontend (`maplibre-gl@^5.24.0`):**

- **Assente** `line-z-offset` / `line-elevation-reference` (API tipiche **Mapbox** elevated-line — non nei `.d.ts` MapLibre del progetto).
- Upstream MapLibre: richiesta altitude LineString/Marker ancora aperta/storica (#644 / #6755) — **non** contare su layer `line` nativo elevated.
- **Assenti** oggi `deck.gl` / `three` in [`package.json`](../../radar/frontend/package.json).
- Terrain DEM (`setTerrain`) **non** è il requisito prodotto: serve altezza **artificiale** lungo l’arco (parabola), non quota suolo.

**Conclusione rigorosa:** non si “alzano” gli archi con un paint property sul layer attuale. Serve path **B** o **C** sotto.

---

## 5. Opzioni (valutazione)

| ID | Approccio | Effetto | Effort | Rischi | Hit / hover | Verdetto |
|----|-----------|---------|--------|--------|-------------|----------|
| A | Pseudo-3D (più curvatura Bézier 2D) | Ancora flat | Basso | Basso | Invariato | **Scartata** — non soddisfa l’obiettivo |
| B | **CustomLayer** WebGL `renderingMode: '3d'` + vertici `[lng,lat,alt]` parabola | Vero elevate | Medio-alto | Globo matrix, GL context, colori multi-segment | Shadow hit 2D **o** raycast | **Candidato primario** (no nuova lib) |
| C | **deck.gl `ArcLayer`** (già opzionale in [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md) W3) | Flying arc maturo | Medio | Dipendenza, sync camera/globo, budget bundle | Picking deck | **Fallback** se B fallisce spike |

**Raccomandazione:** spike **B vs C** (½–1 giorno) su globo + pitch ≥45°; scegliere prima dell’impl completa.

---

## 6. Spike GATE (obbligatorio prima dell’impl)

### Setup

- Branch `feature/upgrades`, W1 filtri già mergeati/committati.
- 3–5 archi di test (anche mock) con USA hub.

### Criteri PASS

1. A pitch ≥45° l’arco è **chiaramente sopra** la superficie (non collineare al basemap).
2. Rotate/pitch/drag non spezzano la geometria in modo grave.
3. Hover o equivalente → tooltip/breakdown; click → `relationClicked` / carosello bilaterale.
4. Filtro nazioni W1 continua a controllare quali archi esistono.
5. Nessuna regressione pin / hatching / spider / CSP.
6. Budget FE entro warn/error `angular.json` (o aggiornamento documentato).

### FAIL →

- Documentare blocco; non forzare A (pseudo-3D) come “3D”.
- Rivalutare C o deferire.

---

## 7. Design proposto (post-spike)

### Geometria

- Estendere o aggiungere `greatCircle3d(lat1,lng1,lat2,lng2,n,curvature,peakAltMeters) → [lng,lat,alt][]`.
- Altitudine: `h(t) = H * sin(π t)` (t∈[0,1]); `H` scalato con distanza angolare (cap ragionevole).
- Multicolore: N polyline elevate per segmento categoria **oppure** vertex color nello shader (decisione spike).

### Integrazione host

- File tipici:
  - `maplibre/great-circle.ts` (+ spec)
  - nuovo `maplibre/relations-arc-3d-layer.ts` (CustomLayer) **oppure** bridge deck
  - `radar-map-maplibre.component.ts` — swap visual; strategia hit
- Conservare semantiche: `arcKey`, tooltip, `sourceCountry` / `targetCountry` / category.
- Preferenza hit: mantenere `RELATIONS_HIT` 2D invisibile allineato alla footprint lat/lng (meno rischio) mentre il visual è 3D.

### Fuori scope Wave 2

- Spacing geometrico tra archi
- Nation-hover preview relazioni
- Path Leaflet
- Terrain DEM reale / skybox §3.J (altro piano)
- Soft-restyle opacity “R1” non richiesto dal PO (hover AS-IS)

---

## 8. Docs a GATE W2

- Aggiornare Regola 12 [`radar/.ecc/rules/frontend.md`](../../radar/.ecc/rules/frontend.md)
- Post-ship in [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md) (riga Archi)
- [`docs/03_frontend_and_ui.md`](../../docs/03_frontend_and_ui.md), FE README
- Marcare questo piano → `complete/` a GATE; aggiornare [`../STATUS.md`](../STATUS.md)

---

## 9. Riferimenti esterni (spike)

- MapLibre `CustomLayerInterface` + `renderingMode: '3d'`
- Demo community elevated linestring (es. weglide/maplibre-3d-linestring-demo) — ispirazione, non dipendenza
- deck.gl ArcLayer docs — solo se si sceglie C
- **Non** copiare Mapbox `line-z-offset` nel codice MapLibre sperando che esista
