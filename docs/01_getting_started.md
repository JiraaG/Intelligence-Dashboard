# 🚀 Getting Started

Benvenuto in **Radar Informativo Globale**. Questa guida ti accompagnerà passo-passo nell'installazione, configurazione e nel primissimo avvio dell'intera infrastruttura containerizzata.

---

## 1. Prerequisiti
Prima di iniziare, assicurati di avere installato sulla tua macchina (Windows/Linux/macOS):
- **Docker** e **Docker Compose** (v3 o superiore).
- **Node.js 22+** (solo se intendi compilare manualmente il frontend in locale prima del deploy).
- **Python 3.12+** (solo se intendi lanciare il demone senza Docker).
- Una **API Key di Google Gemini** attiva.

---

## 2. Configurazione Iniziale (.env)

Il progetto richiede alcune variabili d'ambiente per funzionare (chiavi API, credenziali DB).
Nella cartella `radar/` troverai un file chiamato `.env.example`. 

1. Duplica il file `.env.example` e rinominalo in `.env`.
2. Compila i valori al suo interno.

```ini
# Esempio di file .env
DATABASE_URL=postgresql://radar_user:radar_pass_secure@radar-db:5432/radar_db

# Credenziali Miniflux
MINIFLUX_API_URL=http://radar-miniflux:8080
MINIFLUX_USERNAME=admin
MINIFLUX_PASSWORD=admin_secure_password

# API Key Google Gemini
GEMINI_API_KEY=AIzaSyB...

# Modalità Debug (False in produzione per nascondere gli stack trace)
DEBUG=False
```

> [!WARNING]
> Mai tracciare su Git il file `.env`! Le credenziali di database e le API Key non devono mai uscire dal tuo computer locale. Il file `.gitignore` è già configurato per proteggerti.

---

## 3. Avvio dell'Infrastruttura (Docker)

L'intero sistema (Database, Demone Python, Frontend Angular, Aggregatore RSS) è pacchettizzato in 4 container orchestrati da Docker Compose.

Dal terminale, posizionati all'interno della cartella `radar/` ed esegui:

```bash
docker compose up --build -d
```

### Cosa succede in background:
1. Viene creata la rete isolata `radar-network`.
2. Si avvia `radar-db` (PostgreSQL).
3. Si avvia `radar-miniflux` per la gestione RSS.
4. Si avvia `radar-backend`, il quale si connette al database, esegue le migrazioni (creazione tabelle) e avvia il demone in loop perpetuo.
5. Si avvia `radar-frontend` (Nginx), che serve l'applicazione Angular sulla porta **80** del tuo computer.

Per verificare che tutto stia girando correttamente:
```bash
docker compose ps
docker compose logs -f radar-backend
```

---

## 4. Configurazione dei Feed RSS (Miniflux)

Affinché il Radar inizi a mostrare notizie sulla mappa, devi dirgli dove andarle a pescare. 
L'aggregatore RSS integrato è **Miniflux**.

1. Apri il browser e vai su `http://localhost:8080`.
2. Fai login usando `MINIFLUX_USERNAME` e `MINIFLUX_PASSWORD` che hai definito nel `.env`.
3. Vai nella sezione **Feeds** -> **Add Feed**.
4. Incolla gli URL delle fonti (es. Reuters, Bloomberg, ANSA).
5. Il backend Python interrogherà automaticamente Miniflux ogni 15 minuti, estraendo solo gli articoli *non letti*, li darà in pasto all'LLM e li salverà.

---

## 5. Visualizzazione della Dashboard

Una volta che il backend ha processato i primi articoli, la mappa inizierà a popolarsi!
Apri il tuo browser all'indirizzo:

👉 **`http://localhost`**

> [!NOTE]
> Il frontend Angular non è esposto tramite un web server di sviluppo (`ng serve`), ma è una build statica altamente ottimizzata, servita da **Nginx** direttamente dal container Docker.
> Nginx funge anche da **Reverse Proxy**: inoltra automaticamente tutte le chiamate fatte a `http://localhost/api/*` al container backend interno `radar-backend:8000`.

---

## 6. Sviluppo e Modifica del Frontend

Se modifichi il codice Angular all'interno di `radar/frontend/src/`, le modifiche **non** appariranno istantaneamente sulla pagina a meno che tu non aggiorni i file pre-compilati e riavvi il container Nginx.

Il workflow corretto per aggiornare l'interfaccia è:

```bash
# 1. Compila il codice in locale
cd radar/frontend
npm run build

# 2. Riavvia il solo container frontend copiando i nuovi file compilati
cd ..
docker compose up --build -d radar-frontend
```
