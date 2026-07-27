# plan-audit — indice

Cartella di audit, prompt orchestratore e SoT del modulo Radar.  
**Non** è codice di produzione.

**Quadro fatto vs da fare:** [`STATUS.md`](STATUS.md)  
**Product docs:** root [`README.md`](../README.md) + [`docs/01–04`](../docs/).

**Anti-drift:** autorità runtime = product docs + Compose (`80:8080`, migrazioni `001–017`) + SoT LLM. Claim storici nei piani in `complete/` possono essere datati (snapshot al momento del GATE — non riscrivere).

## `active/` — vivi

* Relazioni Wave 2 elevate 3D — [`active/plan_impl_map_relations_arcs_3d.md`](active/plan_impl_map_relations_arcs_3d.md) (spike; W1 DONE)
* Fase I MapLibre 3D-primary — [`active/plan_impl_map_3d_globe.md`](active/plan_impl_map_3d_globe.md)
* §3.J globo — [`active/plan_impl_map_globe_projection.md`](active/plan_impl_map_globe_projection.md)
* Prompt ECC in `prompts/active/` (solo non eseguiti)

## `complete/` — chiusi

Vedi [`complete/README.md`](complete/README.md) (**FONTI** feed management, **FinOps UI** + split STATUS/COSTI, **Eager drain**, **FinOps LLM Wave A**, **BORDERLINE effort split**, **Quote per-modello**, **Metrics 013 FinOps**, Phase 0–6, SoT LLM, Fase A Ollama, audit lane env, Fase B/H, archi UI, **W1 filtro nazioni Relazioni**, **Fase C semantic dedup**, Final Release, commenti, Notizie Salvate, playbook, ticket status, monorepo check).

## Layout

```text
plan-audit/
  STATUS.md                 ← fatto vs da fare (leggere per primo)
  README.md                 ← questo indice
  active/                   Piani e spike attivi
  complete/                 Piani e checklist COMPLETATI
  prompts/active/           Prompt non ancora eseguiti (ECC manual/expansion)
  prompts/done/             Prompt eseguiti (storico)
  remediation/              Report ticket DONE (non cancellare)
  archive/plans|ecc|llm-stubs|scratch/
```

## Prompt attivi

* [plan_prompt_ecc_manual_and_expansion.md](prompts/active/plan_prompt_ecc_manual_and_expansion.md) — non ancora eseguito
* [plan_prompt_map_3d_globe.md](prompts/active/plan_prompt_map_3d_globe.md) — mappa 3D / switch vs 3D-only (non eseguito)

## Prompt done (recente)

* [agent_prompt_fonti_feed_management.md](prompts/done/agent_prompt_fonti_feed_management.md) — **FONTI** Giorno+Catalogo / API feeds — **GATE VERDE** 2026-07-27
* [agent_prompt_split_status_costi_topbar.md](prompts/done/agent_prompt_split_status_costi_topbar.md) — Split STATUS left / COSTI right — **DONE / SUPERSEDED** (layout reale in `docs/03`)
* [agent_prompt_audit_finops_status_costs.md](prompts/done/agent_prompt_audit_finops_status_costs.md) — Audit numeri STATUS & COSTI
* [agent_prompt_finops_ui_closeout.md](prompts/done/agent_prompt_finops_ui_closeout.md) — FinOps UI closeout
* [agent_prompt_finops_ui_metrics.md](prompts/done/agent_prompt_finops_ui_metrics.md) — FinOps UI impl W0–W7
* [agent_prompt_eager_drain_closeout.md](prompts/done/agent_prompt_eager_drain_closeout.md) — Eager drain CLOSEOUT + live verify — **GATE VERDE** 2026-07-24
* [agent_prompt_eager_drain_startup.md](prompts/done/agent_prompt_eager_drain_startup.md) — Eager drain impl R1–R6 — **GATE VERDE** 2026-07-24
* [agent_prompt_llm_finops_token_caching.md](prompts/done/agent_prompt_llm_finops_token_caching.md) — **FinOps LLM Wave A (M1–M6 + verifica)** — GATE VERDE (condizionato)
* [agent_prompt_finops_wave_a_soak_verify.md](prompts/done/agent_prompt_finops_wave_a_soak_verify.md) — **FinOps Wave A soak/requeue verify** — eseguito 2026-07-22 (soak OK)


