# PIANO DI IMPLEMENTAZIONE BACKEND DEFINITIVO - MODULO RADAR (ECC ARCHITECTURE)

Il presente documento definisce la specifica tecnica ufficiale e il piano di sviluppo del modulo backend per il progetto **Radar Informativo Globale**. L'architettura è strutturata seguendo il paradigma **ECC (Extraction, Classification, Commit)** ed è progettata per operare al 100% in un ambiente containerizzato Docker ed essere nativamente **cross-platform e multi-dispositivo** (compatibile con host Windows, macOS e Linux).

---

## 1. ARCHITECTURAL MAP & ECC REALIGNMENT

L'architettura del backend si sviluppa all'interno della cartella `backend/app/`, strutturandosi in moduli indipendenti disaccoppiati, conformemente alla filosofia del framework ECC (modularità, testabilità unitaria e isolamento spaziale dei contesti).

### Struttura dei File e Taggatura dello Stato

Di seguito viene mappata l'esatta struttura dei file del backend e dell'infrastruttura di allineamento, con indicazione esplicita dello stato di ciascun file:

```
radar/
├── [IMPLEMENTED] docker-compose.yml       # Setup di orchestrazione con healthcheck e volumi relativi
├── [IMPLEMENTED] .env                     # File locale delle credenziali (non committato)
├── [IMPLEMENTED] .env.example             # Template pubblico delle variabili d'ambiente
├── backend/
│   └── app/
│       ├── [IMPLEMENTED] main.py           # Entrypoint, FastAPI Lifespan, API Router e Background Loop
│       ├── [IMPLEMENTED] requirements.txt # Dipendenze Python cross-platform (compatibili Windows/POSIX)
│       ├── [IMPLEMENTED] core/          # Sotto-sistema di bootstrap e configurazione globale
│       │   ├── [IMPLEMENTED] config.py  # Gestione chiavi API e variabili con fallback automatico
│       │   ├── [IMPLEMENTED] database.py # Client DB asyncpg (no SQLAlchemy) e bootstrap DDL schema
│       │   └── [IMPLEMENTED] logging.py # Logging strutturato rotante
│       ├── [IMPLEMENTED] extraction/    # LAYER E: Ingestione e Sanitizzazione
│       │   ├── [IMPLEMENTED] __init__.py
│       │   ├── [IMPLEMENTED] client.py  # Client API asincrono Miniflux
│       │   ├── [IMPLEMENTED] parser.py  # Rimozione tag HTML e sanitizzazione
│       │   └── [IMPLEMENTED] state.py   # Deduplicazione URL tramite PostgreSQL
│       ├── [IMPLEMENTED] classification/ # LAYER C: API Google Gemini
│       │   ├── [IMPLEMENTED] __init__.py
│       │   ├── [IMPLEMENTED] client.py  # Client Google GenAI SDK (gemma-4-31b)
│       │   ├── [IMPLEMENTED] prompts.py # Prompt di sistema strutturati e istruzioni CoT
│       │   └── [IMPLEMENTED] validator.py # Schema Pydantic e logica correttiva (Retry)
│       └── [IMPLEMENTED] commit/                # LAYER C: Persistenza e Routing
│           ├── [IMPLEMENTED] __init__.py
│           ├── [IMPLEMENTED] db_commit.py       # Commit transazionale relazionale su PostgreSQL (asyncpg puro)
│           ├── [IMPLEMENTED] factory.py         # Markdown Generator (frontmatter piatto Obsidian)
│           ├── [IMPLEMENTED] router.py  # Semantic Routing, Bootstrap del Vault e Slugification NTFS
│           └── [IMPLEMENTED] lock.py            # File Locking concorrente cross-platform (filelock)
└── .ecc/
    ├── [IMPLEMENTED] rules/
    │   ├── [IMPLEMENTED] backend.md        # Regole di codifica backend e divieti
    │   └── [IMPLEMENTED] docker.md         # Linee guida containerizzazione e porte
    └── agents/
        ├── [IMPLEMENTED] pipeline-engineer.md   # Prompt agente per il flusso dati
        └── [IMPLEMENTED] geo-data-architect.md  # Prompt agente per lo schema dati e il Vault
```

