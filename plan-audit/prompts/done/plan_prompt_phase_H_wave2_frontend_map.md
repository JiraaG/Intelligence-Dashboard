# Prompt orchestratore — Fase H · Wave 2/3 (Frontend mappa)

> **Piano SoT:** [`../../active/master_plan_impl_phase_H_geospatial_graph.md`](../../active/master_plan_impl_phase_H_geospatial_graph.md)  
> **Uso:** nuova chat Agent — solo questa wave.  
> **Prerequisito:** Wave 1 chiusa + verifica umana (pytest, curl map-relations, handoff).  
> **Precedente:** [`plan_prompt_phase_H_wave1_backend.md`](plan_prompt_phase_H_wave1_backend.md)  
> **Prossima:** [`plan_prompt_phase_H_wave3_carousel_docs_gate.md`](plan_prompt_phase_H_wave3_carousel_docs_gate.md)

---

## Flusso consigliato (3 chat)

| Chat | File prompt | Scope | Stop |
|------|-------------|--------|------|
| 1 | wave1 | H1 + H2 (DB/LLM/API) + docs slice backend | pytest green + handoff |
| 2 | questo file | H3 + H4 (FE state/mock/mappa) — **no sidebar** | test:ci + handoff |
| 3 | wave3 | H5 + H6 (chip freeze + docs/ECC GATE) | GATE VERDE + sync_skills |

Tra ogni chat: supervisore verifica → eventuale fix → solo poi apri la chat successiva **incollando il handoff** della wave precedente nel blocco `DELTA`.

---

## Checklist verifica pre-Wave 2 (umano / supervisore)

```text
□ Wave 1 handoff ricevuto
□ Migration 011 + related_countries CSV/TEXT[]
□ GET /api/map-relations?date= shape ok
□ Articles includono related_countries[]
□ Nessun tocco a radar/frontend/** in Wave 1
□ pytest -m "not live" green
□ sync_skills --check PASS (skill API / llm-json)
```

---

## Blocco da incollare (copia da qui)

```text
GOAL
Esegui SOLO la Wave 2/3 della Fase H (Frontend mappa/stato): H3 + H4 del master plan.
Zero modifiche a radar-sidebar/**. Non ripianificare. Non rifare il backend salvo bug
bloccante minimo (<10 righe) già esposto da Wave 1 — in quel caso fix + nota handoff e stop.

PIANO SoT (leggere per primo)
plan-audit/active/master_plan_impl_phase_H_geospatial_graph.md
Sezioni: §3, §6.2–6.3 (mappa), §7 H3–H4. Freeze chip = Wave 3, non questa.

DELTA DA WAVE 1 (obbligatorio — incolla/adatta l’handoff Wave 1)
- Branch / commit: …
- File backend già presenti: …
- Shape map-relations esempio: …
- Scostamenti dal piano: …
- Blocchi aperti: …

SKILL OBBLIGATORIE (Read prima di edit)
- .agents/skills/radar-api-contract/SKILL.md
- .agents/skills/spatial-data-mocking/SKILL.md
- .agents/AGENTS.md (Leaflet UMD; freeze — QUI non usare ancora eccezione chip)
- radar/.ecc/rules/frontend.md
- radar/.ecc/agents/angular-map-expert.md

SCOPE IN (allowlist)
- radar/frontend/src/app/models/article.model.ts
- radar/frontend/src/app/models/article.dto.ts
- radar/frontend/src/app/models/map-relation.model.ts (nuovo se serve)
- radar/frontend/src/app/services/article.service.ts
- radar/frontend/src/app/services/article-mock.service.ts
- radar/frontend/src/app/services/state.service.ts (mapRelationsResource + SSE reload)
- radar/frontend/src/app/components/radar-map/radar-map.component.ts
- radar/frontend/src/app/components/radar-map/radar-map.component.scss
- radar/frontend/src/app/components/radar-map/radar-map.component.spec.ts
- radar/frontend/src/app/app.ts / app.html SOLO se serve passare relations alla mappa
- Docs slice Wave 2 (minimo):
  - .agents/skills/spatial-data-mocking/SKILL.md (checklist archi mock)
  - radar/.ecc/agents/angular-map-expert.md (relationsLayerGroup; no leaflet-curve)
  - radar/.ecc/rules/frontend.md (layer relations + fingerprint)
Poi: python radar/.ecc/scripts/sync_skills.py --write && --check

SCOPE OUT (vietato)
- radar/frontend/src/app/components/radar-sidebar/** (anche un chip = FAIL di questa wave)
- Backend ampio (oltre bugfix minimo)
- overview §H full rewrite, freeze skill chip, CLAUDE/AGENTS rewrite completo (= Wave 3)
- npm leaflet-curve / nuove dipendenze
- Fase C, G, edge tipizzati, click arco → sidebar paese
- push / PR

REQUISITI FUNZIONALI WAVE 2
1) Article.related_countries: string[] + DTO guard
2) MapRelationRow + getMapRelations in ArticleService e ArticleMockService
3) StateService.mapRelationsResource (params come map-summary); SSE article_processed → reload insieme a mapSummary
4) relationsLayerGroup; drawGeospatialRelations; polyline curva (Bezier campionata), NO L.curve npm
5) Centroidi: cache GeoJSON getBounds().getCenter() + override US/RU; fallback summary
6) Visibilità: day-view zoom ≥5; nascosto zoom <5 e nation-open
7) Colore CATEGORY_CSS_VARS; weight min(6, 1+volume*0.5); CSS .relational-arc-flow
8) Fingerprint geometria include relations; tooltip informativo opzionale (no navigate)
9) Mock: 2–3 articoli bilaterali + getMapRelations derivato

VINCOLI HARD
- Leaflet solo via window.L + angular.json scripts[]
- MOCK_MODE esplicito; no fallback silenzioso
- No placeholder/TODO
- Sidebar freeze: ZERO tocchi in questa wave

EXIT WAVE 2
cd radar/frontend
npm run typecheck && npm run test:ci && npm run build:ci
# da monorepo root:
python radar/.ecc/scripts/sync_skills.py --check

HANDOFF (coda risposta finale, markdown copiabile)
## Handoff Wave 2 → Wave 3
- Branch / commit: …
- File toccati: …
- Come verificare archi in MOCK_MODE (passi UI): …
- Test FE: comandi + risultato
- sync_skills --check: PASS/FAIL
- Scostamenti dal piano: …
- Blocchi aperti per Wave 3: …
- NON fatto (atteso Wave 3): chip sidebar, freeze skill eccezione, overview §H, GATE STATUS/complete

STOP
Non iniziare Wave 3. Non toccare radar-sidebar/**.
```
