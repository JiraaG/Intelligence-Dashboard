---
name: radar-api-contract
description: >
  Contratto API Phase 5+: GET /api/map-summary (day view), GET /api/saved-summary
  (vault salvati, no date), GET /api/articles envelope {items,next_cursor,total}
  con saved=true cross-day, PATCH read_status / saved_status. DTO FE, MOCK_MODE
  esplicito, main.py API-only.
when_to_use:
  - Modifiche a main.py, articles_query, article.service, article-mock.service
  - Nuovi endpoint o cambi envelope/paginazione
  - Toggle mock vs produzione
  - Notizie salvate / is_saved
version: 1.1.0
---

## Quando attivare

Lavori su FastAPI REST, query articoli, o servizi Angular che chiamano l’API.

## Contratto Phase 5+

| Vista | Endpoint | Shape |
|-------|----------|--------|
| Day (mappa) | `GET /api/map-summary?date=` | Righe `country_code × primary_category` (+ count/read, lat/lon finite) |
| Saved vault | `GET /api/saved-summary` | Stessa shape di map-summary; filtro `is_saved=true`; **senza date** |
| Nation open | `GET /api/articles?date=&country=` | Envelope `{ items, next_cursor, total }` — page ≤ 100; FE concatena |
| Saved open | `GET /api/articles?saved=true&country=` | Stesso envelope; **ignora date**; solo `is_saved` |
| Read | `PATCH /api/articles/{id}/read_status` | `{ is_read }` → `{ status, is_read, is_saved? }`; unread ⇒ `is_saved=false` |
| Save | `PATCH /api/articles/{id}/saved_status` | `{ is_saved }` → `{ status, is_saved, is_read? }`; save ⇒ `is_read=true` |

- `main.py` = **API-only** (pool, migrations, REST). Ingest solo in `worker.py`.
- FE: `getMapSummary` / `getSavedSummary` / `getArticlesPage` allineati a `article.service.ts` e `article-mock.service.ts`.
- Colonna DB: `articles.is_saved` (migration `010_articles_is_saved.sql`).

## MOCK_MODE

- Token `MOCK_MODE` in `services/mock-mode.token.ts` (default `false`).
- **Vietato** fallback silenzioso su mock se l’API fallisce — errore visibile in toolbar.

## DTO / schema

- Pydantic Gemini: `companies_involved` / `tags` / `infrastructural_entities` = **`str` CSV**.
- FE post-API può usare `string[]` dopo `array_agg` — non confondere i layer.
- Categorie primary: 10 SoT (`Nucleare`…`Sicurezza`). Vietato `Chip`/`Acqua`/`Elettronica` come primary.
- Articolo FE: `is_read?` + `is_saved?` (boolean opzionali).

## Anti-pattern

- Restituire `Article[]` globale del giorno al posto di map-summary
- Inventare campi `reasoning` nello schema strict
- Mettere polling ingest in `main.py`
- Riusare `loadCountryArticles(date, …)` per il vault salvati (serve path `saved=true`)
