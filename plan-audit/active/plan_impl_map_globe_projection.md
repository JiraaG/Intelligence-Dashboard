# plan_impl_map_globe_projection — Fase J (upgrade globo vero)

> **Stato:** Futuro / BACKLOG (non aprire finché Fase I non è GATE VERDE, salvo raffinamento globe già scelto in W1)  
> **Data:** 2026-07-20  
> **Prerequisito:** [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md) (Fase I) GATE VERDE  
> **Overview:** `radar_overview_and_upgrades.md` §3.J  

Questo documento è il **dettaglio operativo** dell’ampliamento da mappa MapLibre in **2.5D** (mercator + pitch/bearing) al **globo vero** (`projection: globe`). Il piano base I **cita sempre** questo follow-up.

---

## 1. Contesto

Fase I consegna MapLibre come renderer primario con **parity grafica** day-view / archi H / spider / saved / sidebar. Lo spike W1 può chiudere con:

| Esito W1 | Ruolo di questa Fase J |
|----------|-------------------------|
| `projection=globe` già ok | Raffinamento performance / visuale (opzionale) |
| `projection=mercator+pitch` (2.5D) | **Obiettivo principale:** abilitare globe senza regressione parity |

Leaflet resta dormiente (`MAP_RENDERER=leaflet`); J **non** tocca il path 2D.

---

## 2. Precondizioni

1. Fase I GATE VERDE (facade + `maplibre/` + `leaflet/` legacy).
2. Suite FE `typecheck` / `test:ci` green sul path MapLibre.
3. Machine di riferimento documentata (iGPU tipico + eventuale dGPU).
4. Decisione esplicita PO di aprire J (non mischiare con §3.C o §3.D nello stesso PR salvo nota).

---

## 3. Obiettivi / non obiettivi

**Obiettivi**

- Abilitare / stabilizzare `map.setProjection({ type: 'globe' })` (o API equivalente della major pinnata in I).
- Conservare parity Tests 1–7 (spatial-mocking adattato): hatching, pin HTML, archi great-circle, hub/spider, saved, sidebar.
- Flag runtime `MAP_PROJECTION=mercator|globe` (default: `mercator` finché J non verde; poi `globe` se budget ok).

**Non obiettivi**

- Switch UX toolbar 2D↔3D (piano dedicato TBD).
- Implementazione completa §3.D tileserver (solo nota interazione + retest).
- Rewrite Cesium / terrain DEM / photogrammetry.
- Refactor `radar-sidebar/**` o cambio API Phase 5+.

---

## 4. Spike J0 (go/no-go)

Su build I stabile, stesso dataset mock/prod:

| Metrica | Globe ON | Globe OFF (2.5D) | Soglia go |
|---------|----------|------------------|-----------|
| TTI mappa (first interactive) | … | … | &lt; 3s laptop integrato tipico (allineato budget I) |
| FPS pan / rotate | … | … | Nessun stutter prolungato &gt;100ms |
| Memoria GPU / tab | … | … | Nessun OOM; stabile dopo 5 min idle+pan |
| Parity smoke pin/arco/spider | pass/fail | baseline | pass |

**No-go:** restare su 2.5D; aggiornare overview §3.J con esito; riprovare dopo ottimizzazioni (simplify GeoJSON, fewer arc samples).

---

## 5. Wave J1–J3

| Wave | Scope | Exit |
|------|-------|------|
| **J1** | `MAP_PROJECTION` + camera defaults globe (pitch/bearing reset); style CDN invariato | Globe monta senza crash; flag rollback mercator |
| **J2** | Regressione archi great-circle + hit-test su sfera; macro/dash/fan parity H | Click arco → stesso `relationClicked` |
| **J3** | HTML markers pin/hub/spider ancoraggio su globe; docs §3.J DONE + ECC nota; `sync_skills --check` | Tests 1–7 pass; GATE J |

---

## 6. Interazione con §3.D (tile offline)

- Se **D non attivo:** J resta su CDN; documentare **retest obbligatorio** quando D atterra (style locale + globe = più GPU/IO).
- Se **D già attivo:** J0/J1 devono includere style `/tiles/...` su globe.
- **Evitare** aprire D+J+rewrite feature insieme; ordine preferito: I → (D *o* J) → l’altro, oppure D parallelo a J solo con owner distinti.

---

## 7. Rollback

```text
MAP_PROJECTION=mercator   # default se J non verde / ops incident
MAP_PROJECTION=globe      # post GATE J
```

Un solo path MapLibre in memoria; il flag cambia solo la proiezione, non il renderer.

---

## 8. GATE VERDE J

1. Parity grafica invariata vs I (Tests 1–7).
2. Budget perf J0 rispettato su machine di riferimento.
3. Overview §3.J → **DONE**; questo file → `plan-audit/complete/`.
4. `npm run typecheck && npm run test:ci` green; sidebar freeze intatto.
5. Nota ECC/AGENTS: globe default (o flag) documentato.

---

## 9. Riferimenti

- Piano base I: [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md)
- Overview: `radar_overview_and_upgrades.md` §3.I / §3.J / §3.D
- Skill: `spatial-data-mocking`, `radar-docker-ops`
