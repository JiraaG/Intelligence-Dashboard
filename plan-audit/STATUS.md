# plan-audit — STATUS (fatto vs da fare)

Quadro operativo aggiornato **2026-07-20** (Wave 1 Relazioni nazioni **GATE VERDE**; Fase A LLM locale **COMPLETE**; audit LLM env `c9ef842`; Profilo F `54c8038` + VRAM `2996625`).  
Indice cartelle: [`README.md`](README.md).  
Handoff Final Release: [`remediation/audit_remediation_final_release_handoff.md`](remediation/audit_remediation_final_release_handoff.md).

---

## In corso (active)

| Area | Dove | Note |
|------|------|------|
| Relazioni — archi elevati 3D (Wave 2) | [`active/plan_impl_map_relations_arcs_3d.md`](active/plan_impl_map_relations_arcs_3d.md) | **ACTIVE (spike)** — prerequisito W1 **DONE**. MapLibre `line` flat; no `line-z-offset`; CustomLayer vs deck.gl. |
| Mappa 3D-primary (Phase I) | [`active/plan_impl_map_3d_globe.md`](active/plan_impl_map_3d_globe.md) | Codice + docs shipped; post-ship hatching soft + archi macro solidi |
| Upgrade globo §3.J | [`active/plan_impl_map_globe_projection.md`](active/plan_impl_map_globe_projection.md) | Futuro / BACKLOG |
| ECC manual / expansion | [`prompts/active/plan_prompt_ecc_manual_and_expansion.md`](prompts/active/plan_prompt_ecc_manual_and_expansion.md) | ACTIVE (non eseguito) |
| Prompt mappa 3D (origine) | [`prompts/active/plan_prompt_map_3d_globe.md`](prompts/active/plan_prompt_map_3d_globe.md) | Storico analisi |

---

## Completato

