---
name: radar-quota-ledger
description: >
  QuotaLedger durable: reserve/complete/fail su llm_request_ledger prima di ogni tentativo
  provider; limiti per-lane LLM_SIMPLE_* / LLM_COMPLEX_* (0=unmanaged); soft-trim =
  LLM_SIMPLE.rpd se >0; free=RPM/RPD vs paid=BUDGET; RPD half-open; rispettare 429 Retry-After.
  Complexity v2.2: BORDERLINE → purpose classify:complex.
when_to_use:
  - classification/quota.py, cooldown.py, llm_request_ledger, client cascade/retry
version: 2.3.1
---

## Limiti (obbligatorio)

| Env | Uso |
|-----|-----|
| `LLM_SIMPLE_RPM/TPM/RPD` | Tentativi catena SIMPLE (`purpose=classify:simple`) |
| `LLM_COMPLEX_RPM/TPM/RPD` | Tentativi catena COMPLEX — include **BORDERLINE + COMPLEX** (`purpose=classify:complex`) e custom **`quality:compare`** |
| `0` | Quella dimensione **non** e enforced su quella lane |

`LLM_RPM` / `DEEPSEEK_RPM` = **legacy alias** (default se il campo lane e assente). Non sono un tetto globale shared.

Worker soft-trim usa solo `LLM_SIMPLE.rpd` (se > 0) — indipendente dal provider della lane SIMPLE.

| Tipo | Vincolo | Semantica |
|------|---------|-----------|
| Free (es. Gemini Studio) | RPM + RPD (+ TPM se >0) | `*_RPM` / `*_TPM` / `*_RPD` > 0 |
| Paid (es. DeepSeek) | Credito / soft-cap | `*_RPM`/`*_RPD` = 0 + `*_BUDGET_USD_DAY` |

RPM/TPM pieni → attesa sulla **stessa** lane (no cross). **RPD esaurita** → `QuotaDailyExceeded` → cooldown + residual cross-lane.

- Gemini same-provider `LLM_SIMPLE_FALLBACKS` condividono i contatori `LLM_SIMPLE_*` (lane ledger). Free tier Studio **per modello** ≠ RPD Radar per lane.

Residual cross-lane fattura `ref.quota_lane` (SIMPLE↔COMPLEX se identity diversa).

**Custom purpose `quality:compare`:** usa contatori lane=`complex`; il campo `purpose` è memorizzato **as-is** nel ledger (non overwrite a `classify:complex`).

## Complexity routing (v2.2)

- SIMPLE → reserve `lane=simple`
- BORDERLINE / COMPLEX → reserve `lane=complex`
- quality:compare (Fase C near-dup) → reserve `lane=complex`, `purpose=quality:compare`

## Protocollo

```python
reservation_id = await self.quota.reserve(
    estimated_tokens=..., model=ref.model, lane=ref.quota_lane, provider=ref.provider
)
```

1. Env preferito: `LLM_SIMPLE_*` / `LLM_COMPLEX_*`.
2. Legacy riempie i gap se i campi lane sono assenti.
3. `PROVIDER` ∈ {gemini, deepseek, openai, glm, grok, claude}.
   OpenAI-compat dialect: deepseek → `thinking`; openai|glm|grok → stock (no DeepSeek-only fields).
4. Budget exceeded → skip, no cooldown 24h.

## SoT

`radar/backend/app/core/llm_lanes.py` + `classification/quota.py` + `.env.example` +
`plan-audit/complete/sot_llm_multi_model_fallback.md`.
