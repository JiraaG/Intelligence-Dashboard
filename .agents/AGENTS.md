# AGENTS.md — Radar Informativo Globale (ECC Native Guardrails)

Questo file definisce le regole operative globali, i vincoli architetturali e i guardrail per lo sviluppo del modulo Radar. Queste istruzioni sono immutabili e caricate nativamente ad ogni turno di chat.

---

## 1. Identità del Progetto & Stack Tecnologico

* **Nome:** Radar Informativo Globale (Intelligence Dashboard)
* **Obiettivo:** Applicazione web self-hosted, containerizzata e plug-and-play che aggrega feed RSS, li arricchisce semanticamente via Google Gemini API e li visualizza su una mappa 2D interattiva in stile Palantir (estetica scura, confini SVG nitidi, marker tematici per categoria geopolitica).

### Stack Tecnologico Ufficiale
* **Backend:** Python 3.12-slim (Docker) / 3.14 (locale). Demone asincrono con polling ogni 15 minuti.
* **LLM:** `google-genai` SDK + Gemma 4 31B. Output strutturato via schema Pydantic.
* **Database:** PostgreSQL 15 (`radar-db`). Accesso tramite driver asincrono `asyncpg` puro.
* **Feed Source:** Miniflux REST API.
* **Frontend:** Angular 21 (Standalone Components).
* **Container:** Docker + docker-compose (servizi: `radar-db`, `radar-backend`, `radar-frontend`, `radar-miniflux`).
* **Web Server:** Nginx (Alpine) per servire Angular e proxying `/api/`.

---

## 2. Vincoli di Produzione Cruciali (Radar Specific)

> [!CRITICAL]
> ### ⛔ Divieto Assoluto di Placeholder o "TODO"
> Il codice di produzione deve essere completo, tipizzato tramite Type Hinting, testato e privo di commenti `TODO`, `FIXME`, `HACK`, blocchi `pass` senza codice o sollevamenti di `NotImplementedError`. Ogni riga di codice deve essere pronta per il deployment.
>
> ### ⛔ Obbligo asyncpg Puro (No ORM / No SQLAlchemy)
> Tutte le interazioni con il database PostgreSQL devono avvenire tramite query SQL pure eseguite in modo asincrono con `asyncpg`. È severamente vietato l'uso di SQLAlchemy o altri ORM per garantire la massima efficienza e aderenza alle specifiche tecniche del modulo Radar.
>
> ### ⛔ Purgazione Rigida dei Tag Multimediali nel Parser
> Il modulo `extraction/parser.py` deve eliminare categoricamente tutti i tag HTML e purgare interamente i tag multimediali (`<img>`, `<video>`, `<audio>`, `<noscript>`, `<meta>`) e tutti i loro attributi (es. `src`, `href`, `style`, `alt`) per ottimizzare rigorosamente il consumo dei token dell'LLM.
>
> ### ⛔ Percorso di Fallback del Vault Obsidian
> Il percorso predefinito di fallback per l'inizializzazione del Vault di Obsidian deve essere impostato esplicitamente su `/app/vault`.

---

## 3. Regole di Codifica Backend (Path-Scope: `backend/**`)

1. **Versionamento Dipendenze (requirements.txt):**
   * Non bloccare mai le dipendenze con operatori `==`. Usare sempre `>=` per garantire compatibilità con Python 3.14 su sistemi Windows (es. `asyncpg>=0.31.0`, `pydantic>=2.10.0`).
2. **Il Demone Non Si Ferma Mai:**
   * Il loop di monitoraggio `while True` con `asyncio.sleep(900)` deve catturare qualsiasi eccezione a livello di ciclo e di singolo articolo, garantendo l'esecuzione indefinita.
3. **Deduplicazione Pre-LLM:**
   * Controllare sempre l'esistenza dell'URL dell'articolo nel DB via query SQL prima di effettuare la chiamata all'LLM per ottimizzare i costi API.
4. **Gestione Errori a Tre Livelli:**
   * *Livello 1:* Demone principale (non deve morire).
   * *Livello 2:* Ciclo completo della pipeline (se fallisce un ciclo, il successivo parte).
   * *Livello 3:* Elaborazione del singolo articolo (se un articolo fallisce, si passa al successivo con log di warning/error).
5. **Type Hints & Logging:**
   * Type hints obbligatori su tutte le funzioni pubbliche.
   * Utilizzare il logger centralizzato configurato in `core/logging.py`, evitando categoricamente l'uso di `print()`.
6. **Rate Limiting & Rispetto delle Quote LLM:**
   * Per evitare errori `429 (Too Many Requests)` causati dai limiti del tier di chiamata (15 RPM), implementare un ritardo controllato asincrono di almeno 4 secondi (`await asyncio.sleep(4)`) tra le singole chiamate alle API nel ciclo di classificazione (`classification/client.py`). Questo garantisce uno smaltimento stabile ed affidabile di backlog massivi (1000+ articoli).
