# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Installa dipendenze di build (necessarie per asyncpg che compila estensioni C)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copia e installa dipendenze (layer separato per cache Docker efficiente)
# NOTA: il build context è ./backend, quindi requirements.txt è in app/
COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Production ─────────────────────────────────────────────────────
FROM python:3.12-slim AS production

# Runtime deps per asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crea utente non-root per sicurezza
RUN useradd -m -u 1000 -s /bin/sh radar

# Copia dipendenze installate dallo stage builder
COPY --from=builder /install /usr/local
WORKDIR /app

# Copia codice sorgente dall'app/ del build context
# Il build context è ./backend → copiamo la sottocartella app/ in /app/app
COPY --chown=radar:radar app/ app/
COPY --chown=radar:radar scripts/ scripts/
COPY --chown=radar:radar migrations/ migrations/

# Cambiamo il WORKDIR a /app/app dopo averlo copiato per assicurarci che sia di proprietà di 'radar'
WORKDIR /app/app

# Aggiungi /app al PYTHONPATH per rendere importabile il package 'app'
ENV PYTHONPATH=/app

# Esegui come utente non-root
USER radar

# Porta API FastAPI
EXPOSE 8000

# Healthcheck: verifica che l'endpoint /health risponda
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando di avvio: uvicorn in modalità produzione
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
