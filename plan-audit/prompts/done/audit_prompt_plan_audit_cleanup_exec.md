# Prompt orchestratore — ESECUZIONE pulizia `plan-audit/` (matrice verificata)

> **Uso:** nuova chat Agent — incolla il blocco sotto.  
> **Origine:** piano utente verificato/corretto (2026-07-16).  
> **Predecessore:** [`audit_prompt_plan_audit_cleanup.md`](audit_prompt_plan_audit_cleanup.md) (policy/tassonomia).  
> **Decisione SoT LLM (default in questo prompt):** **RENAME** → `sot_llm_multi_model_fallback.md` + fix link allowlist.  
> Se l’utente dice esplicitamente KEEP-name Phase_AB: salta solo quella riga rename.

---

## Correzioni rispetto al piano grezzo (leggere)

1. **Link sottostimati:** rename SoT LLM e piani `active/` toccano anche  
   `radar/.ecc/skills/*`, `radar/.ecc/rules/backend.md`, `radar/.ecc/agents/pipeline-engineer.md`,  
   `archive/llm-stubs/*.SUPERSEDED.md`, `remediation/*`, `prompts/done/*`,  
   `active/*` cross-link, non solo `.agents/skills` + README.
2. **`remediation/` e `prompts/done/` NON sono “zero link”:** dopo rename/MOVE di active/scratch  
   vanno aggiornati i path (altrimenti trail storico punta a file inesistenti).
3. **Link rotti fuori plan-audit:** `.agents/AGENTS.md` e `docs/02|04` puntano a  
   `../plan_impl_phase_0_6.md` (repo root — **file assente**). Fix obbligatorio →  
   `../plan-audit/active/plan_impl_phase_0_6.md` (e execution twin).  
   `docs/04` punta a `../handoff_ecc_expansion.md` (assente in root) →  
   `../plan-audit/archive/ecc/handoff_ecc_expansion.md`.
4. **Conteggio:** 46 `.md` sotto `plan-audit/` (incl. README + cleanup prompt) — OK.
5. **`verify_cleanup.py`:** non creare tool permanente; gate = script inline one-shot  
   (PowerShell/Python) + grep; opzionale salvare output in chat, non committare lo script.
6. **Open Q default (già decisi in questo prompt):**  
   - Q1 SoT LLM: **RENAME**  
   - Q2 scratch → `archive/scratch/scratch_*`: **SÌ**  
   - Q3 cleanup prompt → `prompts/done/` a fine PASS: **SÌ**

---

## Blocco da incollare