| Area | Dove | Note |
|------|------|------|
| Relazioni — filtro nazioni (Wave 1) | [`complete/plan_impl_map_relations_nation_filter.md`](complete/plan_impl_map_relations_nation_filter.md) | **COMPLETE / GATE VERDE** 2026-07-20 — toolbar **RELAZIONI ATTIVE** (default OFF, OR stella, toggle iOS); `visibleMapRelations`; paint/hover invariati. **Restore point:** `ec771b1` su `feature/upgrades` (pre-W1 archi: `0d942ed`). |
| Fase A — LLM locale AMD/Ollama | [`complete/plan_impl_fase_A_local_amd_ollama.md`](complete/plan_impl_fase_A_local_amd_ollama.md) | **COMPLETE** — W1–W4 + VRAM unload **DONE** (`54c8038` / `2996625`). Scorecard fixture formale = **opz. non bloccante**. |
| Audit LLM env topology | [`complete/audit_llm_lane_env_generalization.md`](complete/audit_llm_lane_env_generalization.md) | **DONE** 2026-07-20 — S3 failover, ricette 1–8, no residual Ollama-think; W2 codice cancelled. Restore docs: **`c9ef842`**. |
| Profilo F Local-Hybrid (impl) | codice + overlay + docs | **DONE** 2026-07-19 — commit **`54c8038`** su `feature/upgrades`. |
| Map nation anchors + summary densi | codice FE `radar-map` + `classification/prompts.py` | **DONE** 2026-07-19 — hub/spider/pin sul centroide nazione (US/RU mainland); summary LLM briefing denso 220–420 char. **Restore point:** `a240b3c` su `feature/upgrades`. |
| Click nazione hatching (zoom &lt; 5) | `radar-map` map-click + `pickCountryCodeAt` | **DONE** 2026-07-19 — bypass canvas `relationsPane`; parity LETTE/TROVATE. Commit `911463a`. |
| Affinamento classificazione (tipologia / anti-XX / archi star) | [`prompts/done/plan_prompt_classification_geo_arcs_refine.md`](prompts/done/plan_prompt_classification_geo_arcs_refine.md) | **DONE** 2026-07-18 — prompt + soft-remap sport; `requeue --purge-all`; docs star; prova da zero. **Restore point:** `f7cf83d` su `feature/upgrades`. |
| Notizie Salvate (`is_saved`) | [`complete/note_notizie_salvate.md`](complete/note_notizie_salvate.md) | Migration `010`; vault cross-day; save⇒read / unread⇒unsave; spiderfy parity LETTE/TROVATE (2026-07-17) |
| Phase 0–6 GATE VERDE | [`complete/plan_impl_phase_0_6.md`](complete/plan_impl_phase_0_6.md) + [`_execution`](complete/plan_impl_phase_0_6_execution.md) | Restore SHA; non backlog |
| Ticket remediation P0–P2 | [`complete/plan_docs_audit_ticket_status.md`](complete/plan_docs_audit_ticket_status.md) | **0 OPEN** |
| Playbook audit docs | [`complete/plan_docs_audit_playbook.md`](complete/plan_docs_audit_playbook.md) | CLOSED |
| Allineamento product docs | [`complete/plan_docs_monorepo_source.md`](complete/plan_docs_monorepo_source.md) | ESEGUITO + coerenza porte/health/requeue |
| Final Release F0–F4 | [`complete/plan_release_final_gate.md`](complete/plan_release_final_gate.md) + report `remediation/*_F*.md` | **PR #1 merged** 2026-07-17; backup, seed 10k, chaos C1–C3, security |
| SoT LLM multi-provider | [`complete/sot_llm_multi_model_fallback.md`](complete/sot_llm_multi_model_fallback.md) | **Vivo** — Profilo F + no-escalate Ollama think (2026-07-19) |
| Commenti codice P0–P2 | [`complete/plan_code_comments_beginner_audit.md`](complete/plan_code_comments_beginner_audit.md) | **P0–P1–P2-01 DONE**; altri P2 inventario restano fuori batch |
| Prompt audit commenti | [`prompts/done/audit_prompt_code_comments_beginner_terra.md`](prompts/done/audit_prompt_code_comments_beginner_terra.md) | Pipeline Terra→Grok chiusa |
| Prompt Final Release Gate | [`prompts/done/audit_prompt_final_release_gate.md`](prompts/done/audit_prompt_final_release_gate.md) | Archiviato 2026-07-18 — gate chiuso |
| Prompt Fase A Ollama | [`prompts/done/plan_prompt_fase_A_local_amd_ollama.md`](prompts/done/plan_prompt_fase_A_local_amd_ollama.md) | Archiviato 2026-07-19 — impl shipped |
| Report ticket singoli | [`remediation/`](remediation/) | Storico — non cancellare |
| Prompt eseguiti | [`prompts/done/`](prompts/done/) | Storico |
| Piani ECC / Limits / stub | [`archive/`](archive/) | SUPERSEDED / PRD |
| Phase B Real-Time (webhook/SSE/soft-refresh) | [`complete/master_plan_impl_phase_B.md`](complete/master_plan_impl_phase_B.md) + [`implementation`](complete/implementation_plan_phase_B.md) + [`analisi`](complete/analisi_dettagliata_fase_B.md) | **DONE / GATE VERDE** 2026-07-18 — HMAC webhook, LISTEN dedicate, SSE, Angular soft-refresh |
| Fase H — Grafo geospaziale | [`complete/master_plan_impl_phase_H_geospatial_graph.md`](complete/master_plan_impl_phase_H_geospatial_graph.md) | **DONE / GATE VERDE** (2026-07-18) — related_countries, GET /api/map-relations, archi mappa, chip carosello, allineamento docs + ECC. |
| Archi multicolore + click bilaterale | [`complete/plan_archi_hatching_multicolor.md`](complete/plan_archi_hatching_multicolor.md) | **DONE / GATE VERDE** (2026-07-18) — Leaflet: macro &lt;5 + tratteggio geometrico ≥5. **MapLibre post-ship (2026-07-20):** macro multicolore solida a **tutti** gli zoom (`0d942ed`). |

