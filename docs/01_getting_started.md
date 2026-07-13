# Manuale Operativo: Installazione, Configurazione e Avvio (Getting Started)

Benvenuto nel manuale operativo del **Radar Informativo Globale**. Questo documento non è una semplice guida rapida, ma un vero e proprio manuale d'uso e configurazione tecnica progettato per amministratori di sistema, data engineer e sviluppatori. Non ometteremo alcun dettaglio tecnico. Segui questo documento passo-passo per garantire una messa in produzione solida e priva di errori.

---

## 1. Requisiti di Sistema e Infrastrutturali

Il sistema è orchestrato interamente tramite container Docker per garantire la riproducibilità esatta dell'ambiente di sviluppo in qualsiasi ambiente di produzione.

### 1.1 Requisiti Hardware Minimi
L'applicazione è composta da 4 microservizi (Database, Miniflux, Backend API, Web Server Frontend). I requisiti di memoria devono sostenere l'esecuzione parallela di questi servizi:
- **RAM**: Minimo 4 GB. (Il database PostgreSQL richiede circa 200-300 MB, Miniflux 50 MB, il Backend Python circa 150 MB, Nginx 30 MB. Il processo di *build* di Angular tramite Node.js richiederà picchi temporanei fino a 1.5 GB di RAM).
- **CPU**: Qualsiasi processore dual-core a 64 bit (x86_64 o ARM64, come Apple Silicon M1/M2).
- **Spazio su Disco**: Almeno 3 GB per lo scaricamento delle immagini di base Alpine, l'installazione dei pacchetti e la persistenza del volume dati del database PostgreSQL e dei file Markdown.

### 1.2 Requisiti Software e Compatibilità OS
- **Windows**: È obbligatorio avere installato **Docker Desktop** con l'integrazione **WSL 2** abilitata (Windows Subsystem for Linux).
- **macOS**: Docker Desktop per Mac (versione nativa Apple Silicon o Intel).
- **Linux**: Docker Engine nativo (versione 24.0+) e il plugin `docker-compose-plugin` (non usare la vecchia versione in Python `docker-compose`).
- **Git**: Per la gestione del repository.

### 1.3 Pre-requisiti di Rete (Porte Locali)
Assicurati che nessun altro software sul tuo computer (come un server Apache o un altro database) stia occupando le seguenti porte:
- **Porta 80 (TCP)**: Richiesta da Nginx per esporre la mappa Angular.
- **Porta 8080 (TCP)**: Richiesta dall'interfaccia web di Miniflux.
- *(Internamente)* Le porte 5432 (Postgres) e 8000 (FastAPI) sono usate dentro la virtual network di Docker, ma non sono esposte pubblicamente per motivi di sicurezza.

