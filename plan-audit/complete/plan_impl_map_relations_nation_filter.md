# Piano — Filtro nazioni Relazioni (Wave 1)

**Stato:** ACTIVE — pronto per implementazione  
**Data:** 2026-07-20  
**Branch:** `feature/upgrades`  
**HEAD contesto grafico archi flat:** `0d942ed` (macro multicolore solida MapLibre a tutti gli zoom)

**Documento gemello (Wave 2 — archi elevati 3D):** [`plan_impl_map_relations_arcs_3d.md`](plan_impl_map_relations_arcs_3d.md)  
**Contesto motore mappa:** [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md) (Phase I MapLibre)  
**Archi UI storici (Leaflet + click bilaterale):** [`../complete/plan_archi_hatching_multicolor.md`](../complete/plan_archi_hatching_multicolor.md)  
**Quadro:** [`../STATUS.md`](../STATUS.md)

---

## 1. Obiettivo

Ridurre lo spaghetti delle relazioni in day-view MapLibre **senza** cambiare lo stile grafico degli archi: aggiungere un pannello verticale sinistro **Relazioni** con flag per nazione (default tutte spente) e Seleziona/Deseleziona tutto.

---

## 2. Decisioni prodotto (bloccate PO 2026-07-20)

| # | Decisione |
|---|-----------|
| 1 | Default: **nessuna** nazione attiva → **0 archi** permanenti |
| 2 | Flag singola nazione + **Seleziona tutto** / **Deseleziona tutto** |
| 3 | Semantica **OR (stella):** arco visibile se `source ∈ enabled` **oppure** `target ∈ enabled` (USA on + Cina off → arco USA↔Cina **sì**) |
| 4 | **Niente** preview relazioni su hover nazione (non sviluppare) |
| 5 | Colore / opacity / weight / hover thicken+Popup archi: **invariati** (nessun restyle W1) |
| 6 | **No** spacing geometrico / fan offset / edge-bundling |
| 7 | Solo path **MapLibre**; Leaflet LEGACY FREEZE |
| 8 | **Non** modificare `radar-sidebar/**` (freeze articoli) — nuovo componente dedicato |
| 9 | Archi “in aria” 3D = **Wave 2** → [`plan_impl_map_relations_arcs_3d.md`](plan_impl_map_relations_arcs_3d.md) — **non** in questo piano |

---

## 3. Pipeline dati

```text
GET /api/map-relations
  → mapRelationsResource (date + sentiment server)
  → filteredMapRelations (Tipologia client, già esistente)
  → visibleMapRelations (NUOVO: filtro nazioni OR su enabled)
  → app-radar-map [mapRelations] → drawGeospatialRelations AS-IS
```

Pannello `radar-relations-panel` scrive solo su `relationCountriesEnabled` in StateService.

---

## 4. Implementazione

### 4.1 State — [`radar/frontend/src/app/services/state.service.ts`](../../radar/frontend/src/app/services/state.service.ts)

- `relationCountriesEnabled = signal<ReadonlySet<string>>(new Set())` — default vuoto.
- `relationCountryOptions = computed` — endpoint unici da `filteredMapRelations`, sort nome IT (`Intl.DisplayNames`), `arcCount` (n° righe o coppie che toccano il codice).
- `visibleMapRelations = computed` — filtra `filteredMapRelations` con OR.
- API: `toggleRelationCountry(code)`, `selectAllRelationCountries()`, `clearRelationCountries()`.
- Prune: quando cambiano le opzioni (data/Tipologia), rimuovere da `enabled` i codici non più presenti; **non** auto-selezionare.
- Spec in `state.service.spec.ts`: default `[]`; US on / CN off → arco presente; select-all / clear.

### 4.2 UI — toolbar [`radar-toolbar`](../../radar/frontend/src/app/components/radar-toolbar/)

- Sezione **RELAZIONI ATTIVE** (stesso pattern di NOTIZIE LETTE/TROVATE / SALVATE): contatore `enabled/total`.
- Tooltip: Seleziona tutto / Deseleziona tutto; lista scrollabile con **checkbox** + flag emoji + nome IT (niente badge volume).
- Campo testo **Filtra nazione…** anche su Nazioni Coinvolte e Nazioni Salvate.
- Rimosso brand-group logo/RADAR dalla toolbar (più spazio).
- Wiring mappa: [`app.html`](../../radar/frontend/src/app/app.html) binding `[mapRelations]="state.visibleMapRelations()"`.
- **Non** creare un pannello dock sinistro separato.

### 4.3 MapLibre — **non modificare** paint/hover/draw

- [`radar-map-maplibre.component.ts`](../../radar/frontend/src/app/components/radar-map/maplibre/radar-map-maplibre.component.ts): riceve già meno righe via input; **zero** cambio a `buildMacroRelationFeatures`, opacity, hover.
- Non toccare [`great-circle.ts`](../../radar/frontend/src/app/components/radar-map/maplibre/great-circle.ts).
- Non toccare `radar-map/leaflet/**`.

### 4.4 Docs ECC / prodotto (a GATE W1)

- [`radar/.ecc/rules/frontend.md`](../../radar/.ecc/rules/frontend.md) Regola 12 — filtro nazioni MapLibre.
- Spatial-mocking Test 7 (SoT `.agents/skills` + mirror `.ecc/skills`).
- [`docs/03_frontend_and_ui.md`](../../docs/03_frontend_and_ui.md), [`radar/frontend/README.md`](../../radar/frontend/README.md).
- Cross-link da questo file a Wave 2.

---

## 5. Criteri di accettazione W1

1. Day-view fresco: **nessun** arco finché non si flagga.
2. Flag USA: solo archi con endpoint USA (anche verso paesi non flaggati).
3. Seleziona tutto / Deseleziona tutto funzionanti sulla lista corrente.
4. Tipologia toolbar continua a filtrare categorie **prima** del filtro nazioni.
5. Nation-open: pannello nascosto; archi nascosti (comportamento esistente).
6. Hover/click arco: thicken + Popup + `relationClicked` **identici** a pre-W1.
7. `npm run typecheck && npm run test:ci` verdi; rebuild Docker FE smoke.

---

## 6. Ordine vs Wave 2

| Ordine | Piano | Quando |
|--------|-------|--------|
| 1 | **Questo documento (W1 filtri)** | Ora — chat sviluppo |
| 2 | [`plan_impl_map_relations_arcs_3d.md`](plan_impl_map_relations_arcs_3d.md) | Solo dopo GATE W1; spike CustomLayer vs deck.gl |

**Divieto:** non implementare archi elevati 3D, soft-restyle, o nation-hover preview in W1.

---

## 7. Riferimenti tecnici utili

- Model: [`map-relation.model.ts`](../../radar/frontend/src/app/models/map-relation.model.ts)
- Skills: `radar-sidebar-freeze`, `spatial-data-mocking`, `angular-developer`, `radar-api-contract`
- UI: http://localhost/ — Compose `radar/docker-compose.yml`
- Commit recente archi solidi: `0d942ed`
