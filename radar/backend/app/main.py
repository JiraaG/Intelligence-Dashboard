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
    build_saved_summary_query,
    clamp_articles_limit,
    normalize_sentiments,
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
    date: Optional[str] = None,
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    category: Optional[str] = Query(None),
    sentiment: Optional[list[str]] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
    cursor: Optional[int] = Query(None, ge=1),
    limit: int = Query(DEFAULT_ARTICLES_LIMIT, ge=1),
    saved: bool = Query(False),
):
    """Pagina articoli: envelope ``{items, next_cursor, total}`` (non array nudo).

    Day-scoped se ``date`` (default); con ``saved=true`` ignora ``date`` e filtra
    ``is_saved``. Keyset ``id DESC``, cursore esclusivo (``id < cursor``).
    ``limit`` capped a 100. ``sentiment`` ripetibile (OR).
    SoT: skill radar-api-contract Phase 5.
    """
    empty = {"items": [], "next_cursor": None, "total": 0}
    if not state.db_pool:
        return empty

    if not saved and not date:
        raise HTTPException(
            status_code=400,
            detail="Parametro date obbligatorio salvo saved=true.",
        )

    pub_date = parse_published_date(date) if (not saved and date) else None
    sentiments = normalize_sentiments(sentiment)
    page_limit = clamp_articles_limit(limit)
    # Una riga in più: se arriva, c'è next_cursor.
    fetch_limit = page_limit + 1

    count_sql, count_params = build_articles_count_query(
        pub_date,
        sentiment=sentiments,
        relevance_level=relevance_level,
        country=country,
        category=category,
        saved_only=saved,
    )
    page_sql, page_params = build_articles_page_query(
        pub_date,
        sentiment=sentiments,
        relevance_level=relevance_level,
        country=country,
        category=category,
        cursor=cursor,
        limit=fetch_limit,
        saved_only=saved,
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
    sentiment: Optional[list[str]] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    """Aggregato ``country_code × primary_category`` per hatching day-view sulla mappa.

    ``sentiment`` ripetibile (OR), allineato a ``/api/articles``.
    """
    if not state.db_pool:
        return []

    pub_date = parse_published_date(date)
    sentiments = normalize_sentiments(sentiment)
    sql, params = build_map_summary_query(
        pub_date,
        sentiment=sentiments,
        relevance_level=relevance_level,
    )

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(row) for row in rows]


@app.get("/api/saved-summary")
async def get_saved_summary(
    sentiment: Optional[list[str]] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    """Aggregato ``country_code × primary_category`` per articoli salvati (no date)."""
    if not state.db_pool:
        return []

    sentiments = normalize_sentiments(sentiment)
    sql, params = build_saved_summary_query(
        sentiment=sentiments,
        relevance_level=relevance_level,
    )

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(row) for row in rows]


@app.get("/api/countries")
async def get_countries_summary(
    date: str,
    sentiment: Optional[list[str]] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    """Rollup compat per paese (senza join junction → nessun rischio cartesiano)."""
    if not state.db_pool:
        return []

    pub_date = parse_published_date(date)
    sentiments = normalize_sentiments(sentiment)
    sql, params = build_countries_summary_query(
        pub_date,
        sentiment=sentiments,
        relevance_level=relevance_level,
    )

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [dict(row) for row in rows]


class ReadStatusUpdate(BaseModel):
    """Body PATCH read-status: solo il flag ``is_read``."""

    is_read: bool


class SavedStatusUpdate(BaseModel):
    """Body PATCH saved-status: solo il flag ``is_saved``."""

    is_saved: bool


@app.patch("/api/articles/{article_id}/read_status")
async def update_article_read_status(article_id: int, status: ReadStatusUpdate):
    """Aggiorna ``articles.is_read``; unread ⇒ anche ``is_saved=false``.

    404 se id assente. Usato dal FE (state ottimistico).
    """
    if not state.db_pool:
        raise HTTPException(status_code=500, detail="Database non disponibile")

    async with state.db_pool.acquire() as conn:
        if status.is_read:
            result = await conn.execute(
                "UPDATE articles SET is_read = TRUE, updated_at = NOW() WHERE id = $1",
                article_id,
            )
            is_saved: Optional[bool] = None
            if result != "UPDATE 0":
                is_saved = await conn.fetchval(
                    "SELECT is_saved FROM articles WHERE id = $1",
                    article_id,
                )
        else:
            result = await conn.execute(
                """
                UPDATE articles
                SET is_read = FALSE, is_saved = FALSE, updated_at = NOW()
                WHERE id = $1
                """,
                article_id,
            )
            is_saved = False
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Articolo non trovato")

    payload: dict[str, Any] = {"status": "success", "is_read": status.is_read}
    if is_saved is not None:
        payload["is_saved"] = bool(is_saved)
    return payload


@app.patch("/api/articles/{article_id}/saved_status")
async def update_article_saved_status(article_id: int, status: SavedStatusUpdate):
    """Aggiorna ``articles.is_saved``; save ⇒ anche ``is_read=true``. Unsave non forza unread."""
    if not state.db_pool:
        raise HTTPException(status_code=500, detail="Database non disponibile")

    async with state.db_pool.acquire() as conn:
        if status.is_saved:
            result = await conn.execute(
                """
                UPDATE articles
                SET is_saved = TRUE, is_read = TRUE, updated_at = NOW()
                WHERE id = $1
                """,
                article_id,
            )
            is_read = True
        else:
            result = await conn.execute(
                "UPDATE articles SET is_saved = FALSE, updated_at = NOW() WHERE id = $1",
                article_id,
            )
            is_read = None
            if result != "UPDATE 0":
                is_read = await conn.fetchval(
                    "SELECT is_read FROM articles WHERE id = $1",
                    article_id,
                )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Articolo non trovato")

    payload: dict[str, Any] = {"status": "success", "is_saved": status.is_saved}
    if is_read is not None:
        payload["is_read"] = bool(is_read)
    return payload
