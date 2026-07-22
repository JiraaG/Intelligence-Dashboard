# Regole Backend — Path-Scope: `backend/**`
> **Scope:** Queste regole si applicano ESCLUSIVAMENTE ai file in `backend/`.
> Non caricare queste regole durante il lavoro su `frontend/` o su file Docker.
> **Priorità:** ALTA — questi vincoli sovrascrivono qualsiasi comportamento default dell'agente.

---

## Regola 0: Versionamento Dipendenze — Direttiva Critica (Python 3.14 / Windows)

> **⛔ DIVIETO ASSOLUTO:** Non bloccare mai le dipendenze con operatori `==` nel file `requirements.txt`.
> Il progetto è sviluppato con **Python 3.14 su Windows**. Le versioni rigide di pacchetti che includono
> estensioni C/Rust (come `asyncpg` e `pydantic`) causano **fallimenti di compilazione a runtime** a causa
> dell'incompatibilità dell'API PyO3 con Python 3.14.

**OBBLIGATORIO — Usare sempre operatori `>=` (minimum floor):**
```text
# CORRETTO: floor minimo garantito, pip sceglie la release compatibile più recente
asyncpg>=0.31.0
pydantic>=2.10.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
httpx>=0.27.0
google-genai>=0.8.0
python-dotenv>=1.0.1
```

**VIETATO — Pin rigido con `==`:**
```text
# SBAGLIATO: blocca su versioni che potrebbero non compilare su Windows con Python 3.14
asyncpg==0.29.0
pydantic==2.9.2
```

Quando aggiungi una nuova dipendenza al `requirements.txt`:
1. Usa sempre `>=X.Y.Z` dove X.Y.Z è la versione minima testata/documentata.
2. Non aggiungere un upper bound (`<`) salvo incompatibilità **documentate e verificate**.
3. Esegui `pip install -r requirements.txt` su un ambiente Windows + Python 3.14 per verificare.

---

## Stack Tecnologico Obbligatorio

| Componente          | Tecnologia Obbligatoria              | VIETATO                               |
|---------------------|--------------------------------------|---------------------------------------|
| LLM SDK             | `google-genai` (Gemini) + **httpx** OpenAI-compatible (`deepseek`/`openai`/`glm`/`grok`) | Package `openai`, `anthropic`, `langchain` |
| Async               | `asyncio` + `asyncio.sleep()`        | `time.sleep()`, `threading.sleep()`   |
| Validazione         | `pydantic` v2 + BaseModel            | Dict non tipizzati, `json.loads()` raw|
| DB Driver           | `asyncpg` (async PostgreSQL)         | `psycopg2`, `SQLAlchemy` ORM          |
| HTTP Client         | `httpx` (async) — Miniflux + OpenAI-compat LLM | `requests` (sincrono)                 |
| HTML Sanitize       | `re` stdlib o `html.parser` stdlib   | `beautifulsoup4` come dipendenza extra |

---

## Regola 1: Il Demone Non Si Ferma Mai

Il loop vive in `worker.py` (`run_pipeline_loop`). Non deve terminare per un singolo
articolo fallito o per un errore Gemini. `CancelledError` va sempre re-raised.
Lo sleep di polling **non** sta in un `finally` di shutdown.

**OBBLIGATORIO:**
```python
async def run_pipeline_loop() -> None:
    while True:
        try:
            await run_pipeline_cycle()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Errore ciclo: %s", e, exc_info=True)
        await asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)
```

**VIETATO:**
```python
# NO: time.sleep blocca l'event loop
import time
time.sleep(900)

# NO: Exception non gestita fa crashare il demone
async def run_pipeline_cycle():
    result = await call_gemini()  # Se lancia eccezione, il processo muore

# NO: sleep di polling dentro finally durante shutdown
finally:
    await asyncio.sleep(900)
```

---

## Regola 2: Deduplicazione Obbligatoria Pre-Gemini

Prima di inviare QUALSIASI articolo a Gemini, controllare il database.
La chiamata a Gemini costa quota API. Non sprecarla su duplicati.

**OBBLIGATORIO:**
```python
# Controlla PRIMA di chiamare Gemini
exists = await conn.fetchval(
    "SELECT EXISTS(SELECT 1 FROM articles WHERE source_url = $1)",
    article_url
)
if exists:
    continue  # Skip immediato, zero token sprecati
```

