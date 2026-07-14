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
| LLM SDK             | `google-genai` (SDK ufficiale Google)| `openai`, `anthropic`, `langchain`    |
| Async               | `asyncio` + `asyncio.sleep()`        | `time.sleep()`, `threading.sleep()`   |
| Validazione         | `pydantic` v2 + BaseModel            | Dict non tipizzati, `json.loads()` raw|
| DB Driver           | `asyncpg` (async PostgreSQL)         | `psycopg2`, `SQLAlchemy` ORM          |
| HTTP Client         | `httpx` (async)                      | `requests` (sincrono)                 |
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
# OBBLIGATORIO: struttura a tre livelli
async def run_pipeline_loop():          # Livello 1
    while True:
        try:
            await run_pipeline_cycle()  # Livello 2
        except Exception as e:
            logger.error(...)
        finally:
            await asyncio.sleep(900)

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
`llm_request_ledger` via `classification/quota.py` **prima** della chiamata Gemini.
Aggiornare **quella** reservation id con usage reale. Spacing in-process con
`time.monotonic()`; RPD half-open su `RADAR_TIME_ZONE`. Rispettare `429` + `Retry-After`.

**OBBLIGATORIO:**
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

**VIETATO:**
```python
# NO: solo asyncio.sleep(4) in-memory come unico rate limit
# NO: date(created_at) = CURRENT_DATE per RPD
# NO: complete() sull'"ultima" riga invece che sulla reservation_id
```

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