---

## Residui post-gate

| Item | Stato | Note |
|------|--------|------|
| Fase 0 — PR `refactor/testing` → `develop` | **DONE** | [PR #1](https://github.com/JiraaG/Dashboard-finance/pull/1) merged 2026-07-17; tip `develop` include Notizie Salvate (`b08fd7e`) oltre al branch |
| Fase 5 — digest pin + drop `--legacy-peer-deps` | **DEFERRED ACCETTATO** | Hardening opzionale; **non** da fare per release. Vedi piano §7 |
| Commenti codice P1/P2 | **Chiuso (P2-01)** | Altri P2 in inventario senza `batch_id` — solo se emerge gap reale |
| Fase C — Dedup semantica `pgvector` | **BACKLOG** | Vedi `radar_overview_and_upgrades.md` §3.C; non iniziata; indipendente da H / A |
| Fase A — LLM locale AMD/Ollama | **COMPLETE** | Impl + VRAM **DONE**. Scorecard fixture = opz. Piano [`complete/plan_impl_fase_A_local_amd_ollama.md`](complete/plan_impl_fase_A_local_amd_ollama.md). |
| Fase H — Grafo geospaziale | **DONE** | related_countries + GET /api/map-relations + archi mappa + chip carosello (2026-07-18). |
| Archi UI (multicolore + click) | **DONE** | Piano [`complete/plan_archi_hatching_multicolor.md`](complete/plan_archi_hatching_multicolor.md). **MapLibre:** residuo opzionale “multicolore anche ≥5” **chiuso** (`0d942ed`). Leaflet legacy: dash+fan ≥5 invariato. |
| Relazioni filtro nazioni (Wave 1) | **DONE** | [`complete/plan_impl_map_relations_nation_filter.md`](complete/plan_impl_map_relations_nation_filter.md). Prossimo: spike Wave 2 elevate. |

**Nessun residuo operativo obbligatorio sulla Fase A / B / H / archi UI / W1 filtri / classification refine / map anchors / Profilo F core / audit env.** Branch di riferimento feature: `feature/upgrades`. Candidata immediata relazioni: **Wave 2 archi elevati**. Blueprint parallelo: **§3.C pgvector**.

**Restore points (catena `feature/upgrades`):** W1 filtri nazioni **`ec771b1`**; archi MapLibre solidi `0d942ed`; docs LLM env `c9ef842`; Profilo F + VRAM `2996625`; Local-Hybrid `54c8038`; map anchors `a240b3c`; click hatching `911463a`; classification/geo `f7cf83d`; archi UI Leaflet `5c74e57`.

Prompt Final Release: [`prompts/done/audit_prompt_final_release_gate.md`](prompts/done/audit_prompt_final_release_gate.md) — **non rieseguire** (F0–F4 chiusi).

**Fuori scope:** scorecard Fase A senza richiesta; refactor/restyle di `radar-sidebar/**` al di fuori delle eccezioni mirate; riaprire ticket CLOSED; rieseguire P0 commenti senza richiesta; attivare Fase 5 senza decisione esplicita; implementare Wave 2 elevate senza spike GATE.

---

## Layout rapido

```text
plan-audit/
  STATUS.md          ← questo file (quadro fatto / residui)
  active/            ← Wave 2 elevate, Phase I map, §3.J, prompt ECC
  complete/          ← Piani COMPLETATI (W1 filtri, Fase A, Phase 0–6, B/H, …)
  prompts/active/    ← prompt non eseguiti (ECC manual/expansion)
  prompts/done/      ← storico (incl. Fase A Ollama, Fase H wave 1–3, Final Release Gate)
  remediation/       ← report DONE (incl. F1–F4)
  archive/           ← SUPERSEDED / scratch / ECC early
```
