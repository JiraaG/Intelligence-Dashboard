# Plan prompt — Fix fasce tipologia MapLibre (isole + anti-bleed, tutte le nazioni)

> **Stato: ACTIVE (non eseguito)** — incollare in chat Agent (o Plan→Agent dopo conferma).  
> **Piano SoT:** [`../active/plan_impl_map_category_fills_islands.md`](../active/plan_impl_map_category_fills_islands.md)  
> **Data prompt:** 2026-07-21  
> **Branch:** `feature/upgrades`  
> **Restore pin/hysteresis (contesto):** `7a2bfc9`

---

## PROMPT (incolla in Agent mode)

```text
# Task — Fix fasce tipologia MapLibre: isole + anti-bleed (TUTTE le nazioni)

## Obiettivo
Implementare SOLO il piano `plan-audit/active/plan_impl_map_category_fills_islands.md`.
Correggere day-view MapLibre hatching (fasce soft O→E) in modo GLOBALE:
1) Isole significative colorate (non solo mainland / largest polygon).
2) Niente bande verticali / fill fuori costa in mare.
IT e UK nello screen PO sono sintomi — NON whitelist. Verifica obbligatoria su ogni nazione colorata.

## SoT obbligatori (leggere all’avvio)
1. `plan-audit/active/plan_impl_map_category_fills_islands.md` — piano (decisioni + accettazione)
2. Skills: `.agents/skills/radar-sidebar-freeze/SKILL.md`, `.agents/skills/spatial-data-mocking/SKILL.md`, `.agents/skills/angular-developer/SKILL.md`
3. `radar/.ecc/rules/frontend.md` (Day open / hatching MapLibre) + `radar/.ecc/agents/angular-map-expert.md`
4. Codice: `radar/frontend/src/app/components/radar-map/maplibre/country-category-fills.ts` (+ spec) e wiring in `radar-map-maplibre.component.ts` (`splitCountryByCategories`)

## Repo / branch
- Workspace: Intelligence-Dashboard root
- Branch: `feature/upgrades`
- Non pushare; commit solo se richiesto dall’utente

## Decisioni bloccate (non riaprire)
- Algoritmo unico per tutte le nazioni; eccezioni solo US/RU mainland bbox
- Isole: pezzi MultiPolygon con area >= 0.5% del largest
- Clip: `polygon-clipping` terra∩strip; VIETATO fallback rettangolo in mare
- MapLibre only; Leaflet LEGACY FREEZE; ZERO edit `radar-sidebar/**`
- No Wave 2 archi, no restyle palette/opacità

## Deliverable
1. `extractPaintPolygons` + rewrite `splitCountryByCategories` con intersezione robusta
2. Dipendenza `polygon-clipping` in FE package.json
3. Spec: fixture arcipelago + concava + US; sweep su countries.geo.json (MultiPolygon) con assert anti-bleed / isole
4. Docs: Regola Day open, FE README, spatial-mocking SoT+mirror (e piano Phase I se ancora “largest only”)
5. Verifica: `npm run typecheck && npm run test:ci`; `docker compose build/up radar-frontend`
6. Smoke UI: pan day-view su OGNI nazione con hatching — isole colorate; niente fill in mare; US/RU mainland-only

## Fuori scope
Leaflet SVG hatching; Wave 2; sidebar; nuove skill/hooks; commit/push senza richiesta esplicita.

## Output atteso a fine task
- Diff riassunta + path file
- Esito typecheck/test:ci + docker
- Note smoke (quante nazioni controllate / eventuali residui)
- Se chiedono commit: messaggio restore-friendly (SHA da registrare in plan-audit/STATUS.md)
```

---

## Uso

1. Aprire chat nuova su `feature/upgrades`.
2. Incollare il blocco `PROMPT` in **Agent**.
3. A GATE VERDE: spostare piano in `plan-audit/complete/`, prompt in `prompts/done/`, aggiornare `STATUS.md` + `active/README.md`.
