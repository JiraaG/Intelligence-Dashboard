# plan-audit — indice

Cartella di audit, prompt orchestratore e SoT operativi del modulo Radar.  
**Non** è codice di produzione; i documenti vivi stanno in `active/`.

## SoT e Piani Correnti (`active/`)

| Documento | Ruolo |
|-----------|--------|
| [sot_llm_multi_model_fallback.md](active/sot_llm_multi_model_fallback.md) | **Source of Truth** per Multi-model LLM + routing (lane env + complexity heuristic v2.2) |
| [plan_release_final_gate.md](active/plan_release_final_gate.md) | Piano per la validazione dei Gate residuali Final Release |
| [plan_docs_audit_playbook.md](active/plan_docs_audit_playbook.md) | Playbook operativo di audit & remediation documentazione |
| [plan_docs_audit_ticket_status.md](active/plan_docs_audit_ticket_status.md) | Stato finale di chiusura e risoluzione dei ticket documentali |
| [plan_impl_phase_0_6.md](active/plan_impl_phase_0_6.md) | Piano di consolidamento Phase 0–6 |
| [plan_impl_phase_0_6_execution.md](active/plan_impl_phase_0_6_execution.md) | Log di esecuzione / scoreboard del consolidamento |

## Layout Cartelle

```text
plan-audit/
  README.md                 ← Questo file (indice SoT unico)
  active/                   SoT e piani operativi correnti (vivi)
  prompts/active/           Prompt orchestratore attivi / in esecuzione
  prompts/done/             Archivio storico dei prompt già eseguiti
  remediation/              Report di chiusura dei ticket di remediation (DONE)
  archive/plans/            Piani operativi storici conclusi o PRD iniziali
  archive/ecc/              Report e handoff storici dell'architettura ECC
  archive/llm-stubs/        Vecchi stub e ricerche LLM superati dal SoT LLM
  archive/scratch/          Checklist e log di audit grezzi (storico)
```

## Prompt Attivi (`prompts/active/`)

* [audit_prompt_final_release_gate.md](prompts/active/audit_prompt_final_release_gate.md) — Prompt per l'esecuzione e validazione dei gate finali di release.

## Note e Storico

* **Limits Plan (DONE):** Il piano operativo LLM Limits è stato archiviato in [plan_llm_limits_periodicity_docs_ecc.md](archive/plans/plan_llm_limits_periodicity_docs_ecc.md).
* **Remediation & Done Prompts:** Tutti i report di remediation dei singoli ticket (es. `audit_remediation_T-P*`) sono conservati nella cartella [remediation/](remediation/). I prompt storici eseguiti sono archiviati in [prompts/done/](prompts/done/).
* **Stub LLM Storici:** Gli stub superati sono in [archive/llm-stubs/](archive/llm-stubs/) e non devono essere usati come riferimento.
* **Complexity v2.2:** SIMPLE = solo `LLM_SIMPLE`; BORDERLINE+COMPLEX = `LLM_COMPLEX` (effort tipico high); L sola → SIMPLE.
* **Limiti:** per-lane `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (`0` = unmanaged); soft-trim = `LLM_SIMPLE.rpd`; free = RPM/RPD, paid = `BUDGET_USD_DAY`.
* **Provider env-swap (2026-07-16):** `gemini` \| `deepseek` \| `openai` \| `glm` \| `grok` \| `claude` (stub). OpenAI-compat dialect: `deepseek` = thinking payload; `openai`/`glm`/`grok` = stock. SoT §5 Profili A–E.
