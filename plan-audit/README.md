# plan-audit — indice

Cartella di audit, prompt orchestratore e SoT del modulo Radar.  
**Non** è codice di produzione.

**Quadro fatto vs da fare:** [`STATUS.md`](STATUS.md)  
**Product docs:** root [`README.md`](../README.md) + [`docs/01–04`](../docs/).

**Anti-drift:** autorità runtime = product docs + Compose (`80:8080`, migrazioni `001–009`) + SoT LLM. Claim storici nei piani in `complete/` possono essere datati.

## `active/` — vivi

| Documento | Ruolo |
|-----------|--------|
| [sot_llm_multi_model_fallback.md](active/sot_llm_multi_model_fallback.md) | **SoT** LLM multi-provider + routing v2.2 |
| [plan_release_final_gate.md](active/plan_release_final_gate.md) | Piano Final Release (**F1–F4 PASS**; resta PR + Fase 5 deferred) |
| [plan_code_comments_beginner_audit.md](active/plan_code_comments_beginner_audit.md) | Piano commenti IT (**P0 DONE**; P1/P2 opt-in) |

## `complete/` — chiusi

Vedi [`complete/README.md`](complete/README.md): Phase 0–6, playbook, ticket status, checklist docs.

## Layout

```text
plan-audit/
  STATUS.md                 ← fatto vs da fare (leggere per primo)
  README.md                 ← questo indice
  active/                   SoT LLM + Final Release + piano commenti
  complete/                 Piani/checklist COMPLETATI
  prompts/active/           Prompt ancora utili (PR gate; ECC expansion)
  prompts/done/             Prompt eseguiti (storico)
  remediation/              Report ticket DONE (non cancellare)
  archive/plans|ecc|llm-stubs|scratch/
```

## Prompt attivi

* [audit_prompt_final_release_gate.md](prompts/active/audit_prompt_final_release_gate.md) — F1–F4 PASS; utile solo per residuo PR
* [plan_prompt_ecc_manual_and_expansion.md](prompts/active/plan_prompt_ecc_manual_and_expansion.md) — non ancora eseguito

## Prompt done (recente)

* [audit_prompt_code_comments_beginner_terra.md](prompts/done/audit_prompt_code_comments_beginner_terra.md) — audit Terra → piano commenti (P0 eseguiti)

## Note

* **Limits Plan (DONE):** [archive/plans/plan_llm_limits_periodicity_docs_ecc.md](archive/plans/plan_llm_limits_periodicity_docs_ecc.md)
* **Stub LLM:** [archive/llm-stubs/](archive/llm-stubs/) — non usare
* **Provider:** `gemini`\|`deepseek`\|`openai`\|`glm`\|`grok`\|`claude`(stub). Dialect: deepseek=`thinking`; openai/glm/grok=`stock`
* **Limiti:** per-lane; `0`=unmanaged; soft-trim=`LLM_SIMPLE.rpd` (bypass ibernazione se residual COMPLEX); RPM/TPM=attesa stessa lane; RPD/cooldown=`QuotaDailyExceeded`→cross-lane; free=RPM/RPD(+TPM); paid=BUDGET
