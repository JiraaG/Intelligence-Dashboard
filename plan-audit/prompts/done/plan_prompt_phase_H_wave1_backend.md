# Prompt orchestratore — Fase H · Wave 1/3 (Backend)

> **Piano SoT:** [`../../active/master_plan_impl_phase_H_geospatial_graph.md`](../../active/master_plan_impl_phase_H_geospatial_graph.md)  
> **Uso:** nuova chat Agent — solo questa wave.  
> **Dopo la wave:** chiudi la chat; chiedi verifica umana/agente supervisore prima di Wave 2.  
> **Prossima:** [`plan_prompt_phase_H_wave2_frontend_map.md`](plan_prompt_phase_H_wave2_frontend_map.md)

---

## Flusso consigliato (3 chat)

| Chat | File prompt | Scope | Stop |
|------|-------------|--------|------|
| 1 | questo file | H1 + H2 (DB/LLM/API) + docs slice backend | pytest green + handoff |
| 2 | wave2 | H3 + H4 (FE state/mock/mappa) — **no sidebar** | test:ci map/typecheck + handoff |
| 3 | wave3 | H5 + H6 (chip freeze + docs/ECC GATE) | GATE VERDE + sync_skills |

Tra ogni chat: supervisore verifica (diff, test, contraddizioni col piano) → eventuale fix nella stessa wave → solo poi apri la chat successiva **incollando il handoff**.

---

## Blocco da incollare (copia da qui)

```text
GOAL
Esegui SOLO la Wave 1/3 della Fase H (Backend): H1 + H2 del master plan.
Non toccare frontend Angular, sidebar, archi Leaflet, né docs FE.
Non ripianificare: decisione v1 = related_countries (CSV ISO → TEXT[] → edge undirected).

PIANO SoT (leggere per primo)
plan-audit/active/master_plan_impl_phase_H_geospatial_graph.md
Sezioni prioritarie: §0.3, §2, §5 (file backend), §6.1, §7 H1–H2, §9.1–9.2 (solo slice backend).

SKILL OBBLIGATORIE (Read prima di edit)
- .agents/skills/llm-json-extraction/SKILL.md
- .agents/skills/radar-api-contract/SKILL.md
- .agents/AGENTS.md
- radar/.ecc/rules/backend.md
- radar/.ecc/agents/pipeline-engineer.md

SCOPE IN (allowlist)
- radar/backend/migrations/011_articles_related_countries.sql (nuovo)
- radar/backend/app/classification/prompts.py
- radar/backend/app/classification/validator.py
- radar/backend/app/commit/db_commit.py
- radar/backend/app/commit/factory.py (frontmatter related_countries YAML only)
- radar/backend/app/api/articles_query.py (build_map_relations_query + campo su articles page)
- radar/backend/app/main.py (GET /api/map-relations; serialize related_countries)
- radar/backend/app/tests/** (validator, query, API)
- Docs slice Wave 1 (obbligatori):
  - .agents/skills/llm-json-extraction/SKILL.md
  - .agents/skills/radar-api-contract/SKILL.md
  - docs/02_architecture_and_backend.md (campo + endpoint)
  - radar/.ecc/CLAUDE.md (solo menzioni migration 011 / related_countries / map-relations)
  - radar/.ecc/agents/pipeline-engineer.md
  - radar/.ecc/agents/geo-data-architect.md
  - radar/.ecc/rules/backend.md (API Phase 5+ → aggiungere map-relations)
Poi: python radar/.ecc/scripts/sync_skills.py --write && --check

SCOPE OUT (vietato in questa chat)
- radar/frontend/** (tutto)
- radar-sidebar/**
- radar_overview §H riscrittura completa (solo nota minima se serve; overview full = Wave 3)
- Fase C pgvector, Fase G wiki-link, edge tipizzati, company→country
- npm deps, leaflet-curve
- commit .env, push, PR

REQUISITI FUNZIONALI WAVE 1
1) Migration 011: articles.related_countries TEXT[] NOT NULL DEFAULT '{}'
2) Prompt: related_countries CSV ISO secondari; Nessuno se vuoti; no primary; no XX; max 5
3) Validator: str CSV; normalize list→CSV; allowlist ISO; soft-drop invalid
4) db_commit + factory YAML list
5) SQL: unnest related + LEAST/GREATEST undirected + GROUP BY category + volume; published_at = $1
6) GET /api/map-relations?date= (+ stessi filtri opzionali di map-summary)
7) GET /api/articles items includono related_countries: string[]
8) Test pytest per validator + query/API

VINCOLI HARD
- asyncpg puro, no ORM
- Pydantic: related_countries = str CSV (NON List[str]); extra=forbid; no reasoning
- main.py API-only (no LLM in API)
- No placeholder/TODO

EXIT WAVE 1
cd radar
# PowerShell: $env:PYTHONPATH="backend"
PYTHONPATH=backend python -m pytest -m "not live" -q
python ../radar/.ecc/scripts/sync_skills.py --check   # da root se path diverso: da monorepo root

HANDOFF (scrivi in coda alla risposta finale, markdown copiabile)
## Handoff Wave 1 → Wave 2
- Branch / commit locali (se creati): …
- File toccati (lista): …
- Endpoint verificato: GET /api/map-relations shape esempio
- Test: comando + risultato
- sync_skills --check: PASS/FAIL
- Scostamenti dal piano (se uno): …
- Blocchi aperti per Wave 2: …
- NON fatto (atteso Wave 2/3): FE, archi, chip sidebar, overview §H full

STOP
Non iniziare Wave 2. Non toccare il frontend.
```