In aggiunta alla dedup URL: dedup **semantica** via embeddings + `pgvector` (migrazione `012`); su near-dup, `quality:compare` su lane COMPLEX decide keep vs replace in-place.

**VIETATO:**
```python
# NO: Chiamata Gemini senza controllo duplicati
result = await call_gemini(article)  # Potrebbe essere un duplicato!
await save_to_db(result)
```

---

## Regola 3: Gestione Errori a Tre Livelli

**Livello 1 (Demone)** — cattura tutto, non fermarsi mai
**Livello 2 (Ciclo)** — un ciclo fallisce, il prossimo parte ugualmente
**Livello 3 (Articolo)** — un articolo fallisce, gli altri vengono processati

```python
# OBBLIGATORIO: struttura a tre livelli (allineata a Regola 1 / worker.py)
async def run_pipeline_loop():          # Livello 1
    while True:
        try:
            await run_pipeline_cycle()  # Livello 2
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(...)
        # Sleep di polling FUORI dal finally di shutdown
        await asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)

async def run_pipeline_cycle():
    articles = await fetch_miniflux_articles()
    for article in articles:
        try:
            await process_article(article)  # Livello 3
        except Exception as e:
            logger.error(f"Articolo fallito: {article.get('url')}: {e}")
            continue  # Vai al prossimo articolo
```

---

## Regola 4: Variabili d'Ambiente Obbligatorie

Le seguenti variabili devono essere lette SEMPRE da `os.environ` o da `.env` via `python-dotenv`.
**NON SCRIVERE MAI un valore segreto reale nel codice sorgente.**

```python
import os
from dotenv import load_dotenv

load_dotenv()  # Carica .env in sviluppo locale

# Lettura variabili (lancerà KeyError se assente → fail fast in avvio)
GEMINI_API_KEY      = os.environ["GEMINI_API_KEY"]
MINIFLUX_API_URL    = os.environ["MINIFLUX_API_URL"]
MINIFLUX_API_KEY    = os.environ["MINIFLUX_API_KEY"]
DATABASE_URL        = os.environ["DATABASE_URL"]
```

---

## Regola 5: Type Hints su Tutte le Funzioni Pubbliche

```python
# OBBLIGATORIO
async def fetch_miniflux_articles(api_url: str, api_key: str) -> list[dict]:
    ...

async def is_article_duplicate(conn: asyncpg.Connection, source_url: str) -> bool:
    ...

async def insert_article(conn: asyncpg.Connection, data: GeopoliticalArticleSchema) -> int:
    ...

# VIETATO
async def process(x):  # Nessun type hint
    ...
```

---

## Regola 6: Logging Strutturato Obbligatorio

Usare `logging` stdlib (non `print()`). Ogni operazione significativa deve essere loggata.

```python
import logging

# Configurazione all'avvio (in main.py)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Pattern obbligatori di logging
logger.info(f"Ciclo pipeline avviato. Trovati {len(articles)} articoli da Miniflux")
logger.debug(f"Articolo duplicato ignorato: {source_url}")
logger.warning(f"Gemini fallback attivato per: {title[:60]}")
logger.error(f"Errore inserimento DB: {e}", exc_info=True)
```

---

## Regola 7: Schema Pydantic Immutabile

Lo schema `GeopoliticalArticleSchema` è il contratto tra backend e frontend.
**Non modificare field names o tipi senza un task esplicito che aggiorna anche il database.**

---

## Regola 8: Entrypoint di Startup (API + Worker)

Phase 2: stessa immagine, due processi.
- API: `WORKDIR=/app`, `PYTHONPATH=/app`, `uvicorn app.main:app`
- Worker: `python -m app.worker`

