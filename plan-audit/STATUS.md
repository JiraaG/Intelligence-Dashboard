# plan-audit — STATUS (fatto vs da fare)

Quadro operativo aggiornato **2026-07-19** (Profilo F Local-Hybrid `54c8038` + **VRAM unload shipped**; map anchors; Fase A ACTIVE solo per scorecard fixture opz.).  
Indice cartelle: [`README.md`](README.md).  
Handoff Final Release: [`remediation/audit_remediation_final_release_handoff.md`](remediation/audit_remediation_final_release_handoff.md).

---

## In corso (active)

| Area | Dove | Note |
|------|------|------|
| Fase A — LLM locale AMD/Ollama | [`active/plan_impl_fase_A_local_amd_ollama.md`](active/plan_impl_fase_A_local_amd_ollama.md) | **ACTIVE (follow-up opz.)** — W1–W4 + VRAM unload **DONE** (core `54c8038` + `ollama_lifecycle`/`OLLAMA_*`). Overlay host, Profilo F, `openai_compat_*`, think Gemma, `normalize_llm_json_dict`, **no SIMPLE Ollama→DeepSeek escalate**, requeue 48h OK. Ops tag tipico **`gemma4-radar`**. Residuo: scorecard fixture formale (opz.). Prompt in [`prompts/done/`](prompts/done/plan_prompt_fase_A_local_amd_ollama.md). |
| ECC manual / expansion | [`prompts/active/plan_prompt_ecc_manual_and_expansion.md`](prompts/active/plan_prompt_ecc_manual_and_expansion.md) | **ACTIVE (non eseguito)** — resta finché non si produce un piano deliverable |

---

## Completato

| Area | Dove | Note |
|------|------|------|
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
| Archi multicolore + click bilaterale | [`complete/plan_archi_hatching_multicolor.md`](complete/plan_archi_hatching_multicolor.md) | **DONE / GATE VERDE** (2026-07-18) — macro multicolore &lt;5, tratteggio geometrico ≥5, `relationsPane`, hover/click → `loadRelationArticles`. |

---

## Residui post-gate

| Item | Stato | Note |
|------|--------|------|
| Fase 0 — PR `refactor/testing` → `develop` | **DONE** | [PR #1](https://github.com/JiraaG/Dashboard-finance/pull/1) merged 2026-07-17; tip `develop` include Notizie Salvate (`b08fd7e`) oltre al branch |
| Fase 5 — digest pin + drop `--legacy-peer-deps` | **DEFERRED ACCETTATO** | Hardening opzionale; **non** da fare per release. Vedi piano §7 |
| Commenti codice P1/P2 | **Chiuso (P2-01)** | Altri P2 in inventario senza `batch_id` — solo se emerge gap reale |
| Fase C — Dedup semantica `pgvector` | **BACKLOG** | Vedi `radar_overview_and_upgrades.md` §C; non iniziata; indipendente da H / A |
| Fase A — LLM locale AMD/Ollama | **ACTIVE (follow-up)** | Impl Profilo F **DONE** (`54c8038`) + **VRAM unload shipped**. Aperto opz.: scorecard fixture. Piano [`active/plan_impl_fase_A_local_amd_ollama.md`](active/plan_impl_fase_A_local_amd_ollama.md). |
| Fase H — Grafo geospaziale | **DONE** | related_countries + GET /api/map-relations + archi mappa + chip carosello (2026-07-18). |
| Archi UI (multicolore + click) | **DONE** | Piano [`complete/plan_archi_hatching_multicolor.md`](complete/plan_archi_hatching_multicolor.md). Residuo **opzionale**: multicolore aggregato anche a zoom ≥ 5. |

**Nessun residuo operativo obbligatorio sulla Fase B / H / archi UI / classification refine / map anchors / Profilo F core.** Branch di riferimento feature: `feature/upgrades`.

**Restore point (Profilo F + VRAM unload):** `2996625` su `feature/upgrades`. Core Local-Hybrid: `54c8038`. Precedenti: map anchors `a240b3c`; click hatching `911463a`; classification/geo `f7cf83d`; archi UI `5c74e57`.

Prompt Final Release: [`prompts/done/audit_prompt_final_release_gate.md`](prompts/done/audit_prompt_final_release_gate.md) — **non rieseguire** (F0–F4 chiusi).

**Fuori scope:** nuove feature Fase A oltre scorecard opz. senza richiesta; refactor/restyle di `radar-sidebar/**` al di fuori delle eccezioni mirate; riaprire ticket CLOSED; rieseguire P0 commenti senza richiesta; attivare Fase 5 senza decisione esplicita.

---

## Layout rapido

```text
plan-audit/
  STATUS.md          ← questo file (quadro fatto / residui)
  active/            ← Piani in corso (Fase A follow-up / ECC prompt)
  complete/          ← Piani COMPLETATI (incl. Phase 0–6, Fase B, Fase H, archi UI)
  prompts/active/    ← prompt non eseguiti (ECC manual/expansion)
  prompts/done/      ← storico (incl. Fase A Ollama, Fase H wave 1–3, Final Release Gate)
  remediation/       ← report DONE (incl. F1–F4)
  archive/           ← SUPERSEDED / scratch / ECC early
```
