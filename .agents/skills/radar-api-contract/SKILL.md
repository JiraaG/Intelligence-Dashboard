---
name: radar-api-contract
description: >
  Contratto API Phase 5: GET /api/map-summary (day view) e GET /api/articles
  envelope {items,next_cursor,total}. DTO FE, MOCK_MODE esplicito, main.py API-only.
when_to_use:
  - Modifiche a main.py, articles_query, article.service, article-mock.service
  - Nuovi endpoint o cambi envelope/paginazione
  - Toggle mock vs produzione
version: 1.0.0
---

## Quando attivare

Lavori su FastAPI REST, query articoli, o servizi Angular che chiamano l’API.

## Contratto Phase 5

| Vista | Endpoint | Shape |
|-------|----------|--------|
| Day (mappa) | `GET /api/map-summary` | Righe `country_code × primary_category` (+ count/read, lat/lon finite) |
| Nation open | `GET /api/articles` | Envelope `{ items, next_cursor, total }` — page ≤ 100; FE concatena |

- `main.py` = **API-only** (pool, migrations, REST). Ingest solo in `worker.py`.
- FE: `getMapSummary` / `getArticlesPage` allineati a `article.service.ts` e `article-mock.service.ts`.

## MOCK_MODE

- Token `MOCK_MODE` in `services/mock-mode.token.ts` (default `false`).
- **Vietato** fallback silenzioso su mock se l’API fallisce — errore visibile in toolbar.

## DTO / schema

- Pydantic Gemini: `companies_involved` / `tags` / `infrastructural_entities` = **`str` CSV**.
- FE post-API può usare `string[]` dopo `array_agg` — non confondere i layer.
- Categorie primary: 10 SoT (`Nucleare`…`Sicurezza`). Vietato `Chip`/`Acqua`/`Elettronica` come primary.

## Anti-pattern

- Restituire `Article[]` globale del giorno al posto di map-summary
- Inventare campi `reasoning` nello schema strict
- Mettere polling ingest in `main.py`
