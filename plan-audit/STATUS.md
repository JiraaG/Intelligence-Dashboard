# plan-audit — STATUS (fatto vs da fare)

Quadro operativo aggiornato **2026-07-17**.  
Indice cartelle: [`README.md`](README.md).  
Handoff Final Release: [`remediation/audit_remediation_final_release_handoff.md`](remediation/audit_remediation_final_release_handoff.md).

---

## Completato

| Area | Dove | Note |
|------|------|------|
| Phase 0–6 GATE VERDE | [`complete/plan_impl_phase_0_6.md`](complete/plan_impl_phase_0_6.md) + [`_execution`](complete/plan_impl_phase_0_6_execution.md) | Restore SHA; non backlog |
| Ticket remediation P0–P2 | [`complete/plan_docs_audit_ticket_status.md`](complete/plan_docs_audit_ticket_status.md) | **0 OPEN** |
| Playbook audit docs | [`complete/plan_docs_audit_playbook.md`](complete/plan_docs_audit_playbook.md) | CLOSED |
| Allineamento product docs | [`complete/plan_docs_monorepo_source.md`](complete/plan_docs_monorepo_source.md) | ESEGUITO + coerenza porte/health/requeue |
| Final Release F1–F4 | [`active/plan_release_final_gate.md`](active/plan_release_final_gate.md) + report `remediation/*_F*.md` | Backup, seed 10k, chaos C1–C3, security |
| SoT LLM multi-provider | [`active/sot_llm_multi_model_fallback.md`](active/sot_llm_multi_model_fallback.md) | **Vivo** — §0 limiti/failover RPM·TPM vs RPD (2026-07-17) |
| Commenti codice P0–P2 | [`active/plan_code_comments_beginner_audit.md`](active/plan_code_comments_beginner_audit.md) | **P0–P1–P2-01 DONE**; altri P2 inventario restano fuori batch |
| Prompt audit commenti | [`prompts/done/audit_prompt_code_comments_beginner_terra.md`](prompts/done/audit_prompt_code_comments_beginner_terra.md) | Pipeline Terra→Grok chiusa |
| Report ticket singoli | [`remediation/`](remediation/) | Storico — non cancellare |
| Prompt eseguiti | [`prompts/done/`](prompts/done/) | Storico |
| Piani ECC / Limits / stub | [`archive/`](archive/) | SUPERSEDED / PRD |

---

## Residui post-gate

| Item | Stato | Note |
|------|--------|------|
| Fase 0 — PR `refactor/testing` → `develop` (senza merge auto) | **Aperto** | Branch pushed; aprire via [compare](https://github.com/JiraaG/Dashboard-finance/compare/develop...refactor/testing?expand=1) (`gh` opzionale) |
| Fase 5 — digest pin + drop `--legacy-peer-deps` | **DEFERRED ACCETTATO** | Non blocca merge; vedi piano §7 |
| Commenti codice P1/P2 | **Opt-in** | Solo su richiesta; batch in piano §5 (`P1-01`…`P1-03`, `P2-01`) |

Prompt orchestratore (solo se serve chiudere Fase 0): [`prompts/active/audit_prompt_final_release_gate.md`](prompts/active/audit_prompt_final_release_gate.md) — **F1–F4 già PASS**, non rieseguire.

**Fuori scope:** nuove feature; `radar-sidebar/**`; riaprire ticket CLOSED; rieseguire P0 commenti senza richiesta.

---

## Layout rapido

```text
plan-audit/
  STATUS.md          ← questo file (quadro fatto / residui)
  active/            ← SoT LLM + Final Release + piano commenti (P1/P2 residui)
  complete/          ← piani e checklist COMPLETATI
  prompts/active/    ← prompt post-gate (PR) + ECC expansion (non eseguito)
  prompts/done/      ← storico (incl. audit commenti Terra)
  remediation/       ← report DONE (incl. F1–F4)
  archive/           ← SUPERSEDED / scratch / ECC early
```
