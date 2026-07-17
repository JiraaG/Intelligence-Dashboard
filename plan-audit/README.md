# plan-audit — indice

Cartella di audit, prompt orchestratore e SoT operativi del modulo Radar.  
**Non** è codice di produzione.

**Product docs (manuali operatori):** root [`README.md`](../README.md) + [`docs/01–04`](../docs/).  
**Checklist allineamento docs:** [`plan_docs_monorepo_source.md`](active/plan_docs_monorepo_source.md).

**Anti-drift:** claim storici nei phase plans (es. porte `80:80`, migrazioni `001–007`) possono essere datati. Autorità runtime = product docs + Compose (`80:8080`, migrazioni `001–009`) + SoT LLM. Niente file operativi in root oltre questo README; scratch solo in `archive/scratch/`.

## SoT e piani in `active/` — vivi vs chiusi

### Vivi (usare)

| Documento | Ruolo |
|-----------|--------|
| [sot_llm_multi_model_fallback.md](active/sot_llm_multi_model_fallback.md) | **SoT** LLM multi-provider + routing (lane env + complexity v2.2) |
| [plan_release_final_gate.md](active/plan_release_final_gate.md) | Gate residuali Final Release (**≠** Phase 6 GATE) |
| [plan_docs_monorepo_source.md](active/plan_docs_monorepo_source.md) | Checklist allineamento README/docs/ops/ECC |

### Chiusi (riferimento — non backlog)

| Documento | Ruolo |
|-----------|--------|
| [plan_impl_phase_0_6.md](active/plan_impl_phase_0_6.md) | Piano Phase 0–6 (**DONE / GATE VERDE**) + restore SHA |
| [plan_impl_phase_0_6_execution.md](active/plan_impl_phase_0_6_execution.md) | Scoreboard esecuzione Phase 0–6 (**chiuso**) |
| [plan_docs_audit_playbook.md](active/plan_docs_audit_playbook.md) | Playbook audit/remediation (**CLOSED**) |
| [plan_docs_audit_ticket_status.md](active/plan_docs_audit_ticket_status.md) | Trail ticket docs/codice (**CLOSED**, 0 OPEN) |

> Phase plans restano in `active/` finché Final Release non è chiuso (ancora citati da README/docs). Poi: candidati a `archive/plans/`.

## Layout cartelle

```text
plan-audit/
  README.md                 ← Questo file (indice)
  active/                   SoT vive + piani chiusi di riferimento
  prompts/active/           Prompt orchestratore attivi
  prompts/done/             Prompt già eseguiti (storico)
  remediation/              Report chiusura ticket (DONE — non cancellare)
  archive/plans/            Piani operativi storici / PRD
  archive/ecc/              Handoff ECC storici
  archive/llm-stubs/        Stub LLM SUPERSEDED
  archive/scratch/          Checklist audit grezze
```

## Prompt attivi (`prompts/active/`)

* [audit_prompt_final_release_gate.md](prompts/active/audit_prompt_final_release_gate.md) — Gate finali di release.

## Note e storico

* **Limits Plan (DONE):** [plan_llm_limits_periodicity_docs_ecc.md](archive/plans/plan_llm_limits_periodicity_docs_ecc.md).
* **Remediation & Done Prompts:** [remediation/](remediation/) + [prompts/done/](prompts/done/) — SoT storico del lavoro; **non eliminare**.
* **Stub LLM:** [archive/llm-stubs/](archive/llm-stubs/) — non usare come riferimento.
* **Complexity v2.2:** SIMPLE = `LLM_SIMPLE`; BORDERLINE+COMPLEX = `LLM_COMPLEX`; L sola → SIMPLE.
* **Limiti:** per-lane `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (`0` = unmanaged); soft-trim = `LLM_SIMPLE.rpd`; free = RPM/RPD, paid = `BUDGET_USD_DAY`.
* **Provider:** `gemini` \| `deepseek` \| `openai` \| `glm` \| `grok` \| `claude` (stub). Dialect: deepseek=`thinking`; openai/glm/grok=`stock`. SoT §5 Profili A–E.
