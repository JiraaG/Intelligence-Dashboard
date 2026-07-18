# Quadro Generale e Possibili Upgrade — Radar Informativo Globale

Questo documento offre una panoramica del sistema **Radar Informativo Globale** (Intelligence Dashboard), descrivendo l'architettura, lo stato dello sviluppo (Phase 0–6 e i test del Final Release Gate) e le proposte estese per i futuri upgrade del sistema in base ai commenti e alle verifiche effettuate.

---

## 1. Cos'è il Sistema (Panoramica)

**Radar Informativo Globale** è un'applicazione web self-hosted, containerizzata e plug-and-play progettata per l'analisi e il monitoraggio geopolitico e strategico in stile "Palantir". Il sistema aggrega feed di notizie, le analizza semanticamente per estrarre informazioni rilevanti e le mappa visivamente su un'interfaccia interattiva a scopi decisionali.

### Flusso Logico delle Informazioni
1. **Aggregazione:** L'utente aggiunge feed RSS su un'istanza dedicata di [Miniflux](https://miniflux.app/).
2. **Ingestione & Deduplica:** Un demone asincrono (Worker) effettua il polling di Miniflux, scarta gli articoli duplicati verificando gli URL in database e purga l'HTML da tag multimediali per ottimizzare i token.
3. **Classificazione Semantica (LLM):** Il Worker invia il testo ad un LLM (Gemini SDK o provider compatibili con OpenAI via HTTPX come DeepSeek, GLM, Grok, OpenAI). L'LLM restituisce un output strutturato (JSON strict validato via Pydantic) contenente:
   - Paese/i coinvolti (Country codes ISO)
   - Categoria geopolitica principale (scelta tra 10 aree: Nucleare, Energia, Infrastrutture, Geopolitica, Economia, Tecnologia, Spazio, Ambiente, Salute, Sicurezza)
   - Sentiment (positivo, neutrale, negativo)
   - Entità infrastrutturali, aziende coinvolte e tag tematici rilevanti.
4. **Persistenza & Archiviazione:**
   - I dati strutturati vengono salvati su database PostgreSQL (tramite query pure asincrone `asyncpg`).
   - Viene generata una scheda dell'articolo in formato Markdown, archiviata in un **Vault di Obsidian** locale su disco organizzato per Categoria e Nazione (percorso `/app/vault`).
   - Gli articoli vengono marcati come letti su Miniflux solo dopo il completamento della transazione.
5. **Visualizzazione (Dashboard):** L'utente consulta le notizie tramite una mappa 2D scura basata su Leaflet (SPA Angular 21). La mappa mostra aggregati giornalieri, colora le nazioni tramite tratteggi (hatching SVG) in base alle categorie, e permette di esplorare le notizie tramite indicatori emoji personalizzati (spiderfy) e un carosello laterale.

---

## 2. Cosa è Stato Sviluppato (Stato Corrente)

Tutte le fasi fondamentali dello sviluppo (**Phase 0–6**) sono state completate con successo (**GATE VERDE**), e i test del **Final Release Gate (F1–F4)** sono superati.

### A. Backend (`radar/backend/`)
* **Separazione Netta API/Worker:** Il file [main.py](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/backend/app/main.py) si occupa solo di servire le API REST e i controlli di liveness/readiness, mentre [worker.py](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/backend/app/worker.py) gestisce autonomamente l'ingestione dei dati in background. Un blocco cooperativo (*advisory lock*) a livello DB garantisce che non girino mai due worker leader contemporaneamente.
* **LLM Multi-Provider & QuotaLedger:** Supporto nativo per Google Gemini (`google-genai` SDK) e client compatibili con OpenAI (DeepSeek, GLM, Grok, OpenAI) via HTTPX. La gestione delle quote ([quota.py](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/backend/app/classification/quota.py)) traccia in modo persistente le richieste per evitare crash legati ai limiti giornalieri (RPD) o al minuto (RPM/TPM), implementando failover automatici tra modelli di complessità differente (SIMPLE/COMPLEX) o tra provider diversi.
* **Cooldown Durable dei Modelli:** Gestione automatica dell'isolamento dei modelli malfunzionanti (tramite tabella PostgreSQL dedicated) in caso di errori persistenti nelle chiamate API.
* **Outbox Pattern:** Le transazioni su DB e la scrittura fisica sul file-system del Vault Obsidian sono regolate da una coda outbox persistente. Questo garantisce tolleranza ai crash: un fallimento nella scrittura del file sul Vault non provoca la perdita dell'articolo, e Miniflux viene notificato solo a transazione completata con successo.
* **Database Relazionale Puro:** Tutte le query sono scritte in SQL puro ed eseguite in modalità asincrona usando `asyncpg` per garantire la massima efficienza prestazionale ed eliminare il sovraccarico di un ORM.

### B. Frontend (`radar/frontend/`)
* **Architettura Angular 21 Standalone:** Utilizzo intensivo di Signals per la reattività dello stato dell'applicazione ([state.service.ts](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/frontend/src/app/services/state.service.ts)) e modularità standalone.
* **Integrazione Leaflet Safe per ESBuild:** Caricamento di Leaflet e dei suoi plugin (MarkerCluster) tramite script globali in `angular.json` per evitare incompatibilità del namespace UMD indotte dai compilatori moderni.
* **Mappa Avanzata & Visualizzazione Geografica:**
   - **Hatching SVG Dinamico:** Tratteggi colorati complessi sulle geometrie nazionali per indicare combinazioni di categorie geopolitiche.
   - **Pin Summary Nazionali:** Un indicatore unico per nazione con anello conico (*conic-gradient*) che mostra graficamente la distribuzione delle categorie del giorno corrente.
   - **Spiderfy personalizzato per Categoria:** All'apertura del dettaglio nazione, i cluster si dividono a raggiera mostrando le emoji specifiche associate alla categoria degli articoli attivi nel carosello.
* **Notizie Salvate (Vault):** Barra di stato unificata con contatore globale, contrassegno immediato di salvataggio/rimozione (`is_saved`), e allineamento automatico dei flag di lettura (`save ⇒ read`, `unread ⇒ unsave`).

### C. DevOps, Containerizzazione e Sicurezza
* **Docker Multi-stage & Reti Isolate:** Cinque servizi integrati (`radar-db`, `radar-backend`, `radar-worker`, `radar-frontend`, `radar-miniflux`) separati su due reti virtuali bridge (`radar-edge` e `radar-data`). Il frontend dialoga con l'esterno ma non ha accesso diretto al database o a Miniflux.
* **Healthcheck conformi ad Alpine:** Utilizzo di `wget` nativo anziché `curl` all'interno dei container Alpine per monitorare i servizi in modo efficiente.
* **Nginx Dynamic DNS:** Nginx agisce come reverse proxy configurato con resolver DNS dinamico per prevenire errori `502 Bad Gateway` in caso di riavvio improvviso dei container.
* **Sicurezza & CSP:** Intestazioni CSP (Content Security Policy) rigide impostate su Nginx, prevenzione delle minacce XSS nei marker della mappa ed esclusione del tag `latest` per garantire la riproducibilità delle immagini.

### D. Esito del Final Release Gate (F1–F4 PASS)
* **F1 (Backup & Restore):** Script pronti ed end-to-end testati per il salvataggio incrementale/completo del database Postgres e del Vault Obsidian con validazione dei checksum SHA-256.
* **F2 (Seed 10k & Performance):** Simulazione di carico con 10.000 articoli caricati per un singolo giorno. Le aggregazioni spaziali SQL basate su indici dedicati e query `LATERAL` si sono dimostrate stabili e l'interfaccia utente ha retto il volume di rendering senza degradazione.
* **F3 (Chaos Testing):** Test di kill violento dei container worker e database durante la pipeline di classificazione. Nessun dato è andato perso, e i lock di leadership e le transazioni outbox si sono ripristinati correttamente al riavvio.
* **F4 (Security Scan):** Scansione delle dipendenze Python (`pip-audit`) e verifica manuale dell'escaping dei marker contro minacce di iniezione di codice JavaScript (XSS).

---

## 3. Sviluppi Futuri e Upgrade (Revisione Integrata)

### A. Generalizzazione del Motore LLM & Configurazione Locale AMD

L'obiettivo è svincolare il codice backend da logiche cablate e consentire all'utente di configurare **qualsiasi** provider LLM (pubblico o locale) tramite il file `.env`.

* **Configurazione Dinamica a Canali (Lanes):**
  Nel file `.env`, l'operatore configurerà delle variabili standardizzate:
  - `LLM_SIMPLE_PROVIDER` / `LLM_COMPLEX_PROVIDER` (es. `gemini`, `openai`, `deepseek`, `anthropic`, o `custom_endpoint`)
  - `LLM_SIMPLE_API_KEY` / `LLM_COMPLEX_API_KEY`
  - `LLM_SIMPLE_BASE_URL` / `LLM_COMPLEX_BASE_URL` (per ridirigere le chiamate a un server locale o un proxy aziendale)
  - `LLM_SIMPLE_MODEL` / `LLM_COMPLEX_MODEL`
  - `LLM_SIMPLE_DIALECT` / `LLM_COMPLEX_DIALECT` (es. `thinking` per DeepSeek R1/V3, `stock` per OpenAI standard, `gemini` per l'SDK nativo)
  - Limiti di consumo associati: `LLM_SIMPLE_RPM`, `LLM_SIMPLE_TPM`, `LLM_SIMPLE_RPD` e `LLM_SIMPLE_BUDGET_USD_DAY`.
* **Integrazione Locale su Linux + GPU AMD (Radeon RX 6750 XT 12GB):**
  Avendo a disposizione una GPU AMD Radeon RX 6750 XT con **12 GB di VRAM** su sistema operativo Linux:
  - **Modello Consigliato per Lane SIMPLE:** **Gemma 2 9B (Instruct)** o **Qwen 2.5 14B (Instruct)**. Entrambi i modelli, in quantizzazione `Q4_K_M`, occupano rispettivamente circa 5.5 GB e 9 GB di VRAM. La RX 6750 XT da 12 GB può ospitarli interamente in memoria lasciando ampio spazio per il sistema e la finestra di contesto. Gemma 2 9B/14B e Qwen 2.5 14B offrono eccezionali capacità logico-strutturali, ideali per garantire l'output JSON rigido richiesto dalla lane SIMPLE.
  - **Integrazione Lane COMPLEX:** Per non saturare i 12 GB di VRAM (che non permetterebbero di far girare contemporaneamente due modelli locali di grandi dimensioni), la scelta ottimale è mantenere la lane **COMPLEX su API Cloud** (usando le API gratuite di Gemini Flash, DeepSeek API, Grok o GLM). Questo garantisce un'ottima accuratezza sui testi complessi a costo computazionale locale nullo, mantenendo la GPU libera per il solo modello della lane SIMPLE.
  - **Hosting Locale:** Il motore locale verrà gestito tramite un container **Ollama** compatibile con ROCm (driver grafici AMD su Linux) integrato nel file `docker-compose.yml` nella rete `radar-data`.

---

### B. Ingestione Real-Time e Soft Refresh Frontend

* **Meccanismo Webhook:**
  Al posto del polling a tempo del worker (es. ogni 15 minuti), Miniflux viene configurato per inviare una notifica push (HTTP POST) a un nuovo endpoint dedicato del backend (`/api/webhooks/miniflux`) non appena un feed viene scaricato.
* **Aggiornamento "Soft Refresh" in Interfaccia:**
  Non sarà necessario aggiornare manualmente la pagina del browser per vedere le notizie.
  1. Il backend riceve il webhook, elabora l'articolo, lo inserisce a DB e lo proietta nel Vault.
  2. A transazione completata, il backend pubblica un evento su un canale persistente (es. **Server-Sent Events - SSE** o **WebSockets**).
  3. Il frontend Angular intercetta l'evento tramite un servizio di ascolto integrato in [StateService](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/frontend/src/app/services/state.service.ts).
  4. Il segnale (`Signal`) relativo al sommario della mappa viene aggiornato reattivamente in memoria.
  5. Leaflet esegue il ridisegno locale del pin della nazione e della percentuale di colorazione circostante (soft-refresh visuale istantaneo), mantenendo la UI costantemente sincronizzata con il flusso globale.

---

### C. Deduplicazione Semantica tramite Embeddings

* **Funzionamento:**
  Invece di limitarsi a controllare la corrispondenza esatta dei caratteri dell'URL (inadeguata se feed diversi pubblicano lo stesso articolo con parametri UTM o domini differenti):
  1. Si abilita l'estensione **`pgvector`** sul database PostgreSQL (`radar-db`).
  2. Si integra un modelo di embedding locale molto leggero (es. `all-MiniLM-L6-v2` o `bge-small-en-v1.5`, che producono vettori a 384 dimensioni in pochi millisecondi su CPU).
  3. Per ogni articolo in ingresso, viene calcolato l'embedding del titolo o delle prime frasi e salvato come vettore nel DB.
  4. Prima di chiamare l'LLM, il worker effettua una ricerca di similarità vettoriale (distanza coseno) contro gli articoli inseriti nelle ultime 24-48 ore.
  5. Se la vicinanza supera una soglia definita (es. **85% o 90%**), l'articolo viene contrassegnato come duplicato semantico. Viene salvata la referenza nel DB ma viene saltato il passaggio all'LLM, risparmiando tempo di elaborazione e token.

---

## D. Mappe Offline in Ambienti Isolati (Air-Gapped) — [FASE FINALE]

Questo upgrade è classificato come **attività finale** (da realizzare per ultima).

* **Come funziona il recupero dei dati offline:**
  In un contesto militare o di rete aziendale isolata (air-gapped) con *zero* accesso a Internet:
  - **Origine dei Feed:** I feed RSS non provengono dal web. Miniflux raccoglie i feed da server di monitoraggio interni alla rete locale (intranet), da database di agenzie locali, o tramite script di scraping operanti all'interno di perimetri di rete circoscritti. In alternativa, gli operatori caricano periodicamente file statici (dump XML/JSON) di notizie.
  - **Il Problema della Mappa:** Anche se backend e Miniflux funzionano internamente, il browser dell'operatore, non avendo accesso ad internet, non riuscirebbe a scaricare i tasselli (tiles) geografici da server esterni come CartoDB o OpenStreetMap, mostrando una mappa grigia e vuota.
* **Procedura di Implementazione e Verifica Tecnica:**
  1. **Tile Server Locale:** Aggiungere un servizio nel file `docker-compose.yml` basato su un'immagine leggera (es. `maptiler/tileserver-gl` o un server Node/Python minimale). Questo servizio leggerà un archivio compresso geografico (file `.mbtiles` del mondo, es. OpenMapTiles, di circa 2-4 GB a seconda dello zoom massimo).
  2. **Routing Nginx:** Configurare [nginx.conf](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/frontend/nginx.conf) per intercettare la rotta `/tiles/` e inoltrare le richieste al servizio di tile locale.
  3. **Configurazione Leaflet:** Modificare il componente [radar-map.component.ts](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/frontend/src/app/components/radar-map/radar-map.component.ts) in modo che utilizzi il percorso relativo locale `/tiles/{z}/{x}/{y}.png` anziché l'URL CDN esterno di CartoDB.
  4. **Verifica:** Spegnere la connessione di rete dell'host e verificare che al caricamento dell'interfaccia i confini e le immagini geografiche della mappa si disegnino istantaneamente recuperando i dati dal container locale.

---

### E. Slider Temporale per l'Analisi Storica (Utilità)

A differenza del filtro a calendario (che serve a selezionare un giorno specifico in modo puntuale), lo **slider temporale per lo "scorrimento veloce"** risponde a precise necessità di analisi di intelligence geopolitica:

1. **Rilevamento di Anomalie Temporali:** Trascinando lo slider avanti e indietro (o premendo un tasto "Play" per l'animazione automatica delle date), l'analista può vedere dinamicamente come i vettori di crisi energetica o militare si spostano nello spazio geografico nell'arco delle settimane.
2. **Percezione della Durata dell'Evento:** Consente di distinguere a colpo d'occhio un evento di crisi transitorio (una nazione che si colora per un solo giorno) da una tensione persistente (una nazione che mantiene il tratteggio SVG acceso per settimane).
3. **Presentazioni e Briefing Situazionali:** Offre uno strumento visivo immediato da mostrare ai decisori per riprodruire la "cronistoria visiva" delle tensioni globali dell'ultimo mese senza dover fare clic 30 volte sul calendario.

---

### F. Mappatura Sub-Nazionale e Integrazione Coordinate Locali (Concetto Futuro)

* **Gestione degli Articoli Generali (Senza Nazione):**
  *Stato attuale:* Il sistema gestisce già questa situazione appoggiandosi al codice nazione fittizio `XX`. Questa impostazione ottimale verrà mantenuta senza modifiche.
* **Integrazione Coordinate Locali (Opzione A — Evidenziatore di Prossimità):**
  *Nota:* Questa proposta è conservata come **idea concettuale** da valutare successivamente, per evitare di alterare anzitempo il funzionamento della griglia colorata nazionale o la logica nativa dei cluster Leaflet.
  - *Funzionamento dell'idea:* Mantenere inalterata la vista globale con la griglia colorata e i pin centrali. Solamente quando la nazione viene cliccata e la sidebar è aperta, se un articolo selezionato ha coordinate precise estratte dall'LLM, sulla mappa appare temporaneamente un **cerchio pulsante luminoso (glow effect)** sulla città o sull'infrastruttura d'interesse, spostandosi reattivamente allo scorrere del carosello.

---

### G. Obsidian Vault: Collegamenti Bidirezionali (Wiki-Links)

* **Analisi del Vault Attuale:**
  Attualmente, [factory.py](file:///c:/Users/lucag/Documents/Intelligence-Dashboard/radar/backend/app/commit/factory.py) genera file Markdown strutturati con un frontmatter YAML pulito e un corpo semplice composto da:
  ```markdown
  # Riassunto
  [Testo del riassunto]
  # Entità Infrastrutturali
  - [Entità 1]
  - [Entità 2]
  ```
* **Evoluzione con Collegamenti Bidirezionali:**
  Per sfruttare appieno la visualizzazione a grafo di Obsidian, le entità estratte devono essere collegate.
  - *Modifiche al generatore:* Il codice di `factory.py` viene esteso per racchiudere le entità nel corpo del Markdown in doppie parentesi quadre:
    - Le aziende coinvolte diventano `[[Azienda A]]`, `[[Azienda B]]`.
    - Le entità fisiche e infrastrutturali diventano `[[Centrale Nucleare di Caorso]]` o `[[Porto di Trieste]]`.
    - In calce a ciascun file viene generata una riga di tag geografico-tematici, come:
      `Nazione: [[IT]] | Categoria: [[Nucleare]]`
  - In questo modo, aprendo il Vault in Obsidian, tutti gli articoli che menzionano la stessa azienda o la stessa centrale nucleare risulteranno automaticamente collegati allo stesso nodo, permettendo all'utente di navigare la mappa concettuale delle relazioni geopolitiche direttamente dall'applicazione Obsidian.

---

## H. Visualizzazione a Grafo Geospaziale (Relazioni sulla Mappa)

Invece di sostituire interamente la mappa geografica con un grafo astratto a nodi su sfondo bianco (che risulterebbe meno intuitivo e meno attraente a livello visivo), si propone una modalità di **Grafo Geospaziale (Overlay Relazionale)** integrata direttamente sulla mappa esistente.

```text
               [Curve Animate e Colorate]
      (Paese A: Centroide) ~~~~~~~~~~~~~~~~~~~> (Paese B: Centroide)
               [Spessore = Volume Articoli]
```

* **Funzionamento del Toggle:**
  Tramite un pulsante "Visualizza Relazioni" sulla barra degli strumenti della mappa, l'operatore attiva l'overlay relazionale. La mappa geografica rimane visibile come sfondo scuro.
* **Proiezione delle Connessioni:**
  - **Curve Relazionali Georiferite:** Il sistema individua gli articoli che collegano più paesi (es. accordi bilaterali, import/export energetico, minacce transfrontaliere).
  - La mappa disegna delle **linee curve dinamiche e animate (archi)** che collegano direttamente i centroidi delle nazioni coinvolte.
  - **Codifica Visiva dei Collegamenti:**
    - *Colore:* Le curve assumono il colore associato alla categoria geopolitica prevalente (es. giallo per Nucleare, verde per Energia).
    - *Spessore/Opacità:* Lo spessore della curva è proporzionale al volume degli articoli che uniscono quei due paesi nel giorno o nel periodo selezionato.
    - *Animazione:* Subili micro-animazioni (es. flussi luminosi che viaggiano lungo l'arco) indicano la direzione della collaborazione o del vettore di minaccia.
* **Interazione e Utilità:**
  - Facendo clic su una curva di collegamento, si apre un popup o una sidebar che elenca i titoli dei relativi articoli geopolitici.
  - Questa modalità unisce l'estetica e la chiarezza della mappa geografica con il potere d'analisi di un grafo relazionale, rendendo le informazioni immediatamente comprensibili e visivamente di forte impatto per qualsiasi tipologia di utente.

---

## I. Struttura di Sicurezza "No-GDPR" per la Distribuzione

Per facilitare la distribuzione dell'applicazione ed eliminare qualsiasi necessità di raccogliere dati personali degli utenti (escludendo l'impatto normativo GDPR, cookie policy o database di credenziali individuali), il sistema adotta una struttura di sicurezza basata esclusivamente su restrizioni infrastrutturali:

* **IP Binding Rigido (Sicurezza Standard e Attiva):**
  Nel file `docker-compose.yml`, la porta esposta dal frontend Nginx viene vincolata all'interfaccia di loopback locale dell'host:
  `ports: - "127.0.0.1:80:8080"`
  Questo impedisce che la dashboard sia visibile o raggiungibile da altri dispositivi collegati alla stessa rete locale (Wi-Fi/LAN), limitando l'accesso solo al computer locale in cui gira il container.
* **CORS Same-Origin strict (Sicurezza Standard e Attiva):**
  L'API FastAPI accetta chiamate provenienti solo dall'host locale configurato nel reverse-proxy, bloccando preventivamente script dannosi esterni da browser.
* **Nginx Basic Authentication (Opzione di Sicurezza Extra/Opzionale):**
  *Nota:* Questa funzionalità non è configurata di default per evitare complessità immediate, ma è mantenuta come **soluzione extra di sicurezza** qualora l'operatore desideri esporre la dashboard nella LAN per un piccolo team:
  - Si abilita una direttiva static password standard (`auth_basic`) sul server Nginx. L'header di autenticazione statico blocca l'accesso a monte a livello di rete, senza memorizzare cookie traccianti o richiedere l'uso di dati personali, preservando la conformità GDPR.
