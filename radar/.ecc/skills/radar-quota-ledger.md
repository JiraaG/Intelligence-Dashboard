---
name: radar-quota-ledger
description: >
  QuotaLedger durable: reserve/complete/fail su llm_request_ledger prima di ogni
  tentativo Gemini; RPD half-open; rispettare 429 Retry-After.
when_to_use:
  - classification/quota.py, llm_request_ledger, client Gemini retry
version: 1.0.0
---

## Quando attivare

Modifiche a rate limit, ledger SQL, o retry del classification client.

## Protocollo

```python
reservation_id = await self.quota.reserve(estimated_tokens=..., model=self.model)
try:
    response = await asyncio.wait_for(
        self.client.aio.models.generate_content(...),
        timeout=GEMINI_REQUEST_TIMEOUT,
    )
    await self.quota.complete(reservation_id, actual_tokens)
except asyncio.CancelledError:
    await self.quota.fail(reservation_id)  # o release se provider non avviato
    raise
```

1. **Reserve prima** di ogni tentativo provider (anche retry).
2. **Complete/fail** sulla **stessa** `reservation_id` — mai “ultima riga”.
3. Spacing in-process con `time.monotonic()`; RPD half-open su `RADAR_TIME_ZONE`.
4. On **429**: rispettare `Retry-After`.

## Anti-pattern

- Solo `asyncio.sleep(4)` in-memory come unico rate limit
- `date(created_at) = CURRENT_DATE` ingenuo per RPD
- Skip reserve sui retry di validazione

## SoT

`radar/.ecc/rules/backend.md` Regola 9 + `classification/quota.py` + migration `003_quota_ledger.sql`.
