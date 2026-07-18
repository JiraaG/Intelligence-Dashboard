# Piano di Implementazione — Fase B: Ingestione Real-Time e Soft Refresh Frontend (SSE / Webhooks)

Questo piano di implementazione definisce la strategia dettagliata per realizzare la **Fase B: Ingestione Real-Time e Soft Refresh Frontend** del sistema **Radar Informativo Globale**, partendo dal documento di riferimento `radar_overview_and_upgrades.md`.

## User Review Required

> [!IMPORTANT]
> ### Architettura Pub/Sub PostgreSQL LISTEN/NOTIFY
> Al fine di mantenere l'infrastruttura il più possibile leggera, autonoma (plug-and-play) e priva di ulteriori servizi terzi (come Redis o RabbitMQ), proponiamo l'utilizzo del meccanismo nativo **LISTEN/NOTIFY di PostgreSQL** tramite il driver `asyncpg` per gestire la comunicazione inter-processo (IPC) tra i container separati `radar-backend` e `radar-worker`.
>
> ### Nessuna Violazione del Sidebar Freeze
> I refresh sul frontend Angular 21 avverranno tramite ri-caricamenti selettivi ed emissioni reattive sui Signals esistenti (`mapSummaryResource.reload()`, `savedSummaryResource.reload()`, `detailArticles.update(...)`), preservando interamente le reference degli oggetti visualizzati nel carosello PrimeNG in `radar-sidebar` e soddisfacendo in pieno il vincolo di *Sidebar freeze*.

## Open Questions
- N/A - Architettura validata tramite analisi successiva.

## Proposed Changes

### Backend (FastAPI + Worker)

#### [MODIFY] [main.py](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/backend/app/main.py)
* Aggiunta dell'endpoint webhook `/api/webhooks/miniflux` per la ricezione push di notizie.
* Aggiunta del Broadcast Manager asincrono `SSEBroadcastManager` e del listener in background `backend_article_listener` per ascoltare il canale `radar_article_processed`.
* Aggiunta dell'endpoint SSE `/api/articles/events` per inviare aggiornamenti al frontend in tempo reale.

#### [MODIFY] [config.py](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/backend/app/core/config.py)
* Aggiunta di `MINIFLUX_WEBHOOK_SECRET` per la sicurezza e validazione delle chiamate webhook.

#### [MODIFY] [worker.py](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/backend/app/worker.py)
* Implementazione del listener Postgres `start_postgres_trigger_listener` sul canale `radar_worker_trigger`.
* Modifica del ciclo `run_pipeline_loop` per l'attesa asincrona con `asyncio.wait_for` ed `asyncio.Event`.
* Invio di `NOTIFY radar_article_processed` al completamento dell'elaborazione dell'articolo.

---

### Frontend (Angular 21)

