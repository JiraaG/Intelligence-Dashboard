# Prompt orchestratore — chiusura fase LLM Limits / Docs-ECC

> **Commit fase docs:** `5b1f6eb` — `docs(radar): align ECC/skills to per-lane LLM limits and ops profiles`  
> **Piano SoT:** [`../../active/LLM_Limits_Periodicity_Docs_ECC_Plan.md`](../../active/LLM_Limits_Periodicity_Docs_ECC_Plan.md)  
> **SoT design:** [`../../active/LLM_Multi_Model_Fallback_Phase_AB.md`](../../active/LLM_Multi_Model_Fallback_Phase_AB.md)  
> **Uso:** nuova chat Agent — incolla il blocco sotto. Autonomia totale; non chiedere conferma per read/grep/docker/pytest; chiedi solo prima di commit/push o edit `.env` live.

---

## Blocco da incollare

```text
GOAL
Chiudere formalmente la fase “LLM Limits + Docs/ECC per-lane” con verifica
approfondita end-to-end: coerenza docs↔codice↔ENV, mirror skill, gate anti-regressione,
suite pytest, stack Docker healthy, ciclo articoli Miniflux→classify (SIMPLE + COMPLEX/
BORDERLINE), ledger, outbox, log worker. Produrre report PASS/FAIL + residuali.
Non riscrivere il motore quota/routing salvo bug runtime bloccante verificato.
Non toccare sidebar FE, schema Pydantic field names, SYSTEM_PROMPT CoT, package openai,
vault content, commit .env, archive/llm-stubs.

CONTESTO (già fatto — non rieseguire allineamento docs da zero)
- Commit: 5b1f6eb docs(radar): align ECC/skills to per-lane LLM limits and ops profiles
- Piano DONE: plan-audit/active/LLM_Limits_Periodicity_Docs_ECC_Plan.md
- Profilo ops tipico: B DeepSeek-only (SIMPLE effort=none, COMPLEX effort=high, RPM/RPD=0)
- Motore già live: llm_lanes.py + quota.py + complexity v2.2 + residual cross-lane

SoT DA LEGGERE PRIMA
1) plan-audit/active/LLM_Limits_Periodicity_Docs_ECC_Plan.md
2) plan-audit/active/LLM_Multi_Model_Fallback_Phase_AB.md  (§5–§6 obbligatori)
3) .agents/skills/radar-quota-ledger/SKILL.md
4) .agents/skills/llm-json-extraction/SKILL.md
5) radar/.ecc/rules/backend.md (Regola 9 / 9b)
6) .agents/AGENTS.md (sidebar freeze, asyncpg, no openai)

ECC PROFILI / SKILL
- radar/.ecc/agents/pipeline-engineer.md
- .agents/skills/radar-docker-ops/SKILL.md
- .agents/skills/radar-quota-ledger/SKILL.md
- .agents/skills/llm-json-extraction/SKILL.md

RUOLI (obbligatori — Task tool in parallelo quando indipendenti; altrimenti turni sequenziali)

════════════════════════════════════════════════════════════
1) SUPERVISORE (Agent principale)
════════════════════════════════════════════════════════════
- Conferma Profilo A vs B da .env live SENZA stampare secret
  (solo chiavi non-secret: LLM_*_PROVIDER, *_RPM/RPD, ROUTING_*, WORKER_POLL_*).
- Spezza in wave; dispatch VERIFICATORE-DOCS, VERIFICATORE-CODICE, OPS-DOCKER,
  PIPELINE-E2E; integra report; se FAIL → remediation minima in allowlist o blocker.
- Output finale: scheda chiusura fase (PASS/FAIL, evidenze, residuali, next).

════════════════════════════════════════════════════════════
2) VERIFICATORE-DOCS (Task explore o generalPurpose — read-only)
════════════════════════════════════════════════════════════
Gate grep anti-regressione (FAIL se frase è verità operativa senza lane/legacy):
  - "soft-trim worker: solo Gemini RPD"
  - "Limiti per provider: Gemini LLM_*"
Escludere da FAIL: occorrenze solo come criterio di gate in plan/prompt.

Coerenza obbligatoria (stessa semantica):
  AGENTS.md + radar-quota-ledger + Phase_AB §6 + runbook
  su soft-trim = LLM_SIMPLE.rpd e limiti per-lane.

Mirror hash/contenuto:
  .agents/skills/radar-quota-ledger/SKILL.md ≡ radar/.ecc/skills/radar-quota-ledger.md
  .agents/skills/llm-json-extraction/SKILL.md ≡ radar/.ecc/skills/llm-json-extraction.md

Check .env.example:
  - Profilo B attivo + Profilo A commentato (o viceversa se live=hybrid)
  - Commenti free=RPM/RPD>0 vs paid=0+BUDGET; legacy = fill-gap inerti se lane settate

Diff chiavi: .env.example vs .env live (solo NAMES, mai valori secret).
Segnalare: chiavi mancanti, extra, legacy inerti, GEMINI_* inutilizzato sotto Profilo B.

════════════════════════════════════════════════════════════
3) VERIFICATORE-CODICE (Task generalPurpose / pipeline-engineer mindset)
════════════════════════════════════════════════════════════
Read-only salvo bug bloccante:
  radar/backend/app/core/llm_lanes.py
  radar/backend/app/core/config.py
  radar/backend/app/classification/quota.py
  radar/backend/app/classification/client.py
  radar/backend/app/worker.py (soft-trim SIMPLE.rpd)
  radar/backend/app/classification/complexity.py (v2.2)

Verificare invarianti:
  1. Limiti da LLM_SIMPLE_* / LLM_COMPLEX_* (0 = unmanaged)
  2. Legacy LLM_RPM / DEEPSEEK_* = fill-gap, non tetto globale
  3. Soft-trim worker solo se LLM_SIMPLE.rpd > 0
  4. BORDERLINE+COMPLEX → purpose classify:complex; SIMPLE → classify:simple
  5. Residual SIMPLE↔COMPLEX se identity diversa
  6. No package openai

Smoke pytest (da radar/):
  $env:PYTHONPATH = "backend"
  python -m pytest app/tests/test_complexity.py app/tests/test_classification.py `
    app/tests/test_quota_concurrency.py -q