**API Phase 5+ (query layer):**
- Day: `GET /api/map-summary` → righe aggregate `country_code × primary_category`
- Relations: `GET /api/map-relations` → righe aggregate relazioni undirected `source_country ↔ target_country` per categoria (**star** primary↔each related via `LEAST/GREATEST`; non clique tra related; `XX` escluso)
- Saved vault: `GET /api/saved-summary` → stessa shape, `is_saved=true`, **senza date**
- Nation: `GET /api/articles` → envelope `{ items, next_cursor, total }` (keyset, page ≤ 100; include `related_countries` string array)
- Saved open: `GET /api/articles?saved=true&country=` → stesso envelope, ignora `date`
- `PATCH .../read_status` (unread ⇒ `is_saved=false`); `PATCH .../saved_status` (save ⇒ `is_read=true`)
- Implementazione SQL: `backend/app/api/articles_query.py` + migrazioni `007` + `010_articles_is_saved` + `011_articles_related_countries`

**OBBLIGATORIO (Dockerfile / Compose):**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
# worker Compose override:
python -m app.worker
```

**VIETATO:**
```bash
# NO: avviare l'ingestione dentro il processo API (lifespan FastAPI)
# NO: TaskGroup unbounded su tutte le entry Miniflux
```

---

## Regola 9: Quote LLM Durable (QuotaLedger)

Ogni tentativo provider (incluso retry/validazione) deve **reservare** capacità su
`llm_request_ledger` via `classification/quota.py` **prima** della chiamata Gemini **o** DeepSeek.
Aggiornare **quella** reservation id con usage reale. Spacing in-process con
`time.monotonic()`; RPD half-open su `RADAR_TIME_ZONE`. Rispettare `429` + `Retry-After`.
Hard-fail (RPD day ledger → `QuotaDailyExceeded`, 402, 404 model, 5xx esauriti, 429 daily) → `llm_model_cooldown` 24h, poi **residual** altra lane.
**RPM/TPM pieni → attesa stessa lane** (non cross). Soft-trim worker: se RPD SIMPLE piena ma residual COMPLEX distinto → **non** ibernare il ciclo.

**Limiti per lane (obbligatorio):**
- `LLM_SIMPLE_RPM/TPM/RPD` e `LLM_COMPLEX_*` — contatori separati via `purpose=classify:{lane}`
- `0` = dimensione unmanaged su quella lane
- Legacy `LLM_RPM` / `DEEPSEEK_RPM` = **alias fill-gap**, non tetto globale
- Soft-trim worker = solo `LLM_SIMPLE.rpd` se `> 0` (bypass ibernazione se residual COMPLEX distinto)
- Free → RPM/RPD(+TPM) `> 0`; paid → RPM/RPD `= 0` + `*_BUDGET_USD_DAY` / 402

**OBBLIGATORIO:**
```python
reservation_id = await self.quota.reserve(
    estimated_tokens=..., model=ref.model, lane=ref.quota_lane, provider=ref.provider
)
try:
    # gemini: google-genai | openai-compat: classification/deepseek.py (httpx)
    response = await provider_call(...)
    await self.quota.complete(reservation_id, actual_tokens)
except asyncio.CancelledError:
    await self.quota.fail(reservation_id)  # o release se provider non avviato
    raise
