# plan-audit — indice

Cartella di audit, prompt orchestratore e SoT operativi del Radar.  
**Non** è codice di produzione; i documenti vivi stanno in `active/`.

## SoT correnti (`active/`)

| Documento | Ruolo |
|-----------|--------|
| [LLM_Multi_Model_Fallback_Phase_AB.md](active/LLM_Multi_Model_Fallback_Phase_AB.md) | Multi-model LLM + routing (A+B+C) |
| [audit_remediation_llm_multi_model_fallback.md](remediation/audit_remediation_llm_multi_model_fallback.md) | Report implementazione Fase C |
| [Final_Release_Gate_Plan.md](active/Final_Release_Gate_Plan.md) | Gate residuali Final Release |
| [audit_problemi_documentazione.md](active/audit_problemi_documentazione.md) | Playbook audit/remediation |
| [audit_problemi_documentazione_risoluzione.md](active/audit_problemi_documentazione_risoluzione.md) | Stati ticket P0–P2 |
| [Implementation_Plan.md](active/Implementation_Plan.md) | Consolidation Phase 0–6 |
| [Implementation_Plan_Execution.md](active/Implementation_Plan_Execution.md) | Log esecuzione / scoreboard |

## Layout

```text
plan-audit/
  README.md                 ← questo file
  active/                   SoT e piani vivi
  prompts/active/           prompt orchestratore ancora utili
  prompts/done/             prompt eseguiti (archivio operativo)
  remediation/              report ticket DONE
  archive/plans/            PRD / piani ECC early
  archive/ecc/              handoff ECC storici
  archive/llm-stubs/        stub superseduti dal SoT LLM
  scratch/                  checklist/audit grezzi
```

## Prompt attivi

- [audit_prompt_llm_multi_model_fallback.md](prompts/active/audit_prompt_llm_multi_model_fallback.md)
- [audit_prompt_final_release_gate.md](prompts/active/audit_prompt_final_release_gate.md)

## Note

- Stub LLM storici: `archive/llm-stubs/*.SUPERSEDED.md` → usare solo il SoT in `active/`.
- Canvas IDE complessità: `canvases/article-complexity-routing.canvas.tsx` (fuori da plan-audit).
