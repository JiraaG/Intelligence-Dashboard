# Remediation — LLM multi-model fallback (Fase C)

> **Data:** 2026-07-16  
> **SoT:** [`../active/LLM_Multi_Model_Fallback_Phase_AB.md`](../active/LLM_Multi_Model_Fallback_Phase_AB.md)  
> **Stato:** IMPLEMENTED (default `LLM_ROUTING_MODE=off`; shadow/complexity opt-in via env)

## Summary

- Cascata Gemini: `GEMINI_MODEL` + `GEMINI_MODEL_FALLBACKS`
- Cooldown SQL 24h: migrazione `009_llm_model_cooldown.sql` + `classification/cooldown.py`
- Euristica lane v2.1: `classification/complexity.py` (quorum famiglie)
- DeepSeek High via **httpx** (`classification/deepseek.py`) — no package `openai`
- Router in `classification/client.py`: mode off / complexity+shadow / complexity live
- Docs: `.env.example`, `docs/runbook.md`, ECC `backend.md`, skill `llm-json-extraction`

## Files touched

| Path | Cambio |
|------|--------|
| `radar/backend/migrations/009_llm_model_cooldown.sql` | NEW |
| `radar/backend/app/core/config.py` | env routing/DeepSeek/chain |
| `radar/backend/app/classification/complexity.py` | NEW |
| `radar/backend/app/classification/cooldown.py` | NEW |
| `radar/backend/app/classification/deepseek.py` | NEW |
| `radar/backend/app/classification/client.py` | cascade + lanes |
| `radar/backend/app/tests/test_complexity.py` | NEW |
| `radar/backend/app/tests/test_cooldown.py` | NEW |
| `radar/backend/app/tests/test_classification.py` | 404→HARD_COOLDOWN, cascade tests |
| `radar/.env.example` | nuove vars |
| `radar/docs/runbook.md` | multi-model + cooldown |
| `radar/.ecc/rules/backend.md` | httpx DeepSeek; openai package vietato |
| `.agents/skills/llm-json-extraction/SKILL.md` | dual-provider note |
| `plan-audit/` | reorg cartelle + SoT §12 |

## Ops enable

```text
GEMINI_MODEL=gemini-3.5-flash
GEMINI_MODEL_FALLBACKS=gemini-2.5-flash,gemini-3.1-flash-lite
LLM_ROUTING_MODE=complexity
LLM_ROUTING_SHADOW=true
DEEPSEEK_API_KEY=...
DEEPSEEK_REASONING_EFFORT=high
```

Rebuild worker after migrate: `docker compose up -d --build radar-worker`.

## Gate

```powershell
cd radar
$env:PYTHONPATH = "backend"
python -m pytest -m "not live" -q
python -m pytest backend/app/tests/test_classification.py backend/app/tests/test_complexity.py backend/app/tests/test_cooldown.py -q
```

## Non toccato

Sidebar, schema Pydantic campi, SYSTEM_PROMPT CoT, package openai, FE model_id, alzare `[:4000]`.
