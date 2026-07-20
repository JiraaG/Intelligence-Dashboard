# Piano — Archi hatching multicolore + interazione bilaterale

**Progetto:** Radar Informativo Globale  
**Documento:** `plan-audit/complete/plan_archi_hatching_multicolor.md`  
**Stato:** **DONE / GATE VERDE** (2026-07-18)  
**Contesto:** follow-up Fase H ([`master_plan_impl_phase_H_geospatial_graph.md`](master_plan_impl_phase_H_geospatial_graph.md))

**Overview:** Archi in hatching (zoom &lt; 5) come 1 linea aggregata **multicolore** per coppia paese↔paese; a zoom ≥ 5 linee **per-categoria** con tratteggio geometrico (no `dashArray`). Hover/click → sidebar bilaterale A↔B. Pane `relationsPane` (z 550) sopra confini/label, sotto i pin.

---

## Deliverable chiusi

| Zoom | Vista | Comportamento |
|------|--------|----------------|
| **&lt; 5** | Hatching | 1 Bézier multicolore + hit-area; click → articoli bilaterali **tutte** le categorie |
| **≥ 5** | Pin | 1 linea per `(pair × category)`, fan offset, tratteggio geometrico + hit-area; click → bilaterale **solo** quella tipologia |
| Nation open | Detail | Layer relazioni nascosto |

**Interazione**

- Hit-area `.relational-arc-hit` su `relationsPane` (canvas renderer sul pane dedicato).
- Label tile CartoDB su `labelsPane` z **450**, `pointer-events: none` (sotto gli archi).
- Emit `relationClicked` → `StateService.loadRelationArticles` / `App.onRelationClick` (preserveZoom, soft-reload SSE con `relationFocus`).

**Bugfixati**

1. Sovrapposizione categorie stessa Bézier a zoom ≥ 5 → fan offset.
2. Tratteggio che “scorre” al pan → tratteggio geometrico lat/lng (no `dashArray`).
3. Hover rubato da poligoni/label in Europa densa → `relationsPane` z 550 + hit più larga.

**File principali:** `radar-map.component.ts` / `.scss` / `.spec.ts`, `leaflet.stub.ts`, `state.service.ts`, `app.ts` / `app.html`, `docs/03`, ECC `frontend.md` + `angular-map-expert.md`.

---

## Decisione v1 (confermata)

1. Zoom &lt; 5: aggregazione FE per pair; segmenti colorati ∝ volume; tooltip breakdown; click bilaterale all-cat.
2. Zoom ≥ 5: per-categoria + tratteggio geometrico + fan; click bilaterale filtered by category.
3. Nation-open: hide.
4. No nuove dipendenze npm / `leaflet-curve`.

---

## Residuo opzionale (non blocca GATE)

- Linea **multicolore aggregata** anche a **zoom ≥ 5**: **chiuso su MapLibre** (2026-07-20 — stile macro a tutti gli zoom). Resta intenzionalmente su **Leaflet legacy** (dash+fan ≥5, LEGACY FREEZE).
- Frecce direzionali; query API server-side per pair; chip navigabili.

---

## Checklist validazione (eseguita)

1. Seed day-view zoom 3: archi multicolore + hover/click bilaterale.
2. Zoom ≥ 5: N linee per N categorie, tratteggio fermo al pan, hover hit-area.
3. Click pin-arco: sidebar solo tipologia, entrambe le nazioni.
4. Nation open: archi nascosti.
5. Unit test FE: 41 pass; Docker rebuild frontend healthy.
