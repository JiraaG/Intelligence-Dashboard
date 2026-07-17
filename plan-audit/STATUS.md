# plan-audit — STATUS (fatto vs da fare)

Quadro operativo aggiornato **2026-07-17**.  
Indice cartelle: [`README.md`](README.md).

---

## Completato

| Area | Dove | Note |
|------|------|------|
| Phase 0–6 GATE VERDE | [`complete/plan_impl_phase_0_6.md`](complete/plan_impl_phase_0_6.md) + [`_execution`](complete/plan_impl_phase_0_6_execution.md) | Restore SHA; non backlog |
| Ticket remediation P0–P2 | [`complete/plan_docs_audit_ticket_status.md`](complete/plan_docs_audit_ticket_status.md) | **0 OPEN** |
| Playbook audit docs | [`complete/plan_docs_audit_playbook.md`](complete/plan_docs_audit_playbook.md) | CLOSED |
| Allineamento product docs | [`complete/plan_docs_monorepo_source.md`](complete/plan_docs_monorepo_source.md) | ESEGUITO + coerenza porte/health/requeue |
| SoT LLM multi-provider | [`active/sot_llm_multi_model_fallback.md`](active/sot_llm_multi_model_fallback.md) | **Vivo** (design/routing) |
| Report ticket singoli | [`remediation/`](remediation/) | Storico — non cancellare |
| Prompt eseguiti | [`prompts/done/`](prompts/done/) | Storico |
| Piani ECC / Limits / stub | [`archive/`](archive/) | SUPERSEDED / PRD |

---

## Da fare (unico backlog vivo)

SoT: [`active/plan_release_final_gate.md`](active/plan_release_final_gate.md)  
Prompt: [`prompts/active/audit_prompt_final_release_gate.md`](prompts/active/audit_prompt_final_release_gate.md)

| Fase | Lavoro | Stato |
|------|--------|-------|
| 0 | PR `refactor/testing` → base (senza merge) | **Aperto** |
| 1 | Backup / restore drill | **Aperto** |
| 2 | Seed 10k + misura budget | **Aperto** |
| 3 | Chaos kill/restart (dopo backup) | **Aperto** |
| 4 | SAST / image scan / XSS spot | **Aperto** |
| 5 | Digest pin + drop `--legacy-peer-deps` | **DEFERRED** (tenere deferred) |

**Fuori scope:** nuove feature; `radar-sidebar/**`; riaprire ticket CLOSED.

---

## Layout rapido

```text
plan-audit/
  STATUS.md          ← questo file (quadro fatto / da fare)
  active/            ← SOLO vivo: SoT LLM + Final Release Gate
  complete/          ← piani e checklist COMPLETATI
  prompts/active/    ← prompt Final Release
  prompts/done/      ← storico
  remediation/       ← report DONE
  archive/           ← SUPERSEDED / scratch / ECC early
```
