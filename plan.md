# DOCUMENTO DI SPECIFICA TECNICA (PRD) - RADAR INFORMATIVO GLOBALE

## 1. VISIONE E OBIETTIVO PRINCIPALE

Sviluppare un'applicazione web self-hosted, modulare e completamente containerizzata denominata "Radar Informativo Globale" (Intelligence Dashboard). Il sistema ha lo scopo di aggregare notizie tramite feed RSS, arricchirle semanticamente tramite un LLM in cloud estraendone dati geopolitici e aziendali univoci, e visualizzarle su una mappa 2D interattiva caratterizzata da un'estetica operativa scura e minimale (stile "Palantir"). L'applicazione deve essere distribuibile tramite Docker, funzionare immediatamente dopo l'estrazione ("plug-and-play") e non richiedere alcun sistema di autenticazione o gestione di dati personali, mostrando direttamente le informazioni elaborate in interfaccia.

---

## 2. ARCHITETTURA E FLUSSO DEI DATI (PIPELINE)

### FASE 1: INGESTIONE TEMPORIZZATA (BACKEND PYTHON)

* **Meccanismo di Polling:** Il backend ospita un servizio Python che gira in background come un demone asincrono continuo tramite un loop infinito (`while True`) e un'attesa programmata di esattamente 15 minuti (`asyncio.sleep(900)`).
* **Raccolta Feed:** Ogni 15 minuti lo script interroga le API dell'aggregatore centrale Miniflux per prelevare gli ultimi articoli inseriti nei feed RSS e non ancora contrassegnati come letti.
* **Sanitizzazione e Unicità:** Il testo grezzo e il titolo della notizia vengono ripuliti da tutti i tag HTML. Prima di inviare i dati all'LLM, il backend esegue una query preventiva su PostgreSQL verificando l'URL sorgente dell'articolo: se l'URL è già presente, l'articolo viene saltato per impedire duplicazioni nel database.

### FASE 2: ELABORAZIONE E ARRICCHIMENTO SEMANTICO (GOOGLE GEMINI API)

* **Integrazione SDK:** Lo script Python utilizza l'SDK ufficiale di Google (`google-genai`) interfacciandosi inizialmente con il modello **Gemini 1.5 Flash / Flash 3.1 lite**, consentendo di valutare l'efficacia del piano gratuito prima di un eventuale passaggio a modelli superiori.
* **Structured Outputs:** Il prompt di sistema sfrutta le funzionalità di output strutturato dell'API di Google (tramite schemi Pydantic o modalità JSON nativa) per azzerare le allucinazioni e costringere l'LLM a rispondere esclusivamente con un oggetto JSON valido e privo di testo introduttivo o conclusivo.
* **Contratto del JSON Strutturato:** L'LLM deve mappare la notizia nei seguenti campi rigidi:
1. `title`: Titolo dell'articolo ottimizzato e ripulito dall'IA.
2. `summary`: Riassunto esecutivo essenziale di massimo due frasi.
3. `published_at`: Data di pubblicazione normalizzata in formato ISO8601 (YYYY-MM-DD).
4. `source_url`: URL originale della notizia.
5. `country_code`: Codice della nazione di riferimento in formato standard ISO Alpha-2 (es. IT, US, CN).
6. `coordinates`: Oggetto contenente `latitude` e `longitude` in formato decimale. *Regola Geografica:* Se l'articolo parla di una nazione in generale senza citare una città o un punto preciso, l'LLM deve inserire le coordinate del centro geografico di quella nazione.
7. `companies_involved`: Array di stringhe contenente i nomi delle aziende coinvolte nella notizia.
8. `tags`: Array di stringhe contenente i molteplici tag tematici (es. Nucleare, Elettronica, Chip, Acqua, Energia).
9. `primary_category`: **Una e una sola categoria principale obbligatoria** estratta da un set predefinito (es. Nucleare, Elettronica, Chip, Acqua, Energia, Infrastrutture). Questo campo è univoco ed è fondamentale per determinare la visualizzazione grafica sul frontend.


* **Logica di Fallback:** Il codice Python include un blocco di cattura degli errori per gestire eventuali anomalie di parsing o risposte vuote, applicando coordinate neutre di sicurezza prima della scrittura su DB.

### FASE 3: PERSISTENZA DEI DATI (POSTGRESQL)

* **Configurazione del DB:** Database PostgreSQL ospitato in un container dedicato. Non è prevista alcuna gestione di utenti, tabelle di sessione o login.
* **Struttura delle Tabelle:** La tabella principale `articles` memorizza i campi del JSON (inclusa la coordinata geografica e la categoria primaria). Le tabelle di supporto `companies` e `tags` gestiscono le relazioni molti-a-molti con gli articoli mediante tabelle di giunzione intermediarie.
* **Ottimizzazione delle Richieste:** Vengono creati indici di database espliciti sulle colonne delle coordinate geografiche e della data di pubblicazione per garantire query istantanee durante le operazioni di filtraggio del frontend.

---

## 3. INTERFACCIA UTENTE (UI/UX) E COMPORTAMENTO DELLA MAPPA

### FASE 4: CONFIGURAZIONE FRONTEND (ANGULAR 21 + PRIMENG)

