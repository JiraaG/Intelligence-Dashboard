# Piano — Fix fasce tipologia MapLibre (isole + anti-bleed, tutte le nazioni)

**Stato:** COMPLETE / GATE VERDE  
**Branch:** `feature/upgrades`  
**Data GATE:** 2026-07-21  
**Prompt gemello:** [`../prompts/done/plan_prompt_map_category_fills_islands.md`](../prompts/done/plan_prompt_map_category_fills_islands.md)  
**Contesto mappa:** [`../active/plan_impl_map_3d_globe.md`](../active/plan_impl_map_3d_globe.md) (Phase I MapLibre)  
**Soglia hatch↔pin:** `MAP_ZOOM_PIN_THRESHOLD=4` + isteresi (`7a2bfc9`)  
**Quadro:** [`../STATUS.md`](../STATUS.md)  
**Restore point:** tip `feature/upgrades` al commit di chiusura GATE (registrato in STATUS + README restore table)

---

## 1. Obiettivo

Correggere le fasce soft O→E (`country-category-fills.ts`) in day-view MapLibre in modo **globale** (ogni nazione del GeoJSON / `map-summary`):

1. **Isole significative colorate** (prima solo `extractLargestPolygon` → Sicilia/Sardegna e analoghi restavano neri).
2. **Niente bleed in mare** (bande verticali oltre costa: UK e coste concave).

IT/UK nello screen PO erano **sintomi**, non whitelist.

---

## 2. Decisioni prodotto (bloccate — rispettate)

| # | Decisione |
|---|-----------|
| 1 | Algoritmo **unico** per tutte le nazioni via `splitCountryByCategories` |
| 2 | Eccezioni SoT solo **US** / **RU** (bbox mainland hardcoded, antimeridiano) |
| 3 | Isole: pezzi MultiPolygon con `area >= 0.5%` del largest |
| 4 | Clip fasce: intersezione terra∩strip con `polygon-clipping` — **vietato** fallback rettangolo in mare |
| 5 | Verifica obbligatoria su **tutte** le nazioni colorate (unit sweep + smoke) |
| 6 | Path **MapLibre** only; Leaflet LEGACY FREEZE (SVG hatching invariato) |
| 7 | **Non** toccare `radar-sidebar/**`, Wave 2 archi, opacità/palette |

---

## 3. Cause AS-IS (pre-fix)

File: [`radar/frontend/src/app/components/radar-map/maplibre/country-category-fills.ts`](../../radar/frontend/src/app/components/radar-map/maplibre/country-category-fills.ts)

- `extractLargestPolygon()` droppava isole MultiPolygon.
- Sutherland–Hodgman su coste concave + fasce sottili → geometrie quasi-strip in mare.
- Fallback rettangolo di fascia se clip falliva → bleed in mare.

---

## 4. Implementazione (shipped)

### 4.1 Helper

- `extractPaintPolygons(geometry, countryCode)`: US/RU ∩ mainland bbox; altri = largest + pezzi ≥ 0.5% area largest.
- Bbox fasce non-US/RU = unione paint (`paintPolygonsBbox`) così isole fuori dal solo largest restano colorate.
- Per ogni tipologia: terra∩strip via `polygon-clipping`; skip se vuoto — **no** fallback in mare.

### 4.2 Dipendenza

- `polygon-clipping` in `radar/frontend/package.json` (+ `allowedCommonJsDependencies` in `angular.json`).

### 4.3 Test

`country-category-fills.spec.ts`: fixture arcipelago + concava anti-bleed + US; sweep MultiPolygon su `countries.geo.json` (skip se asset assente).

### 4.4 Docs / ECC

Allineati: Regola Day open (`radar/.ecc/rules/frontend.md`), FE README, spatial-mocking SoT+mirror, `angular-map-expert`, AGENTS, CLAUDE, Phase I plan hatching row. **Nessuna** nuova skill/hook (fuori scope).

---

## 5. Accettazione

- [x] `npm run typecheck && npm run test:ci` (FE) — 66/66
- [x] Docker `radar-frontend` rebuild healthy (+ stack up; Miniflux UI via overlay `lan` su `:8080`)
- [x] Smoke: sweep unit 151 MultiPolygon (91 con isole ≥0.5%); IT/GB/GR/… paint MultiPolygon; US/RU mainland-only; pipeline articoli OK post-restart worker
- [x] Docs/ECC allineati
- [x] Restore SHA registrato in STATUS / README al GATE

---

## 6. Fuori scope (invariato)

Leaflet SVG hatching; restyle colori; Wave 2 elevate; sidebar; nuove skill/hooks dedicate.
