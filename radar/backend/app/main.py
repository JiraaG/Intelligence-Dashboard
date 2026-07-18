"""
Radar Informativo Globale — Backend FastAPI (solo API).

Ingestione RSS/LLM: servizio Compose ``radar-worker`` (`python -m app.worker`).
Questo processo espone solo health + REST; pool e migrazioni nel lifespan.
Niente Miniflux / classificazione / outbox qui.

SoT:
    docs/02 §API/worker; skill radar-api-contract; docs/02 §health live vs ready.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional, AsyncIterator

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Response, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.articles_query import (
    DEFAULT_ARTICLES_LIMIT,
    build_articles_count_query,
    build_articles_page_query,
    build_countries_summary_query,
    build_map_summary_query,
    build_map_relations_query,
    build_saved_summary_query,
    clamp_articles_limit,
    normalize_sentiments,
    parse_published_date,
)
from app.core.config import (
    CORS_ALLOW_ORIGINS,
    DATABASE_URL,
    MINIFLUX_WEBHOOK_SECRET,
    WORKER_HEARTBEAT_STALE_SECONDS,
)
from app.core.database import bootstrap_database, init_pool
from app.core.heartbeat import evaluate_readiness
from app.core.logging import setup_logging

logger = logging.getLogger("radar.main")


class SSEBroadcastManager:
    """Fan-out in-process: 1 publisher, N code client SSE (event-loop singolo)."""

    def __init__(self, *, queue_maxsize: int = 32) -> None:
        self._queue_maxsize = queue_maxsize
        self._subscribers: set[asyncio.Queue[str | None]] = set()

    def subscribe(self) -> asyncio.Queue[str | None]:
        q: asyncio.Queue[str | None] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str | None]) -> None:
        self._subscribers.discard(q)

    def publish(self, payload: str) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    logger.warning("SSE client queue piena: evento scartato.")

    def close_all(self) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self._subscribers.clear()


class AppState:
    """Stato globale API: pool database e gestore eventi real-time SSE (Fase B)."""

    def __init__(self) -> None:
        self.db_pool: Optional[Any] = None
        self.sse: SSEBroadcastManager = SSEBroadcastManager()
        self.listen_conn: Optional[asyncpg.Connection] = None
        self.listen_ready: asyncio.Event = asyncio.Event()
        self._article_notify_callback: Any = None


state = AppState()


async def backend_article_listener() -> None:
    """Una LISTEN globale su radar_article_processed → SSEBroadcastManager."""
    conn = await asyncpg.connect(DATABASE_URL)
    state.listen_conn = conn

    def _on_notify(
        _conn: asyncpg.Connection,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        state.sse.publish(payload)

    state._article_notify_callback = _on_notify
    await conn.add_listener("radar_article_processed", _on_notify)
    state.listen_ready.set()
    logger.info("LISTEN backend attivo su radar_article_processed.")
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        raise
    finally:
        try:
            await conn.close()
        except Exception as err:
            logger.debug("Chiusura listen_conn API: %s", err)
        state.listen_conn = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Avvio: pool → migrazioni → listen; shutdown: listen task cancel → chiudi pool."""
    setup_logging()
    logger.info("Avvio del server FastAPI (API only). Inizializzazione pool...")
    listener_task: asyncio.Task | None = None
    try:
        state.db_pool = await init_pool(DATABASE_URL)
        await bootstrap_database(state.db_pool)

        # Avvio del listener dedicato PG LISTEN per gli SSE (Fase B)
        listener_task = asyncio.create_task(
            backend_article_listener(),
            name="radar-backend-article-listener",
        )
        await asyncio.wait_for(state.listen_ready.wait(), timeout=30.0)
        logger.info("Bootstrap API + LISTEN SSE completato.")
    except Exception as init_err:
        logger.critical("Errore critico all'avvio del lifespan: %s", init_err, exc_info=True)
        if listener_task is not None:
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
        if state.db_pool is not None:
            await state.db_pool.close()
            state.db_pool = None
        raise

    yield

    logger.info("Arresto del server FastAPI in corso...")
    state.sse.close_all()
    if listener_task is not None:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
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


@app.get("/api/map-relations")
async def get_map_relations(
    date: str,
    sentiment: Optional[list[str]] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5),
):
    """Aggregato delle relazioni undirected ``source_country ↔ target_country`` per categoria.

    Stessi filtri opzionali di map-summary (sentiment e relevance_level).
    """
    if not state.db_pool:
        return []

    pub_date = parse_published_date(date)
    sentiments = normalize_sentiments(sentiment)
    sql, params = build_map_relations_query(
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


def verify_miniflux_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verifica HMAC-SHA256 Miniflux (hex) con confronto a tempo costante."""
    if not MINIFLUX_WEBHOOK_SECRET:
        return False
    if not signature_header:
        return False
    expected = hmac.new(
        MINIFLUX_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())


@app.post("/api/webhooks/miniflux", status_code=202)
async def miniflux_webhook(
    request: Request,
    x_miniflux_signature: str | None = Header(default=None, alias="X-Miniflux-Signature"),
    x_miniflux_event_type: str | None = Header(default=None, alias="X-Miniflux-Event-Type"),
) -> dict[str, str]:
    """Trigger-only: HMAC + NOTIFY. Nessuna classificazione / commit qui."""
    if state.db_pool is None:
        raise HTTPException(status_code=503, detail="database_unavailable")

    raw_body = await request.body()
    if not verify_miniflux_signature(raw_body, x_miniflux_signature):
        logger.warning("Webhook Miniflux rifiutato: firma assente o non valida.")
        raise HTTPException(status_code=401, detail="invalid_signature")

    try:
        payload: dict[str, Any] = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    event_type = (x_miniflux_event_type or payload.get("event_type") or "").strip()
    if event_type != "new_entries":
        return {"status": "ignored", "event_type": event_type or "unknown"}

    entry_id = "0"
    entries = payload.get("entries")
    if isinstance(entries, list) and entries:
        first = entries[0]
        if isinstance(first, dict) and first.get("id") is not None:
            entry_id = str(first["id"])

    async with state.db_pool.acquire() as conn:
        await conn.execute("SELECT pg_notify($1, $2)", "radar_worker_trigger", entry_id)

    logger.info("Webhook new_entries accettato; NOTIFY radar_worker_trigger id=%s", entry_id)
    return {"status": "accepted"}


SSE_PING_INTERVAL_SECONDS = 30.0


@app.get("/api/articles/events")
async def articles_events() -> StreamingResponse:
    """Endpoint SSE per lo streaming degli articoli processati in tempo reale (Fase B)."""
    async def event_generator() -> AsyncIterator[bytes]:
        queue = state.sse.subscribe()
        try:
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(),
                        timeout=SSE_PING_INTERVAL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    yield b": ping\n\n"
                    continue
                if item is None:
                    break
                data = item.replace("\n", " ").replace("\r", " ")
                yield f"event: article_processed\ndata: {data}\n\n".encode("utf-8")
        finally:
            state.sse.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
