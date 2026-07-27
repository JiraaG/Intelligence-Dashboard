---
name: radar-quota-ledger
description: >
  QuotaLedger durable: reserve/complete/fail su llm_request_ledger prima di ogni tentativo
  provider; limiti per-lane LLM_SIMPLE_* / LLM_COMPLEX_* (0=unmanaged); soft-trim =
  LLM_SIMPLE.rpd se >0; free=RPM/RPD vs paid=BUDGET; RPD half-open; rispettare 429 Retry-After.
  Complexity v2.2: BORDERLINE → purpose classify:complex;
  effort da LLM_BORDERLINE_REASONING_EFFORT (default/ops tipico high; COMPLEX tipico max).
when_to_use:
  - classification/quota.py, cooldown.py, llm_request_ledger, client cascade/retry
version: 2.4.0
---

## Limiti (obbligatorio)

| Env | Uso |
|-----|-----|
| `LLM_SIMPLE_RPM/TPM/RPD` | Tentativi catena SIMPLE (`purpose=classify:simple`) |
| `LLM_COMPLEX_RPM/TPM/RPD` | Tentativi catena COMPLEX — include **BORDERLINE + COMPLEX** (`purpose=classify:complex`) e custom **`quality:compare`** |
| `0` | Quella dimensione **non** e enforced su quella lane |

`LLM_RPM` / `DEEPSEEK_RPM` = **legacy alias** (default se il campo lane e assente). Non sono un tetto globale shared.

- Ciascun modello della catena (primary e FALLBACKS) eredita il default di lane `LLM_SIMPLE_*` (o override `LLM_SIMPLE_MODEL_LIMITS`) con contatori e pool RPD **indipendenti per modello**.
- Soft-trim worker: calcola il residuo RPD di ciascun modello gestito nella catena SIMPLE. Ibberna il ciclo solo se **tutti** i modelli SIMPLE gestiti sono esausti e non c'è residual COMPLEX.

Residual cross-lane fattura `ref.quota_lane` (SIMPLE↔COMPLEX se identity diversa).

**Custom purpose `quality:compare`:** usa contatori lane=`complex`; il campo `purpose` è memorizzato **as-is** nel ledger (non overwrite a `classify:complex`).

## Complexity routing (v2.2)

- BORDERLINE / COMPLEX → reserve `lane=complex` (`purpose=classify:complex`). Nota effort BORDERLINE: BORDERLINE usa effort da `LLM_BORDERLINE_REASONING_EFFORT` (default/ops tipico `high` con escalate `high` su `ValidationError`), mantenendo `purpose=classify:complex`.
- quality:compare (Fase C near-dup) → reserve `lane=complex`, `purpose=quality:compare`

## Protocollo

```python
reservation_id = await self.quota.reserve(
    estimated_tokens=...,
    model=ref.model,
    lane=ref.quota_lane,
    provider=ref.provider,
    reasoning_effort=ref.reasoning_effort,
)
```

1. Env preferito: `LLM_SIMPLE_*` / `LLM_COMPLEX_*`.
2. Legacy riempie i gap se i campi lane sono assenti.
3. `PROVIDER` ∈ {gemini, deepseek, openai, glm, grok, claude}.
   OpenAI-compat dialect: deepseek → `thinking`; openai|glm|grok → stock (no DeepSeek-only fields).
4. Budget exceeded → skip, no cooldown 24h.
5. **`reasoning_effort`** persistito su `llm_request_ledger` (migrazione `015_llm_ledger_reasoning_effort.sql`; default `'none'`). Usato dal breakdown COSTI per tupla `(model, reasoning_effort)`.

## Cooldown RPD vs ore

- **RPD esaurita** (`QuotaDailyExceeded`): `until_ts=day_end` della finestra giornaliera (`compute_day_window` / `RADAR_TIME_ZONE`) → `ModelCooldownStore.set_cooldown(..., until=day_end)`. Non usare +24h statiche per RPD.
- **Altri cooldown** (es. 5xx / retry esauriti): `set_cooldown(..., hours=LLM_MODEL_COOLDOWN_HOURS)` (default tipico 24h).
- UI STATUS: countdown live su `cooldown_until` (`formatCooldownUntil`).

## SoT

`radar/backend/app/core/llm_lanes.py` + `classification/quota.py` + `classification/cooldown.py` + `.env.example` +
`plan-audit/complete/sot_llm_multi_model_fallback.md`.
