---
name: radar-quota-ledger
description: >
  QuotaLedger durable: reserve/complete/fail su llm_request_ledger prima di ogni
  tentativo provider (Gemini o DeepSeek); RPD half-open; 429 Retry-After breve;
  hard-fail → llm_model_cooldown 24h (tabella separata, non il ledger).
when_to_use:
  - classification/quota.py, cooldown.py, llm_request_ledger, client cascade/retry
version: 1.1.0
---
    10|
## Quando attivare

Modifiche a rate limit, ledger SQL, cooldown modelli, o retry del classification client.

## Protocollo

```python
reservation_id = await self.quota.reserve(estimated_tokens=..., model=active_model)
try:
    response = await provider_call(...)  # gemini or deepseek
    await self.quota.complete(reservation_id, actual_tokens)
except asyncio.CancelledError:
    await self.quota.fail(reservation_id)  # o release se provider non avviato
    raise
```

1. **Reserve prima** di ogni tentativo provider (anche retry / switch modello / escalate).
2. **Complete/fail** sulla **stessa** `reservation_id` — mai “ultima riga”.
3. Spacing in-process con `time.monotonic()`; RPD half-open su `RADAR_TIME_ZONE`.
4. On **429** breve: rispettare `Retry-After` — **non** scrivere cooldown 24h.
5. Hard-fail (RPD day, 402 crediti, 404 model, 5xx esauriti): `llm_model_cooldown` poi next model.

## Anti-pattern

- Solo `asyncio.sleep(4)` in-memory come unico rate limit
- `date(created_at) = CURRENT_DATE` ingenuo per RPD
- Skip reserve sui retry di validazione

## SoT

`radar/.ecc/rules/backend.md` Regola 9 + `classification/quota.py` + migration `003_quota_ledger.sql`.