Se fallisce: fix minimo SOLO su allowlist codice sotto; ritestare.

════════════════════════════════════════════════════════════
4) OPS-DOCKER (Task shell + skill radar-docker-ops)
════════════════════════════════════════════════════════════
Da radar/:
  docker compose up -d
  # Preferire up -d, non restart parallelo di tutto lo stack
  docker compose ps
  docker compose exec -T radar-backend curl -sf http://localhost:8000/health/live
  docker compose exec -T radar-backend curl -sf http://localhost:8000/health/ready

Criteri PASS:
  - radar-db, radar-backend, radar-miniflux, radar-frontend healthy
  - radar-worker up + heartbeat_ok su /health/ready
  - outbox_failed = 0 (o spiegare residuali)

Log bootstrap (ultime ~80 righe):
  docker compose logs --tail=80 radar-worker
  Cercare: ClassificationClient pronto, routing=complexity, shadow=false,
  simple=deepseek/…, complex=deepseek/… (o hybrid se Profilo A).

════════════════════════════════════════════════════════════
5) PIPELINE-E2E (Task pipeline-engineer + shell)
════════════════════════════════════════════════════════════
Obiettivo: dimostrare SIMPLE + COMPLEX/BORDERLINE su articoli reali.

A) Snapshot pre:
  - count articles ultimi 30m
  - ledger purpose/status ultimi 30m
  - unread Miniflux total (via API nel container, no secret in output)

B) Requeue controllato (N=20 tipico):
  Se esiste script: docker compose exec -T radar-worker python -m app.scripts._tmp_requeue20 20
  Altrimenti procedura equivalente:
    - marca N entry Miniflux read → unread
    - DELETE articles + outbox per quegli URL
    - opz. delete vault md correlati
  NON commitare script _tmp_ se non richiesti.

C) Forza ciclo: docker compose restart radar-worker
   (poll default 900s — restart = ciclo immediato)

