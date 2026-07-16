# Remediation — LLM multi-model fallback (Fase C + lane env v2.2)

> **Data:** 2026-07-16 (aggiornato lane env)  
> **SoT:** [`../active/LLM_Multi_Model_Fallback_Phase_AB.md`](../active/LLM_Multi_Model_Fallback_Phase_AB.md)  
> **Stato:** IMPLEMENTED  
> - Default codice: `LLM_ROUTING_MODE=off`, `LLM_ROUTING_SHADOW=true` (boot sicuro)  
> - Ops tipico: `MODE=complexity`, `SHADOW=false`, Lite SIMPLE + DeepSeek High COMPLEX

## Summary

- Cascata Gemini: `LLM_SIMPLE_MODEL` (o `GEMINI_MODEL`) + `GEMINI_MODEL_FALLBACKS` se provider=gemini
- Lane assignment env: `LLM_SIMPLE_PROVIDER|MODEL` + `LLM_COMPLEX_PROVIDER|MODEL` (`gemini` \| `deepseek`)
- Cooldown SQL 24h: migrazione `009_llm_model_cooldown.sql` + `classification/cooldown.py`
- Euristica lane v2.1: `classification/complexity.py` (quorum famiglie)
- DeepSeek High via **httpx** (`classification/deepseek.py`) — no package `openai`; `classify_json(model=ref.model)`
- Router in `classification/client.py`: off / shadow / complexity live + escalate BORDERLINE
- Docs: `.env.example`, `docs/runbook.md`, ECC `backend.md` / `CLAUDE.md`, skill `llm-json-extraction`

## Files touched

| Path | Cambio |
|------|--------|
| `radar/backend/migrations/009_llm_model_cooldown.sql` | NEW |
| `radar/backend/app/core/config.py` | DeepSeek + routing + `LLM_SIMPLE_*` / `LLM_COMPLEX_*` |
| `radar/backend/app/classification/complexity.py` | NEW |
| `radar/backend/app/classification/cooldown.py` | NEW |
| `radar/backend/app/classification/deepseek.py` | NEW; override `model=` per lane |
| `radar/backend/app/classification/client.py` | cascade + lanes + escalate |
| `radar/backend/app/tests/test_complexity.py` | NEW |
| `radar/backend/app/tests/test_cooldown.py` | NEW |
| `radar/backend/app/tests/test_classification.py` | cascade / cooldown; routing isolato nei unit test |
| `radar/.env.example` | lane + DeepSeek + routing |
| `radar/docs/runbook.md` | multi-model + lane swap |
| `radar/.ecc/rules/backend.md` | httpx DeepSeek; Regola lane env |
| `radar/.ecc/CLAUDE.md` | stack LLM dual-provider |
| `radar/.ecc/skills/llm-json-extraction.md` | dual-provider + lane env |
| `.agents/skills/llm-json-extraction/SKILL.md` | mirror |
| `plan-audit/active/LLM_Multi_Model_Fallback_Phase_AB.md` | SoT v2.2 |

## Ops enable (live tipico)

```text
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_MODEL_FALLBACKS=
LLM_ROUTING_MODE=complexity
LLM_ROUTING_SHADOW=false
LLM_ROUTING_STRICT=0
LLM_COMPLEXITY_ESCALATE_ON_VALIDATION=1
LLM_SIMPLE_PROVIDER=gemini
LLM_SIMPLE_MODEL=gemini-3.1-flash-lite
LLM_COMPLEX_PROVIDER=deepseek
LLM_COMPLEX_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=...          # solo in .env locale; mai commit
DEEPSEEK_REASONING_EFFORT=high
```

Swap COMPLEX → Google (solo env):

```text
LLM_COMPLEX_PROVIDER=gemini
LLM_COMPLEX_MODEL=gemini-3.5-flash
```

Rebuild worker after migrate: `docker compose up -d --build radar-worker`.

## Gate

```powershell
cd radar
$env:PYTHONPATH = "backend"
python -m pytest -m "not live" -q
python -m pytest backend/app/tests/test_classification.py backend/app/tests/test_complexity.py backend/app/tests/test_cooldown.py -q
```

## Residui noti

| Item | Nota |
|------|------|
| `DEEPSEEK_BUDGET_USD_DAY` | Env letto; soft-cap **non enforced** in v1 |
| Default codice vs `.env.example` | Codice: `MODE=off` / `SHADOW=true`; example = ops complexity |

## Non toccato

Sidebar, schema Pydantic campi, SYSTEM_PROMPT CoT, package openai, FE model_id, alzare `[:4000]`, commit `.env`.
