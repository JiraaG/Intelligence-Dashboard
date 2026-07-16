# Prompt orchestratore — pulizia & allineamento `plan-audit/`

> **Uso:** nuova chat Agent — incolla il blocco sotto.  
> **Obiettivo:** ridurre il rumore tra SoT vivi, prompt, remediation e archivio; rinominare in modo coerente; aggiornare `README.md` come unico indice.  
> **Inventario di partenza (2026-07-16):** ~45 file `.md` sotto `plan-audit/`.  
> **Non** è un refactor del codice Radar: solo governance documentale in `plan-audit/` (+ link da `docs/`/`README` se stale).

---

## Blocco da incollare

```text
GOAL
Fare pulizia strutturata di plan-audit/: classificare ogni .md (KEEP / MERGE / MOVE /
RENAME / ARCHIVE / DELETE), allineare duplicati e contraddizioni, applicare una
tassonomia di nomi coerente e leggibile, aggiornare plan-audit/README.md come indice
SoT unico, archiviare prompt eseguiti. Produrre matrice decisionale (con colonna
rename) + diff file toccati. Non cancellare storia utile di remediation senza evidenza
di supersede. Non toccare codice runtime, .env, sidebar FE, vault.

CONTESTO
- plan-audit/ NON è produzione: contiene SoT operativi, prompt orchestratore, report DONE.
- Layout atteso (già dichiarato in README):
    active/           → SoT / piani ANCORA vivi o di riferimento corrente
    prompts/active/   → prompt da rieseguire / ancora utili
    prompts/done/     → prompt già eseguiti (archivio operativo)
    remediation/      → report ticket DONE (audit trail — default KEEP)
    archive/plans|ecc|llm-stubs/ → storici superseduti
    scratch/          → grezzi; candidati ad archive o delete se assorbiti da ECC
- Fase LLM Limits/Docs-ECC: PASS (commit 5b1f6eb + close). Motore per-lane live.
- SoT LLM design: active/sot_llm_multi_model_fallback.md
- Piano Limits eseguito: active/LLM_Limits_Periodicity_Docs_ECC_Plan.md (DONE)
- Remediation LLM: remediation/audit_remediation_llm_multi_model_fallback.md

════════════════════════════════════════════════════════════
TASSONOMIA NOMI (obbligatoria — coerente, chiara, dettagliata)
════════════════════════════════════════════════════════════

Pattern file (kebab o snake accettati; preferire **snake** già dominante; niente spazi):

  <kind>_<domain>_<topic>[_<qualifier>].md

kind (prefisso obbligatorio per ruolo):
  sot_          → Source of Truth operativo ancora vivo (solo in active/)
  plan_         → Piano di lavoro (in corso in active/; DONE → archive/plans/)
  prompt_       → Prompt orchestratore (in prompts/active|done/; vedi sotto)
  remediation_  → Report chiusura ticket/fase (in remediation/)
  handoff_      → Handoff ECC / sessioni storiche (archive/ecc/)
  scratch_      → Grezzo non-SoT (scratch/ o archive/scratch/)
  stub_         → Stub superseduto (archive/…/*.SUPERSEDED.md — tenere suffisso)

domain (secondo segmento, vocabolario chiuso quando possibile):
  llm | docs | ecc | release | impl | map | audit | backend | frontend | infra

topic: slug corto del contenuto (es. multi_model_fallback, limits_periodicity,
  final_release_gate, phase_0_6, spider_dezoom).

qualifier (opzionale):
  _v2_2 | _phase_ab | _close | _execution | _playbook | _status | _batch
  Per stub: .SUPERSEDED.md in coda al nome (già in uso — mantenere).

Prompt — schema dedicato (già quasi uniforme; normalizzare):
  audit_prompt_<domain>_<topic>[_<qualifier>].md
  Esempi OK:
    audit_prompt_final_release_gate.md
    audit_prompt_llm_limits_docs_ecc.md
    audit_prompt_llm_limits_phase_close.md
    audit_prompt_plan_audit_cleanup.md   ← questo file

Remediation — schema dedicato:
  audit_remediation_<ticket_or_topic>.md
  Ticket storici: mantenere ID (T-P0-02, T-P2_batch) per tracciabilità.
  Tematici: audit_remediation_llm_multi_model_fallback.md (OK — non accorciare a “llm”).

Regole RENAME:
  1. Un rename DEVE migliorare leggibilità O allineare al pattern kind_domain_topic.
  2. Vietato rename “cosmetico” che spezza dozzine di link senza guadagno semantico.
  3. Se sposti cartella (MOVE) e rinomini nello stesso passo: un solo `git mv` al path finale.
  4. Dopo ogni RENAME/MOVE: grep + aggiorna link in plan-audit/, docs/, .agents/, radar/.ecc/
     che citano il path vecchio (allowlist).
  5. Nella matrice: colonna “Nome proposto” sempre compilata (anche se = attuale → “—”).
  6. Header H1 del file allineato al nuovo nome (titolo umano, non necessariamente slug).
  7. README: solo nomi NUOVI post-rename.

RENAME PROPOSTI DI DEFAULT (adattare con evidenza; non applicare ciechi)

active/
  sot_llm_multi_model_fallback.md
    → KEEP name OR sot_llm_multi_model_fallback.md
    Motivo alt: “Phase_AB” è storico; “sot_llm_*” segnala SoT. Rischio med (molti link).
    Preferenza: KEEP name se link sparsi; altrimenti rename + fix link massivo.

  LLM_Limits_Periodicity_Docs_ECC_Plan.md  (DONE)
    → MOVE+RENAME archive/plans/plan_llm_limits_periodicity_docs_ecc.md
    Motivo: non è più SoT vivo; era piano operativo eseguito.

  plan_release_final_gate.md
    → plan_release_final_gate.md   (se resta in active/)
    Motivo: prefisso plan_ + domain release chiaro.

  plan_impl_phase_0_6.md
    → plan_impl_phase_0_6.md
  plan_impl_phase_0_6_execution.md
    → plan_impl_phase_0_6_execution.md
    Motivo: coppia ovvia; “Implementation_” generico.

  plan_docs_audit_playbook.md
    → plan_docs_audit_playbook.md
  plan_docs_audit_ticket_status.md
    → plan_docs_audit_ticket_status.md
    Motivo: “problemi” ambiguo; playbook vs status separati.

prompts/active/ → prompts/done/ (MOVE; rename solo se serve)
  audit_prompt_llm_limits_docs_ecc.md      → (done/) KEEP name
  audit_prompt_llm_limits_phase_close.md   → (done/) KEEP name
  audit_prompt_llm_multi_model_fallback.md → (done/) audit_prompt_llm_multi_model_fallback_research.md
    Motivo: chiarisce che è prompt di ricerca storica, non SoT.
  audit_prompt_final_release_gate.md       → KEEP in active/ (finché gate aperto)
  audit_prompt_plan_audit_cleanup.md       → dopo esecuzione PASS → prompts/done/ KEEP name

remediation/
  audit_remediation_T-P*.md                → KEEP (ID ticket = tracciabilità)
  audit_remediation_llm_multi_model_fallback.md → KEEP
  audit_remediation_final_release_handoff.md → KEEP o audit_remediation_release_final_handoff.md
  audit_remediation_spider_dezoom.md       → KEEP (topic map chiaro)

archive/
  llm-stubs/*.SUPERSEDED.md                → KEEP (già correttamente marcati)
  plans/plan.md                            → plan_ecc_early_root.md (se ancora generico)
  plans/plan_backend_ecc.md / plan_frontend_ecc.md → KEEP se già chiari
  ecc/*Handoff.md                          → handoff_ecc_architecture_audit.md /
                                             handoff_ecc_expansion.md (snake)

scratch/
  scratch_backend_audit.md   → scratch_backend_audit.md  (poi MOVE archive/scratch/)
  scratch_backend_rules.md   → scratch_backend_rules.md
  frontend_*.md / infra_*.md → stesso schema scratch_<domain>_<topic>.md

Anti-pattern da correggere se trovati:
  - Nomi senza kind (solo “plan.md”, “notes.md”)
  - CamelCase misto a snake nello stesso folder senza motivo
  - Doppioni “audit_audit_*” o “plan_plan_*”
  - “Final” / “Phase_AB” / “v2” nel filename senza dominio (llm|release|impl)
  - Prompt in active/ con suffisso _done / _close già eseguiti (devono stare in done/)

INVENTARIO ATTUALE (verificare e aggiornare — non inventare path)

active/ (7)
  sot_llm_multi_model_fallback.md
  LLM_Limits_Periodicity_Docs_ECC_Plan.md
  plan_release_final_gate.md
  plan_impl_phase_0_6.md
  plan_impl_phase_0_6_execution.md
  plan_docs_audit_playbook.md
  plan_docs_audit_ticket_status.md

prompts/active/ (5 incl. cleanup)
  audit_prompt_final_release_gate.md
  audit_prompt_llm_limits_docs_ecc.md
  audit_prompt_llm_limits_phase_close.md
  audit_prompt_llm_multi_model_fallback.md
  audit_prompt_plan_audit_cleanup.md

prompts/done/ (9) — verificare naming/duplicati
remediation/ (11) — default KEEP
archive/ (7) — llm-stubs SUPERSEDED + plans + ecc
scratch/ (6) — candidati archive/scratch/ + prefisso scratch_

SKILL / REGOLE
- .agents/AGENTS.md (sidebar freeze, no secret commit)
- Non editare radar/backend/** salvo path docs in plan-audit
- Codice + skill radar-quota-ledger vincono su contraddizioni docs LLM

RUOLI (obbligatori)

1) SUPERVISORE
   - Inventario ricorsivo plan-audit/**/*.md (path + 1 riga ruolo + stato proposto).
   - Approva policy: preferire MOVE/RENAME in archive/done a DELETE irrevocabile.
   - DELETE solo se: (a) byte-duplicate, (b) stub SUPERSEDED già coperto da SoT,
     (c) scratch assorbito al 100% da ECC rules (citare path SoT).
   - Dispatch INVENTORY → DECISION → EXECUTOR → VERIFIER.
   - Chiedere conferma utente SOLO per: delete di >3 file, merge che scarta contenuto
     non banale, spostare Implementation_* fuori da active/, oppure RENAME del SoT LLM
     (Phase_AB → sot_llm_*) perché spezza molti link.

2) INVENTORY-AUDITOR (Task explore — read-only)
   Per ogni file produrre riga:
     path | categoria | last-purpose | overlap-with | nome_attuale_ok? | nome_proposto | proposta_azione
   Categorie: SOT_ACTIVE | PLAN_DONE | PROMPT_ACTIVE | PROMPT_DONE |
              REMEDIATION | ARCHIVE | SCRATCH | ORPHAN | DUPLICATE
   Flag nome_attuale_ok? = YES se rispetta tassonomia; NO + proposta slug.
   Overlap tipici da verificare:
     - LLM_Limits_* vs Phase_AB §5–§8 vs remediation LLM
     - audit_prompt_llm_* vs stato esecuzione
     - Implementation_Plan vs Execution vs Final_Release_Gate
     - audit_problemi_* vs remediation/T-P*
     - scratch/*_rules.md vs radar/.ecc/rules/{backend,frontend,docker}.md
     - README SoT table vs filesystem reale (README stale = FAIL)

3) DECISION-ARCHITECT (Task generalPurpose — propone, non esegue ancora)
   Output obbligatorio: matrice Markdown

   | Path attuale | Azione | Path finale (cartella+nome) | Motivo | Rischio | Link da aggiornare (stima) |
   |--------------|--------|-----------------------------|--------|---------|----------------------------|
   | … | KEEP\|MERGE\|MOVE\|RENAME\|MOVE+RENAME\|ARCHIVE\|DELETE | … | … | low\|med\|high | N / paths |

   Policy di default (adattare con evidenza) — includere RENAME dalla sezione sopra:
   A. KEEP (+ eventuale RENAME basso rischio) in active/:
      - SoT LLM (Phase_AB): KEEP name di default; RENAME solo con OK utente
      - Final_Release → plan_release_final_gate.md se rename low-link
      - Implementation_* → plan_impl_phase_0_6[_execution].md
      - audit_problemi_* → plan_docs_audit_{playbook|ticket_status}.md
   B. MOVE+RENAME → archive/plans/:
      - Limits plan DONE → plan_llm_limits_periodicity_docs_ecc.md
   C. MOVE → prompts/done/ (+ rename research se utile):
      - llm_limits_docs_ecc, llm_limits_phase_close
      - llm_multi_model_fallback → …_research.md
   D. KEEP prompts/active/: final_release_gate (+ cleanup finché non PASS)
   E. KEEP remediation/*; rename solo se viola tassonomia in modo grave
   F. KEEP archive/llm-stubs/* SUPERSEDED
   G. scratch/: RENAME scratch_* + MOVE archive/scratch/
   H. README.md: solo path finali post-rename

   MERGE ammessi:
   - Limits ridondante con Phase_AB + remediation: stub corto OPPURE archive + link
   - NON fondere Phase_AB nel Limits plan

4) EXECUTOR (dopo OK supervisore sulla matrice)
   - Applicare SOLO azioni low/med; high-risk stop + chiedi utente.
   - Preferire `git mv` path_attuale path_finale (MOVE+RENAME atomico).
   - Dopo ogni rename: aggiornare H1 se fuorviante; grep path vecchio; fix link allowlist.
   - Aggiornare plan-audit/README.md (nomi finali).
   - Opzionale: nota in remediation LLM sul nuovo path del Limits plan.

5) VERIFIER
   Gate PASS se:
   - Ogni path in README esiste col NOME FINALE
   - Nessun prompt eseguito PASS resta in prompts/active/ senza giustificazione
   - SoT LLM unico chiaro (Phase_AB o sot_llm_* se rinominato)
   - File in active/ rispettano tassonomia O hanno motivazione KEEP-name in matrice
   - Grep: zero link rotti verso path pre-rename (campione: titoli slug principali)
   - Contatore N file prima/dopo per cartella
   - Nessun secret/.env; nessun edit fuori allowlist

ALLOWLIST EDIT
plan-audit/**/*.md
plan-audit/**/ (move/rename/delete solo sotto plan-audit/)
docs/**/*.md          — SOLO link rotti / path rinominati
radar/docs/runbook.md — SOLO link rotti
radar/.ecc/CLAUDE.md / .agents/AGENTS.md — SOLO se citano path plan-audit rinominati

VIETATO
- Cancellare remediation/T-P* senza supersede
- Riscrivere motore LLM / codice backend
- Commit .env; edit vault; sidebar FE
- Rename del SoT LLM senza conferma utente
- Inventare nuovi SoT paralleli a Phase_AB
- Rename che rompe ID ticket remediation (T-P0-02 ecc.) senza bisogno reale

DONE WHEN
- Matrice completa (azione + path finale/nome per ogni .md)
- Azioni eseguite (o blocker documentati)
- README allineato ai nomi finali
- Verifier PASS
- Report: keep/move/rename/merge/delete counts + SoT active/ + prompt active/

REPORT FINALE (formato)
## plan-audit cleanup
- Verdetto: PASS | FAIL
- Prima → dopo: N file (per cartella)
- Rename effettuati: elenco old → new (tabella)
- SoT in active/ (nomi finali): …
- Prompt ancora in prompts/active/: …
- Merge / Delete: …
- Residuali / chiedi utente: …
- Next: Final Release | altro
```

---

## Note operative

| Ruolo | Tool | Note |
|-------|------|------|
| Supervisore | Agent principale | Approva delete/merge/rename SoT ad alto rischio |
| Inventory | Task `explore` | Include `nome_proposto` per ogni file |
| Decision | Task `generalPurpose` | Matrice con path finale = cartella + nome |
| Executor | Agent / Task | `git mv` atomico MOVE+RENAME |
| Verifier | Task `explore` | Link + tassonomia + README |

**Preferenza:** `git mv` verso path finale (cartella + nome) piuttosto che delete.  
**Rename SoT LLM (`Phase_AB` → `sot_llm_*`):** solo con conferma utente.  
**Non** rieseguire Fase LLM Limits: housekeeping documentale only.