#### [MODIFY] [state.service.ts](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/frontend/src/app/services/state.service.ts)
* Inizializzazione del client `EventSource` verso `/api/articles/events` all'interno dell'apposita zona Angular (`NgZone.runOutsideAngular` per l'ascolto e `NgZone.run` per la propagazione UI).
* Sottoscrizione all'evento `article_processed` e ri-chiamata asincrona di `.reload()` sui Signals `mapSummaryResource` e `savedSummaryResource`.
* Esposizione del Signal `lastProcessedArticleEvent`.

#### [MODIFY] [app.ts](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/frontend/src/app/app.ts)
* Creazione di un `effect` per monitorare `lastProcessedArticleEvent`.
* Se la sidebar è aperta per la nazione interessata dal nuovo articolo, ricarica silente tramite `state.loadCountryArticles(...)` e aggiornamento dei marker con ri-attivazione dello spiderfy, preservando l'articolo visualizzato nel carosello.

---

### Aggiornamento Documentazione e Regole ECC

#### [MODIFY] [README.md](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/README.md)
* Aggiornamento del diagramma Mermaid `Flusso Logico ed Interazione dei Componenti` per mostrare l'innesco webhook da Miniflux a FastAPI e la notifica SSE al frontend.
* Aggiunta di `MINIFLUX_WEBHOOK_SECRET` tra le variabili di configurazione richieste.

#### [MODIFY] [.env.example](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/.env.example)
* Aggiunta della variabile `MINIFLUX_WEBHOOK_SECRET`.

#### [MODIFY] [radar-api-contract.md](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/.ecc/skills/radar-api-contract.md)
* Inserimento dei nuovi contratti API: `POST /api/webhooks/miniflux` (inbound) e `GET /api/articles/events` (outbound SSE).

#### [MODIFY] [backend.md](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/.ecc/rules/backend.md)
* Estensione delle linee guida architetturali per imporre che tutti i `LISTEN` PostgreSQL vengano eseguiti tramite una connessione `asyncpg` dedicata e non prelevata dal pool, per prevenire la *pool starvation*.

---

## Dettaglio delle Sotto-Fasi Implementative

### Sotto-Fase 1: Webhook di Ingestione in FastAPI & Pub/Sub di Innesco
* **Obiettivo:** Creazione dell'endpoint `/api/webhooks/miniflux` in `main.py` per ricevere le notifiche push. FastAPI invia una notifica `NOTIFY radar_worker_trigger, 'entry_id'` a PostgreSQL tramite connessione pool.

### Sotto-Fase 2: Risveglio Asincrono del Worker Leader
* **Obiettivo:** Il worker ascolta sul canale `radar_worker_trigger` con un listener asincrono in background utilizzando una connessione dedicata (fuori dal pool per evitare interferenze). Il loop del demone si risveglia istantaneamente tramite un `asyncio.Event`, cadendo in timeout periodico regolare (polling statico di salvaguardia) solo in assenza di segnali real-time. Questo approccio è 100% retrocompatibile.

### Sotto-Fase 3: Pub/Sub degli Articoli Elaborati e Canale SSE FastAPI
* **Obiettivo:** Il worker notifica il completamento dell'elaborazione di un articolo tramite `NOTIFY radar_article_processed`. FastAPI intercetta il messaggio con una connessione listener dedicata (globale al server, non legata ai client) e inoltra il messaggio alle code di tutti i client collegati all'endpoint SSE `/api/articles/events`. Utilizzo rigoroso dei ping di keep-alive e dell'header `X-Accel-Buffering: no`.

### Sotto-Fase 4: Client SSE Angular in StateService e Soft Refresh Reattivo
* **Obiettivo:** Inserimento dell'EventSource in `state.service.ts` e di un `effect` in `app.ts` per l'aggiornamento automatico dei dati della mappa e della sidebar (se aperta sul paese interessato), senza distruggere i componenti del carosello e preservando in modo ottimistico l'UX per modifiche read/save simultanee in atto.

### Sotto-Fase 5: Aggiornamento Asset Documentali e Standard ECC
* **Obiettivo:** Allineare i manuali architetturali, i contratti API, il README principale e i file `.env.example` per stabilizzare la nuova Fase B nel contesto standard del progetto, garantendo la compatibilità con i successivi aggiornamenti (es. Deduplica `pgvector` Fase C o Graph Vis Fase H).

---

## Revisione di Sistema Globale

Questa architettura si sposa in modo trasparente e propedeutico con i blueprint indicati in `radar_overview_and_upgrades.md`:
* **Fase C (Deduplica pgvector):** La deduplica semantica agirà normalmente all'interno del flusso del worker *dopo* l'innesco del webhook, prevenendo la propagazione dell'evento SSE in caso di articoli duplicati non salvati.
* **Fase H (Geospatial Graph):** Il soft-refresh dei *Signals* permetterà l'apparizione o l'aggiornamento immediato in tempo reale degli "archi" grafici descritti, sfruttando interamente la reattività di `rxResource`.
* **Outbox Pattern:** Resta garantito. L'evento SSE `radar_article_processed` viene emesso solo dopo l'inserimento database per mantenere solidità transazionale e sicurezza dei dati prima della notifica visiva.

---

## Verification Plan

### Automated Tests & Scripts
* **Test del Webhook & Trigger:** Script offline per simulare la POST di Miniflux con payload JSON ed header di sicurezza, osservando i log di FastAPI e PostgreSQL.
* **Test dell'SSE stream:** Comando `curl -N http://localhost:8000/api/articles/events` per verificare l'invio immediato degli eventi notificati a database.
* **E2E Smoke Verification:** Inserimento di una entry fittizia a database con `NOTIFY` e verifica visiva dell'aggiornamento dei cerchi e dei marker sulla mappa Angular senza ricaricamento di pagina.
