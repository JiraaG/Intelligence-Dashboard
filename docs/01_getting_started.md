# Manuale Operativo: Installazione, Configurazione e Avvio (Getting Started)

Benvenuto nel manuale operativo del **Radar Informativo Globale**. Questo documento fornisce una guida tecnica rigorosa per l'installazione, configurazione e validazione dell'infrastruttura.

---

## 1. Requisiti di Sistema e Infrastrutturali

Il sistema è orchestrato interamente tramite container Docker.

### 1.1 Requisiti Generali
- **RAM**: Minimo 4 GB. 
- **CPU**: Architettura x86_64 o ARM64.
- **Porte Locali Esclusive**:
  - `80` (TCP): Nginx (Frontend).
  - `8080` (TCP): Miniflux (Aggregatore RSS).

### 1.2 Generazione Chiave API (Google Gemini)
Il reasoning LLM richiede accesso a Google Gemini.
1. Ottieni una API Key su [Google AI Studio](https://aistudio.google.com/).
2. Non condividere mai questa chiave e preparati a inserirla nel file `.env`.

---

## 2. Configurazione `.env` e Variabili d'Ambiente

Copia il file `.env.example` in `.env`. Tutte le variabili sono riportate nella seguente tabella. Nessun dato sensibile deve essere hardcoded e il file `.env` è ignorato da Git.

| Variabile | Obbligatoria | Default | Descrizione |
|---|---|---|---|
| `GOOGLE_API_KEY` | Sì | — | Chiave primaria per l'SDK `google-genai`. Ha precedenza su `GEMINI_API_KEY`. |
| `GEMINI_API_KEY` | Opzionale | — | Chiave di fallback per retrocompatibilità. |
| `GEMINI_MODEL` | No | `gemma-4-31b-it` | Modello LLM da utilizzare. |
| `LLM_RPM` | No | `10` | Rate limit: Richieste per minuto. |
| `LLM_TPM` | No | `0` | Rate limit: Token per minuto (0 = disabilitato). |
| `LLM_RPD` | No | `1400` | Rate limit: Richieste massime giornaliere prima dell'ibernazione. |
| `MINIFLUX_API_URL` | Sì | `http://radar-miniflux:8080` | URL interno per la comunicazione Backend-Miniflux. |
| `MINIFLUX_ADMIN_USERNAME` | Sì | `admin` | Username admin per Miniflux. |
| `MINIFLUX_ADMIN_PASSWORD` | Sì | — | Password per Miniflux. **Importante:** Non usare il carattere `$` (verrebbe interpretato da Docker Compose). |
| `MINIFLUX_API_KEY` | Sì | — | Generabile dall'interfaccia di Miniflux post-installazione. |
| `POSTGRES_USER` | Sì | `radar_user` | Username per il database. |
| `POSTGRES_PASSWORD` | Sì | — | Password per PostgreSQL (no carattere `$`). |
| `POSTGRES_DB` | Sì | `radar_db` | Nome del database. |
| `DATABASE_URL` | No | *Docker Compose* | Stringa connessione iniettata in container. |
| `POSTGRES_HOST` / `PORT` | No | `localhost` / `5432` | Parametri di fallback per sviluppo in locale fuori Docker. |

---

## 3. Provisioning Asset e Build

### 3.1 Provisioning GeoJSON
Prima di lanciare la build del frontend, è obbligatorio posizionare il file dei confini mondiali nel path previsto:
`radar/frontend/src/assets/data/countries.geo.json`

Se il file non è tracciato o manca, il frontend fallirà in fase di compilazione o non disegnerà le nazioni.

### 3.2 Avvio dell'Infrastruttura
Il progetto utilizza build multi-stage e non richiede software locale (né Node, né Python).

Esegui dalla cartella `radar/`:
```bash
docker compose up --build -d
```

**Dietro le quinte:**
- **Backend (Python 3.12-slim)**: Il builder C compila i moduli per `asyncpg`. L'immagine finale gira come utente non-root `radar` con `PYTHONPATH=/app`.
- **Frontend (Angular)**: La fase `builder` esegue `npm install` e compila staticamente l'app, trasferendo solo la cartella `/dist/` nell'immagine `nginx:alpine`.

---

## 4. Validazione e Verifiche

Una volta avviato, usa questi comandi (da PowerShell o bash) per validare lo stato:

**1. Verifica Nginx e Frontend**
```bash
curl.exe -I http://localhost/health
```

**2. Verifica API Backend**
```bash
curl.exe "http://localhost/api/articles?date=2026-07-13"
```

**3. Ispezione Diretta Database**
```bash
docker compose exec radar-db psql -U radar_user -d radar_db -c "\dt"
```

---

## 5. Setup Miniflux e Ingestion

Miniflux funge da ingestore. Affinché il backend possa estrarre dati, procedi così:

1. Accedi a `http://localhost:8080` usando `MINIFLUX_ADMIN_USERNAME` e password.
2. Vai su **Settings → API Keys → Create** e genera un token.
3. Copia il token nel tuo file `.env` alla voce `MINIFLUX_API_KEY`.
4. Riavvia il backend affinché legga il `.env` aggiornato: `docker compose restart radar-backend`.
5. Inserisci i feed (vedi il file [RSS.txt](../RSS.txt) per fonti raccomandate). 

**Il Ciclo di Polling:**
All'avvio, il backend esegue un "refresh best effort" per svuotare Miniflux. Poi entra in un loop immortale (ogni 900s) che:
- Estrae articoli **unread** (pubblicati nelle ultime 48h).
- Esegue la deduplicazione URL in PostgreSQL prima di inoltrare le richieste.
- Sottopone il contenuto all'LLM.
- Interrompe le chiamate se la soglia giornaliera (RPD) viene superata.

---

## 6. Troubleshooting e Manutenzione

### PostgreSQL: InvalidPasswordError
Se ricevi un errore di password invalida nel backend, verifica di non aver inserito il carattere `$` in `POSTGRES_PASSWORD` o `DATABASE_URL`. Docker Compose interpreta il `$` come interpolazione di variabile e corrompe la stringa.

### Miniflux: Exited (1)
Se il container `radar-miniflux` fallisce in `Exited (1)`, significa che le sue migrazioni non hanno trovato il database pronto. Usa `docker compose restart radar-miniflux` una volta che `radar-db` è sano.

### Limiti LLM (429 Too Many Requests)
Errori 429 dalla console indicano il raggiungimento del cap TPM/RPM. L'architettura è resiliente: ritenterà nel ciclo successivo con backoff. Se l'errore persiste, verifica le quote in Google AI Studio.

### Fallback Vault e Backup Dati
- I dati tabellari sono persistiti nel bind-mount locale `radar/data/postgres/`.
- I file Markdown sono nel vault locale `radar/vault/`. In caso di failure del volume, il sistema effettua il fallback generando gli output su `/app/vault`.
Il backup consiste nel fare una copia sicura di queste due directory fisiche.
