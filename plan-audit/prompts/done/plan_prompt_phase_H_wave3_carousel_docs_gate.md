# Prompt orchestratore — Fase H · Wave 3/3 (Carosello + Docs/ECC GATE)

> **Piano SoT:** [`../../active/master_plan_impl_phase_H_geospatial_graph.md`](../../active/master_plan_impl_phase_H_geospatial_graph.md)  
> **Uso:** nuova chat Agent — solo questa wave (chiusura Fase H).  
> **Prerequisito:** Wave 1 + Wave 2 chiuse e verificate; handoff Wave 2 incollato in `DELTA`.  
> **Precedente:** [`plan_prompt_phase_H_wave2_frontend_map.md`](plan_prompt_phase_H_wave2_frontend_map.md)  
> **Wave 1:** [`plan_prompt_phase_H_wave1_backend.md`](plan_prompt_phase_H_wave1_backend.md)

---

## Flusso consigliato (3 chat)

| Chat | File prompt | Scope | Stop |
|------|-------------|--------|------|
| 1 | wave1 | H1 + H2 backend | pytest + handoff |
| 2 | wave2 | H3 + H4 mappa (no sidebar) | test:ci + handoff |
| 3 | questo file | H5 + H6 chip + docs/ECC + GATE | GATE VERDE |

Dopo GATE: spostare i tre prompt in `plan-audit/prompts/done/` e il master plan in `plan-audit/complete/`.

---

## Checklist verifica pre-Wave 3

```text
□ Handoff Wave 2 ricevuto
□ Archi MOCK visibili zoom ≥5; nascosti hatching / nation-open
□ Nessuna dep leaflet-curve
□ Sidebar ancora senza chip related (atteso — arriva ora)
□ typecheck + test:ci + build:ci green
□ Backend Wave 1 ancora ok (pytest smoke)
```

---

## Blocco da incollare (copia da qui)

```text
GOAL
Chiudi la Fase H: Wave 3/3 = H5 (chip carosello, eccezione freeze) + H6 (docs .md + ECC + GATE).
Backend e mappa sono già fatti (Wave 1–2). Non rifare API/archi salvo bug bloccante minimo.
Non ripianificare: decisione v1 invariata.

PIANO SoT (leggere per primo)
plan-audit/active/master_plan_impl_phase_H_geospatial_graph.md
Sezioni: §4 carosello, §9 docs/ECC (obbligatorio), §6.3–6.5, §7 H5–H6, §10 GATE.

DELTA DA WAVE 1–2 (obbligatorio — incolla handoff)
- Cosa già in codice: …
- Fix post-verifica già applicati: …
- Residui aperti: …
- Branch: …

SKILL OBBLIGATORIE (Read)
- .agents/skills/radar-sidebar-freeze/SKILL.md
- .agents/skills/radar-api-contract/SKILL.md
- .agents/skills/llm-json-extraction/SKILL.md
- .agents/skills/spatial-data-mocking/SKILL.md
- docs/04_ecc_framework.md (sync mirror)
- .agents/AGENTS.md

SCOPE H5 (allowlist stretta sidebar)
- radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.html
- radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.scss
- (ts solo se serve binding tipizzato già presente — niente refactor)
- .agents/skills/radar-sidebar-freeze/SKILL.md → seconda eccezione mirata:
  Salva + sezione chip related_countries (single+carousel). Vietato altro.

REQUISITI H5
1) Sezione "🌐 Paesi correlati" dopo Aziende / prima Tag (single + carousel)
2) p-chip radar-chip related-chip; testo getCountryName(iso); display-only
3) *ngIf su related_countries.length
4) git diff --stat -- radar/frontend/src/app/components/radar-sidebar
   → solo file chip, nessun refactor carousel / article-list

SCOPE H6 — checklist piano §9 (tutti i path rilevanti)
Product docs:
- radar_overview_and_upgrades.md §H (ELIMINARE sketch unnest(infrastructural_entities);
  documentare related_countries + map-relations + polyline + chip + soft-refresh)
- docs/02_architecture_and_backend.md
- docs/03_frontend_and_ui.md (archi + eccezione freeze chip)
- docs/01_getting_started.md SOLO se elenca smoke curl map-summary → aggiungi map-relations
- docs/04_ecc_framework.md se stale su freeze/skills
- README.md solo se elenca feature API Phase 5+
- radar/docs/runbook.md (curl map-relations nello smoke)
- radar/ops/README.md se elenca smoke API

ECC / Cursor:
- .agents/AGENTS.md (freeze dual-exception)
- radar/.ecc/CLAUDE.md (011, related_countries, map-relations, freeze)
- radar/.ecc/rules/backend.md, frontend.md, testing.md (se serve)
- radar/.ecc/agents/angular-map-expert.md, pipeline-engineer.md, geo-data-architect.md
- .cursor/rules/radar-frontend.mdc se dice “solo Salva” → aggiornare
- .cursor/commands/radar-smoke.md se elenca map-summary → + map-relations
Skills SoT già toccate in W1/W2: verifica completezza; poi:
  python radar/.ecc/scripts/sync_skills.py --write
  python radar/.ecc/scripts/sync_skills.py --check

plan-audit:
- STATUS.md → Fase H DONE / GATE VERDE
- Sposta master_plan_impl_phase_H_geospatial_graph.md → plan-audit/complete/
- Aggiorna plan-audit/active/README.md (vuoto o next)
- Sposta questi tre prompt wave1/2/3 → plan-audit/prompts/done/
- Aggiorna plan-audit/README.md indice prompt

SCOPE OUT
- Refactor sidebar / article-list / ResizeObserver carousel
- leaflet-curve, click chip → flyTo, edge tipizzati, Fase C/G
- push / PR se non richiesto esplicitamente dall’utente in questa chat

VINCOLI HARD
- Eccezione freeze SOLO chip related (+ docs); niente restyle ampio
- sync_skills --check exit 0 obbligatorio
- No placeholder/TODO
- Overview §H non deve più contenere unnest(infrastructural_entities) come query reale

EXIT / GATE VERDE
cd radar
PYTHONPATH=backend python -m pytest -m "not live" -q
cd frontend && npm run typecheck && npm run test:ci && npm run build:ci
# monorepo root:
python radar/.ecc/scripts/sync_skills.py --check

Report finale:
- Checklist §6 + §9 spuntata
- File toccati Wave 3
- Conferma GATE + path piano in complete/
- Residuali (se uno)

STOP
Dopo GATE non aprire Wave 4. Fase H chiusa.
```
