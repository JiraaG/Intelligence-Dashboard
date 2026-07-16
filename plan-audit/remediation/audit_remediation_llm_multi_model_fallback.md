# Remediation — LLM multi-model fallback (Fase C + lane env + complexity v2.2)

> **Data:** 2026-07-16 (aggiornato **complexity heuristic v2.2** + routing BORDERLINE→COMPLEX)  
> **SoT:** [`../active/LLM_Multi_Model_Fallback_Phase_AB.md`](../active/LLM_Multi_Model_Fallback_Phase_AB.md)  
> **Canvas audit:** `canvases/complexity-routing-audit.canvas.tsx`  
> **Stato:** IMPLEMENTED  
> - Default codice: `LLM_ROUTING_MODE=off`, `LLM_ROUTING_SHADOW=true` (boot sicuro)  
> - Ops tipico: `MODE=complexity`, `SHADOW=false`, DeepSeek Flash **none** SIMPLE + Flash **high** BORDERLINE/COMPLEX

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
| `plan-audit/active/LLM_Multi_Model_Fallback_Phase_AB.md` | SoT aggiornato |

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
| Default codice vs `.env.example` | Codice: `MODE=off` / `SHADOW=true`; example = ops complexity |

## Non toccato

Sidebar, schema Pydantic campi, SYSTEM_PROMPT CoT, package openai, FE model_id, alzare `[:4000]`, commit `.env`.