* **Stack Grafico:** L'interfaccia è una Single Page Application sviluppata in Angular 21, supportata dalla libreria di componenti nativi **PrimeNG** per la gestione di layout, caroselli e filtri.
* **Estetica Palantir:** La mappa 2D è scura e minimale (es. basata su tile *CartoDB Positron Dark* tramite la libreria Leaflet o OpenLayers), con confini nazionali netti, puliti ed evidenziati da linee sottili in tonalità desaturate, escludendo elementi morfologici superflui (rilievi, foreste) per far risaltare unicamente i dati geopolitici.
* **Gestione Geografica Locale:** I confini delle nazioni vengono gestiti in modo offline caricando un file statico `countries.geo.json` memorizzato direttamente negli assets locali di Angular (`src/assets/data/`). La libreria della mappa legge questo file e genera automaticamente i poligoni come nodi **SVG** all'interno del DOM del browser.

### FASE 5: LOGICA DI ZOOM, LAYOUT SPLIT-SCREEN E CLUSTERING

* **Zoom Out (Vista Globale):** Quando la mappa mostra l'intero planisfero o macro-regioni, i singoli marker puntuali vengono nascosti. Le nazioni che contengono notizie in quel determinato giorno vengono evidenziate applicando ai poligoni SVG un riempimento grafico a righe colorate (**Pattern Hatching SVG**). Se all'interno di uno stato sono presenti notizie di categorie differenti, il pattern a righe utilizzerà i diversi colori associati alle categorie primarie coinvolte. Cliccando su una nazione colorata, l'interfaccia mostra un pop-up o un'infografica generale con il riepilogo numerico di tutte le notizie presenti in quell'area.
* **Zoom In (Vista Dettaglio):** Quando l'utente zooma in avanti sulla mappa, il riempimento SVG a righe colorate delle nazioni sfuma progressivamente tramite CSS fino a raggiungere un'opacità pari a zero, lasciando visibili solo i confini netti. Contemporaneamente, compaiono i marker puntuali precisi. Ciascun marker mostra un'icona tematica specifica associata alla sua `primary_category` (es. un simbolo del reattore per il Nucleare, un chip per l'Elettronica, una goccia per l'Acqua).
* **Layout Dinamico Split-Screen:** Di base, la mappa occupa il 100% dello schermo. Al click (o all'hover) su un marker, Angular attiva uno stato di transizione fluida: la mappa viene rimpicciolita e spostata sul lato destro occupando il **70%** dello schermo (mantenendo centrato il punto selezionato). Sul lato **sinistro** compare una schermata aggiuntiva (una barra laterale verticale che occupa il **30%** dello schermo, implementata tramite il componente `p-sidebar` di PrimeNG). All'interno di questa barra viene renderizzata l'ultima notizia pertinente con tutti i dati estratti dall'LLM (Titolo, Data, Riassunto di due frasi, badge cliccabili per tag e aziende, e un collegamento ipertestuale per aprire la notizia originale via web).
* **Clustering Spaziale e Carosello:** Se più notizie insistono nella stessa identica zona o in un'area molto ristretta, l'algoritmo di clustering del frontend (configurato con un raggio di circa 40 pixel) evita la sovrapposizione visiva raggruppando i punti sotto un unico marker speciale di "Gruppo". Facendo click su questo marker di gruppo, si apre la barra laterale sinistra. Al suo interno, Angular istanzia il componente `p-carousel` di PrimeNG: l'utente può scorrere lateralmente tramite frecce o swipe le schede di tutte le notizie presenti in quel punto, leggendo per ciascuna i rispettivi dettagli elaborati da Gemini.

### FASE 6: FILTRAGGIO TEMPORALE DINAMICO

* **Controllo di Navigazione:** Nella parte superiore della mappa è posizionata una barra di controllo temporale fluttuante (utilizzando il componente `p-calendar` o uno slider orizzontale di PrimeNG).
* **Aggiornamento Reattivo:** Quando l'utente seleziona un giorno differente, Angular intercetta l'evento e invia una richiesta mirata alle API del backend richiedendo esclusivamente i dati di quella data. I marker correnti vengono distrutti e la mappa ridisegna all'istante i nuovi punti e i pattern SVG delle nazioni, aggiornando la vista senza richiedere il ricaricamento della pagina nel browser.

---

## 4. DEPLOYMENT E INFRASTRUTTURA (DOCKER)

### FASE 7: ARCHITETTURA CONTAINERIZZATA "PLUG & PLAY"

* **Isolamento di Rete:** L'intero ecosistema viene configurato e coordinato tramite un unico file `docker-compose.yml` diviso in tre servizi isolati che comunicano all'interno di una rete virtuale interna dedicata:
1. `radar-db`: Esegue PostgreSQL e utilizza un volume locale persistente sul file system dell'host per garantire la conservazione dei dati tra i riavvii.
2. `radar-backend`: Esegue l'ambiente Python ospitando il loop asincrono di 15 informazioni, l'integrazione con Miniflux, l'SDK `google-genai` e l'esposizione degli endpoint API per il frontend.
3. `radar-frontend`: Ospita la build di produzione di Angular 21, compilata e servita tramite un server web Nginx leggero.


* **Distribuzione Immediata:** L'applicazione è progettata per essere estratta sul server o computer locale (ambiente Ubuntu) e avviata immediatamente tramite il comando `docker compose up -d`. L'unica porta esposta verso l'esterno è quella del server Nginx (es. porta 80 o 4200), rendendo la dashboard subito accessibile su localhost senza interventi sistemistici o configurazioni di sicurezza esterne.