* [agent_prompt_borderline_effort_final_polish.md](prompts/done/agent_prompt_borderline_effort_final_polish.md) — polish C3/C6/C7
* [agent_prompt_borderline_effort_split_closeout.md](prompts/done/agent_prompt_borderline_effort_split_closeout.md) — closeout C1–C12
* [agent_prompt_borderline_effort_split.md](prompts/done/agent_prompt_borderline_effort_split.md) — **BORDERLINE effort none + escalate high** GATE VERDE
* [plan_prompt_borderline_cost_routing.md](prompts/done/plan_prompt_borderline_cost_routing.md) — **Analisi BORDERLINE costi** (chiusa 2026-07-22; esito → effort-split)
* [agent_prompt_per_model_quota.md](prompts/done/agent_prompt_per_model_quota.md) — **Quote per-modello** (failover L1 pool separati; GATE live 3.5 vs 3.1 2026-07-22)

* [agent_prompt_fase_metrics_013_verify_fix.md](prompts/done/agent_prompt_fase_metrics_013_verify_fix.md) — **Metrics 013 micro-fix** (verify ledger scoped + rebuild + STATUS → GREEN onesto)
* [agent_prompt_fase_metrics_013_gate_closeout.md](prompts/done/agent_prompt_fase_metrics_013_gate_closeout.md) — closeout YELLOW→GREEN (funzionale; verify ancora da scoped)
* [agent_prompt_fase_metrics_013.md](prompts/done/agent_prompt_fase_metrics_013.md) — Metrics 013 impl
* [agent_prompt_fase_C_semantic_dedup.md](prompts/done/agent_prompt_fase_C_semantic_dedup.md) — Fase C semantic dedup GATE (2026-07-22)
* [plan_prompt_fase_A_local_amd_ollama.md](prompts/done/plan_prompt_fase_A_local_amd_ollama.md) — Fase A Ollama (archiviato 2026-07-19)
* [plan_prompt_phase_H_wave3_carousel_docs_gate.md](prompts/done/plan_prompt_phase_H_wave3_carousel_docs_gate.md) — H5+H6 chip + docs/ECC GATE (2026-07-18)
* [plan_prompt_phase_H_wave2_frontend_map.md](prompts/done/plan_prompt_phase_H_wave2_frontend_map.md) — H3+H4 mappa (2026-07-18)
* [plan_prompt_phase_H_wave1_backend.md](prompts/done/plan_prompt_phase_H_wave1_backend.md) — H1+H2 backend (2026-07-18)
* [audit_prompt_final_release_gate.md](prompts/done/audit_prompt_final_release_gate.md) — Final Release F0–F4 CLOSED (archiviato 2026-07-18)
* [audit_prompt_code_comments_beginner_terra.md](prompts/done/audit_prompt_code_comments_beginner_terra.md) — audit Terra → piano commenti (P0 eseguiti)

## Note

* **Limits Plan (DONE):** [archive/plans/plan_llm_limits_periodicity_docs_ecc.md](archive/plans/plan_llm_limits_periodicity_docs_ecc.md)
* **Stub LLM:** [archive/llm-stubs/](archive/llm-stubs/) — non usare
* **Provider:** `gemini`\|`deepseek`\|`openai`\|`glm`\|`grok`\|`claude`(stub). Dialect: deepseek=`thinking`; openai/glm/grok=`stock`
* **Limiti:** tetti per-lane + contatori per-model; `0`=unmanaged; soft-trim=residuo catena SIMPLE (bypass ibernazione se residual COMPLEX); RPM/TPM=attesa stessa lane (spacing); RPD/cooldown=`QuotaDailyExceeded`→L1 poi cross-lane; free=RPM/RPD(+TPM); paid=BUDGET
