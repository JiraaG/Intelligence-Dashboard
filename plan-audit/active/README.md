# active/ — Documenti attivi

Questa directory contiene i piani di progettazione e di implementazione attualmente in corso.

## Stato

**Attivo**

- **Fix fasce tipologia (isole + anti-bleed)** — [`plan_impl_map_category_fills_islands.md`](plan_impl_map_category_fills_islands.md) (**ACTIVE**; prompt [`../prompts/active/plan_prompt_map_category_fills_islands.md`](../prompts/active/plan_prompt_map_category_fills_islands.md)).
- **Relazioni Wave 2 — archi elevati 3D** — [`plan_impl_map_relations_arcs_3d.md`](plan_impl_map_relations_arcs_3d.md) (**spike**; prerequisito W1 = [`../complete/plan_impl_map_relations_nation_filter.md`](../complete/plan_impl_map_relations_nation_filter.md) **GATE VERDE**).
- **Fase I — Mappa 3D-primary (MapLibre)** — [`plan_impl_map_3d_globe.md`](plan_impl_map_3d_globe.md) (**codice + docs shipped** 2026-07-20; move a `complete/` su ok utente). Follow-up globo: sempre [`plan_impl_map_globe_projection.md`](plan_impl_map_globe_projection.md) (§3.J).
- **Fase J — Upgrade globo vero** — [`plan_impl_map_globe_projection.md`](plan_impl_map_globe_projection.md) (**Futuro / BACKLOG**).
- Prompt non eseguito: [`../prompts/active/plan_prompt_ecc_manual_and_expansion.md`](../prompts/active/plan_prompt_ecc_manual_and_expansion.md) (ECC manual / expansion); [`../prompts/active/plan_prompt_map_category_fills_islands.md`](../prompts/active/plan_prompt_map_category_fills_islands.md) (fasce isole/bleed).
- Prompt mappa 3D (origine analisi): [`../prompts/active/plan_prompt_map_3d_globe.md`](../prompts/active/plan_prompt_map_3d_globe.md).

**Completati di recente (riferimento)**

- **Relazioni Wave 1 — filtro nazioni** — [`../complete/plan_impl_map_relations_nation_filter.md`](../complete/plan_impl_map_relations_nation_filter.md) (GATE VERDE 2026-07-20; toolbar **RELAZIONI ATTIVE**).
- **Fase A — LLM locale AMD / Ollama** — [`../complete/plan_impl_fase_A_local_amd_ollama.md`](../complete/plan_impl_fase_A_local_amd_ollama.md) (`54c8038` / VRAM `2996625`; scorecard opz.).
- **Audit LLM env topology** — [`../complete/audit_llm_lane_env_generalization.md`](../complete/audit_llm_lane_env_generalization.md) (`c9ef842`).
- **Archi multicolore + click bilaterale** — [`../complete/plan_archi_hatching_multicolor.md`](../complete/plan_archi_hatching_multicolor.md) (GATE VERDE 2026-07-18; MapLibre solidi `0d942ed`).
- **Fase H (Grafo Geospaziale)** — [`../complete/master_plan_impl_phase_H_geospatial_graph.md`](../complete/master_plan_impl_phase_H_geospatial_graph.md).
- **Fase B (Real-Time / SSE)** — in [`../complete/`](../complete/).

Roadmap parallela (`radar_overview_and_upgrades.md` §3): **Fase C — Deduplicazione semantica (`pgvector`)** in backlog (indipendente da I/J).

Quadro globale: [`../STATUS.md`](../STATUS.md).
