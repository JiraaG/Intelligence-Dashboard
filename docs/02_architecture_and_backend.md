# ⚙️ Architettura e Backend

## Panoramica dell'Architettura

L'infrastruttura di **Radar Informativo Globale** è pensata per trasformare in automatico flussi di dati grezzi (feed RSS) in informazioni strutturate, georeferenziate e analizzate semanticamente.

```
┌─────────────┐     RSS Polling      ┌──────────────┐
│  RSS Feeds  │ ──────────────────→  │   Miniflux   │
│  (Internet) │                      │  :8080       │
└─────────────┘                      └──────┬───────┘
                                            │
                                   fetch_unread()
                                            │
                                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI :8000)                    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              PIPELINE LOOP (ogni 15 min)             │    │
│  │                                                      │    │
│  │  Layer E ──── Layer C (Classify) ──── Layer C (Commit)    │
│  │  Extraction     ┌──────────────┐     ┌────────────┐       │
│  │  ┌──────────┐   │ Google Gemini│     │ PostgreSQL │       │
│  │  │ Miniflux │   │ Gemma 4 31B  │     │ radar-db   │       │
│  │  │ Client   │──→│ Structured   │──→  │ :5432      │       │
│  │  └──────────┘   │ Output JSON  │     └────────────┘       │
│  │       │         └──────────────┘            │             │
│  │       │                                     │             │
│  │  ┌────┴──────┐                    ┌─────────┴──────┐      │
│  │  │ HTML      │                    │ Markdown Vault │      │
│  │  │ Sanitizer │                    │ (Obsidian)     │      │
│  │  └───────────┘                    └────────────────┘      │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  REST API: GET /api/articles, GET /api/countries, /health    │
└──────────────────────────┬───────────────────────────────────┘
                           │
                    Nginx Proxy (/api/)
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                FRONTEND (Nginx + Angular :80)                │
└──────────────────────────────────────────────────────────────┘
```

---

## La Pipeline a Tre Strati (Layer)

Il cuore del backend, scritto in Python 3.12 con FastAPI, risiede nella cartella `radar/backend/app/`. Il processo che si ripete ogni 15 minuti è diviso in tre fasi rigorose.

### Layer E: Extraction (Estrazione)
Il modulo `extraction` si occupa di interfacciarsi con Miniflux tramite chiamate REST asincrone (`httpx`).
1. Scarica tutti gli articoli non ancora "letti".
2. Verifica su PostgreSQL se l'URL originale (`source_url`) è già stato elaborato in precedenza, scartando i duplicati.
3. Rimuove brutalmente tutti i tag multimediali (immagini, video, script) tramite il modulo `parser.py` per risparmiare preziosi token del LLM.

### Layer C: Classification (Classificazione)
Gli articoli sanitizzati vengono spediti alle API di Google Gemini (`gemma-4-31b-it`).
Questa fase utilizza una tecnica di Prompting detta **Chain-of-Thought (CoT)** combinata con gli **Structured Outputs** (JSON).

Il modello deve compilare il seguente schema Pydantic (`GeopoliticalArticleSchema`):

```python
class GeopoliticalArticleSchema(BaseModel):
    reasoning: str                        # Analisi logica (CoT)
    title: str                            # Sintesi in < 120 caratteri
    summary: str                          # Sintesi esecutiva in 1-2 frasi
    published_at: str                     # Data ISO YYYY-MM-DD
    source_url: str                       
    country_code: str                     # Codice ISO Nazione (es. IT, US, XX)
    latitude: float                       
    longitude: float                      
    companies_involved: str               # Stringa separata da virgole (CSV)
    tags: str                             # Stringa separata da virgole
    primary_category: Literal[            # Categoria da lista fissa di 10
        "Nucleare", "Energia", "Infrastrutture", "Geopolitica", 
        "Economia", "Tecnologia", "Spazio", "Ambiente", 
        "Salute", "Sicurezza"
    ]
    sentiment: Literal["Positivo", "Neutrale", "Negativo"]
    infrastructural_entities: str         # Asset fisici coinvolti (CSV)
    relevance_level: int                  # Scala 1–5
```

> [!IMPORTANT]
> L'uso di stringhe delimitate da virgole (CSV) per campi come `companies_involved` o `tags` anziché array di stringhe (`List[str]`) è una decisione architetturale voluta. Previene la saturazione dei buffer JSON del modello Gemini, evitando errori HTTP 500 durante la validazione schematica.

### Layer C: Commit (Salvataggio)
Una volta validato l'output JSON, i dati vengono scritti in due destinazioni:
1. **PostgreSQL**: Vengono popolati i record principali (`articles`), le entità correlate (`companies`, `tags`) e le tabelle di giunzione. Il salvataggio avviene con query SQL pure usando `asyncpg` (niente ORM come SQLAlchemy per massimizzare le prestazioni).
2. **Obsidian Vault**: Una copia della notizia viene fisicamente scritta sul disco (dentro `radar/vault/`) come file Markdown. Il router crea dinamicamente l'albero delle directory (`/Categoria/Nazione/articolo.md`) inserendo tutte le entità estratte come **Frontmatter YAML** in cima al file, rendendolo analizzabile nativamente in Obsidian.

---

## Gestione degli Errori e Resilienza

Il demone `run_pipeline_loop` (in `main.py`) è costruito per non arrestarsi mai. Usa un meccanismo di tolleranza agli errori su 3 livelli:

- **Errore di Rete / Gemini 500**: Se l'API di Google risponde con un errore temporaneo (`HTTP 500 Internal Server Error` o `429 Too Many Requests`), il blocco `try/except` nel client intercetta l'eccezione, logga un "WARNING" e inserisce l'articolo in coda per il ciclo successivo. 
- **Errore di Formato Strutturale**: Se il modello LLM restituisce un JSON malformato che Pydantic non riesce a validare, scatta il *Fallback*.
- **Meccanismo di Fallback**: Un articolo non valido non blocca la pipeline. Viene generata una riga di "Fallback" neutrale associata allo stato "XX" (Unknown) per garantire che l'esecuzione prosegua.
