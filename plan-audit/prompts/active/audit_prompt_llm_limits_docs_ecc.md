# Prompt orchestratore — LLM limits + Docs/ECC align

> **Piano SoT:** [`../../active/LLM_Limits_Periodicity_Docs_ECC_Plan.md`](../../active/LLM_Limits_Periodicity_Docs_ECC_Plan.md)  
> **SoT design LLM:** [`../../active/LLM_Multi_Model_Fallback_Phase_AB.md`](../../active/LLM_Multi_Model_Fallback_Phase_AB.md)  
> **Uso:** incolla il blocco sotto in una nuova chat Agent (autonomia totale).  
> **Default profilo ops da documentare:** entrambi A e B in `.env.example`; profilo **attivo** nell’example = B (DeepSeek-only) se coerente con live; A in blocco commentato.

---

## Blocco da incollare (copia da qui)

```text
GOAL
Allineare documentazione, ECC e skill Cursor alla semantica per-lane già implementata nel codice Radar
(limiti LLM_SIMPLE_* / LLM_COMPLEX_*, soft-trim = LLM_SIMPLE.rpd, free RPM/RPD vs paid BUDGET_USD_DAY,
residual SIMPLE↔COMPLEX, periodicità WORKER_POLL_INTERVAL_SECONDS). Non riscrivere il motore di
routing/quota salvo bug bloccante scoperto in verifica. Operare in totale autonomia; correggere
in corso d’opera se supervisore/verificatore trovano contraddizioni.

PIANO SoT (leggere per primo)
plan-audit/active/LLM_Limits_Periodicity_Docs_ECC_Plan.md

SoT DESIGN (aggiornare §5–§6)
plan-audit/active/LLM_Multi_Model_Fallback_Phase_AB.md

SKILL OBBLIGATORIE (Read + seguire)
- .agents/skills/radar-quota-ledger/SKILL.md
- .agents/skills/llm-json-extraction/SKILL.md
- radar/.ecc/rules/backend.md (Regola 9 / 9b)
- .agents/AGENTS.md (sidebar freeze, asyncpg, no openai package)

ECC AGENT PROFILE
- radar/.ecc/agents/pipeline-engineer.md  → ownership pipeline/docs correlati

RUOLI (obbligatori — Task tool o turni sequenziali espliciti)

1) SUPERVISORE (orchestratore)
   - Legge il piano SoT + skill + allowlist.
   - Conferma profilo docs: documentare A (hybrid) + B (DeepSeek-only); example attivo = B
     salvo evidenza che .env live è hybrid (NON commitare .env; non stampare secret).
   - Spezza lavoro in wave; assegna ESECUTORE; dopo ogni wave chiama VERIFICATORE.
   - Se VERIFICATORE fallisce: correggi (re-dispatch ESECUTORE) finché gate PASS o
     documenta blocker in remediation.
   - NON toccare sidebar FE, schema Pydantic field names, SYSTEM_PROMPT CoT, package openai,
     vault content, commit .env, archive/llm-stubs.

2) ESECUTORE (pipeline-engineer mindset)
   - Applica edit SOLO sull’allowlist del piano §8.2.
   - Ordine obbligatorio:
     (1) Phase_AB §5–§6
     (2) ECC: rules/backend.md 9/9b, CLAUDE.md, pipeline-engineer.md
     (3) Skills: .agents/skills/* poi mirror identico radar/.ecc/skills/*
     (4) .agents/AGENTS.md
     (5) docs/01_getting_started.md, docs/02_architecture_and_backend.md,
         docs/04_ecc_framework.md se stale, radar/docs/runbook.md, radar/.env.example
     (6) remediation + plan-audit/README.md
   - Principi unici da propagare (piano §8.1): per-lane limits; legacy = alias;
     soft-trim SIMPLE.rpd; free vs paid; residual; WORKER_POLL_INTERVAL_SECONDS; v2.2.
   - .env.example: blocco attivo Profilo B + blocco commentato Profilo A (o viceversa se
     supervisore decide hybrid); commenti free=RPM/RPD>0 vs paid=0+BUDGET.
   - Se scopri bug codice bloccante (docs direbbero una cosa falsa sul runtime): fix minimo
     in allowlist codice sotto, altrimenti solo docs + nota remediation.

3) VERIFICATORE (dopo ogni wave e a chiusura)
   - Grep anti-regressione (FAIL se frase è unica verità senza lane/legacy):
       "soft-trim worker: solo Gemini RPD"
       "Limiti per provider: Gemini LLM_*"
   - Coerenza: AGENTS.md + radar-quota-ledger + Phase_AB §6 + runbook dicono la stessa cosa
     su soft-trim e limiti per-lane.
   - Mirror: .agents/skills/radar-quota-ledger/SKILL.md ≡ radar/.ecc/skills/radar-quota-ledger.md
     (stesso per llm-json-extraction) — contenuto allineato.
   - Smoke test se toccato codice Python:
       cd radar; $env:PYTHONPATH="backend";
       python -m pytest app/tests/test_complexity.py app/tests/test_classification.py
       app/tests/test_quota_concurrency.py -q
   - Output: PASS / FAIL + lista path + eventuali residuali.

ALLOWLIST EDIT (solo questi path, salvo fix bug minimo verificato)
plan-audit/active/LLM_Multi_Model_Fallback_Phase_AB.md
plan-audit/active/LLM_Limits_Periodicity_Docs_ECC_Plan.md  (aggiorna stato todo se serve)
plan-audit/remediation/audit_remediation_llm_multi_model_fallback.md
plan-audit/README.md
plan-audit/prompts/active/audit_prompt_llm_multi_model_fallback.md
docs/01_getting_started.md
docs/02_architecture_and_backend.md
docs/04_ecc_framework.md
radar/docs/runbook.md
radar/.env.example
radar/.ecc/CLAUDE.md
radar/.ecc/rules/backend.md
radar/.ecc/agents/pipeline-engineer.md
radar/.ecc/skills/radar-quota-ledger.md
radar/.ecc/skills/llm-json-extraction.md
.agents/skills/radar-quota-ledger/SKILL.md
.agents/skills/llm-json-extraction/SKILL.md
.agents/AGENTS.md

ALLOWLIST CODICE (solo se VERIFICATORE/SUPERVISORE confermano bug runtime)
radar/backend/app/core/config.py
radar/backend/app/core/llm_lanes.py
radar/backend/app/classification/quota.py
radar/backend/app/classification/client.py
radar/backend/app/worker.py
radar/backend/app/tests/test_*.py  (solo test correlati)

FILE DI RIFERIMENTO READ-ONLY (non editare salvo necessità)
radar/backend/app/classification/complexity.py
radar/backend/app/classification/deepseek.py
radar/backend/app/classification/cooldown.py
plan-audit/archive/llm-stubs/*   (VIETATO edit)

DONE WHEN
- Tutti i todo del piano §8 eseguiti
- Gate grep PASS
- Mirror skills sync
- Remediation aggiornata con “docs/ECC allineati per-lane”
- plan-audit/README.md elenca LLM_Limits_Periodicity_Docs_ECC_Plan.md
- Report finale breve: file toccati, profilo example, residuali (shadow 3g / VERIFY_IN_STUDIO se ancora aperti)

CORREZIONE IN CORSO D’OPERA
Se un doc contraddice il codice: il codice + skill radar-quota-ledger vincono.
Se Phase_AB e skill divergono: aggiorna Phase_AB a per-lane (non degradare lo skill).
Se ESECUTORE esce dall’allowlist: SUPERVISORE stop + revert scope.
Non chiedere conferma all’utente per edit docs/ECC nella allowlist; chiedi solo se serve
modificare .env live (secret) o cambiare profilo attivo A↔B oltre al default sopra.
```

---

## Note operative

| Ruolo | Tool Cursor tipico | Skill / profilo |
|-------|--------------------|-----------------|
| Supervisore | Agent principale | Piano + AGENTS.md |
| Esecutore | Task `generalPurpose` o turno dedicato | `pipeline-engineer` + `radar-quota-ledger` + `llm-json-extraction` |
| Verificatore | Task `explore` o turno Grep/pytest | Gate del prompt |

Non rieseguire Fase C multi-model da zero: il motore esiste; questo prompt è **docs/ECC align + ops clarity**.
