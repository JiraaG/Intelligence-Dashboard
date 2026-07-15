# Regole Docker — Path-Scope: `docker-compose.yml`, `**/Dockerfile`, `nginx.conf`
> **Scope:** Queste regole si applicano ESCLUSIVAMENTE ai file di containerizzazione.
> Non caricare queste regole durante il lavoro su `backend/` o `frontend/`.
> **Priorità:** ALTA — garantiscono isolamento di rete, persistenza dati e deploy plug-and-play.

---

## Principio Architetturale Fondamentale

Il sistema Radar è composto da **cinque servizi Docker** su due reti bridge:
`radar-edge` (frontend ↔ backend) e `radar-data` (backend, worker, db, miniflux).
Il frontend espone la porta **80** su tutte le interfacce (plug-and-play).
Miniflux **non** pubblica porte host di default (override `docker-compose.lan.yml` o
`docker-compose.hardened.yml` per admin UI).

```
Internet/LAN → [Porta 80] → radar-frontend (Nginx) ──radar-edge──→ radar-backend
                                                                  │
                                                            radar-data
                                          ┌──────────┬────────────┼──────────┐
                                          │          │            │          │
                                   radar-worker   radar-db   radar-miniflux
                                      (ingest)
```

Phase 3 DONE: edge/data, `/health/live`+`/ready`, CSP, ops backup, soft hardening.
Phase 4 DONE: frontend lifecycle/security (non tocca Compose).
Phase 6 DONE / GATE VERDE: docs/CI/GeoJSON/runbook. **Deferred post–Phase 6 (prodotto):** image digest pin SHA e drop `--legacy-peer-deps` (quando matrix Angular/CDK/PrimeNG allineata).
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

**OBBLIGATORIO (compose reale):**
```yaml
radar-db:
  volumes:
    - ./data/postgres:/var/lib/postgresql/data
```

**VIETATO:**
```yaml
# NO: Volume anonimo senza path host (dati non accessibili / persi al down -v)
volumes:
  - /var/lib/postgresql/data

# NO: Named volume + driver_opts (non è lo schema Compose attuale)
volumes:
  radar-postgres-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./data/postgres
```

---

## Regola 3: Reti edge + data (Phase 3)

Frontend mai sulla stessa rete di PostgreSQL.

**OBBLIGATORIO:**
```yaml
networks:
  radar-edge:
    driver: bridge
  radar-data:
    driver: bridge
    # internal: false — worker/backend need egress (Gemini / Miniflux fetch)

# frontend: solo radar-edge
# backend: radar-edge + radar-data
# worker, db, miniflux: solo radar-data
```

---

## Regola 4: Healthcheck Obbligatori

Compose healthcheck del backend = **`/health/live`** (non ready).
Frontend `depends_on` backend healthy (= live). Worker attende db + Miniflux healthy.
Miniflux: `["CMD", "/usr/bin/miniflux", "-healthcheck", "auto"]`.

```yaml
# Backend liveness (Compose + Dockerfile)
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s

# Frontend healthcheck (Nginx Alpine → wget)
healthcheck:
  test: ["CMD", "wget", "-qO-", "http://127.0.0.1:80/health"]
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

## Regola 6: Dockerfile Backend — Multi-Stage Python 3.12 Slim

Allineato a `radar/backend/Dockerfile`. `WORKDIR=/app`, `PYTHONPATH=/app`.
API default: `uvicorn app.main:app`. Worker Compose override: `python -m app.worker`.

```dockerfile
# Stage 1: Builder (gcc + libpq-dev per asyncpg)
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production
FROM python:3.12-slim AS production
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 -s /bin/sh radar
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=radar:radar app/ app/
COPY --chown=radar:radar scripts/ scripts/
COPY --chown=radar:radar migrations/ migrations/
ENV PYTHONPATH=/app
USER radar
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

---

## Regola 7: Dockerfile Frontend — Multi-Stage Build (Zero Config)

> [!NOTE]
> Per garantire una vera distribuzione plug-and-play ("Zero-Config"), il modulo Radar di produzione DEVE compilare il frontend all'interno di un container. Non si deve mai richiedere all'utente di installare Node.js.
> Il workflow per aggiornare il frontend è unicamente: `docker compose up --build -d radar-frontend`

```dockerfile
# Stage 1: Build Angular (allineato a radar/frontend/Dockerfile)
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --legacy-peer-deps
COPY . .
# GeoJSON è gitignored: fetch+verify OBBLIGATORIO prima del build
RUN node scripts/verify-geojson.mjs --fetch
RUN npm run build

# Stage 2: Nginx Production Server
FROM nginx:1.27-alpine AS production
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/radar-frontend/browser /usr/share/nginx/html
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

> **Deferred post–Phase 6:** drop `--legacy-peer-deps` solo quando la matrix Angular/CDK/PrimeNG è allineata; digest pin immagini = opzionale prodotto.

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

    # Headers di sicurezza (no X-XSS-Protection — obsoleto)
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    # CSP: Angular + Carto tiles + Google Fonts (vedi nginx.conf reale)

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
