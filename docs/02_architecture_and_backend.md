# Architettura e backend

Stack Phase **0–6 DONE / GATE VERDE**. Piano master: [`plan_impl_phase_0_6.md`](../plan-audit/complete/plan_impl_phase_0_6.md). Scoreboard: [`plan_impl_phase_0_6_execution.md`](../plan-audit/complete/plan_impl_phase_0_6_execution.md). SoT LLM: [`sot_llm_multi_model_fallback.md`](../plan-audit/complete/sot_llm_multi_model_fallback.md). Codice: `radar/backend/`.

---

## Separazione API / worker

| Processo | Entry | Ruolo |
|----------|-------|--------|
| API | `python -m uvicorn` / `main.py` | FastAPI: pool, migrazioni, REST, health |
| Ingest | `python -m app.worker` (`radar-worker`) | Polling Miniflux, coda bounded, LLM multi-provider, commit/outbox, heartbeat |

Non avviare due worker leader: advisory lock session-level. L’API non esegue ingest nel lifespan.

```mermaid
flowchart TD
  Start([Inizio ciclo worker]) --> Fetch[Miniflux unread ~48h]
  Fetch --> Loop{Prossimo articolo?}
  Loop -->|no| Done([Fine ciclo / sleep poll])
  Loop -->|sì| Dedup{URL già in DB?}
  Dedup -->|sì| Loop
  Dedup -->|no| Parse[Sanitize HTML]
  Parse --> Cx[Complexity v2.2 → lane SIMPLE/COMPLEX]
  Cx --> Quota[QuotaLedger reserve per lane]
  Quota --> LLM[LLM structured output]
  LLM -->|invalid / retryable| Retry{Tentativi rimasti?}
  Retry -->|sì| LLM
  Retry -->|no| Fallback[Fallback entity XX]
  LLM -->|ok| Commit[Tx DB + article_outbox]
  Fallback --> Commit
  Commit --> Vault[Reconcile vault atomico]
  Vault -->|completed| Mark[Miniflux mark-read]
  Mark --> Loop
```

Moduli sotto `radar/backend/app/`:

1. **`core/`** — config bounded, pool asyncpg, `migrations.py`, logging, heartbeat, **`llm_lanes.py`** (provider/dialect/lane)
2. **`extraction/`** — client Miniflux (httpx, byte limits, retry), parser HTML, dedup
3. **`classification/`** — client Gemini (`google-genai`) + OpenAI-compat httpx (`deepseek`/`openai`/`glm`/`grok`; dialect); `claude` = stub; **`complexity.py`** v2.2; **`cooldown.py`**; `quota.py` per-lane; prompts (no CoT); validator Pydantic strict
4. **`commit/`** — commit atomico, outbox, vault `yaml.safe_dump` + write atomica
5. **`api/`** — query helpers Phase 5 (`articles_query.py`)
6. **`scripts/`** — ops `requeue_articles.py` — dettaglio [runbook](../radar/docs/runbook.md)

---

## Classification (LLM)

- Schema: `GeopoliticalArticleSchema` — `ConfigDict(strict=True, extra="forbid")`
- Campi multi-valore **`str` CSV** (`companies_involved`, `tags`, `infrastructural_entities`, `related_countries`) — non `List[str]`
- Nessun campo `reasoning` / Chain-of-Thought
- `build_gemini_response_schema()` sanitizza lo schema per l’API Google
- 10 categorie: Nucleare, Energia, Infrastrutture, Geopolitica, Economia, Tecnologia, Spazio, Ambiente, Salute, Sicurezza
- Prompt SoT: `classification/prompts.py` — fallback `Tecnologia`+`XX` **ristretto** (solo assenza di fatti geo/industriali/politici); albero decisionale anti-`XX`; multilaterali = 1 primary + `related_countries` CSV
- Fallback geografico su fallimento irreversibile: paese `XX`, categoria `Infrastrutture` (vedi `validator.py`)
- Provider: `gemini` \| `deepseek` \| `openai` \| `glm` \| `grok` \| `claude` (**stub**; Messages API non implementata)
- Dialect OpenAI-compat: deepseek=`thinking`; openai/glm/grok=`stock`; via httpx (**no** package `openai`)
- Quote: `llm_request_ledger` via `QuotaLedger` — limiti **per lane** `LLM_SIMPLE_*` / `LLM_COMPLEX_*` (`0` = unmanaged); soft-trim worker = `LLM_SIMPLE.rpd` se >0; free=RPM/RPD(+TPM), paid=BUDGET; legacy fill-gap — **non** `COUNT(*)` su `articles` per RPD
- **Limiti e cambio modello (Profilo A hybrid):** RPM/TPM pieni → **attesa** sulla stessa lane (non si passa all’altro modello). **RPD esaurita** / cooldown / 429 daily → `QuotaDailyExceeded` + residual **cross-lane** (es. Gemini SIMPLE → DeepSeek COMPLEX e viceversa). Soft-trim: se RPD SIMPLE piena ma residual COMPLEX distinto, il ciclo **non** iberna (failover per-articolo). Caps Studio tipici Flash Lite: RPM≤12, TPM=250K, RPD=500 (VERIFY_IN_STUDIO).
- Routing: SIMPLE → `LLM_SIMPLE_*`; BORDERLINE+COMPLEX → `LLM_COMPLEX_*`; residual SIMPLE↔COMPLEX se identity diversa; Profili A–E in `.env.example` + SoT
- Periodicità ingest: `WORKER_POLL_INTERVAL_SECONDS` (default 900)

