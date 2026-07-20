# Piano — Filtro nazioni Relazioni (Wave 1)

**Stato:** COMPLETE / GATE VERDE — 2026-07-20  
**Branch:** `feature/upgrades`  
**HEAD contesto grafico archi flat (pre-W1):** `0d942ed` (macro multicolore solida MapLibre a tutti gli zoom)  
**Restore point W1:** `ec771b1` su `feature/upgrades` — `git checkout ec771b1`. Quadro: [`../STATUS.md`](../STATUS.md).

**Documento gemello (Wave 2 — archi elevati 3D, ancora ACTIVE):** [`../active/plan_impl_map_relations_arcs_3d.md`](../active/plan_impl_map_relations_arcs_3d.md)  
**Contesto motore mappa:** [`../active/plan_impl_map_3d_globe.md`](../active/plan_impl_map_3d_globe.md) (Phase I MapLibre)  
**Archi UI storici (Leaflet + click bilaterale):** [`plan_archi_hatching_multicolor.md`](plan_archi_hatching_multicolor.md)  
**Quadro:** [`../STATUS.md`](../STATUS.md)

---

## 1. Obiettivo

Ridurre lo spaghetti delle relazioni in day-view MapLibre **senza** cambiare lo stile grafico degli archi: filtro nazioni (default tutte spente) con Seleziona/Deseleziona tutto, esposto in toolbar come **RELAZIONI ATTIVE**.

---

## 2. Decisioni prodotto (bloccate PO 2026-07-20; UI finalizzata in sessione)

| # | Decisione |
|---|-----------|
| 1 | Default: **nessuna** nazione attiva → **0 archi** permanenti |
| 2 | Toggle singola nazione + **Seleziona tutto** / **Deseleziona tutto** |
| 3 | Semantica **OR (stella):** arco visibile se `source ∈ enabled` **oppure** `target ∈ enabled` (USA on + Cina off → arco USA↔Cina **sì**) |
| 4 | **Niente** preview relazioni su hover nazione (non sviluppare) |
| 5 | Colore / opacity / weight / hover thicken+Popup archi: **invariati** (nessun restyle W1) |
| 6 | **No** spacing geometrico / fan offset / edge-bundling |
| 7 | Solo path **MapLibre**; Leaflet LEGACY FREEZE |
| 8 | **Non** modificare `radar-sidebar/**` — UI in **toolbar** (non pannello dock sinistro) |
| 9 | Archi “in aria” 3D = **Wave 2** → [`../active/plan_impl_map_relations_arcs_3d.md`](../active/plan_impl_map_relations_arcs_3d.md) — **non** in questo piano |
| 10 | UI AS-IS: sezione toolbar **RELAZIONI ATTIVE** `enabled/total`; tooltip con toggle **iOS** a destra del nome, bottoni accent, filtro testo; stesso filtro testo anche su Nazioni Coinvolte / Nazioni Salvate; brand logo/RADAR rimosso dalla toolbar |

---

## 3. Pipeline dati

```text
GET /api/map-relations
  → mapRelationsResource (date + sentiment server)
  → filteredMapRelations (Tipologia client)
  → visibleMapRelations (filtro nazioni OR su enabled)
  → app-radar-map [mapRelations] → drawGeospatialRelations AS-IS
```

Toolbar scrive solo su `relationCountriesEnabled` in `StateService` (inject).

---

## 4. Implementazione (AS-IS shipped in `ec771b1`)

### 4.1 State — [`radar/frontend/src/app/services/state.service.ts`](../../radar/frontend/src/app/services/state.service.ts)

- `relationCountriesEnabled`, `relationCountryOptions`, `visibleMapRelations`
- Helper puri: `buildRelationCountryOptions`, `filterMapRelationsByEnabledCountries`
- API: `toggleRelationCountry` / `selectAllRelationCountries` / `clearRelationCountries` + prune effect
- Spec: `state.service.spec.ts`

### 4.2 UI — [`radar-toolbar`](../../radar/frontend/src/app/components/radar-toolbar/)

- **RELAZIONI ATTIVE** + tooltip (toggle iOS, select/clear, filtro nazione)
- Filtro testo nazione anche su LETTE/TROVATE e SALVATE
- Binding: [`app.html`](../../radar/frontend/src/app/app.html) → `[mapRelations]="state.visibleMapRelations()"`

### 4.3 MapLibre — paint/hover/draw **invariati**

- Nessun tocco a `buildMacroRelationFeatures` / `great-circle.ts` / `leaflet/**`

### 4.4 Docs / ECC

- Regola 12 `radar/.ecc/rules/frontend.md`; Test 7 spatial-mocking (SoT + mirror)
- `docs/03_frontend_and_ui.md`, `radar/frontend/README.md`, root `README.md`
- Piano archiviato qui in `complete/`

---

## 5. Criteri di accettazione W1 — GATE VERDE

1. Day-view fresco: **nessun** arco finché non si attiva un toggle.
2. USA on: solo archi con endpoint USA (anche verso paesi off).
3. Seleziona tutto / Deseleziona tutto OK.
4. Tipologia toolbar filtra **prima** del filtro nazioni.
5. Nation-open: archi nascosti (comportamento esistente); toolbar resta disponibile.
6. Hover/click arco: thicken + Popup + `relationClicked` identici a pre-W1.
7. `npm run typecheck && npm run test:ci` verdi; rebuild Docker FE smoke.

---

## 6. Ordine vs Wave 2

| Ordine | Piano | Stato |
|--------|-------|--------|
| 1 | **Questo documento (W1 filtri)** | **COMPLETE / GATE VERDE** (`ec771b1`) |
| 2 | [`../active/plan_impl_map_relations_arcs_3d.md`](../active/plan_impl_map_relations_arcs_3d.md) | Spike/impl **dopo** questo GATE |

---

## 7. Riferimenti

- Model: [`map-relation.model.ts`](../../radar/frontend/src/app/models/map-relation.model.ts)
- Skills: `radar-sidebar-freeze`, `spatial-data-mocking`, `angular-developer`, `radar-api-contract`
- UI: http://localhost/ — Compose `radar/docker-compose.yml`
- Pre-W1 archi solidi: `0d942ed`
- W1 restore: `ec771b1`
