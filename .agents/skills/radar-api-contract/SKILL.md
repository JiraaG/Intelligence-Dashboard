---
name: radar-api-contract
description: >
  Contratto API Phase 5+: GET /api/map-summary (day view), GET /api/saved-summary
  (vault salvati, no date), GET /api/articles envelope {items,next_cursor,total}
  con saved=true cross-day, GET /api/map-relations (archi relazioni),
  PATCH read_status / saved_status, POST webhook (HMAC), e GET events (SSE).
  DTO FE, MOCK_MODE esplicito, main.py API-only.
when_to_use:
  - Modifiche a main.py, articles_query, article.service, article-mock.service
  - Nuovi endpoint o cambi envelope/paginazione
  - Toggle mock vs produzione
  - Notizie salvate / is_saved
  - Webhook di ingestione o streaming SSE
version: 1.3.0
---

## Quando attivare

Lavori su FastAPI REST, query articoli, o servizi Angular che chiamano l’API.

## Contratto Phase 5+

| Vista | Endpoint | Shape |
|-------|----------|--------|
| Day (mappa) | `GET /api/map-summary?date=` | Righe `country_code × primary_category` (+ count/read, lat/lon finite) |
| Relations | `GET /api/map-relations?date=` | Righe undirected star `primary↔each related` (`LEAST/GREATEST` × categoria; non clique). FE: archi MapLibre great-circle (default) via `visibleMapRelations` (toolbar **RELAZIONI ATTIVE**, default 0 archi); legacy Leaflet `relationsPane`; click → `loadRelationArticles` bilaterale |
| Saved vault | `GET /api/saved-summary` | Stessa shape di map-summary; filtro `is_saved=true`; **senza date** |
| Nation open | `GET /api/articles?date=&country=` | Envelope `{ items, next_cursor, total }` — page ≤ 100; FE concatena. Items include optional FinOps denorm fields, LATERAL ledger tokens/cost (`prompt_tokens`, `completion_tokens`, `cached_prompt_tokens`, `estimated_cost_usd`, `llm_execution_time_ms`, `llm_request_count`), and resolved `feed_url` |
| Saved open | `GET /api/articles?saved=true&country=` | Stesso envelope; **ignora date**; solo `is_saved` |
| Read | `PATCH /api/articles/{id}/read_status` | `{ is_read }` → `{ status, is_read, is_saved? }`; unread ⇒ `is_saved=false` |
| Save | `PATCH /api/articles/{id}/saved_status` | `{ is_saved }` → `{ status, is_saved, is_read? }`; save ⇒ `is_read=true` |
| Webhook ingest | `POST /api/webhooks/miniflux` | Header `X-Miniflux-Signature` (HMAC-SHA256 hex sul raw body); event utile `new_entries`. Risposta `202` accepted / `401` firma / `ignored` altri eventi. **Trigger-only** → `NOTIFY radar_worker_trigger`. Nessuna classificazione in `main.py`. |
| SSE real-time | `GET /api/articles/events` | `text/event-stream`; event `article_processed` + data JSON `{article_id,country_code,primary_category,published_at}`; commenti `: ping` ogni 30s; header `X-Accel-Buffering: no`. |
| Metrics Summary | `GET /api/metrics/summary?from=&to=` | JSON `{from, to, total_articles, total_clean_chars, total_clean_words, avg_pipeline_latency_ms, avg_embedding_time_ms, llm: {total_requests, total_prompt_tokens, total_completion_tokens, total_cached_prompt_tokens, cache_hit_rate_pct, avg_execution_time_ms, total_estimated_cost_usd, models_breakdown: [{model, provider, requests_count, total_tokens}]}, dedup: {total_events, url_exact_count, semantic_vector_count, content_hash_count}}` |
| Metrics Status | `GET /api/metrics/status` | JSON `{as_of, timezone, level, estimated_cost_usd_today, l1_likely_active, l1_reason, models: [{role, lane, provider, model, rpd_used, rpd_limit, cooling_down, cooldown_until}], llm}` |
| Metrics by-feed | `GET /api/metrics/by-feed?from=&to=` | JSON `{from, to, items: [{feed_id, feed_domain, feed_title, article_count, total_clean_chars, avg_clean_chars, avg_pipeline_latency_ms, avg_embedding_time_ms}]}` |
| Metrics dedup | `GET /api/metrics/dedup?from=&to=` | JSON `{from, to, items: [{dedup_kind, action_taken, event_count, avg_cosine_distance, avg_confidence}]}` |

- `main.py` = **API-only** (pool, migrations, REST, webhook, SSE). Ingest solo in `worker.py`.
- FE: `getMapSummary` / `getSavedSummary` / `getArticlesPage` allineati a `article.service.ts` e `article-mock.service.ts`.
- Colonna DB: `articles.is_saved` (migration `010_articles_is_saved.sql`) e `articles.related_countries` (migration `011_articles_related_countries.sql`).

## MOCK_MODE

- Token `MOCK_MODE` in `services/mock-mode.token.ts` (default `false`).
- **Vietato** fallback silenzioso su mock se l’API fallisce — errore visibile in toolbar.
- Se `MOCK_MODE` è `true`, il frontend **non** deve connettersi ad `EventSource('/api/articles/events')`.

## DTO / schema

- Pydantic Gemini: `companies_involved` / `tags` / `infrastructural_entities` = **`str` CSV**.
- FE post-API può usare `string[]` dopo `array_agg` — non confondere i layer.
- Categorie primary: 10 SoT (`Nucleare`…`Sicurezza`). Vietato `Chip`/`Acqua`/`Elettronica` come primary.
- Articolo FE: `is_read?` + `is_saved?` (boolean opzionali).

## Anti-pattern

- Restituire `Article[]` globale del giorno al posto di map-summary
- Inventare campi `reasoning` nello schema strict
- Mettere polling ingest o classificazione in `main.py`
- Riusare `loadCountryArticles(date, …)` per il vault salvati (serve path `saved=true`)
- Fare LISTEN PostgreSQL dal pool asyncpg o per-client SSE
- Soft-refresh FE che sostituisce tutte le reference `Article` del carosello (viola sidebar freeze UX)
- Omettere verifica HMAC o usare `==` invece di `hmac.compare_digest`