D) Osserva log (2–5 min):
  docker compose logs -f --tail=0 radar-worker
  Evidenze richieste:
    - "route lane=SIMPLE → … effort=none" + "OK … lane=SIMPLE"
    - "route lane=COMPLEX → … effort=high" e/o BORDERLINE effort=high
    - DeepSeek ok / assenza errori sistemici 402/5xx a cascata
  Stop follow dopo evidenze sufficienti (non lasciare -f appeso).

E) Snapshot post:
  SELECT purpose, status, count(*) FROM llm_request_ledger
    WHERE created_at > NOW() - INTERVAL '15 minutes' GROUP BY 1,2;
  Atteso tipico Profilo B: classify:simple completed > 0 AND classify:complex completed > 0
  articles nuovi > 0; /health/ready outbox_pending/writing/failed puliti o spiegati.

F) Considerazioni aggiuntive se necessarie:
  - Se solo SIMPLE: campione HN/tech può essere skewed — allargare N o scegliere feed geo
  - Se reserved stuck > 5 min: indagare timeout/cooldown
  - Se Profilo B: residual cross-lane può non scattare (stessa identity modello) — by design
  - Non attivare Profilo A / VERIFY_IN_STUDIO / shadow 3g in questa chiusura salvo richiesta utente

════════════════════════════════════════════════════════════
6) AUDITOR RESIDUALI (Task explore — chiusura)
════════════════════════════════════════════════════════════
Elenco residuali noti da confermare aperti/chiusi:
  - VERIFY_IN_STUDIO (solo Profilo A)
  - Shadow 3g opzionale (LLM_ROUTING_SHADOW=true → log lane, call sempre SIMPLE)
  - Phase_AB sezioni storiche ancora “Gemini-first” fuori §5–§6
  - Script _tmp_requeue* untracked (tenere fuori git o promuovere a tools/ops)
  - Commit .env vietato

ALLOWLIST FIX (solo se bug verificato in questa chiusura)
radar/backend/app/core/config.py
radar/backend/app/core/llm_lanes.py
radar/backend/app/classification/quota.py
radar/backend/app/classification/client.py
radar/backend/app/worker.py
radar/backend/app/tests/test_*.py
docs / plan-audit / .ecc / .agents (solo se trovate contraddizioni docs↔codice)
radar/.env.example (mai .env)

VIETATO
sidebar FE; schema field names; SYSTEM_PROMPT CoT; package openai; vault; commit .env;
riscrivere motore “per gusto”; hardcodare RPD DeepSeek; push remoto senza richiesta.

DONE WHEN
- Tutti i ruoli sopra hanno prodotto PASS o FAIL documentato
- Gate grep PASS
- Mirror skills PASS
- pytest smoke PASS
- Docker ready PASS
- E2E: almeno 1 OK SIMPLE + 1 OK COMPLEX|BORDERLINE nei log + ledger coerente
- Report chiusura breve in chat + aggiornamento opzionale
  plan-audit/remediation/audit_remediation_llm_multi_model_fallback.md
  con sezione “Phase close verification YYYY-MM-DD”

REPORT FINALE (obbligatorio — formato)
## Chiusura fase LLM Limits / Docs-ECC
- Verdetto: PASS | FAIL
- Profilo ops: A | B
- Commit base: 5b1f6eb
- Gate docs / mirror / pytest / docker / e2e: ciascuno PASS|FAIL + 1 riga evidenza
- File toccati in chiusura (se fix): …
- Residuali aperti: …
- Raccomandazione next: archiviare prompt / Final Release / shadow 3g / altro
```

---

## Note operative sotto-agenti

| Ruolo | Tool tipico | Skill / profilo |
|-------|-------------|-----------------|
| Supervisore | Agent principale | Piano + AGENTS.md |
| Verificatore docs | Task `explore` | Gate del prompt |
| Verificatore codice | Task `generalPurpose` | `pipeline-engineer`, `radar-quota-ledger` |
| Ops Docker | Task `shell` | `radar-docker-ops` |
| Pipeline E2E | Task `shell` + `generalPurpose` | `pipeline-engineer`, `llm-json-extraction` |
| Auditor residuali | Task `explore` | README plan-audit |

Parallelizzare dove possibile: docs ∥ codice ∥ docker-up; E2E solo dopo docker ready.