### 1.4 Generazione della API Key (Google Gemini)
Il cuore analitico del radar si basa sul LLM di Google (`gemma-4-31b-it`).
1. Naviga su [Google AI Studio](https://aistudio.google.com/).
2. Accedi con un account Google.
3. Seleziona "Get API Key" nel pannello laterale.
4. Clicca su "Create API Key" associandola a un progetto Google Cloud nuovo o esistente.
5. Copia la stringa alfanumerica lunga generata. Ti servirà nel passaggio successivo.

---

## 2. Preparazione dell'Ambiente e File `.env`

Apri il tuo terminale preferito (Bash, PowerShell o Zsh) e posizionati nella root del progetto scaricato:

```bash
cd "Dashboard finance/radar/"
```

### 2.1 Architettura del `.env`
Il progetto utilizza le best practice del *Twelve-Factor App*. Tutte le configurazioni (credenziali, chiavi API, URL di rete) non sono **mai** scritte direttamente nel codice, ma vengono iniettate a runtime tramite un file `.env` locale.

1. Troverai un file di esempio chiamato `.env.example`.
2. Duplica questo file e chiamalo rigorosamente `.env`. (Su Linux/Mac: `cp .env.example .env`).
3. Apri il file `.env` appena creato.

Ecco la disamina chirurgica di **tutti** i parametri che dovrai configurare:

```ini
# ==============================================================================
# CONFIGURAZIONE DATABASE POSTGRESQL
# ==============================================================================
# Inserisci le credenziali del database. Il docker-compose le userà per 
# inizializzare il container PostgreSQL al primo avvio.
POSTGRES_USER=radar_user
POSTGRES_PASSWORD=INSERISCI_LA_TUA_PASSWORD
POSTGRES_DB=radar_db

# DATABASE_URL viene costruito dinamicamente dal docker-compose per il backend.
# In sviluppo locale, puoi forzarlo così:
# DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}

# ==============================================================================
# CONFIGURAZIONE MINIFLUX (AGGREGATORE RSS)
# ==============================================================================
# L'URL interno a cui il backend Python chiederà le notizie. Usa il nome del container.
MINIFLUX_API_URL=http://radar-miniflux:8080
# Le credenziali di amministrazione che userai per accedere all'interfaccia web
MINIFLUX_ADMIN_USERNAME=admin
MINIFLUX_ADMIN_PASSWORD=PASSWORD_SICURA_MINIFLUX
# API Key generata dall'interfaccia web (da inserire dopo il primo login)
MINIFLUX_API_KEY=

# Limite di articoli da estrarre ad ogni ciclo (usa 50-100 in produzione)
MINIFLUX_LIMIT=50

# ==============================================================================
# CONFIGURAZIONE GOOGLE GEMINI (INTELLIGENZA ARTIFICIALE)
# ==============================================================================
# Incolla qui la chiave API creata al punto 1.4. Non mettere le virgolette.
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemma-4-31b-it

# Governance e Rate Limits (fondamentale per evitare ban dell'API)
LLM_RPM=10
LLM_TPM=0
LLM_RPD=1400

# ==============================================================================
# CONFIGURAZIONE COMPORTAMENTO BACKEND
# ==============================================================================
# Se True: log prolissi e stack trace completi su console.
DEBUG=False
```

> [!WARNING]
> Il file `.env` contiene credenziali sensibili e costa denaro in chiamate API se compromesso. Il sistema di versionamento (vedi il file `.gitignore` del progetto) ignora di default questo file. **Non forzare mai il caricamento del `.env` su un repository Git remoto.**

---

## 3. Costruzione, Boot e Gestione dell'Infrastruttura (Docker)

Il file `docker-compose.yml` è lo spartito che istruisce Docker su come assemblare i 4 componenti.

### 3.1 Avvio Plug-and-Play (Zero-Config)
Grazie all'architettura Docker **Multi-Stage Build**, non hai bisogno di installare nient'altro sulla tua macchina (né Node.js, né Python, né database locali). Tutto l'ambiente, la pre-compilazione di Angular e la risoluzione delle dipendenze avvengono in camere stagne isolate all'interno di Docker.

Dal terminale (all'interno della cartella `radar/`), esegui il singolo e onnipotente comando:
```bash
docker compose up --build -d
```

**Analisi del flusso di Build e Boot (Cosa sta facendo Docker?):**
1. **Fase Rete & Volumi**: Crea la `radar-network` (bridge). Crea il volume `radar/data/postgres/` legandolo (`bind-mount`) al sistema. Questo garantisce che i dati sopravvivano anche se distruggi i container.
2. **Build del Frontend (Multi-stage)**: Avvia un container invisibile Node.js per compilare il codice Angular e installare le dipendenze in totale isolamento. Trasferisce poi la cartella `dist/` pulita e compilata all'interno di un leggerissimo container `nginx:1.27-alpine` (~30MB), buttando via i pesanti sorgenti Node.
3. **Build del Backend (Multi-stage)**: Compila le librerie C/C++ Python (`asyncpg`) in una fase builder, e trasferisce l'eseguibile pulito in un container `python:3.12-slim` di produzione.
4. **Ordine di Avvio (`depends_on`)**: 
   - Parte `radar-db` e segnala lo stato "healthy" una volta pronto a ricevere query.
   - Partono `radar-miniflux` (esegue le migrazioni interne) e `radar-backend` (avvia FastAPI e il demone asincrono).
   - Parte `radar-frontend` (Nginx), in ascolto per servire l'interfaccia utente al mondo esterno.

### 3.2 Comandi Docker Indispensabili per l'Operatività
Di seguito il cheat-sheet per governare l'intera dashboard:

| Azione Desiderata | Comando da Eseguire | Descrizione |
|-------------------|---------------------|-------------|
| **Visualizzare i container** | `docker compose ps` | Elenca tutti i container, il loro stato (Up/Exited) e le porte mappate. |
| **Arrestare il sistema** | `docker compose stop` | Ferma tutti i servizi mantenendo lo stato. |
| **Distruggere il sistema** | `docker compose down` | Ferma e rimuove i container e la rete virtuale. **Non tocca i dati**. |
| **Piallare tutto (Reset Totale)** | `docker compose down -v` | ⚠️ **ATTENZIONE:** Rimuove anche i volumi anonimi interni. I dati in `radar/data/postgres` essendo un bind-mount non si cancellano, ma resetterai le configurazioni interne. |
| **Riavviare un servizio singolo** | `docker compose restart radar-backend` | Utile se il demone Python si incanta o se si modificano configurazioni minori. |
| **Ricostruire dopo mod. frontend** | `docker compose up --build -d radar-frontend` | Essenziale se cambi i colori in `styles.scss` o i componenti Angular. |

### 3.3 Verifiche di Funzionamento (Health Checks Intensi)
Una volta avviato, non dare per scontato che tutto funzioni. Fai queste verifiche:

**Verifica A: Nginx è in ascolto?**
Esegui:
```bash
curl -I http://localhost
```
*Dovresti ricevere una risposta HTTP 200 OK da Nginx.*

**Verifica B: Il backend Python è crashato all'avvio?**
Esegui:
```bash
docker compose logs --tail=100 radar-backend
```
*Se il file `.env` contiene un URL errato, vedrai un errore "asyncpg.exceptions.InvalidCatalogNameError". Se tutto è sano, vedrai "Uvicorn running on http://0.0.0.0:8000".*

**Verifica C: Esplorazione Manuale del Database (Entrare in PostgreSQL)**
Vuoi verificare fisicamente se i dati vengono inseriti?
```bash
docker exec -it radar-db psql -U radar_user -d radar_db
```
Sei dentro al terminale SQL. Digita:
`\dt` *(Per elencare le tabelle come articles, companies, tags).*
`SELECT title FROM articles LIMIT 5;` *(Per leggere gli articoli).*
Digita `\q` per uscire.

---

## 4. Configurazione Interfaccia RSS (L'Alimentazione del Radar)

Se tutto è avviato, il database è vuoto. Dobbiamo agganciare le sonde al mondo esterno. L'interfaccia preposta è Miniflux.

1. Apri un browser web all'indirizzo **`http://localhost:8080`**. Questa è l'interfaccia cruda di Miniflux.
2. Fai login usando `MINIFLUX_USERNAME` e `MINIFLUX_PASSWORD` dal tuo `.env`.
3. Vai nel tab in alto **Feeds** -> Clicca su **Add Feed**.
4. Inserisci URL validi. *(Suggerimenti: Reuters World News, BleepingComputer, Bloomberg, NASA feed, WHO news)*.
5. Scegli una *Category* per Miniflux. **Importante:** Miniflux non sa nulla delle 10 categorie del radar (Nucleare, Ambiente, ecc.). Le categorie di Miniflux servono solo a te per organizzazione.
6. Salva e lascia che Miniflux scarichi il feed.

### 4.1 La Magia del Demone in Background (Polling Loop)
Entro massimo 15 minuti, il container `radar-backend` esegue questi passaggi asincroni silenziosi:
1. Chiama le API interne di Miniflux: *"Dammi tutti gli articoli non letti"*.
2. Purga l'HTML grezzo estraendo solo testo pulito.
3. Lo invia a Gemini LLM chiedendo una strutturazione in formato JSON.
4. Salva i dati analitici su Postgres (`articles`, `tags`, `companies_involved`).
5. Scrive un file Markdown fisico locale.
6. Segna l'articolo come "Letto" su Miniflux per non riprocessarlo al ciclo successivo.

---

## 5. Visualizzazione della Dashboard Principale

Dopo qualche minuto dal setup di Miniflux, apri la dashboard principale all'indirizzo esposto:

👉 **`http://localhost`**

> [!NOTE] 
> **Dettaglio Architetturale Nginx (Reverse Proxy)**: Qualsiasi richiesta HTTP generata dal frontend Javascript a `http://localhost/api/...` viene intercettata segretamente da Nginx (porta 80) e inoltrata al backend asincrono (porta 8000 interna). Questo previene i fastidiosi problemi di policy CORS.

Sulla mappa vedrai nazioni colorate (Hatching SVG) e cluster Leaflet. Cliccando sui cluster o selezionando una nazione, la UI passerà automaticamente alla modalità "Split-Screen" rivelando la sidebar laterale (il Carosello) con le notizie impaginate, classificate e codificate a colori.

---

## 6. Il Vault Markdown (Esportazione Fisica e Obsidian)

Tutti i dati vivono in PostgreSQL, ma il sistema esporta simultaneamente ogni articolo come un file di testo (Markdown).
Naviga nella cartella: **`radar/vault/`**.

Troverai le directory generate dinamicamente, secondo il pattern:
`vault/{MacroCategoria}/{CodiceISO-Paese}/{Data}_{Titolo}_{Hash}.md`
*(Esempio: `vault/Sicurezza/US/2026-07-13_attacco-cyber_x82a.md`)*.

### 6.1 Integrazione Potente con Obsidian
1. Scarica e installa il software [Obsidian.md](https://obsidian.md/).
2. Apri Obsidian e seleziona "Open folder as vault".
3. Punta Obsidian alla directory esatta `radar/vault/`.
Tutti gli attributi estratti da Gemini sono stampati in cima ad ogni Markdown all'interno di un blocco **YAML Frontmatter**. Questo permette al motore Graph View di Obsidian di collegare visivamente (a ragnatela) le notizie che condividono gli stessi tag o aziende, fornendo un livello analitico offline slegato da Docker e dal Database.

---

## 7. Troubleshooting e Risoluzione dei Problemi Comuni

Anche seguendo le istruzioni, potresti incappare in problemi sistemistici.

### 7.1 Errore All'Avvio: `bind: address already in use`
**Causa:** Un software sul tuo computer sta usando la porta 80 o 8080.
**Verifica diagnostica (Windows):** Esegui `netstat -ano | findstr :80` dal terminale admin per trovare il Process ID (PID) responsabile.
**Soluzione Rapida:** Nel file `docker-compose.yml`, cerca la voce `ports` del frontend. Cambia `"80:80"` in `"8081:80"`. Apri poi il browser su `http://localhost:8081`.

### 7.2 Nginx restituisce: `502 Bad Gateway`
**Causa:** Nginx (frontend) si è avviato prima del Backend, oppure il Backend è andato in crash.
**Soluzione:** 
1. Controlla il core: `docker compose logs radar-backend`. Se c'è un "Traceback" (crash), è colpa del backend. Risolvi prima l'errore lì (spesso è un problema di credenziali DB sbagliate nel `.env`).
2. Se il backend è sano, basta forzare la ri-risoluzione DNS in Nginx riavviando il servizio di facciata: `docker compose restart radar-frontend`.

### 7.3 Errori continui nei Log Backend: `HTTP 500 / 429` (Gemini API)
**Causa:** L'API Key di Gemini ha raggiunto i rate limits (429) o Google Cloud è temporaneamente offline (500).
**Soluzione:** Non devi fare nulla. L'architettura è stata esplicitamente progettata con un blocco `try/except` di Fallback. L'errore verrà loggato (in colore giallo come `WARNING`), l'esecuzione del demone non si arresterà, e l'articolo verrà lasciato "Unread" in Miniflux per essere processato al ciclo successivo, garantendo Zero Data Loss.

### 7.4 Il Container Backend si ferma in `Exited (1)` ripetutamente
**Causa:** Molto probabilmente stai eseguendo lo script su Windows ed è subentrato un problema con i ritorni a capo testuali (CRLF contro LF) nello script Python o nel Dockerfile bash.
**Soluzione:** Modifica la gestione globale in Git:
`git config --global core.autocrlf false`
Cancella il repository, fai di nuovo `git clone` e ripeti la build. Il motore Linux del container digerirà correttamente gli a capo.