---

## 2. AGENTIC LIFECYCLE & INFRASTRUCTURE EVOLUTION

Ereditando i principi operativi definiti in `AGENTS.md` e `RULES.md` del repository ECC originale, lo sviluppo dell'infrastruttura segue un ciclo di vita incrementale:

1. **Allineamento dei Prompt degli Agenti `[IMPLEMENTED]`**:
   Se durante lo sviluppo si rende necessario modificare lo stack tecnologico o l'interfaccia di un layer (es. passaggio a chiavi multiple o nuovi vincoli di sanitizzazione dei file), il prompt dell'agente responsabile (`.ecc/agents/pipeline-engineer.md` o `.ecc/agents/geo-data-architect.md`) **deve essere aggiornato** per rispecchiare i nuovi confini applicativi prima di procedere con la scrittura del codice.
2. **Sincronizzazione di Fine Fase**:
   L'allineamento dei file agentici (`.ecc/agents/*.md`) e delle regole di sviluppo (`.ecc/rules/*.md`) deve avvenire **alla fine di ogni singola Fase della Roadmap**, garantendo che la documentazione e i guardrail dell'IDE siano allineati prima di iniziare il blocco di lavoro successivo.
3. **Principio di Disaccoppiamento e Testing**:
   La logica di business non deve dipendere dal database o dal filesystem. Si deve implementare l'isolamento dei metodi per permettere test offline deterministici con mockup.

---

## 3. WORKLOG DETTAGLIATO PER LAYER (IL "COSA" E IL "COME")

### LAYER E: EXTRACTION (Ingestion & Data Preparation)

#### [IMPLEMENTED] `extraction/client.py` — Miniflux Client
* **Funzionalità**: Connessione sicura e asincrona all'aggregatore RSS Miniflux.
* **Algoritmo**:
  * Inizializza `httpx.AsyncClient` leggendo `MINIFLUX_API_URL` e autenticando tramite l'header `X-Auth-Token` contenente `MINIFLUX_API_KEY`.
  * Metodo `async def fetch_unread_entries(limit: int = 50) -> list[dict]`: Recupera i feed non letti dal server.
  * Metodo `async def mark_as_read(entry_ids: list[int]) -> None`: Invia una richiesta `PUT` a `/v1/entries` impostando lo stato come `read` per gli ID degli articoli elaborati.

#### [IMPLEMENTED] `extraction/parser.py` — Text Cleansing & Parsing
* **Funzionalità**: Sanitizzazione dei dati dei feed per rimuovere rumore HTML.
* **Algoritmo**:
  * Utilizza una classe derivata da `html.parser.HTMLParser` per analizzare il contenuto HTML dell'articolo.
  * Rimuove tassativamente i tag `<script>`, `<style>`, `<iframe>`, `<svg>` e i tag di tracciamento pubblicitario.
  * Sostituisce le entità HTML comuni (`&amp;` → `&`, `&quot;` → `"`, `&#39;` → `'`).
  * Collassa gli spazi bianchi e le righe vuote multiple per ottimizzare l'uso dei token di contesto dell'LLM.

#### [IMPLEMENTED] `extraction/state.py` — State Management & Deduplicazione
* **Funzionalità**: Impedisce la duplicazione dei dati relazionali e lo spreco di chiamate API a Gemini.
* **Algoritmo**:
  * Metodo `async def is_article_duplicate(conn: asyncpg.Connection, url: str) -> bool`: Esegue una query preventiva su PostgreSQL per verificare se l'URL dell'articolo è già presente nella tabella `articles`:
    ```sql
    SELECT EXISTS(SELECT 1 FROM articles WHERE source_url = $1);
    ```
  * Se l'articolo è duplicato, l'ingestione salta direttamente alla notizia successiva senza interpellare l'LLM, evitando scansioni onerose sul filesystem.

