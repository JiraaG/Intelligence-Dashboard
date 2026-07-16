---
name: radar-quota-ledger
description: >
  QuotaLedger per lane: LLM_SIMPLE_RPM/TPM/RPD e LLM_COMPLEX_RPM/TPM/RPD
  (0=unmanaged, contatori separati via purpose classify:{lane});
  provider type seleziona adapter; budget USD opzionale; hard-fail → cooldown 24h.
  Complexity v2.2: BORDERLINE riserva su purpose=classify:complex.
when_to_use:
  - classification/quota.py, cooldown.py, llm_request_ledger, client cascade/retry
version: 2.2.0
---

## Limiti (obbligatorio)

| Env | Uso |
|-----|-----|
| `LLM_SIMPLE_RPM/TPM/RPD` | Tentativi catena SIMPLE (`purpose=classify:simple`) |
| `LLM_COMPLEX_RPM/TPM/RPD` | Tentativi catena COMPLEX — include **BORDERLINE + COMPLEX** (`purpose=classify:complex`) |
| `0` | Quella dimensione **non** e enforced su quella lane |

`LLM_RPM` / `DEEPSEEK_RPM` = **legacy alias** (default se il campo lane e assente). Non sono un tetto globale shared.

Worker soft-trim usa solo `LLM_SIMPLE.rpd` (se > 0).

## Complexity routing (v2.2)

- SIMPLE → reserve `lane=simple`
- BORDERLINE / COMPLEX → reserve `lane=complex` (stesso ledger COMPLEX)

## Protocollo

```python
reservation_id = await self.quota.reserve(
    estimated_tokens=..., model=ref.model, lane=ref.quota_lane, provider=ref.provider
)
```

1. Env preferito: `LLM_SIMPLE_*` / `LLM_COMPLEX_*`.
2. Legacy riempie i gap se i campi lane sono assenti.
3. `PROVIDER` ∈ {gemini, deepseek, openai, claude}.
4. Budget exceeded → skip, no cooldown 24h.

## SoT

`radar/backend/app/core/llm_lanes.py` + `classification/quota.py` + `.env.example` +
`plan-audit/active/LLM_Multi_Model_Fallback_Phase_AB.md`.
