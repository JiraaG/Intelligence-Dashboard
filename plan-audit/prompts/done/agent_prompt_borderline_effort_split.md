# Agent prompt — BORDERLINE effort split (review R1–R12 + GATE requeue)

> **Stato: ACTIVE** — usa **questo** prompt per l’implementazione (sostituisce il prompt corto precedente).  
> **Piano SoT:** [`../../active/plan_impl_borderline_effort_split.md`](../../active/plan_impl_borderline_effort_split.md) — **obbligatorio §9 Review R1–R12**  
> **Branch:** `feature/upgrades`  
> **Analisi:** [`../done/plan_prompt_borderline_cost_routing.md`](../done/plan_prompt_borderline_cost_routing.md)  
> **PO:** nessun `git commit` / `git push` in questa wave.

---

## Come usare

1. Nuova chat **Agent** su `feature/upgrades`.
2. Se hai già un Implementation Plan interno, **R1–R12 override** dove confligge.
3. Incolla il blocco **PROMPT** sotto per intero.
4. A fine GATE: aggiorna `STATUS.md` / indici; **non** spostare il piano in `complete/` finché il PO non chiude esplicitamente.

---

## PROMPT (incolla in Agent mode)

```text
# Task — IMPLEMENTAZIONE + GATE: BORDERLINE effort=none + escalate high
# (con correzioni review R1–R12 sull’Implementation Plan)

## Ruolo
Pipeline engineer Radar. Implementa lo split effort BORDERLINE, applica le correzioni R1–R12, aggiorna docs/ECC, esegui pytest + requeue live end-to-end. Schema/prompt classify **immutabili**. Sidebar freeze. **Nessun git commit**.

## Autorità (ordine)
1. `plan-audit/active/plan_impl_borderline_effort_split.md` (SoT) — incluso **§9 R1–R12**
2. Questo prompt (chiusure operative)
3. Skills: `radar-quota-ledger`, `llm-json-extraction`, `radar-requeue-ops`, `radar-docker-ops`
4. SoT lane `plan-audit/complete/sot_llm_multi_model_fallback.md` §4 (aggiorna in place)
5. Vietato: `radar-sidebar/**`; UI; migration DB; move BL→Gemini; 4ª fascia; terzo model ID; commit `.env` / secret

## Il tuo Implementation Plan è OK su
- Parse `LLM_BORDERLINE_REASONING_EFFORT` (default `high` se unset)
- `_borderline_chain` + `_chain_for(BORDERLINE)`
- Test unitari chain/escalate/compat
- `.env.example` + runbook + SoT §4.4 + skill quota-ledger
- Target ops post-GATE = `none`

## Correzioni OBBLIGATORIE (R1–R12) — override sul tuo plan

### R1 — CRITICO: effort per-call (senza questo lo split è NO-OP)
`_compat_client("complex")` cachea un `DeepSeekClient` con `effort=LLM_COMPLEX` (high).
Oggi `classify_json` ignora `ref.reasoning_effort` → BL “none” chiamerebbe comunque high.

Devi:
1. `DeepSeekClient.build_payload(..., effort: str | None = None)` e `classify_json(..., effort: str | None = None)` → usa `effort if effort is not None else self.effort`
2. In `client.py` `_compat_call`: passare `effort=ref.reasoning_effort`
3. Test che con BL none il payload DeepSeek abbia `thinking: {type: disabled}` (assert su `build_payload` / dialect test), non solo il log `route … effort=none`

### R2 — `_borderline_chain`
Copia struttura `_complex_chain` (provider, model, FALLBACKS, `quota_lane=complex`); cambia solo `reasoning_effort=LLM_BORDERLINE_REASONING_EFFORT`.

### R3 — Escalate
`escalate_ref` = primary COMPLEX con `LLM_COMPLEX.reasoning_effort` (high). Con BL none → escalate reale (identity include effort). Con entrambi high → no-op AS-IS.

### R4 — Parse knob
Unset/"" → high. `off`/`disabled` → none. `low`/`medium` → high + warning. Unknown → high + warning.

### R5 — `quality:compare` invariato (resto `effort=none` sul suo path).

### R6 — Docs ECC completi (aggiorna in place, NON spostare piani complete/)
Minimo:
- `radar/.env.example`
- `radar/docs/runbook.md` (knob + dual-run + rollback + caveat XX + requeue GATE)
- `plan-audit/complete/sot_llm_multi_model_fallback.md` §4.4
- `.agents/skills/radar-quota-ledger/SKILL.md` + mirror `radar/.ecc/skills/…`
- `docs/02_architecture_and_backend.md` (routing: BL effort knob)
- `.agents/AGENTS.md` + `radar/.ecc/CLAUDE.md` (+ rules ECC se citano BL=high fisso)
- root `README.md` se parla di complexity/effort lanes
- `plan-audit/README.md` + `plan-audit/STATUS.md` (indice active; link prompt Agent)
- `llm-json-extraction` skill solo se afferma BL always high

### R7 — GATE live requeue (obbligatorio, distruttivo, skill radar-requeue-ops)
```bash
cd radar
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 40 --dry-run
# solo se anteprima OK:
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 40
# Imposta LLM_BORDERLINE_REASONING_EFFORT=none nel .env ops (NON git add .env)
docker compose up -d --build radar-worker
docker compose logs radar-worker --since 10m 2>&1 | tee /tmp/bl-effort-gate.log
```
Assert:
- Log: `classify lane=BORDERLINE` e `route lane=BORDERLINE → … effort=none`
- Se ValidationError: escalate / `escalated=True` verso high
- `classification_lane` DB = `complex` (execution), NON stringa `borderline`
- Ledger `purpose=classify:complex`; Gemini simple RPD non assorbe i BL
- Vault: md ricreati; no Traceback; ciclo worker senza errori bloccanti
- Rollback smoke: env `high`, restart, log `effort=high`

Opzionale `--purge-all` solo con conferma esplicita (wipe totale). Preferire requeue N senza purge-all per GATE mirato.
VIETATO: DELETE SQL ad-hoc; script fuori dal container; purge senza dry-run.

### R8 — Pytest in container
```bash
docker compose exec -T radar-worker pytest \
  app/tests/test_classification.py \
  app/tests/test_complexity.py \
  app/tests/test_openai_compat_dialect.py -q
```

### R9 — Nessun git commit / push in questa wave.

### R10 — No dual-write automatico none+high per articolo.

### R11 — Non testare `articles.classification_lane == 'borderline'`.

### R12 — Runbook: caveat escalate≠fix geo XX; KPI dual-run dal piano §5.

## Design chiuso (riassunto)
```
SIMPLE     → LLM_SIMPLE
BORDERLINE → LLM_COMPLEX provider/model + LLM_BORDERLINE_REASONING_EFFORT (default high; ops none)
COMPLEX    → LLM_COMPLEX + LLM_COMPLEX_REASONING_EFFORT (high)
quality:compare → effort none (invariato)
purpose/lane ledger BL → classify:complex / complex
```

## Ordine di lavoro
1. Leggi SoT §3 + §9 e `client._compat_client` / `deepseek.classify_json` (conferma gap R1).
2. Implementa W1 (config + chain + R1 effort per-call) + W2 test.
3. W3 docs/ECC lista R6.
4. W4 GATE: pytest container → requeue dry-run → requeue → rebuild worker con `none` → assert log/DB/vault → rollback smoke `high` → ripristina target ops concordato.
5. Aggiorna STATUS/README plan-audit; lascia piano in `active/` finché PO non chiude.
6. Report finale: file toccati, esito pytest, esito GATE, env finale, **nessun commit**.

## Fuori scope
UI, sidebar, mappa, schema/prompt, migration, `LLM_BORDERLINE_PROVIDER/MODEL`, colonna `complexity_lane`, move BL→Gemini.

Inizia da R1 (effort per-call) prima di qualsiasi docs.
```