---

### LAYER C: CLASSIFICATION (Gemini Cloud Orchestration)

#### [IMPLEMENTED] `classification/client.py` — SDK Gemini Client
* **Funzionalità**: Connessione sicura alle API Cloud di Google Gemini.
* **Algoritmo**:
  * Utilizza l'SDK ufficiale `google-genai` compatibile con Python 3.11+.
  * Inizializza il client tramite `client = genai.Client(api_key=LLM_API_KEY)`.
  * Modello target obbligatorio: `gemma-4-31b`.

#### [IMPLEMENTED] `classification/prompts.py` — Prompt Engine & CoT
* **Funzionalità**: Gestione dei prompt e delle definizioni delle categorie.
* **Algoritmo**:
  * Utilizza istruzioni **Chain-of-Thought (CoT)** che guidano il modello a generare internamente un campo di ragionamento logico prima di compilare la struttura JSON finale.
  * Impone l'elenco chiuso di categorie primarie: `['Nucleare', 'Elettronica', 'Chip', 'Acqua', 'Energia', 'Infrastrutture']`.

#### [IMPLEMENTED] `classification/validator.py` — Pydantic Validation Pipeline
* **Funzionalità**: Validazione formale dell'output strutturato generato dall'LLM.
* **Algoritmo**:
  * Converte la risposta JSON di Gemini nello schema Pydantic `GeopoliticalArticleSchema`:
    ```python
    from pydantic import BaseModel, Field
    from typing import List, Literal

    class GeopoliticalArticleSchema(BaseModel):
        title: str = Field(description="Titolo normalizzato privo di elementi di clickbait")
        summary: str = Field(description="Sintesi esecutiva densa di informazioni di massimo due frasi")
        published_at: str = Field(description="Data di pubblicazione in formato YYYY-MM-DD")
        source_url: str = Field(description="URL originale dell'articolo")
        country_code: str = Field(description="Codice ISO Alpha-2 della nazione coinvolta (es. IT, US, UA)")
        latitude: float = Field(description="Latitudine geografica in gradi decimali")
        longitude: float = Field(description="Longitudine geografica in gradi decimali")
        companies_involved: List[str] = Field(description="Elenco delle aziende o corporazioni industriali menzionate")
        tags: List[str] = Field(description="Lista di tag semantici estratti")
        primary_category: Literal["Nucleare", "Elettronica", "Chip", "Acqua", "Energia", "Infrastrutture"]
        sentiment: Literal["Positivo", "Neutrale", "Negativo"] = Field(description="Sentiment strategico dell'articolo")
        infrastructural_entities: List[str] = Field(description="Elenco di asset o infrastrutture fisiche citate")
        relevance_level: int = Field(description="Grado di rilevanza geopolitica da 1 a 5", ge=1, le=5)
    ```
  * In caso di anomalia di validazione, reinvia l'output malformato a Gemini per 1 tentativo di correzione automatica includendo il tracciamento dell'errore.
  * Se fallisce, applica valori di fallback: `country_code = "XX"`, `latitude = 0.0`, `longitude = 0.0`, `primary_category = "Infrastrutture"`, `sentiment = "Neutrale"`.

---

### LAYER C: COMMIT (PostgreSQL & Obsidian Vault)