```

**VIETATO:**
```python
# NO: solo asyncio.sleep(4) in-memory come unico rate limit
# NO: date(created_at) = CURRENT_DATE per RPD
# NO: complete() sull'"ultima" riga invece che sulla reservation_id
# NO: package openai / anthropic / langchain
# NO: trattare LLM_RPM come tetto globale shared tra lane
```

---

## Regola 9b: Lane LLM via env (complexity routing v2.2)

Routing opzionale (`LLM_ROUTING_MODE=off|complexity`). Lane = heuristic in
`classification/complexity.py`: **rischio estrazione schema** (G/E/X), non lunghezza sola.

| Env | Ruolo |
|-----|--------|
| `LLM_SIMPLE_PROVIDER` / `LLM_SIMPLE_MODEL` / `*_REASONING_EFFORT` | Solo lane **SIMPLE** (tipico `effort=none`) |
| `LLM_SIMPLE_RPM/TPM/RPD` / `*_BUDGET_USD_DAY` | Limiti lane SIMPLE (`0` = unmanaged) |
| `LLM_COMPLEX_PROVIDER` / `LLM_COMPLEX_MODEL` / `*_REASONING_EFFORT` | **BORDERLINE + COMPLEX** + escalate (tipico `effort=high`) |
| `LLM_COMPLEX_RPM/TPM/RPD` / `*_BUDGET_USD_DAY` | Limiti lane COMPLEX (`0` = unmanaged) |
| `GEMINI_MODEL_FALLBACKS` | Cascata CSV extra **solo** se provider lane = gemini |
| `DEEPSEEK_*` / `LLM_RPM` | Legacy key/model/effort/base + alias fill-gap quote |
| `LLM_ROUTING_SHADOW=true` | Logga lane; chiama sempre catena SIMPLE |
| `WORKER_POLL_INTERVAL_SECONDS` | Cadenza ciclo ingest (default 900) |

**Lane v2.2:** L sola → SIMPLE; 1 di {G,E,X} → BORDERLINE; ≥2 famiglie (L solo in combo) → COMPLEX.
`geo_marker` da solo richiede `body_len ≥ 1500`; ≥2 country names → G sempre.
Residual SIMPLE↔COMPLEX se identity diversa (fattura `ref.quota_lane`).
`PROVIDER` ∈ {gemini, deepseek, openai, glm, grok, claude}; OpenAI-compat dialect:
deepseek → thinking; openai|glm|grok → stock. `claude` = stub.

**Invarianti:** stesso `content[:4000]` su tutte le lane; schema/prompt immutabili;
OpenAI-compat riceve `model=` + dialect da provider (`deepseek` = thinking; `openai`/`glm`/`grok` = stock);
mai hardcodare API key; mai commit `.env`; no package `openai`.

SoT: `plan-audit/complete/sot_llm_multi_model_fallback.md` + skill `radar-quota-ledger`.

---

## Regola 10: Logging.py — Fallback Graceful per Permessi File

`makedirs` della directory `logs/` e `RotatingFileHandler` DEVONO essere in try/except.
Con `WORKDIR=/app` e user non-root, `/app/logs` può non essere scrivibile: il console handler resta obbligatorio.

**OBBLIGATORIO:**
```python
try:
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(log_file, ...)
    root_logger.addHandler(file_handler)
except OSError as e:
    root_logger.warning("File log non disponibile: %s. Solo console.", e)
```

**VIETATO:**
```python
# NO: Crash all'avvio se la directory logs/ non esiste o non è scrivibile
os.makedirs(log_dir, exist_ok=True)  # Senza try/except prima del console handler
```

---

## Criteri di Accettazione Automatici

Questi pattern nel codice causano un BLOCCO immediato:

| Pattern Vietato                          | Motivo                                    |
|------------------------------------------|-------------------------------------------|
| `time.sleep()`                           | Blocca event loop async                   |
| `except: pass`                           | Swallowed exception senza logging         |
| `except Exception: continue` (senza log) | Errore silenzioso                         |
| `GEMINI_API_KEY = "AIzaSy..."`           | Segreto hardcoded                         |
| `call_gemini()` prima di `SELECT EXISTS` | Manca deduplicazione pre-Gemini           |
| `requests.get()` al posto di `httpx`     | Chiamata sincrona in contesto async       |
| Funzione pubblica senza type hints       | Contratto di interfaccia mancante         |
| Ingestione nel lifespan di `main.py`     | Deve vivere in `worker.py` / `radar-worker` |
| Solo `asyncio.sleep(4)` senza ledger     | Quote non durable cross-process           |
| `os.makedirs()` senza try/except nei log | Crash startup per permessi container      |
| Swallow di `CancelledError`              | Shutdown non cancellabile                 |

---

## Regola 11: LISTEN/NOTIFY PostgreSQL — connessioni dedicate (Fase B)

> **DIVIETO:** Usare `async with pool.acquire() as conn` per `LISTEN` di lunga durata.
> Sottrarrebbe slot permanenti al pool (`max_size` tipico 10) e causerebbe starvation.

**OBBLIGATORIO:**
- Worker: connessione dedicata `await asyncpg.connect(DATABASE_URL)` per `LISTEN radar_worker_trigger` (distinta da `lock_conn` leadership).
- API FastAPI: **una sola** connessione dedicata nel `lifespan` per `LISTEN radar_article_processed`, con fan-out in-process (`SSEBroadcastManager`) verso i client SSE.
- `NOTIFY` di breve durata può usare connessioni del pool (`pg_notify`).

**VIETATO:**
- Un `LISTEN` per ogni client SSE.
- Tenere `LISTEN` su connessioni ottenute dal pool HTTP request-scoped.