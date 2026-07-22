# Agent prompt — BORDERLINE effort split CLOSEOUT (stessa chat)

> **Stato: ACTIVE** — ripresa / closeout dopo walkthrough (2026-07-22).  
> **Uso:** incolla nella **stessa** chat Agent che ha già implementato R1–R12 (contesto vivo).  
> **SoT:** [`../../active/plan_impl_borderline_effort_split.md`](../../active/plan_impl_borderline_effort_split.md)  
> **PO:** ancora **nessun git commit** finché non richiesto.

---

## Verdetto audit walkthrough (rigoroso)

### Cosa è VERDE (non rifare)
- R1 effort per-call in `deepseek.build_payload` / `classify_json` + `client` passa `effort=ref.reasoning_effort` — **OK**
- `_borderline_chain` + `_chain_for(BORDERLINE)` — **OK**
- Live ops: `LLM_BORDERLINE_REASONING_EFFORT=none`; log `route … effort=none` + `OK … lane=BORDERLINE escalated=False` (10 hit)
- Execution lane DB resta `complex`; ledger `classify:complex`
- Completion token bassi su parte delle call coerenti con `none`
- Docs principali: runbook knob, SoT §4.4 tabella, AGENTS/CLAUDE, docs/02, quota-ledger mirror, `.agents` llm-json-extraction
- Nessun commit (R9)

### Cosa è INCOMPLETO / INCONGRUENTE (obbligatorio chiudere)

| ID | Gap | Severità |
|----|-----|----------|
| C1 | **Nessun unit test escalate** BL `none` → `escalate_ref` effort `high` (identity diversa); walkthrough lo dichiara ma non c’è | Alta |
| C2 | **Nessun test default unset** → `LLM_BORDERLINE_REASONING_EFFORT == "high"` | Media |
| C3 | Pytest GATE fatto su **host `.venv`**, non `docker compose exec radar-worker pytest` (R8) | Media |
| C4 | Mirror **stale**: `radar/.ecc/skills/llm-json-extraction.md` ancora «tipico effort=high» mentre `.agents/.../SKILL.md` è aggiornato | Alta (ECC drift) |
| C5 | `radar/.ecc/rules/backend.md` ancora «BORDERLINE+COMPLEX tipico high» senza knob | Media |
| C6 | SoT §8.2 riga ancora `_chain_for(BORDERLINE) → … effort high` (contraddice §4.4 aggiornato) | Media |
| C7 | `runbook.md` riga Local-Hybrid/gate ancora aspetta `BORDERLINE … effort=high` | Bassa |
| C8 | `radar_overview_and_upgrades.md` ancora «BORDERLINE … effort high» | Bassa |
| C9 | Root `README.md` non menziona `LLM_BORDERLINE_REASONING_EFFORT` | Bassa |
| C10 | `.env.example` ha `LLM_BORDERLINE_REASONING_EFFORT=none` **attivo** mentre codice/docs dicono default safe=`high` — chi copia example abilita `none` senza dual-run formale | Media (ops) |
| C11 | Dual-run **KPI XX** non misurati nel walkthrough (solo smoke log); escalate live **mai osservato** (ok se VE=0, ma test unitario obbligatorio) | Alta per GATE formale |
| C12 | Checklist SoT piano §7 ancora unchecked; `STATUS.md` ancora ACTIVE senza nota “impl done / closeout pending” | Bassa |

---

## PROMPT (incolla nella stessa chat Agent)