```text
GOAL
Eseguire la pulizia/allineamento plan-audit/ secondo la MATRICE VERIFICATA sotto:
git mv + rename tassonomici, fix link (plan-audit + allowlist esterna), aggiornare
plan-audit/README.md, verificare gate. Non toccare codice runtime Radar, .env, sidebar,
vault. Non cancellare remediation ticket.

DECISIONI GIÀ PRESE (non ri-chiedere salvo override utente in chat)
1) RENAME SoT LLM: active/sot_llm_multi_model_fallback.md
   → active/sot_llm_multi_model_fallback.md  (+ aggiornare TUTTI i riferimenti allowlist)
2) scratch/* → archive/scratch/scratch_*.md
3) A fine PASS: MOVE questo prompt e audit_prompt_plan_audit_cleanup.md in prompts/done/

SoT / SKILL
- Tassonomia: kind_domain_topic (sot_|plan_|audit_prompt_|audit_remediation_|handoff_|scratch_)
- Codice + radar-quota-ledger restano autorità su sematica LLM; qui solo path docs

RUOLI
1) SUPERVISORE — applica matrice; stop solo su collisioni path o delete non in matrice
2) EXECUTOR — git mv atomici; poi sweep link; poi README
3) VERIFIER — gate sotto; report PASS/FAIL

ORDINE ESECUZIONE (obbligatorio)
A. Snapshot: conta file per cartella; lista path attuali
B. Crea dir mancanti: plan-audit/archive/scratch/
C. git mv secondo matrice (una riga alla volta o batch sicuro)
D. Sweep link (grep old basename/path → replace new) su allowlist
E. Riscrivi plan-audit/README.md (solo SoT/prompt ancora active; nota done/archive)
F. Aggiorna H1 dei file rinominati se titolo ancora “Phase_AB” / “Problemi documentazione”
   in modo fuorviante (titolo umano OK; non serve = slug)
G. Verifier gates
H. MOVE prompts cleanup → done/

MATRICE VERIFICATA (46 file — path relativi a plan-audit/)

| Path attuale | Azione | Path finale | Rischio |
|---|---|---|---|
| README.md | MODIFY | README.md | low |
| active/sot_llm_multi_model_fallback.md | MOVE+RENAME | active/sot_llm_multi_model_fallback.md | med |
| active/LLM_Limits_Periodicity_Docs_ECC_Plan.md | MOVE+RENAME | archive/plans/plan_llm_limits_periodicity_docs_ecc.md | low |
| active/plan_release_final_gate.md | RENAME | active/plan_release_final_gate.md | low |
| active/plan_impl_phase_0_6.md | RENAME | active/plan_impl_phase_0_6.md | low |
| active/plan_impl_phase_0_6_execution.md | RENAME | active/plan_impl_phase_0_6_execution.md | low |
| active/plan_docs_audit_playbook.md | RENAME | active/plan_docs_audit_playbook.md | low |
| active/plan_docs_audit_ticket_status.md | RENAME | active/plan_docs_audit_ticket_status.md | low |
| prompts/active/audit_prompt_final_release_gate.md | KEEP + fix link interni | stesso | low |
| prompts/active/audit_prompt_llm_limits_docs_ecc.md | MOVE | prompts/done/audit_prompt_llm_limits_docs_ecc.md | low |
| prompts/active/audit_prompt_llm_limits_phase_close.md | MOVE | prompts/done/audit_prompt_llm_limits_phase_close.md | low |
| prompts/active/audit_prompt_llm_multi_model_fallback.md | MOVE+RENAME | prompts/done/audit_prompt_llm_multi_model_fallback_research.md | low |
| prompts/active/audit_prompt_plan_audit_cleanup.md | MOVE (fine) | prompts/done/audit_prompt_plan_audit_cleanup.md | low |
| prompts/active/audit_prompt_plan_audit_cleanup_exec.md | MOVE (fine) | prompts/done/audit_prompt_plan_audit_cleanup_exec.md | low |
| prompts/done/* (9 esistenti) | KEEP + fix link verso active/scratch rinominati | stesso | low |
| remediation/* (11) | KEEP + fix link | stesso | low |
| archive/ecc/handoff_ecc_architecture_audit.md | RENAME | archive/ecc/handoff_ecc_architecture_audit.md | low |
| archive/ecc/handoff_ecc_expansion.md | RENAME | archive/ecc/handoff_ecc_expansion.md | low |
| archive/llm-stubs/*.SUPERSEDED.md (2) | KEEP + fix link SoT | stesso | low |
| archive/plans/plan_ecc_early_root.md | RENAME | archive/plans/plan_ecc_early_root.md | low |
| archive/plans/plan_backend_ecc.md | KEEP | stesso | low |
| archive/plans/plan_frontend_ecc.md | KEEP | stesso | low |
| archive/scratch/scratch_backend_audit.md | MOVE+RENAME | archive/scratch/scratch_backend_audit.md | low |
| archive/scratch/scratch_backend_rules.md | MOVE+RENAME | archive/scratch/scratch_backend_rules.md | low |
| archive/scratch/scratch_frontend_audit.md | MOVE+RENAME | archive/scratch/scratch_frontend_audit.md | low |
| archive/scratch/scratch_frontend_rules.md | MOVE+RENAME | archive/scratch/scratch_frontend_rules.md | low |
| archive/scratch/scratch_infra_audit.md | MOVE+RENAME | archive/scratch/scratch_infra_audit.md | low |
| archive/scratch/scratch_infra_rules.md | MOVE+RENAME | archive/scratch/scratch_infra_rules.md | low |

MAPPA REPLACE (basename → nuovo path canonico da usare nei link)

sot_llm_multi_model_fallback.md
  → plan-audit/active/sot_llm_multi_model_fallback.md
LLM_Limits_Periodicity_Docs_ECC_Plan.md
  → plan-audit/archive/plans/plan_llm_limits_periodicity_docs_ecc.md
plan_release_final_gate.md
  → plan-audit/active/plan_release_final_gate.md
plan_impl_phase_0_6_execution.md
  → plan-audit/active/plan_impl_phase_0_6_execution.md
plan_impl_phase_0_6.md
  → plan-audit/active/plan_impl_phase_0_6.md
plan_docs_audit_ticket_status.md
  → plan-audit/active/plan_docs_audit_ticket_status.md
plan_docs_audit_playbook.md
  → plan-audit/active/plan_docs_audit_playbook.md
handoff_ecc_architecture_audit.md
  → plan-audit/archive/ecc/handoff_ecc_architecture_audit.md
handoff_ecc_expansion.md
  → plan-audit/archive/ecc/handoff_ecc_expansion.md
archive/scratch/scratch_backend_audit.md → plan-audit/archive/scratch/scratch_backend_audit.md
  (stesso schema per backend_rules, frontend_*, infra_*)
plan.md (solo se riferito come archive/plans/plan_ecc_early_root.md)
  → plan-audit/archive/plans/plan_ecc_early_root.md

ALLOWLIST FIX LINK (obbligatoria)
plan-audit/**/*.md
.agents/AGENTS.md
.agents/skills/**/SKILL.md
docs/01_getting_started.md
docs/02_architecture_and_backend.md
docs/04_ecc_framework.md
radar/docs/runbook.md
radar/.ecc/CLAUDE.md
radar/.ecc/rules/backend.md
radar/.ecc/agents/pipeline-engineer.md
radar/.ecc/skills/radar-quota-ledger.md
radar/.ecc/skills/llm-json-extraction.md

Dopo rename skill .agents → RI-SYNC mirror .ecc (stesso contenuto path SoT).

FIX LINK ROTTI SPECIFICI
.agents/AGENTS.md:
  ../plan_impl_phase_0_6.md → ../plan-audit/active/plan_impl_phase_0_6.md
  ../plan_impl_phase_0_6_execution.md → ../plan-audit/active/plan_impl_phase_0_6_execution.md
docs/02_architecture_and_backend.md:
  ../plan_impl_phase_0_6.md → ../plan-audit/active/plan_impl_phase_0_6.md
docs/04_ecc_framework.md:
  ../plan_impl_phase_0_6.md → ../plan-audit/active/plan_impl_phase_0_6.md
  ../plan_impl_phase_0_6_execution.md → ../plan-audit/active/plan_impl_phase_0_6_execution.md
  ../handoff_ecc_expansion.md → ../plan-audit/archive/ecc/handoff_ecc_expansion.md
  (se citato Architecture handoff: → handoff_ecc_architecture_audit.md)
radar/.ecc/CLAUDE.md: aggiornare menzioni Implementation_Plan* ai path plan-audit/active/

README.md FINALE (requisiti)
- Tabella SoT active/: sot_llm_*, plan_release_final_gate, plan_impl_*, plan_docs_audit_*
- Prompt active/: solo audit_prompt_final_release_gate.md (cleanup già in done)
- Layout: aggiungere archive/scratch/
- Nota: Limits plan archiviato in archive/plans/plan_llm_limits_periodicity_docs_ecc.md
- Nota: SoT LLM = active/sot_llm_multi_model_fallback.md
- Link remediation LLM + prompt done elencati in breve o “vedi cartella”

VERIFIER GATES (PASS tutti)
1) Ogni link in README risolvibile (file esiste)
2) Grep FAIL se ancora presenti come path vivi (non solo menzioni storiche in frasi):
   - plan-audit/active/sot_llm_multi_model_fallback.md
   - plan-audit/active/LLM_Limits_Periodicity_Docs_ECC_Plan.md
   - plan-audit/scratch/   (dir vuota o assente OK)
3) Grep skill+ecc: devono citare sot_llm_multi_model_fallback.md
4) Nessun file in active/ fuori tassonomia senza motivazione
5) prompts/active/ contiene SOLO final_release_gate (dopo move cleanup)
6) Conteggio: documentare N prima/dopo per cartella
7) Non committare .env; non edit fuori allowlist

VIETATO
- Delete remediation/T-P*
- Delete stub SUPERSEDED
- Riscrivere motore LLM / codice
- Lasciare AGENTS/docs con link a root Implementation_Plan assente

DONE WHEN
- Matrice applicata
- Link allowlist aggiornati + mirror skill sync
- README allineato
- Verifier PASS
- Prompt cleanup (+ exec) in prompts/done/

REPORT
## plan-audit cleanup exec
- Verdetto: PASS|FAIL
- Rename SoT LLM: done (old→new)
- Tabella old→new (sintesi)
- Link esterni fixati: AGENTS/docs/ecc (elenco)
- prompts/active rimanenti: …
- Residuali: …
```

---

## Note

| Aspetto | Decisione corretta |
|---------|-------------------|
| Rename SoT LLM | Sì (default); KEEP solo se override utente |
| Scratch | `archive/scratch/scratch_*` |
| remediation/done link | **Aggiornare** (piano grezzo errato) |
| verify_cleanup.py | No file permanente; gate inline |
| AGENTS/docs | Fix path rotti verso `plan-audit/active/…` |
