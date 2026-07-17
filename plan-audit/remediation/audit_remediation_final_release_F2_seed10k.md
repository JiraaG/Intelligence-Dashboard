# Final Release — Fase 2 Seed 10k + budget

**Stato:** PASS  
**Data:** 2026-07-17  
**Branch:** `refactor/testing` @ `7472acd`

---

## Procedura

```text
docker compose exec -T radar-backend python /app/scripts/seed_perf_articles.py \
  --date 2099-01-01 --count 10000
```

- Data dedicata: **2099-01-01** (non tocca day-view “oggi”)
- Non tocca vault / Miniflux
- Seed duration: ~11 s (laptop)

## Misure

| Check | Risultato |
|-------|-----------|
| Rows `published_at=2099-01-01` | **10000** |
| Countries / categories | 100 / 10 |
| `EXPLAIN` map-summary aggregate | **Index Only Scan** `idx_articles_pub_country_cat`; exec **2.5 ms**; buffers hit=13 |
| `EXPLAIN` count by date | **Index Only Scan** `idx_articles_published_at`; exec **2.1 ms** |
| `GET /api/map-summary?date=2099-01-01` | **61 ms**, ~12 KB (summary pins, non 10k marker) |
| `GET /api/articles?date=2099-01-01&country=US&limit=100` | **70 ms**, envelope con pagination |

## Criteri PASS

- [x] Seed completa &lt; 5 min  
- [x] Indici usati (no seq scan full table sulla data seed)  
- [x] Day-view API = aggregati (payload piccolo)  
- [x] Nation open = pagination (limit 100)

## Note

- Dati seed lasciati in DB per smoke FE (date picker `2099-01-01`). Opzionale cleanup:  
  `DELETE FROM articles WHERE published_at = '2099-01-01';`
- XSS/spot FE manuale su data seed: demandabile in Fase 4.

## Decisione

**Fase 2 PASS** — proseguire a Fase 3 (chaos) con backup fresco già presente.