#### [IMPLEMENTED] `commit/db_commit.py` — PostgreSQL Persistenza
* **Funzionalità**: Salvataggio dei dati all'interno dello schema relazionale tramite query asincrone con `asyncpg` puro, **senza l'uso di SQLAlchemy** per garantire la massima efficienza e uniformità del driver database.
* **Algoritmo**:
  * Esegue una transazione atomica asincrona:
    1. Inserisce l'articolo nella tabella `articles` utilizzando `ON CONFLICT (source_url) DO NOTHING` e recupera l'ID.
    2. Esegue l'upsert idempotente dei record all'interno delle tabelle `companies` e `tags` tramite clausole `ON CONFLICT (name) DO NOTHING`.
    3. Popola le junction table `article_companies` e `article_tags` associando l'ID dell'articolo agli ID di aziende e tag.

#### [IMPLEMENTED] `commit/factory.py` — Markdown Generator
* **Funzionalità**: Generazione del file `.md` compatibile con Obsidian.
* **YAML Frontmatter**: Genera array piatti standard per tag e aziende per preservare l'ordine e facilitare la lettura, formattando la geolocalizzazione secondo la sintassi a lista singola per il plugin Leaflet:
  ```yaml
  ---
  title: "[Titolo]"
  location: [latitude, longitude]
  country: "[country_code]"
  category: "[primary_category]"
  tags: [tag1, tag2]
  companies: [company_name]
  sentiment: "[sentiment]"
  relevance: [relevance_level]
  published: [published_at]
  source: "[source_url]"
  ---
  ```
  Genera il corpo del documento Markdown stampando la sezione `# Riassunto` e `# Entità Infrastrutturali`.

#### [IMPLEMENTED] `commit/router.py` — Semantic Routing & Vault Bootstrap
* **Bootstrap Automatico**:
  * All'avvio dell'applicazione, il metodo `initialize_vault_directories()` scansiona la directory `/app/vault/`. Se risulta vuota, crea automaticamente le sottocartelle macro-categorie: `/app/vault/Energia`, `/app/vault/Chip`, `/app/vault/Nucleare`, `/app/vault/Acqua`, `/app/vault/Infrastrutture`, `/app/vault/Elettronica`.
