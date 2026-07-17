# Prompt orchestratore — chiusura residuali post plan-audit cleanup

> **Uso:** nuova chat Agent — incolla il blocco sotto.  
> **Contesto:** cleanup `plan-audit/` già eseguito (~PASS); verifica ha trovato gap.  
> **Alcuni fix già applicati** (README root, Limits header links, `Fase2_Implementation_Plan.md`, handoff path in execution). Questo prompt **verifica** quei fix e chiude ciò che resta.  
> **Non** rieseguire la matrice rename da zero.

---

## Blocco da incollare

```text
GOAL
Chiudere i residuali della verifica post–plan-audit cleanup: confermare i fix già
fatti, correggere citazioni stale rimaste (soprattutto ecc_deep_dive_analysis_v2.md
e eventuali link rotti), rieseguire i gate di verifica, produrre report PASS/FAIL.
Non rifare git mv di massa. Non toccare codice runtime, .env, sidebar, vault.

CONTESTO (AS-IS atteso)
- SoT LLM: plan-audit/active/sot_llm_multi_model_fallback.md
- Limits DONE: plan-audit/archive/plans/plan_llm_limits_periodicity_docs_ecc.md
- Impl: plan-audit/complete/plan_impl_phase_0_6.md (+ _execution)
- Release gate: plan-audit/active/plan_release_final_gate.md
- Docs audit: plan_docs_audit_playbook.md / plan_docs_audit_ticket_status.md
- Scratch: plan-audit/archive/scratch/scratch_*.md
- Handoff ECC: plan-audit/archive/ecc/handoff_ecc_*.md
- prompts/active/: SOLO audit_prompt_final_release_gate.md
- Cleanup prompts: già in prompts/done/

FIX GIÀ FATTI (verificare, non duplicare se già OK)
1) README.md (repo root): link Implementation_Plan* / ECC_Expansion → path plan-audit/
2) archive/plans/plan_llm_limits_periodicity_docs_ecc.md header:
   prompt → ../../prompts/done/audit_prompt_llm_limits_docs_ecc.md
   SoT → ../../active/sot_llm_multi_model_fallback.md
3) plan_impl_phase_0_6*.md: ripristinato nome `Fase2_Implementation_Plan.md`
   (non `Fase2_Implementation_Plan.md`)
4) plan_impl_phase_0_6_execution.md: handoff con path plan-audit/archive/ecc/...

RESIDUALI DA CHIUDERE
A) ecc_deep_dive_analysis_v2.md (repo root)
   - Aggiornare tabella/tree/citazioni che puntano a Implementation_Plan*,
     ECC_*Handoff.md, plan.md in root o path pre-cleanup.
   - Destinazioni canoniche = path sotto plan-audit/ sopra.
   - Non riscrivere il manuale: solo link e nomi file.

B) Sweep anti-regressione (grep) — FAIL se path VIVI inesistenti in link markdown:
   Cerca e correggi (se sono href/path operativi, non citazioni storiche in prompt done):
   - ](plan-audit/complete/plan_impl_phase_0_6.md) o ](../plan-audit/complete/plan_impl_phase_0_6.md) senza plan-audit/
   - ](plan-audit/archive/ecc/handoff_ecc_expansion.md) / ](plan-audit/archive/ecc/handoff_ecc_architecture_audit.md) in root
   - plan-audit/active/sot_llm_multi_model_fallback.md
   - plan-audit/archive/plans/plan_llm_limits_periodicity_docs_ecc.md
   - plan-audit/scratch/ (dir non deve esistere)
   - Fase2_Implementation_Plan.md  (bug rename cieco — deve restare Fase2_Implementation_Plan.md)

C) Eccezioni OK (non “fixare” a meno che non siano href rotti):
   - Stringhe old-path dentro prompts/done/* come istruzioni storiche del blocco text
   - Mentions in audit_prompt_plan_audit_cleanup*.md della matrice “prima”
   - Nome storico “Phase_AB” come testo narrativo se il link punta a sot_llm_*

D) Opzionale low-priority:
   - Bare basename in archive/ecc/handoff_*.md tipo `plan_impl_phase_0_6_execution.md`
     senza path: preferire `../../complete/plan_impl_phase_0_6_execution.md` se è un link.
   - Root README tree già aggiornato: conferma coerenza.

ALLOWLIST EDIT
README.md                          (repo root — se ancora stale)
ecc_deep_dive_analysis_v2.md
plan-audit/**/*.md                 (solo fix link / typo path)
.agents/AGENTS.md                  (solo se ancora stale)
.agents/skills/**/SKILL.md         (+ mirror radar/.ecc/skills/* se tocchi SoT path)
docs/02_architecture_and_backend.md
docs/04_ecc_framework.md
radar/.ecc/CLAUDE.md
radar/.ecc/rules/backend.md
radar/.ecc/agents/pipeline-engineer.md

VIETATO
- Nuova ondata di rename tassonomici
- Delete remediation/ o stub SUPERSEDED
- Edit .env, codice backend/frontend, sidebar
- Inventare file Fase2_plan_impl_* 

RUOLI
1) SUPERVISORE — conferma AS-IS filesystem (Test-Path / Glob), poi dispatch
2) FIXER — applica solo residuali A–D
3) VERIFIER — gate sotto

VERIFIER GATES (tutti PASS)
1) plan-audit/scratch/ non esiste; active/ senza LLM_*Phase_AB / Limits plan
2) README.md root: ogni link plan-audit/ risolvibile; nessun Implementation_Plan.md in root
3) ecc_deep_dive_analysis_v2.md: link piani/handoff puntano a plan-audit/…
4) Grep `Fase2_plan_impl_phase_0_6` → 0 hit
5) Skill + ecc citano sot_llm_multi_model_fallback.md
6) prompts/active/ = solo final_release_gate
7) Header Limits archiviato: link prompt done + SoT active risolvibili

DONE WHEN
- Residual A–B chiusi (C/D se trovati)
- Verifier PASS
- Report breve; se tutto già OK: “noop + PASS”

REPORT
## plan-audit residual close
- Verdetto: PASS | FAIL
- Fix già presenti / confermati: …
- Fix nuovi in questa sessione: elenco path
- Grep residuali aperti: …
- Next: commit cleanup+residuali (su richiesta) | Final Release gate
```

---

## Note

| Cosa | Nota |
|------|------|
| Scope | Solo residuali verifica, non re-cleanup |
| Priorità | `ecc_deep_dive_analysis_v2.md` + anti-`Fase2_plan_impl_*` + README root |
| Commit | Solo se l’utente lo chiede dopo PASS |
