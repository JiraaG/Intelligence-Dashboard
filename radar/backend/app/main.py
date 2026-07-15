"""
Radar Informativo Globale — Backend FastAPI App (API only).

Ingestione RSS/LLM: servizio Compose ``radar-worker`` (`python -m app.worker`).
Questo processo espone solo health + REST; pool e migrazioni nel lifespan.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import CORS_ALLOW_ORIGINS, DATABASE_URL, WORKER_HEARTBEAT_STALE_SECONDS
from app.core.database import bootstrap_database, init_pool
from app.core.heartbeat import evaluate_readiness
from app.core.logging import setup_logging

logger = logging.getLogger("radar.main")


class AppState:
    """Stato globale API: solo pool database."""

    def __init__(self) -> None:
        self.db_pool: Optional[asyncpg.Pool] = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """init pool → migrations; reverse on shutdown. No pipeline / Miniflux / Gemini."""
    setup_logging()
    logger.info("Avvio del server FastAPI (API only). Inizializzazione pool...")

    try:
        state.db_pool = await init_pool(DATABASE_URL)
        await bootstrap_database(state.db_pool)
        logger.info("Bootstrap API completato.")
    except Exception as init_err:
        logger.critical("Errore critico all'avvio del lifespan: %s", init_err, exc_info=True)
        if state.db_pool is not None:
            await state.db_pool.close()
            state.db_pool = None
        raise

    yield

    logger.info("Arresto del server FastAPI in corso...")
    if state.db_pool is not None:
        await state.db_pool.close()
        state.db_pool = None
        logger.info("Pool connessioni PostgreSQL chiuso correttamente.")

    logger.info("Radar Backend arrestato.")


app = FastAPI(
    title="Radar Informativo Globale — API",
    description="Backend API del Radar geopolitico ed infrastrutturale.",
    version="1.0.0",
    lifespan=lifespan,
)

if CORS_ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info("CORS allowlist attiva: %s", CORS_ALLOW_ORIGINS)
else:
    logger.info("CORS disabilitato (allowlist vuota — same-origin via Nginx).")


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    """Liveness: processo API su. Usato da Compose HEALTHCHECK (non dipende dal worker)."""
    return {"status": "ok", "service": "radar-backend"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Alias di /health/live per compatibilità."""
    return await health_live()


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, Any]:
    """
    Readiness: pool, migrazione heartbeat, freshness leader.
    503 non deve far restartare l'API (Compose usa /health/live).
    """
    if state.db_pool is None:
        response.status_code = 503
        return {
            "status": "not_ready",
            "service": "radar-backend",
            "reasons": ["pool_unavailable"],
        }

    ready, details = await evaluate_readiness(
        state.db_pool,
        stale_seconds=WORKER_HEARTBEAT_STALE_SECONDS,
    )
    payload: dict[str, Any] = {
        "status": "ready" if ready else "not_ready",
        "service": "radar-backend",
        **details,
    }
    if not ready:
        response.status_code = 503
    return payload


@app.get("/api/articles")
async def get_articles(
    date: str,
    sentiment: Optional[str] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    if not state.db_pool:
        return []

    try:
        pub_date = datetime.strptime(date.replace("/", "-"), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato data non valido. Usa il formato ISO YYYY-MM-DD.",
        )

    query_parts = [
        """
        SELECT
            a.id, a.title, a.summary, a.published_at::text AS published_at, a.source_url,
            a.country_code, a.latitude, a.longitude, a.primary_category,
            a.sentiment, a.relevance_level, a.infrastructural_entities, a.feed_title,
            a.is_read,
            COALESCE(array_agg(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL), '{}') AS companies_involved,
            COALESCE(array_agg(DISTINCT t.name) FILTER (WHERE t.name IS NOT NULL), '{}') AS tags
        FROM articles a
        LEFT JOIN article_companies ac ON ac.article_id = a.id
        LEFT JOIN companies c ON c.id = ac.company_id
        LEFT JOIN article_tags at2 ON at2.article_id = a.id
        LEFT JOIN tags t ON t.id = at2.tag_id
        WHERE a.published_at = $1
        """
    ]

    params: list = [pub_date]

    if sentiment:
        params.append(sentiment)
        query_parts.append(f"AND a.sentiment = ${len(params)}")

    if relevance_level is not None:
        params.append(relevance_level)
        query_parts.append(f"AND a.relevance_level = ${len(params)}")

    query_parts.append("GROUP BY a.id ORDER BY a.id DESC")
    final_query = " ".join(query_parts)

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(final_query, *params)

    return [dict(row) for row in rows]


@app.get("/api/countries")
async def get_countries_summary(
    date: str,
    sentiment: Optional[str] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    if not state.db_pool:
        return []

    try:
        pub_date = datetime.strptime(date.replace("/", "-"), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato data non valido. Usa il formato ISO YYYY-MM-DD.",
        )

    query_parts = [
        """
        SELECT
            country_code,
            array_agg(DISTINCT primary_category) AS categories,
            COUNT(*) AS article_count
        FROM articles
        WHERE published_at = $1
        """
    ]

    params: list = [pub_date]

    if sentiment:
        params.append(sentiment)
        query_parts.append(f"AND sentiment = ${len(params)}")

    if relevance_level is not None:
        params.append(relevance_level)
        query_parts.append(f"AND relevance_level = ${len(params)}")

    query_parts.append("GROUP BY country_code")
    final_query = " ".join(query_parts)

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(final_query, *params)

    return [dict(row) for row in rows]


class ReadStatusUpdate(BaseModel):
    is_read: bool


@app.patch("/api/articles/{article_id}/read_status")
async def update_article_read_status(article_id: int, status: ReadStatusUpdate):
    if not state.db_pool:
        raise HTTPException(status_code=500, detail="Database non disponibile")

    async with state.db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE articles SET is_read = $1, updated_at = NOW() WHERE id = $2",
            status.is_read,
            article_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Articolo non trovato")

    return {"status": "success", "is_read": status.is_read}
