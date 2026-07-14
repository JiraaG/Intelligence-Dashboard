# Regole Docker — Path-Scope: `docker-compose.yml`, `**/Dockerfile`, `nginx.conf`
> **Scope:** Queste regole si applicano ESCLUSIVAMENTE ai file di containerizzazione.
> Non caricare queste regole durante il lavoro su `backend/` o `frontend/`.
> **Priorità:** ALTA — garantiscono isolamento di rete, persistenza dati e deploy plug-and-play.

---

## Principio Architetturale Fondamentale

Il sistema Radar è composto da **cinque servizi Docker** su una rete bridge interna
`radar-network`: `radar-db`, `radar-backend` (API), `radar-worker` (ingest),
`radar-frontend`, `radar-miniflux`.
Il frontend espone la porta 80; Miniflux può esporre 8080 (da restringere in Phase 3).

```
Internet → [Porta 80] → radar-frontend (Nginx)
                                │
              rete interna radar-network
          ┌──────────┬──────────┼──────────┐
          │          │          │          │
   radar-backend  radar-worker radar-db  radar-miniflux
      (API)         (ingest)
```

Phase 3 del Consolidation Plan introdurrà reti `edge`/`data` e hardening — **non** sono lo stato attuale.
---

## Regola 1: Cinque Servizi, Nomi Immutabili

I nomi dei servizi in `docker-compose.yml` sono fissi e referenziati nel codice.
Non rinominarli senza aggiornare anche le variabili d'ambiente e il codice Python.

| Nome Servizio     | Immagine Base          | Funzione                              |
|-------------------|------------------------|---------------------------------------|
| `radar-db`        | `postgres:15-alpine`   | Database PostgreSQL persistente       |
| `radar-backend`   | Custom Python 3.12     | API REST FastAPI (no ingest)          |
| `radar-worker`    | Stessa immagine backend | Ingest Miniflux→Gemini→DB/Vault (`python -m app.worker`) |
| `radar-frontend`  | Custom Node + Nginx    | Build Angular 21 + web server Nginx   |
| `radar-miniflux`  | `miniflux/miniflux:2.3.2` | Aggregatore RSS integrato nello stack |

---

## Regola 2: Volume Persistente Obbligatorio per PostgreSQL

Il volume PostgreSQL deve essere persistente sul filesystem dell'host.
Se il container viene ricreato, i dati NON devono andare persi.

**OBBLIGATORIO:**
```yaml
volumes:
  radar-postgres-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./data/postgres  # Cartella locale sul host
```

**VIETATO:**
```yaml
# NO: Volume senza nome (dati persi al docker-compose down -v)
volumes:
  - /var/lib/postgresql/data

# NO: Volume named ma senza binding locale (dati non accessibili dall'host)
volumes:
  postgres_data:
```

---

## Regola 3: Rete Virtuale Interna Dedicata

Tutti i servizi devono essere connessi a una rete interna.
Il frontend non deve avere accesso diretto al database.

**OBBLIGATORIO:**
```yaml
networks:
  radar-network:
    driver: bridge
    internal: false  # false = permette al backend di uscire su Internet per Gemini/Miniflux

# In ogni servizio:
networks:
  - radar-network
```

---

## Regola 4: Healthcheck Obbligatori

Ogni servizio deve avere un healthcheck. Il backend e il frontend dipendono dal DB.
Usare `depends_on` con `condition: service_healthy` per la sequenza di avvio.

```yaml
# PostgreSQL healthcheck
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 20s

# Backend healthcheck (endpoint /health su FastAPI)
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s

# Frontend healthcheck (Nginx risponde su porta 80/health)
healthcheck:
  test: ["CMD", "curl", "-sf", "http://127.0.0.1:80/health"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 15s
```

---

## Regola 5: Variabili d'Ambiente tramite .env

Le credenziali non devono essere scritte in `docker-compose.yml`.
Usare `env_file: .env` e riferimenti a variabili con `${VARIABILE}`.

**OBBLIGATORIO:**
```yaml
radar-backend:
  env_file:
    - .env
  environment:
    DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@radar-db:5432/${POSTGRES_DB}
```