```text
# Task — CLOSEOUT BORDERLINE effort split (NON rifare il core)

## Contesto
Hai già implementato lo split (R1 effort per-call, `_borderline_chain`, docs parziali, requeue live con `none`). Un audit esterno ha trovato gap di completezza sotto. **Non** riscrivere il design. Chiudi C1–C12. **Nessun git commit**.

## Autorità
1. `plan-audit/active/plan_impl_borderline_effort_split.md` §5–§9
2. Questo closeout
3. Skills requeue/docker/quota-ledger
4. Sidebar freeze; schema immutabile

## Lavoro obbligatorio

### A — Test mancanti (C1, C2, C3)
1. `test_classification.py`:
   - Escalate: con `LLM_BORDERLINE_REASONING_EFFORT=none`, forza ValidationError ripetuti sul path BL finché `outcome=="escalate"` / oppure assert che `escalate_ref.reasoning_effort == LLM_COMPLEX.reasoning_effort == "high"` e `escalate_ref.identity != borderline_ref.identity`; idealmente mock `_run_model_attempts` / provider per vedere una call con effort high dopo fail.
   - Default: monkeypatch env unset o testa il valore esportato da config con default high (senza rompere altri test).
2. Riesegui pytest **in container**:
   ```bash
   cd radar
   docker compose exec -T radar-worker pytest \
     app/tests/test_classification.py \
     app/tests/test_complexity.py \
     app/tests/test_openai_compat_dialect.py -q
   ```

### B — Drift ECC / docs (C4–C9)
Aggiorna **in place** (non spostare piani complete):
- `radar/.ecc/skills/llm-json-extraction.md` ≡ `.agents/skills/llm-json-extraction/SKILL.md` (riga BORDERLINE + knob)
- `radar/.ecc/rules/backend.md` — tabella env: aggiungere `LLM_BORDERLINE_REASONING_EFFORT`; non dire più che BL è sempre high
- `plan-audit/complete/sot_llm_multi_model_fallback.md` §8.2: sostituire «BORDERLINE → effort high» con effort da knob + escalate
- `radar/docs/runbook.md`: allineare riga gate Local-Hybrid (`BORDERLINE … effort=` da env, tipico ops `none`)
- `radar_overview_and_upgrades.md`: BORDERLINE effort da `LLM_BORDERLINE_REASONING_EFFORT`
- Root `README.md`: una riga sotto Routing LLM sul knob (default safe high / ops none)

### C — `.env.example` (C10)
Best practice: nel blocco esempio mettere
```bash
# Default safe (AS-IS). Per target ops post-GATE: none
LLM_BORDERLINE_REASONING_EFFORT=high
```
oppure lasciare commentato il valore e documentare che unset=`high`. **Non** lasciare `=none` come default silenzioso per chi clona il repo senza aver letto il dual-run. L’ops `.env` live può restare `none` (non commitare `.env`).

### D — KPI dual-run minimi (C11) — misura, non dual-write
Senza `--purge-all` di massa salvo necessità:
1. Campione recente: recompute `score_complexity` su articles ultimi (title+body_excerpt); XX rate su heur BORDERLINE con ops `none`.
2. Confronta vs baseline analisi (~1% XX su BL high) — tolleranza piano §5 (+3pp go / +5pp no-go).
3. Conta log `escalated=True` / `Escalate early` su BL (può essere 0).
4. Scrivi esito nel report (go/no-go). Se no-go XX → rollback ops a `high` e documenta.

### E — Plan-audit hygiene (C12)
- Aggiorna checklist §7 in `plan_impl_borderline_effort_split.md` (check ciò che è fatto; lascia unchecked solo ciò che PO deve chiudere).
- `STATUS.md`: nota «impl+docs closeout in corso / GATE KPI …» — **non** spostare in `complete/` finché PO non conferma.
- Non commitare.

## Fuori scope
- Nuovo model ID / move BL→Gemini / colonna complexity_lane / UI / sidebar
- Rifattorizzare `_compat_client` oltre l’effort per-call già fatto
- git commit / push

## Deliverable
1. Diff test + docs ECC allineati
2. Output pytest **container** verde
3. Tabella KPI XX / escalate / env finale ops
4. Checklist piano aggiornata
5. Conferma: nessun commit

Inizia da C4 mirror llm-json-extraction + C1 test escalate.
```
