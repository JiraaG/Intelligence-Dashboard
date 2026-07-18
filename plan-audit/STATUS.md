# plan-audit — STATUS (fatto vs da fare)

Quadro operativo aggiornato **2026-07-18**.  
Indice cartelle: [`README.md`](README.md).  
Handoff Final Release: [`remediation/audit_remediation_final_release_handoff.md`](remediation/audit_remediation_final_release_handoff.md).

---

## Completato

| Area | Dove | Note |
|------|------|------|
| Notizie Salvate (`is_saved`) | [`complete/note_notizie_salvate.md`](complete/note_notizie_salvate.md) | Migration `010`; vault cross-day; save⇒read / unread⇒unsave; spiderfy parity LETTE/TROVATE (2026-07-17) |
| Phase 0–6 GATE VERDE | [`complete/plan_impl_phase_0_6.md`](complete/plan_impl_phase_0_6.md) + [`_execution`](complete/plan_impl_phase_0_6_execution.md) | Restore SHA; non backlog |
| Ticket remediation P0–P2 | [`complete/plan_docs_audit_ticket_status.md`](complete/plan_docs_audit_ticket_status.md) | **0 OPEN** |
| Playbook audit docs | [`complete/plan_docs_audit_playbook.md`](complete/plan_docs_audit_playbook.md) | CLOSED |
| Allineamento product docs | [`complete/plan_docs_monorepo_source.md`](complete/plan_docs_monorepo_source.md) | ESEGUITO + coerenza porte/health/requeue |
| Final Release F0–F4 | [`complete/plan_release_final_gate.md`](complete/plan_release_final_gate.md) + report `remediation/*_F*.md` | **PR #1 merged** 2026-07-17; backup, seed 10k, chaos C1–C3, security |
| SoT LLM multi-provider | [`complete/sot_llm_multi_model_fallback.md`](complete/sot_llm_multi_model_fallback.md) | **Vivo** — §0 limiti/failover RPM·TPM vs RPD (2026-07-17) |
| Commenti codice P0–P2 | [`complete/plan_code_comments_beginner_audit.md`](complete/plan_code_comments_beginner_audit.md) | **P0–P1–P2-01 DONE**; altri P2 inventario restano fuori batch |
| Prompt audit commenti | [`prompts/done/audit_prompt_code_comments_beginner_terra.md`](prompts/done/audit_prompt_code_comments_beginner_terra.md) | Pipeline Terra→Grok chiusa |
| Prompt Final Release Gate | [`prompts/done/audit_prompt_final_release_gate.md`](prompts/done/audit_prompt_final_release_gate.md) | Archiviato 2026-07-18 — gate chiuso |
| Report ticket singoli | [`remediation/`](remediation/) | Storico — non cancellare |
| Prompt eseguiti | [`prompts/done/`](prompts/done/) | Storico |
| Piani ECC / Limits / stub | [`archive/`](archive/) | SUPERSEDED / PRD |
| Phase B Real-Time (webhook/SSE/soft-refresh) | [`complete/master_plan_impl_phase_B.md`](complete/master_plan_impl_phase_B.md) + [`implementation`](complete/implementation_plan_phase_B.md) + [`analisi`](complete/analisi_dettagliata_fase_B.md) | **DONE / GATE VERDE** 2026-07-18 — HMAC webhook, LISTEN dedicate, SSE, Angular soft-refresh |

---

## Residui post-gate

| Item | Stato | Note |
|------|--------|------|
| Fase 0 — PR `refactor/testing` → `develop` | **DONE** | [PR #1](https://github.com/JiraaG/Dashboard-finance/pull/1) merged 2026-07-17; tip `develop` include Notizie Salvate (`b08fd7e`) oltre al branch |
| Fase 5 — digest pin + drop `--legacy-peer-deps` | **DEFERRED ACCETTATO** | Hardening opzionale; **non** da fare per release. Vedi piano §7 |
| Commenti codice P1/P2 | **Chiuso (P2-01)** | Altri P2 in inventario senza `batch_id` — solo se emerge gap reale |
| Fase C — Dedup semantica `pgvector` | **NEXT** | Vedi `radar_overview_and_upgrades.md` §C; non iniziata |

**Nessun residuo operativo obbligatorio sulla Fase B.** Branch corrente di riferimento: `feature/upgrades` (Phase B) / `develop` (baseline release).

Prompt Final Release: [`prompts/done/audit_prompt_final_release_gate.md`](prompts/done/audit_prompt_final_release_gate.md) — **non rieseguire** (F0–F4 chiusi).

**Fuori scope:** nuove feature; `radar-sidebar/**`; riaprire ticket CLOSED; rieseguire P0 commenti senza richiesta; attivare Fase 5 senza decisione esplicita.

---

## Layout rapido

```text
plan-audit/
  STATUS.md          ← questo file (quadro fatto / residui)
  active/            ← Piani in corso (vuota post–Fase B GATE)
  complete/          ← Piani COMPLETATI (incl. Phase 0–6 + Fase B)
  prompts/active/    ← solo prompt non eseguiti (ECC expansion)
  prompts/done/      ← storico (incl. Final Release Gate + audit commenti)
  remediation/       ← report DONE (incl. F1–F4)
  archive/           ← SUPERSEDED / scratch / ECC early
```
