# plan-audit — indice

Cartella di audit, prompt orchestratore e SoT del modulo Radar.  
**Non** è codice di produzione.

**Quadro fatto vs da fare:** [`STATUS.md`](STATUS.md)  
**Product docs:** root [`README.md`](../README.md) + [`docs/01–04`](../docs/).

**Anti-drift:** autorità runtime = product docs + Compose (`80:8080`, migrazioni `001–011`) + SoT LLM. Claim storici nei piani in `complete/` possono essere datati.

## `active/` — vivi

* Nessun piano di implementazione in corso (solo prompt ECC in `prompts/active/`)

## `complete/` — chiusi

Vedi [`complete/README.md`](complete/README.md) (Phase 0–6, SoT LLM, Fase A Ollama, audit lane env, Fase B/H, archi UI, Final Release, commenti, Notizie Salvate, playbook, ticket status, monorepo check).

## Layout

```text
plan-audit/
  STATUS.md                 ← fatto vs da fare (leggere per primo)
  README.md                 ← questo indice
  active/                   Vuoto di piani (vedi README in cartella)
  complete/                 Piani e checklist COMPLETATI
  prompts/active/           Prompt non ancora eseguiti (ECC manual/expansion)
  prompts/done/             Prompt eseguiti (storico)
  remediation/              Report ticket DONE (non cancellare)
  archive/plans|ecc|llm-stubs|scratch/
```

## Prompt attivi

* [plan_prompt_ecc_manual_and_expansion.md](prompts/active/plan_prompt_ecc_manual_and_expansion.md) — non ancora eseguito

## Prompt done (recente)

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
* **Limiti:** per-lane; `0`=unmanaged; soft-trim=`LLM_SIMPLE.rpd` (bypass ibernazione se residual COMPLEX); RPM/TPM=attesa stessa lane; RPD/cooldown=`QuotaDailyExceeded`→cross-lane; free=RPM/RPD(+TPM); paid=BUDGET
