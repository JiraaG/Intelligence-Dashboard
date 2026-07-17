# Plan prompt — Commenti codice “principiante” (audit Terra/Sol MAX → piano .md)

> **Stato: DONE (2026-07-17)** — archiviato in `prompts/done/`.  
> Piano prodotto: [`active/plan_code_comments_beginner_audit.md`](../../active/plan_code_comments_beginner_audit.md) (`status: execute-p0-done`).  
> Non rieseguire questo prompt salvo nuovo audit da zero.
>
> **Pipeline completata:**  
> 1) Terra/Sol MAX — audit + piano `.md` ✅  
> 2) Grok 4.5 — refine ✅  
> 3) Grok 4.5 Agent — batch `P0-01`…`P0-09` ✅ (P1/P2 opt-in sul piano)

---

## PROMPT (storico — incolla in Plan mode — modello Terra MAX / Sol MAX)

```text
Ruolo: auditor tecnico senior del monorepo Radar Informativo Globale (ECC overlay).
Mode: PLAN (sola lettura sul codice prodotto). Sei autorizzato a CREARE/SOVRASCRIVERE
UN SOLO deliverable su disco: il file piano Markdown indicato sotto. Vietato modificare
qualsiasi altro file (backend, frontend, hooks, docs SoT, skills, AGENTS, ecc.).

═══════════════════════════════════════════════════════════════════
DELIVERABLE OBBLIGATORIO (scrivi su disco — non bastare la UI del piano)
═══════════════════════════════════════════════════════════════════
Path ESATTO da creare/sovrascrivere:
  plan-audit/active/plan_code_comments_beginner_audit.md

Dopo aver completato ricerca + sottoagenti, DEVI scrivere quel file con Write/tool
equivalente. Il file è la SoT per le fasi successive (raffinamento Grok 4.5 → esecuzione Grok).
Se CreatePlan/UI piano esiste, allinealo al contenuto del file, ma il file .md è prioritario.

Frontmatter YAML obbligatorio in cima al file:
---
title: Piano commenti codice principiante — Radar
status: draft-audit-terra
model: terra-or-sol-max
pipeline: terra-audit → grok-refine → grok-execute
created: YYYY-MM-DD
scope: backend-app-prod + frontend-active + ecc-hooks-adapters-sync + ops-sh
exclude: tests, radar-sidebar, migrations-sql, node_modules, data, backups, vault
comment_language: it
behavior_change: false
---

═══════════════════════════════════════════════════════════════════
OBIETTIVO
═══════════════════════════════════════════════════════════════════
Analisi SUPER DETTAGLIATA e piano ESEGUIBILE per ricoprire il codice di commenti
e docstring in stile “principiante legge ogni istruzione non ovvia”:
- ogni metodo/funzione pubblica: scopo, parametri, return, side-effect, errori
- chiavi/valori env, dict, costanti: significato + vincolo SoT se esiste
- rami if/except/retry/lock: perché esistono (non narrare sintassi ovvia)
- riferimenti espliciti ai manuali (“vedi AGENTS §… / skill X / docs/04”) invece di
  duplicare paragrafi interi

ZERO cambio logica. Diff futuri = solo commenti/docstring (whitespace innocuo ok).

═══════════════════════════════════════════════════════════════════
SCOPE FISSO (non chiedere; non allargare)
═══════════════════════════════════════════════════════════════════
INCLUSO:
- radar/backend/app/**/*.py  ESCLUSI tests/ e qualsiasi **/test_*.py
- radar/frontend/src/app/**/*.{ts,html,scss}
  ESCLUSI: components/radar-sidebar/**  (FREEZE ASSOLUTO)
  ESCLUSI: **/*.spec.ts
- radar/.ecc/hooks/*.py
- radar/.ecc/scripts/sync_skills.py
- .cursor/hooks/*-adapter.py
- radar/ops/*.sh

ESCLUSO:
- radar/backend/migrations/*.sql (schema: non commentare massivamente)
- node_modules, dist, data/postgres, radar/backups/, vault/
- Clonare/installare ECC upstream; CodeWiki (spesso vuota = non-SoT)

Lingua commenti target: ITALIANO. Termini tecnici EN ammessi se già SoT
(MOCK_MODE, reserve/complete, QuotaDailyExceeded, spiderfy, …).

═══════════════════════════════════════════════════════════════════
SoT OBBLIGATORI DA LEGGERE / CROSS-CHECK
═══════════════════════════════════════════════════════════════════
Prodotto / ops:
- README.md
- docs/01_getting_started.md, docs/02_*.md (backend), docs/03_*.md (frontend), docs/04_ecc_framework.md
- radar/docs/runbook.md
- radar/ops/README.md

ECC / guardrail:
- .agents/AGENTS.md  (Magna Carta — vincoli immutabili)
- radar/.ecc/CLAUDE.md  (skill map)
- radar/.ecc/rules/backend.md, frontend.md, docker.md, testing.md
- .agents/skills/*/SKILL.md  (tutte; priorità: llm-json-extraction, radar-quota-ledger,
  radar-api-contract, radar-sidebar-freeze, radar-docker-ops, radar-requeue-ops,
  spatial-data-mocking, radar-geojson-assets)
- ecc_deep_dive_analysis_v2.md  — descrittivo; se contraddice docs/04 o AGENTS → VINCE docs/04+AGENTS

Plan-audit (stato / gate; non reinventare prodotto):
- plan-audit/STATUS.md
- plan-audit/complete/plan_impl_phase_0_6.md
- plan-audit/complete/plan_impl_phase_0_6_execution.md
- plan-audit/active/sot_llm_multi_model_fallback.md
- plan-audit/archive/ecc/handoff_ecc_expansion.md  (wiring DONE — non riproporre)

Upstream ECC (filosofia only; fetch se serve; non installare):
- https://raw.githubusercontent.com/affaan-m/ECC/main/docs/architecture/cross-harness.md
- NON basarti su CodeWiki se vuota

Vincoli NON negoziabili (i commenti futuri NON devono contraddirli):
- sidebar freeze radar-sidebar/** + p-carousel
- ingest solo worker.py; main.py API-only
- MOCK_MODE esplicito; nation-fetch detailError → banner (T-P1-04)
- cluster maxClusterRadius 40; spiderfyOnMaxZoom false
- Pydantic CSV str (FE string[] solo post-API)
- reti radar-edge / radar-data; health live vs ready
- quota per-lane; RPM/TPM attesa stessa lane; RPD → QuotaDailyExceeded + residual
- nessun TODO/FIXME/HACK/placeholder nei commenti nuovi

═══════════════════════════════════════════════════════════════════
METODO — SOTTOAGENTI IN PARALLELO (read-only) POI SINTESI TUA
═══════════════════════════════════════════════════════════════════
Lancia almeno 4 sottoagenti explore/generalPurpose in parallelo.
Modello sottoagenti: stesso Terra/Sol MAX se disponibile; altrimenti il più capace.

A) docs-sot-matrix
   Output: tabella SoT path → temi chiave → moduli codice che DEVONO rifletterli nei commenti.
   Elenca CONTRADDIZIONI tra docs/04, AGENTS, CLAUDE, V2, skills (con path+citazione corta).

B) backend-comment-gap
   Per OGNI file prod in radar/backend/app (no tests): LOC approx, densità commenti AS-IS,
   zone opache (quota, complexity v2.2, outbox, advisory lock, lanes, cooldown).
   Assegna P0/P1/P2 + motivazione + stima effort (S/M/L).

C) frontend-comment-gap
   Stesso per FE attivo (map, state, services, toolbar, models). MAI proporre edit sidebar.
   Flag: MOCK_MODE, detailError, cluster/spiderfy, window.L / angular.json scripts.

D) ecc-ops-comment-gap
   hooks pre/post, adapters, sync_skills.py, ops/*.sh: cosa già denso vs gap.
   Verifica allineamento secret/domains hook ↔ settings.json (solo report, no edit).

Dopo i 4 report: TU consolidi, risolvi conflitti, e SCRIVI il file deliverable.

═══════════════════════════════════════════════════════════════════
STANDARD COMMENTI (da fissare nel piano — non applicare al codice ora)
═══════════════════════════════════════════════════════════════════
Template docstring IT (Python):
  \"\"\"Cosa fa in 1 riga.
  Args: ...
  Returns: ...
  Raises/Side-effects: ...
  SoT: path skill/rule/docs se rilevante
  \"\"\"

Regole densità:
- SÌ: perché di un ramo, invarianti, vincoli prodotto, unità, fail-closed
- NO: “incrementa i di 1”, ripetere il nome della variabile, copiare AGENTS intero
- Citare SoT per riferimento; non inventare comportamento assente nel codice
- Se codice e manuale divergono: segnalare nel piano come CONTRADDIZIONE (P0 docs o codice),
  NON “sistemare” nel passaggio commenti

Esempio BUONO / CATTIVO: includine 2+2 nel file piano (Python + TypeScript).

═══════════════════════════════════════════════════════════════════
STRUTTURA OBBLIGATORIA DEL FILE plan_code_comments_beginner_audit.md
═══════════════════════════════════════════════════════════════════
1. Executive summary (max 15 righe) + verdetto densità AS-IS
2. Matrice SoT → moduli codice (+ contraddizioni)
3. Standard commento (template + buono/cattivo)
4. Inventario file completo con colonne:
   path | layer | LOC~ | gap P0/P1/P2 | effort | note SoT | batch_id
5. Sequenza batch di esecuzione (max 3–5 file per batch; ordine dipendenze:
   core/config → extraction → classification → commit → worker → api/main → FE → ecc/ops)
6. Gate di accettazione per batch e finali (misurabili):
   - git diff --stat -- radar/frontend/src/app/components/radar-sidebar  → vuoto
   - cd radar && set PYTHONPATH=backend && python -m pytest -m "not live" -q
   - (FE) cd radar/frontend && npm run typecheck
   - nessuna riga TODO/FIXME introdotta
   - ogni public def/async def / metodo export TS nel batch ha docstring/JSDoc
7. Rischi (rumore review, drift commento≠codice, token context) + mitigazioni
8. Fuori scope esplicito
9. Istruzioni per fase 2 (Grok 4.5 refine): cosa può tagliare/riorganizzare senza perdere P0
10. Istruzioni per fase 3 (Grok 4.5 Agent execute): “esegui solo batch Px; no scope creep”

═══════════════════════════════════════════════════════════════════
VINCOLI DI QUESTA CHAT
═══════════════════════════════════════════════════════════════════
- Nessun commento aggiunto al codice prodotto in questa sessione
- Nessun commit/push
- Nessun tocco sidebar
- Nessun clone ECC
- Deliverable = SOLO plan-audit/active/plan_code_comments_beginner_audit.md
- Se un file è già ben commentato: marcarla P2/skip con prova (citazione 2–3 righe)

Inizia: lancia i 4 sottoagenti → leggi SoT → scrivi il file completo → conferma path + conteggio file P0.
```

---

## Note operative (storico)

| Step | Chat | Modello | Azione | Esito |
|------|------|---------|--------|-------|
| 1 | Plan | **Terra MAX** o **Sol MAX** | Incolla il blocco `## PROMPT` | ✅ |
| 2 | Plan/Ask | **Grok 4.5** | Raffina il piano `.md` | ✅ |
| 3 | Agent | **Grok 4.5** | Batch P0 del piano | ✅ P0; P1/P2 residui |

**Piano vivo:** [`plan-audit/active/plan_code_comments_beginner_audit.md`](../../active/plan_code_comments_beginner_audit.md)