* **Routing Semantico & Pattern Nomi File**:
  * Genera un pattern nome file robusto che include l'hash dell'URL sorgente (calcolato tramite l'algoritmo MD5 o SHA-256 troncato a 8 caratteri) per evitare collisioni a livello di filesystem in caso di titoli duplicati:
    `filename = {published_at}_{slugified_title}_{url_hash}.md`
  * Costruisce il percorso di destinazione: `/app/vault/{primary_category}/{country_code}/{filename}`.
* **Sanitizzazione NTFS / POSIX (Cross-Platform)**:
  * La funzione `slugify_title(title: str) -> str` applica una pulizia aggressiva rimuovendo tutti i caratteri illegali e non sicuri per i filesystem Windows (NTFS/FAT), macOS (APFS) e Linux (ext4): `\`, `/`, `:`, `*`, `?`, `"`, `<`, `>`, `|`. Questi caratteri vengono sostituiti da un trattino `-` sicuro.

#### [IMPLEMENTED] `commit/lock.py` — Concurrency Lock
* **Funzionalità**: Impedisce scritture simultanee corrotte o conflitti sul filesystem dell'host.
* **Algoritmo**:
  * Utilizza la libreria cross-platform **`filelock`** (`filelock.FileLock`). Questa libreria gestisce i lock in modo sicuro e nativo sia sui sistemi POSIX (Linux/macOS tramite descrittori di file standard) sia sulle API di Windows, evitando crash di I/O legati ai meccanismi di montaggio dei volumi Docker condivisi.

---

## 4. CORE & INFRASTRUCTURE (Docker, Config, State)

L'intera applicazione viene eseguita in container Docker isolati.

### [IMPLEMENTED] `core/config.py` — Configurazione API Key
Gestione della priorità di caricamento delle chiavi API nel sottomodulo di configurazione:
```python
import os
from dotenv import load_dotenv

load_dotenv()

# Priorità GOOGLE_API_KEY, fallback automatico su GEMINI_API_KEY
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

LLM_API_KEY = GOOGLE_API_KEY or GEMINI_API_KEY
if not LLM_API_KEY:
    raise ValueError("Configurazione Errata: Manca GOOGLE_API_KEY o GEMINI_API_KEY nel file .env")
```

### [IMPLEMENTED] `core/database.py` — Bootstrap Database PostgreSQL
All'avvio del container backend, prima dell'esecuzione del loop di monitoraggio, viene invocata la funzione `bootstrap_database()`. Questa funzione esegue le istruzioni DDL per l'inizializzazione automatica delle tabelle e degli indici se non sono presenti nel database PostgreSQL:

```sql
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    published_at DATE NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    country_code CHAR(2) NOT NULL DEFAULT 'XX',
    latitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    longitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    primary_category VARCHAR(50) NOT NULL CHECK (primary_category IN ('Nucleare', 'Elettronica', 'Chip', 'Acqua', 'Energia', 'Infrastrutture')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS article_companies (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, company_id)
);

CREATE TABLE IF NOT EXISTS article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

-- Indici di ricerca
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_geo_date ON articles (published_at, latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_articles_country_date ON articles (country_code, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles (primary_category, published_at DESC);
```

### [IMPLEMENTED] `docker-compose.yml` — Healthcheck & Volumi Relativi
Configurazione infrastrutturale aggiornata con volume per il Vault locale `./vault` dell'host, blocco healthcheck per PostgreSQL e servizio Miniflux integrato:

```yaml
version: '3.8'

services:
  # ─── 1. DATABASE POSTGRESQL ─────────────────────────────────────────────────
  radar-db:
    image: postgres:15-alpine
    container_name: radar-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    networks:
      - radar-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

  # ─── 2. BACKEND PYTHON (FastAPI + Pipeline) ─────────────────────────────────
  radar-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    container_name: radar-backend
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}"
      OBSIDIAN_VAULT_PATH: "/app/vault"
    volumes:
      - ./vault:/app/vault  # Mappa la cartella relativa ./vault dell'host
    depends_on:
      radar-db:
        condition: service_healthy  # Avvia il backend solo a DB pronto ed healthy
    networks:
      - radar-network

  # ─── 4. MINIFLUX (Aggregatore RSS) ──────────────────────────────────────────
  radar-miniflux:
    image: miniflux/miniflux:latest
    container_name: radar-miniflux
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}?sslmode=disable
      - RUN_MIGRATIONS=1
      - CREATE_ADMIN=1
      - ADMIN_USERNAME=${MINIFLUX_ADMIN_USERNAME}
      - ADMIN_PASSWORD=${MINIFLUX_ADMIN_PASSWORD}
    depends_on:
      radar-db:
        condition: service_healthy
    networks:
      - radar-network

networks:
  radar-network:
    driver: bridge
    name: radar-network
```

### [IMPLEMENTED] `.env` — Credenziali Locali
```ini
POSTGRES_USER=radar_user
POSTGRES_PASSWORD=radar_password_secure
POSTGRES_DB=radar_db

GOOGLE_API_KEY=AIzaSyYourGoogleApiKeyHere

MINIFLUX_API_URL=http://radar-miniflux:8080
MINIFLUX_API_KEY=your_miniflux_token
MINIFLUX_ADMIN_USERNAME=admin
MINIFLUX_ADMIN_PASSWORD=admin123
```

---

## 5. ROADMAP DI SVILUPPO FASE PER FASE

Nel pieno rispetto delle direttive di sviluppo di ECC, adozione obbligatoria del workflow **TDD (Test-Driven Development)**: ogni funzionalità introdotta deve essere preceduta dalla stesura di test ed avere una copertura target del **80%+**. I commit sul codice dovranno seguire le convenzioni semantiche standard (es. `feat:`, `fix:`, `docs:`).

### Fase 1: Setup Core, Ingestione & Database Bootstrap
* **Attività**:
  * Creazione della struttura delle directory all'interno del backend `backend/app/`.
  * Sviluppo dei moduli di configurazione `core/config.py` (con gestione doppia API key) e `core/logging.py`.
  * Sviluppo di `core/database.py` per avviare il bootstrap DDL delle tabelle PostgreSQL e dei relativi indici.
  * Sviluppo del modulo `extraction/client.py` (Miniflux), `extraction/parser.py` (Text cleaning) e `extraction/state.py` (Deduplicazione su PostgreSQL).
  * **Allineamento Agente**: Verifica e allineamento di `pipeline-engineer.md` `[IMPLEMENTED]`.
* **Input**: Feed non letti in arrivo da Miniflux.
* **Output**: Testo pulito e normalizzato, database configurato automaticamente con tabelle ed indici pronti.
* **Verifiche di Test (TDD)**:
  * Esecuzione script di bootstrap all'avvio e validazione della struttura PostgreSQL.
  * Test unitari per `strip_html_tags` per verificare la corretta rimozione dei tag e la sanitizzazione.

### Fase 2: Integrazione Gemini API & Validazione Pydantic
* **Attività**:
  * Sviluppo del modulo `classification/client.py` integrando l'SDK ufficiale `google-genai` con puntamento al modello `gemma-4-31b` ed implementando il meccanismo di rate limiting asincrono (almeno 4s di attesa tra le chiamate) per non saturare la quota di 15 RPM.
  * Scrittura di `classification/prompts.py` (System Prompt + CoT).
  * Sviluppo di `classification/validator.py` per gestire la validazione formale e il loop di recupero/retry degli errori.
  * **Allineamento Agente**: Verifica e allineamento di `geo-data-architect.md` `[IMPLEMENTED]`.
* **Input**: Testo dell'articolo normalizzato dal Layer E.
* **Output**: Oggetto `GeopoliticalArticleSchema` validato.
* **Verifiche di Test (TDD)**:
  * Test asincroni con risposte mockate e risposte reali di Gemini per validare l'output JSON e la corretta assegnazione del sentiment e delle coordinate geografiche.
  * Validazione della corretta applicazione del fallback in caso di fallimenti ripetuti di validazione.

### Fase 3: Commit Engine & Vault Obsidian
* **Attività**:
  * Sviluppo di `commit/factory.py` (Generazione Markdown con frontmatter YAML a liste piatte standard e pattern nome file con URL hash).
  * Sviluppo del modulo `commit/router.py` (Bootstrap delle macro-cartelle del Vault ed algoritmo di sanitizzazione Windows/NTFS dei nomi dei file).
  * Sviluppo di `commit/db_commit.py` per l'inserimento atomico e idempotente dei dati relazionali nel database (asyncpg puro).
  * Sviluppo di `commit/lock.py` integrato con la libreria cross-platform `filelock`.
  * **Allineamento Agente**: Revisione finale delle regole in `.ecc/rules/backend.md` `[IMPLEMENTED]`.
* **Input**: Oggetto `GeopoliticalArticleSchema` validato dal Layer C.
* **Output**: File Markdown creati e organizzati semanticamente nel Vault locale `./vault` e transazione consolidata nel database.
* **Verifiche di Test (TDD)**:
  * Verifica che all'avvio le cartelle del Vault vengano inizializzate se mancanti.
  * Test dell'algoritmo di sanitizzazione NTFS dei titoli (rimozione di `\ / : * ? " < > |`).
  * Verifica che le coordinate YAML siano a lista singola `location: [lat, lon]` e che `tags` e `companies` siano array piatti standard.
  * Verifica che il file lock con `filelock` blocchi correttamente la scrittura concorrente e si comporti correttamente sui filesystem host.

### [IMPLEMENTED] Fase 4: Integrazione FastAPI & Lifespan Task Registration
* **Attività**:
  * Cablaggio delle pipeline asincrone in `main.py`.
  * Registrazione del background loop di monitoraggio asincrono (polling ogni 15 minuti via `asyncio.sleep(900)`) all'interno dell'evento di **Lifespan** di FastAPI sfruttando `asyncio.create_task` per impedire il blocco del server Uvicorn.
  * Esposizione degli endpoint REST delle API in `main.py` per l'interfaccia Angular.
* **Input**: Articoli RSS reali da Miniflux.
* **Output**: Backend integrato attivo in container Docker, con background loop eseguito asincronamente in lifespan.
* **Verifiche di Test**:
  * Test di integrazione end-to-end sul ciclo completo di ingestione, classificazione e commit (DB + Obsidian).
  * Validazione delle performance degli endpoint API con database popolato.
  * Verifica che il server Uvicorn rimanga reattivo durante l'esecuzione del ciclo di background.

---

## 6. VERIFICATION PLAN

### Automated Tests (Pytest - Target Copertura: 80%+)
1. **Extraction Test Suite** (`backend/app/tests/test_extraction.py`):
   - Testa il comportamento di `MinifluxClient` mockando le chiamate HTTP di rete.
   - Testa la funzione `strip_html_tags` con input contenenti tag annidati, script e iframe dannosi.
   - Testa `is_article_duplicate` verificando che risponda `True` o `False` a seconda dei record inseriti.
2. **Classification Test Suite** (`backend/app/tests/test_classification.py`):
   - Invia testi mockati al validatore Pydantic e assicura che il JSON prodotto corrisponda esattamente ai campi di `GeopoliticalArticleSchema`.
   - Verifica che in caso di risposte corrotte, la pipeline esegua la richiesta correttiva e, in ultima istanza, applichi il fallback `country_code = "XX"` e coordinate `0.0`.
3. **Commit Test Suite** (`backend/app/tests/test_commit.py`):
   - Valida che `initialize_vault_directories` crei le 6 macro-categorie se la directory principale è vuota.
   - Controlla la funzione di slugification: caratteri come `:` o `/` devono essere trasformati in `-`.
   - Valida la scrittura del file `.md` e assicura che lo YAML corrisponda a `location: [latitude, longitude]` e contenga array piatti per `tags` e `companies`.
   - Verifica che il file lock con `filelock` funzioni correttamente su file temporanei cross-platform.
   - Esegue transazioni PostgreSQL e verifica l'integrità referenziale nelle junction tables.
4. **[IMPLEMENTED] Live Integration Test Suite & Production Audit** (`backend/app/tests/test_integration_live.py` & `backend/scripts/test_production_pipeline.py`):
   - Esegue controlli reali senza l'ausilio di mock su database PostgreSQL, client Miniflux, connessione Gemini API (Gemma-4-31b-it) ed il throttling del rate limiter.
   - Throttling rate limiter validato asincronamente con 5 worker eseguiti concorrentemente a esattamente 4 secondi di intervallo temporale l'uno dall'altro.
   - Test E2E transazionale e di scrittura con lock su Vault Obsidian integrato, testato reale e pulito.


### Manual Verification
1. Svuotare la directory `./vault` locale.
2. Eseguire il comando di avvio dell'infrastruttura: `docker compose up -d --build`.
3. Monitorare i log del container backend tramite `docker compose logs -f radar-backend` e assicurarsi che:
   - Compaia il log `Bootstrap database completato` (DDL eseguite correttamente).
   - Compaia il log `Inizializzazione directory Vault completata` (le 6 cartelle delle categorie devono essere apparse nella directory locale `./vault`).
4. Verificare tramite client database che la tabella `articles` contenga il vincolo `UNIQUE` sull'URL e gli indici attivi.
5. Inserire un articolo di test all'interno di Miniflux, attendere il ciclo di elaborazione e verificare la creazione fisica del file Markdown associato (es. sotto `./vault/Nucleare/UA/...`) e la presenza delle coordinate geografiche formattate come `location: [lat, lon]` ed array piatti.