**VIETATO:**
```yaml
# NO: Credenziali hardcoded in docker-compose.yml
environment:
  DATABASE_URL: postgresql://admin:mysecretpassword@radar-db:5432/radar_db
  GEMINI_API_KEY: AIzaSyXXXXXXXXXXXXXX
```

> [!WARNING]
> **Vincolo di Sicurezza sulle Password (No `$`):**
> È vietato l'uso del carattere `$` all'interno del valore delle password (es. `POSTGRES_PASSWORD`). Docker Compose interpreta il `$` come tentativo di interpolazione di variabili d'ambiente, alterando il valore reale della password e causando fallimenti di connessione al database. Usare esclusivamente caratteri alfanumerici, `-` o `_`.

---

## Regola 6: Dockerfile Backend — Python 3.12 Slim

```dockerfile
# Usa sempre slim, non alpine (compatibilità librerie C)
FROM python:3.12-slim

# Nessun utente root in produzione
RUN useradd -m -u 1000 radar
WORKDIR /app

# Installa dipendenze prima del codice (layer caching Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice
COPY --chown=radar:radar . .

# Esegui come utente non-root
USER radar

# Healthcheck endpoint
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Regola 7: Dockerfile Frontend — Multi-Stage Build (Zero Config)

> [!NOTE]
> Per garantire una vera distribuzione plug-and-play ("Zero-Config"), il modulo Radar di produzione DEVE compilare il frontend all'interno di un container. Non si deve mai richiedere all'utente di installare Node.js.
> Il workflow per aggiornare il frontend è unicamente: `docker compose up --build -d radar-frontend`

```dockerfile
# Stage 1: Build dell'applicazione Angular
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . .
RUN npm run build

# Stage 2: Nginx Production Server
FROM nginx:alpine-slim AS production
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/radar-frontend/browser /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## Regola 8: nginx.conf — SPA Routing e Sicurezza

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip per performance
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1000;

    # SPA: tutte le route → index.html (client-side routing Angular)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API al backend (evita CORS in produzione e previene errori 502 Bad Gateway tramite DNS resolver dinamico)
    # IMPORTANTE: Con le variabili in proxy_pass, è obbligatorio usare $request_uri esplicito
    location /api/ {
        resolver 127.0.0.11 valid=10s;
        set $backend_upstream http://radar-backend:8000;
        proxy_pass $backend_upstream$request_uri;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
        proxy_connect_timeout 10s;
    }

    # Headers di sicurezza
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Cache assets statici
    location ~* \.(js|css|png|jpg|ico|svg|woff2)$ {
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # NON cachare index.html (aggiornamenti app immediati)
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
}
```

---

## Regola 9: File .dockerignore Obbligatori

Sia per il frontend che per il backend è **obbligatorio** includere un file `.dockerignore` nella propria root di build per impedire l'invio di directory pesanti (come `node_modules`, `.venv`, cache locali `.angular`) nel contesto di build inviato al demone Docker.

**Esempio di `.dockerignore` per il Frontend:**
```ignore
node_modules/
dist/
.angular/
.git/
README.md
```

**Esempio di `.dockerignore` per il Backend:**
```ignore
.venv/
__pycache__/
*.pyc
.git/
.env
README.md
```

---

## Criteri di Accettazione Automatici

| Pattern Vietato                          | Motivo                                    |
|------------------------------------------|-------------------------------------------|
| Credenziali hardcoded in docker-compose  | Security violation                        |
| Volume senza bind mount locale           | Dati persi al container restart           |
| `depends_on` senza healthcheck           | Race condition all'avvio                  |
| Container che gira come `root`           | Security best practice Docker             |
| Porta PostgreSQL (5432) esposta all'host | DB accessibile direttamente da Internet   |
| Build Angular senza `--configuration=production` | Bundle non ottimizzato             |
| Nginx senza proxy `/api/` al backend     | CORS errors in produzione                 |
| Uso del carattere `$` nelle password     | Causa errori di interpolazione di variabili in Docker Compose |
| Assenza di file `.dockerignore`          | Rallentamento della build e caricamento di contesti pesanti (es. `node_modules`, `.venv`) |
| proxy_pass statico in Nginx senza resolver | Causa errori 502 Bad Gateway se l'IP del container backend cambia dopo un riavvio |
