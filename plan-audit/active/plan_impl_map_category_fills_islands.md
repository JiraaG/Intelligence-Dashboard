# Piano — Fix fasce tipologia MapLibre (isole + anti-bleed, tutte le nazioni)

**Stato:** ACTIVE  
**Branch:** `feature/upgrades`  
**Data:** 2026-07-21  
**Prompt gemello:** [`../prompts/active/plan_prompt_map_category_fills_islands.md`](../prompts/active/plan_prompt_map_category_fills_islands.md)  
**Contesto mappa:** [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md) (Phase I MapLibre)  
**Soglia hatch↔pin:** `MAP_ZOOM_PIN_THRESHOLD=4` + isteresi (`7a2bfc9`)  
**Quadro:** [`../STATUS.md`](../STATUS.md)

---

## 1. Obiettivo

Correggere le fasce soft O→E (`country-category-fills.ts`) in day-view MapLibre in modo **globale** (ogni nazione del GeoJSON / `map-summary`):

1. **Isole significative colorate** (oggi solo `extractLargestPolygon` → Sicilia/Sardegna e analoghi restano neri).
2. **Niente bleed in mare** (bande verticali oltre costa: UK e coste concave).

IT/UK nello screen PO sono **sintomi**, non whitelist.

---

## 2. Decisioni prodotto (bloccate)

| # | Decisione |
|---|-----------|
| 1 | Algoritmo **unico** per tutte le nazioni via `splitCountryByCategories` |
| 2 | Eccezioni SoT solo **US** / **RU** (bbox mainland hardcoded, antimeridiano) |
| 3 | Isole: includere pezzi MultiPolygon con `area >= 0.5%` del largest |
| 4 | Clip fasce: intersezione terra∩strip con `polygon-clipping` — **vietato** fallback rettangolo in mare |
| 5 | Verifica obbligatoria su **tutte** le nazioni colorate (unit sweep + smoke day-view) |
| 6 | Path **MapLibre** only; Leaflet LEGACY FREEZE (SVG hatching invariato) |
| 7 | **Non** toccare `radar-sidebar/**`, Wave 2 archi, opacità/palette |

---

## 3. Cause AS-IS

File: [`radar/frontend/src/app/components/radar-map/maplibre/country-category-fills.ts`](../../radar/frontend/src/app/components/radar-map/maplibre/country-category-fills.ts)

- `extractLargestPolygon()` droppa isole MultiPolygon.
- Sutherland–Hodgman su coste concave + fasce sottili → geometrie quasi-strip in mare.

---

## 4. Implementazione

### 4.1 Helper

- `extractPaintPolygons(geometry, countryCode)`:
  - US/RU → poligoni ∩ mainland bbox
  - altri → largest + pezzi ≥ 0.5% area largest
- Per ogni tipologia `i`: strip bbox su `resolveSplitBbox`; interseca **tutti** i paint-polygon con [`polygon-clipping`](https://www.npmjs.com/package/polygon-clipping); output `Feature` (`Polygon` \| `MultiPolygon`); skip se vuoto.
- Aggiornare commenti SoT (niente più “no isole”).

### 4.2 Dipendenza

- Aggiungere `polygon-clipping` in `radar/frontend/package.json` (`npm ci` / Docker build).

### 4.3 Test

[`country-category-fills.spec.ts`](../../radar/frontend/src/app/components/radar-map/maplibre/country-category-fills.spec.ts):

- Fixture arcipelago generica + concava anti-bleed + regressione US.
- **Sweep** su `countries.geo.json` (o subset MultiPolygon): per ogni feature, `splitCountryByCategories` non emette rettangolo strip puro; MultiPolygon con pezzo ≥0.5% → geometria che include quel pezzo (N=1 → MultiPolygon ≥2 parti dove applicabile).

### 4.4 Docs

Allineare: Regola Day open (`radar/.ecc/rules/frontend.md`), FE README, spatial-mocking (SoT + mirror), riga in `plan_impl_map_3d_globe.md` se ancora “largest only”.

---

## 5. Accettazione

- [ ] `npm run typecheck && npm run test:ci` (FE)
- [ ] Docker `radar-frontend` rebuild healthy
- [ ] Smoke day-view: **ogni** nazione con hatching — isole significative colorate; niente bande in mare; US/RU solo mainland
- [ ] Docs/ECC allineati
- [ ] Restore SHA registrato in STATUS al GATE

---

## 6. Fuori scope

Leaflet SVG hatching; restyle colori; Wave 2 elevate; sidebar; nuove skill/hooks dedicate.