### Cooldown modelli

Hard-fail prolungati: tabella `llm_model_cooldown` (migrazione `009_llm_model_cooldown.sql`), codice `classification/cooldown.py`, knob `LLM_MODEL_COOLDOWN_HOURS`. Non confondere con `429` + `Retry-After` brevi. Clear cooldown + re-ingest: [runbook](../radar/docs/runbook.md) (`docker compose exec -T radar-worker python -m app.scripts.requeue_articles N`).

---

## Persistenza e migrazioni

Schema applicato da `core/migrations.py` + SQL ordinati in `radar/backend/migrations/`:

| File | Ruolo |
|------|--------|
| `001_initial.sql` | Schema base articles/companies/tags |
| `002_pipeline_outbox_and_quotas.sql` | article_outbox |
| `003_quota_ledger.sql` | `llm_request_ledger` |
| `004_worker_heartbeat.sql` | heartbeat leader |
| `005_quota_ledger_align.sql` | allinea ledger legacy |
| `006_quota_ledger_legacy_nulls.sql` | null legacy + request_type |
| `007_articles_query_indexes.sql` | indici Phase 5 |
| `008_outbox_miniflux_marked_at.sql` | mark-read retry / `miniflux_marked_at` |
| `009_llm_model_cooldown.sql` | cooldown durable (provider, model) |
| `010_articles_is_saved.sql` | `articles.is_saved` + indice parziale (vault Notizie Salvate) |
| `011_articles_related_countries.sql` | Aggiunta campo related_countries per grafo geospaziale |

Commit: transazione DB + riga outbox → reconcile vault → mark-read Miniflux **solo** se outbox `completed`.

### Ops scripts

Solo `app/scripts/requeue_articles.py`. Comando canonico (da `radar/`, stack up):

```bash
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20 --dry-run
docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20
docker compose restart radar-worker
```

Effetti collaterali e prerequisiti: [runbook](../radar/docs/runbook.md).

---

## Health

| Path | Semantica |
|------|-----------|
| `/health/live` | Processo su — healthcheck Compose |
| `/health` | Alias live |
| `/health/ready` | Pool + migrazione heartbeat + freshness leader; 503 non deve restartare l’API |

---

## API REST

CORS: middleware solo se `CORS_ALLOW_ORIGINS` non vuoto; metodi `GET`, `PATCH`, `OPTIONS`. Dietro Nginx same-origin: **lasciare vuoto**. Nessuna auth applicativa.

| Metodo | Endpoint | Parametri | Risposta |
|--------|----------|-----------|----------|
| GET | `/api/articles` | `date` (obbl. salvo `saved=true`), `country`, `category`, `sentiment`, `relevance_level`, `cursor`, `limit` ≤ 100, `saved?` | `{ items, next_cursor, total }` — con `saved=true` ignora `date`, filtra `is_saved` |
| GET | `/api/map-summary` | `date`, `sentiment?`, `relevance_level?` | Array `country_code × primary_category` + count/read + lat/lon finite |
| GET | `/api/map-relations` | `date`, `sentiment?`, `relevance_level?` | Righe undirected `source_country ↔ target_country` per categoria (+ volume). Semantica **star** v1: un arco per ogni coppia `(country_code, related)` via `LEAST/GREATEST` — **non** clique tra soli `related_countries` (es. US+IT+FR → US–IT e US–FR, non IT–FR). `XX` escluso. |
| GET | `/api/saved-summary` | `sentiment?`, `relevance_level?` | Stessa shape di map-summary; solo `is_saved=true`; **senza date** |
| GET | `/api/countries` | `date`, filtri opzionali | Rollup paese (`categories`, `article_count`) |
| PATCH | `/api/articles/{id}/read_status` | `{ "is_read": bool }` | `{ "status", "is_read", "is_saved"? }` — unread ⇒ `is_saved=false` |
| PATCH | `/api/articles/{id}/saved_status` | `{ "is_saved": bool }` | `{ "status", "is_saved", "is_read"? }` — save ⇒ `is_read=true` |

Companies/tags sugli articoli: join **LATERAL** (no Cartesian `array_agg` classico). UI giorno: preferire **map-summary**; lista piena in nation-open day **o** vault salvati (`saved=true`, FE pagina fino a `next_cursor` null).

---

## Reti Compose

Vedi `radar/docker-compose.yml`:

- **`radar-edge`**: frontend ↔ backend
- **`radar-data`**: backend, worker, db, miniflux (frontend mai qui)

Ops/backup: [`radar/ops/README.md`](../radar/ops/README.md). Runbook: [`radar/docs/runbook.md`](../radar/docs/runbook.md).
