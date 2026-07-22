# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Installa dipendenze di build (necessarie per asyncpg che compila estensioni C)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copia e installa dipendenze runtime only (layer separato per cache Docker)
# NOTA: il build context è ./backend, quindi requirements.txt è in app/
# pytest* vive in app/requirements-dev.txt e NON entra nell'immagine production.
COPY app/requirements.txt .
# Torch CPU-only: evita wheel CUDA multi-GB inutili (embedder ST gira su CPU).
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt


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

# PYTHONPATH=/app rende importabile il package `app` (API e worker condividono l'immagine)
ENV PYTHONPATH=/app

# Esegui come utente non-root
USER radar

# Pre-download del modello di embedding per utilizzo offline in container
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Porta API FastAPI (il servizio radar-worker override il CMD e non espone HTTP)
EXPOSE 8000

# Liveness only — Compose healthcheck mirrors this; readiness is ops-only (/health/ready).
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Default: API uvicorn. Worker Compose: command ["python", "-m", "app.worker"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
