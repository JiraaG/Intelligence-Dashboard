# Remediation — LLM multi-model fallback (Fase C + lane env + complexity v2.2)

> **Data:** 2026-07-16 (aggiornato **complexity heuristic v2.2** + routing BORDERLINE→COMPLEX + **docs/ECC allineati per-lane**)  
> **SoT:** [`../active/sot_llm_multi_model_fallback.md`](../active/sot_llm_multi_model_fallback.md)  
> **Piano docs/ECC:** [`../archive/plans/plan_llm_limits_periodicity_docs_ecc.md`](../archive/plans/plan_llm_limits_periodicity_docs_ecc.md)  
> **Canvas audit:** `canvases/complexity-routing-audit.canvas.tsx`  
> **Stato:** IMPLEMENTED  
> - Default codice: `LLM_ROUTING_MODE=off`, `LLM_ROUTING_SHADOW=true` (boot sicuro)  
> - Ops tipico: `MODE=complexity`, `SHADOW=false`, DeepSeek Flash **none** SIMPLE + Flash **high** BORDERLINE/COMPLEX  
> - **Docs/ECC allineati per-lane** (2026-07-16): Phase_AB §5–§6, AGENTS, skills, runbook, `.env.example` Profilo B attivo + A commentato

## Summary

- Cascata provider: `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (`gemini` \| `deepseek` \| …)
- **Complessità v2.2** (`classification/complexity.py`): rischio schema (G/E/X); **L sola → SIMPLE**; geo_marker solo se `body_len ≥ 1500`
- **Routing v2.2** (`client._chain_for`): SIMPLE → `LLM_SIMPLE`; **BORDERLINE + COMPLEX → `LLM_COMPLEX`** (effort tipico high)
- Cooldown SQL 24h: migrazione `009_llm_model_cooldown.sql` + `classification/cooldown.py`
- DeepSeek via **httpx** — `thinking: disabled` se effort=`none`; thinking high altrimenti
- Docs: `.env.example`, `docs/runbook.md`, ECC `backend.md` / `CLAUDE.md`, skill `llm-json-extraction`

## Files touched (delta v2.2 routing)

| Path | Cambio |
|------|--------|
| `radar/backend/app/classification/complexity.py` | Heuristic v2.2 (L-sola, G marker threshold) |
| `radar/backend/app/classification/client.py` | BORDERLINE → complex_chain; log `route lane=… effort=` |
| `radar/backend/app/classification/deepseek.py` | effort `none` → thinking disabled |
| `radar/backend/app/tests/test_complexity.py` | L-sola SIMPLE; geo_marker corto ignorato |
| `radar/backend/app/tests/test_classification.py` | `test_chain_for_borderline_uses_complex_lane` |
| `radar/.env.example`, `radar/docs/runbook.md` | BORDERLINE → COMPLEX lane |
| `radar/.ecc/rules/backend.md`, `CLAUDE.md`, skills | Allineamento v2.2 |
| `plan-audit/active/sot_llm_multi_model_fallback.md` | SoT aggiornato |

## Ops enable (live tipico 2026-07-16)

```text
LLM_ROUTING_MODE=complexity
LLM_ROUTING_SHADOW=false
LLM_ROUTING_STRICT=0
LLM_COMPLEXITY_ESCALATE_ON_VALIDATION=1
LLM_SIMPLE_PROVIDER=deepseek
LLM_SIMPLE_MODEL=deepseek-v4-flash
LLM_SIMPLE_REASONING_EFFORT=none
LLM_COMPLEX_PROVIDER=deepseek
LLM_COMPLEX_MODEL=deepseek-v4-flash
LLM_COMPLEX_REASONING_EFFORT=high
DEEPSEEK_API_KEY=...          # solo in .env locale; mai commit
```

Swap COMPLEX → Google (solo env):

```text
LLM_COMPLEX_PROVIDER=gemini
LLM_COMPLEX_MODEL=gemini-3.5-flash
```

Rebuild worker: `docker compose up -d --build radar-worker`.

## Verifica post v2.2 (requeue)

| Atteso | Evidenza |
|--------|----------|
| L-sola → SIMPLE none | Democr.ai / late-40s / smoking / data tools |
| G-sola → BORDERLINE high | El Niño |
| G+L → COMPLEX high | Likweli / World Cup |
| 0 errori pipeline | ciclo commit OK |

## Gate

```powershell
cd radar
$env:PYTHONPATH = "backend"
python -m pytest app/tests/test_complexity.py app/tests/test_classification.py -q
```

## Residui noti

| Item | Nota |
|------|------|
| Pitch HN con multi-country nel body lungo | Può restare COMPLEX (G+L) — non solo geo_marker corto |
| Soft-cap budget | Enforced se `BUDGET_USD_DAY` > 0 |
| Default codice vs `.env.example` | Codice: `MODE=off` / `SHADOW=true`; example = ops complexity Profilo B |
| VERIFY_IN_STUDIO (Profilo A) | Se si attiva hybrid Gemini free: calibrare `LLM_SIMPLE_RPM/RPD` su AI Studio — non inventare |
| Shadow 3g | Opzionale: `LLM_ROUTING_SHADOW=true` per ~3 giorni per osservare mix lane senza cambiare catena (log only) |
| Phase_AB §12 | **DONE** 2026-07-16 — tabella AS-IS allineata a per-lane / soft-trim `LLM_SIMPLE.rpd` |
| Requeue ops | **DONE** — `python -m app.scripts.requeue_articles N` (ex `_tmp_requeue*`) |

## Docs/ECC allineati per-lane (2026-07-16)

Propagati i principi unici (limiti `LLM_SIMPLE_*`/`LLM_COMPLEX_*`, soft-trim = `LLM_SIMPLE.rpd`, free vs paid, residual, `WORKER_POLL_INTERVAL_SECONDS`, v2.2) su Phase_AB §5–§6, ECC Regola 9/9b, CLAUDE, pipeline-engineer, skills mirror, AGENTS, docs/01–02/04, runbook, `.env.example`. Motore routing/quota **non** riscritto.

## Phase close verification 2026-07-16

| Gate | Esito |
|------|--------|
| Docs anti-regressione + coerenza soft-trim | PASS |
| Mirror skills `.agents` ≡ `.ecc` | PASS |
| Invarianti codice per-lane (6/6) | PASS |
| Pytest complexity/classification/quota | PASS — 38 passed |
| Docker live/ready + outbox clean | PASS |
| E2E requeue 20 + log SIMPLE/COMPLEX/BORDERLINE | PASS — ledger 15m: simple 26 + complex 14 completed; articles_15m 39 |

Profilo ops: **B**. Commit base docs: `5b1f6eb`. Prompt chiusura: `plan-audit/prompts/active/audit_prompt_llm_limits_phase_close.md`.
Motore non modificato in chiusura. Residuali post-close: VERIFY_IN_STUDIO (solo A), shadow 3g opzionale.
Phase_AB §12 e `requeue_articles` promossi (2026-07-16).