7. **Architettura Modulare Backend (Path: `backend/app/`):**
   * Il backend è diviso in quattro layer: `core/` (config, db, logging), `extraction/` (Miniflux client, parser HTML, dedup), `classification/` (Gemini client, prompts, schema Pydantic), `commit/` (db_commit, vault factory, file router, file lock).
   * `core/logging.py`: il `RotatingFileHandler` DEVE essere wrappato in `try/except` — il container può non avere permessi di scrittura sulla directory `logs/`. Il fallback deve mantenere attivo il console handler.

---

## 4. Regole di Containerizzazione (Docker & Compose)

1. **Nomi dei Servizi Immutabili:** `radar-db`, `radar-backend`, `radar-frontend`, `radar-miniflux`.
2. **Persistenza Dati:** PostgreSQL deve utilizzare un volume named bind-mounted locale (`./data/postgres`).
3. **Isolamento di Rete:** Tutti i servizi risiedono sulla rete bridge interna `radar-network`. Solo il frontend espone la porta 80 all'host.
4. **Healthcheck & dipende_on:** Il backend e il frontend dipendono da `radar-db` con condizione `service_healthy`.
5. **Password e Sicurezza:** 
   * Le credenziali reali vivono esclusivamente nel file `.env` (ignorato da Git).
   * È vietato l'uso del carattere `$` all'interno del valore delle password in quanto Docker Compose lo interpreta come interpolazione di variabili.
   * Ciascun Dockerfile deve contenere file `.dockerignore` per non includere cache locali o cartelle pesanti (`node_modules`, `.venv`).
6. **Workflow di Compilazione Frontend (Local-to-Docker Copy):**
   * Il Dockerfile del frontend copia gli asset pre-compilati locali da `dist/radar-frontend/browser`. Qualsiasi modifica al codice Angular del frontend richiede prima la compilazione locale (`npm run build` da `radar/frontend`) e poi la ricostruzione del container (`docker compose up --build -d radar-frontend`) affinché Nginx possa servire la versione aggiornata.


---

## 5. Vincoli Frontend Angular 21

> [!WARNING]
> ### ⚠️ Leaflet + ESBuild: Pattern di Importazione Obbligatorio
> `leaflet.markercluster` è una libreria UMD che richiede `window.L`. Con Angular 21 + ESBuild
> (`@angular/build:application`), un `import 'leaflet.markercluster'` come side-effect import
> in un componente TypeScript crea un namespace Leaflet **separato** che non si aggancia al plugin.
> **Soluzione:** caricare Leaflet e MarkerCluster come script globali in `angular.json` → `scripts[]`
> e accedere via `const L = (window as any).L` nel componente.
> Mai usare `import * as L from 'leaflet'` o `import 'leaflet.markercluster'` nei componenti.

> [!NOTE]
> ### 🗺️ Regole di Visualizzazione Mappa e Clustering
> 1. **Calibrazione Clustering**: Configurare `disableClusteringAtZoom: 13` nel `markerClusterGroup`. Questo garantisce che i marker rimangano raggruppati a zoom bassi e intermedi, dividendosi progressivamente in sub-cluster per poi scomporsi automaticamente in singole icone di categoria geopolitica al livello di zoom 13 (evitando sovrapposizioni e zoom infiniti).
> 2. **Estensione Bounding Box per Stati Trans-Antimeridiano**: Nel calcolo dello zoom per nazioni con territori oltre la linea di cambio data (Stati Uniti `US` e Russia `RU`), escludere le coordinate dei territori esterni (es. Alaska/Hawaii per `US`, Chukotka per `RU`) dal calcolo del bounding box per prevenire zoom out globali indesiderati. **Tali territori remoti esclusi devono comunque mantenere l'hatching e la colorazione attiva sulla mappa.**
> 3. **Legenda Colori**: Inserire una legenda glassmorphic orizzontale in assoluto in basso al centro della mappa (`bottom: 20px; left: 50%`) che mostri cerchi luminosi (`box-shadow` del colore di categoria) affiancati alle emoji e ai nomi delle categorie geopolitiche.

> [!IMPORTANT]
> ### Esecuzione Manuale degli Hook
> Prima di dare per completato un file di codice o una modifica strutturale, l'agente deve verificare la conformità eseguendo manualmente gli script presenti in `radar/.ecc/hooks/`:
> 1. **Pre-Tool-Use Scan:** Usare [pre-tool-use.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/.ecc/hooks/pre-tool-use.py) per scansionare l'input del tool alla ricerca di leak di chiavi segrete, pattern di codice vietati o comandi distruttivi.
> 2. **Post-Tool-Use Linting:** Eseguire [post-tool-use.py](file:///c:/Users/lucag/Documents/Dashboard%20finance/radar/.ecc/hooks/post-tool-use.py) per attivare i controlli sintattici e di qualità del codice (ruff per Python, eslint per TS/JS) e garantire che nessun commento `TODO` o placeholder sia presente nel file finale.

