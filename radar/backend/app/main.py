"""
Radar Informativo Globale — Backend FastAPI (solo API).

Ingestione RSS/LLM: servizio Compose ``radar-worker`` (`python -m app.worker`).
Questo processo espone solo health + REST; pool e migrazioni nel lifespan.
Niente Miniflux / classificazione / outbox qui.

SoT:
    docs/02 §API/worker; skill radar-api-contract; docs/02 §health live vs ready.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.articles_query import (
    DEFAULT_ARTICLES_LIMIT,
    build_articles_count_query,
    build_articles_page_query,
    build_countries_summary_query,
    build_map_summary_query,
    clamp_articles_limit,
    parse_published_date,
)
from app.core.config import CORS_ALLOW_ORIGINS, DATABASE_URL, WORKER_HEARTBEAT_STALE_SECONDS
from app.core.database import bootstrap_database, init_pool
from app.core.heartbeat import evaluate_readiness
from app.core.logging import setup_logging

logger = logging.getLogger("radar.main")


class AppState:
    """Stato globale API: solo pool database (nessun client ingest)."""

    def __init__(self) -> None:
        self.db_pool: Optional[Any] = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Avvio: pool → migrazioni; shutdown: chiudi pool. Nessuna pipeline LLM/Miniflux."""
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

# CORS solo se allowlist non vuota; mai "*". Vuoto = same-origin via Nginx.
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
    """Liveness: processo API su. Compose HEALTHCHECK (non dipende dal worker)."""
    return {"status": "ok", "service": "radar-backend"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Alias di ``/health/live`` per compatibilità."""
    return await health_live()


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, Any]:
    """Readiness: pool + migrazione heartbeat + freshness leader.

    503 = non ready (ops); **non** deve far restartare l'API — Compose usa live.
    SoT: docs/02 §health; AGENTS §4.4.
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
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    category: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
    cursor: Optional[int] = Query(None, ge=1),
    limit: int = Query(DEFAULT_ARTICLES_LIMIT, ge=1),
):
    """Pagina articoli day-scoped: envelope ``{items, next_cursor, total}`` (non array nudo).

    Keyset ``id DESC``, cursore esclusivo (``id < cursor``). ``limit`` capped a 100.
    Fetch ``limit+1`` per sapere se esiste una pagina successiva senza round-trip extra.
    SoT: skill radar-api-contract Phase 5.
    """
    empty = {"items": [], "next_cursor": None, "total": 0}
    if not state.db_pool:
        return empty

    pub_date = parse_published_date(date)
    page_limit = clamp_articles_limit(limit)
    # Una riga in più: se arriva, c'è next_cursor.
    fetch_limit = page_limit + 1

    count_sql, count_params = build_articles_count_query(
        pub_date,
        sentiment=sentiment,
        relevance_level=relevance_level,
        country=country,
        category=category,
    )
    page_sql, page_params = build_articles_page_query(
        pub_date,
        sentiment=sentiment,
        relevance_level=relevance_level,
        country=country,
        category=category,
        cursor=cursor,
        limit=fetch_limit,
    )

    async with state.db_pool.acquire() as conn:
        total = int(await conn.fetchval(count_sql, *count_params) or 0)
        rows = await conn.fetch(page_sql, *page_params)

    has_more = len(rows) > page_limit
    page_rows = rows[:page_limit]
    items = [dict(row) for row in page_rows]
    next_cursor: Optional[int] = items[-1]["id"] if has_more and items else None
    return {"items": items, "next_cursor": next_cursor, "total": total}


@app.get("/api/map-summary")
async def get_map_summary(
    date: str,
    sentiment: Optional[str] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    """Aggregato ``country_code × primary_category`` per hatching day-view sulla mappa."""
    if not state.db_pool:
        return []

    pub_date = parse_published_date(date)
    sql, params = build_map_summary_query(
        pub_date,
        sentiment=sentiment,
        relevance_level=relevance_level,
    )

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(row) for row in rows]


@app.get("/api/countries")
async def get_countries_summary(
    date: str,
    sentiment: Optional[str] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    """Rollup compat per paese (senza join junction → nessun rischio cartesiano)."""
    if not state.db_pool:
        return []

    pub_date = parse_published_date(date)
    sql, params = build_countries_summary_query(
        pub_date,
        sentiment=sentiment,
        relevance_level=relevance_level,
    )

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(row) for row in rows]


class ReadStatusUpdate(BaseModel):
    """Body PATCH read-status: solo il flag ``is_read``."""

    is_read: bool


@app.patch("/api/articles/{article_id}/read_status")
async def update_article_read_status(article_id: int, status: ReadStatusUpdate):
    """Aggiorna ``articles.is_read``; 404 se id assente. Usato dal FE (state ottimistico)."""
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
