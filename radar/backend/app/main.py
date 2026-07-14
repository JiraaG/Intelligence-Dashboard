"""
Radar Informativo Globale — Backend FastAPI App
Coordinatore e API Router centrale conforme all'architettura ECC.

Pipeline: Miniflux RSS → Validazione → Sanitizzazione HTML → Deduplicazione URL →
          Google Gemini (Structured Output) → PostgreSQL + Outbox → Vault Obsidian → Mark-read
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import (
    DATABASE_URL,
    LLM_RPD,
    MAX_MINIFLUX_RESPONSE_BYTES,
    MINIFLUX_API_KEY,
    MINIFLUX_API_URL,
    MINIFLUX_CONNECT_TIMEOUT,
    MINIFLUX_LIMIT,
    MINIFLUX_READ_TIMEOUT,
    OBSIDIAN_VAULT_PATH,
)
from app.core.database import bootstrap_database, init_pool
from app.core.logging import setup_logging

from app.extraction.client import MinifluxClient
from app.extraction.entry_validation import ValidatedMinifluxEntry
from app.extraction.parser import strip_html_tags
from app.extraction.state import is_article_duplicate

from app.classification.client import ClassificationClient

from app.commit.db_commit import commit_article_to_db
from app.commit.factory import generate_markdown_content
from app.commit.outbox import process_outbox_row, reconcile_outbox
from app.commit.router import get_article_file_path, initialize_vault_directories

logger = logging.getLogger("radar.main")


class AppState:
    """Contenitore per lo stato globale condiviso dell'applicazione."""

    def __init__(self) -> None:
        self.db_pool: Optional[asyncpg.Pool] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.miniflux_client: Optional[MinifluxClient] = None
        self.classification_client: Optional[ClassificationClient] = None
        self.pipeline_task: Optional[asyncio.Task] = None


state = AppState()


async def process_single_entry(app_state: AppState, entry: ValidatedMinifluxEntry) -> bool:
    """
    Elabora un singolo articolo già validato: dedup, sanitize, LLM, commit+outbox, vault, mark-read.
    Ritorna True in caso di completamento (incluso skip duplicato), False in caso di errore.
    """
    entry_id = entry.id
    source_url = entry.source_url
    title = entry.title
    published_date = entry.published_at
    feed_title = entry.feed_title

    try:
        async with app_state.db_pool.acquire() as conn:
            is_dup = await is_article_duplicate(conn, source_url)

        if is_dup:
            logger.info(
                "Articolo duplicato rilevato: '%s'. Marcatura come letto su Miniflux...",
                title[:50],
            )
            await app_state.miniflux_client.mark_as_read([entry_id])
            return True

        clean_content = strip_html_tags(entry.content)

        extracted_article = await app_state.classification_client.classify_article(
            title=title,
            content=clean_content,
            url=source_url,
            date=published_date,
        )

        # Identità autoritativa Miniflux: non lasciare che l'URL del modello selezioni ON CONFLICT.
        extracted_article = extracted_article.model_copy(
            update={
                "source_url": source_url,
                "published_at": published_date,
            }
        )

        md_content = generate_markdown_content(extracted_article)
        file_path = get_article_file_path(extracted_article, vault_path=OBSIDIAN_VAULT_PATH)

        async with app_state.db_pool.acquire() as conn:
            article_id = await commit_article_to_db(
                conn,
                extracted_article,
                feed_title,
                outbox_target_path=file_path,
                outbox_payload=md_content,
                miniflux_entry_id=entry_id,
            )

        async with app_state.db_pool.acquire() as conn:
            outbox_row = await conn.fetchrow(
                """
                SELECT id, article_id, target_path, payload, payload_checksum,
                       attempt_count, miniflux_entry_id, status
                FROM article_outbox
                WHERE article_id = $1
                  AND status IN ('pending', 'failed')
                """,
                article_id,
            )

        if outbox_row is not None:
            ok = await process_outbox_row(app_state.db_pool, outbox_row, app_state.miniflux_client)
            if not ok:
                logger.error(
                    "Commit DB riuscito ma Vault/outbox fallito per article_id=%s; "
                    "verrà riconciliato al prossimo ciclo.",
                    article_id,
                )
                return False

        logger.info(
            "Articolo elaborato e committato correttamente [ID=%s]: '%s'",
            article_id,
            extracted_article.title[:50],
        )
        return True

    except Exception as article_err:
        logger.error(
            "Errore durante l'elaborazione del singolo articolo '%s': %s",
            title[:50],
            article_err,
            exc_info=True,
        )
        return False


async def run_pipeline_cycle(app_state: AppState) -> None:
    """
    Singolo ciclo pipeline (Level 2): reconcile outbox → RPD → fetch → TaskGroup.
    """
    logger.info("=== Avvio di un nuovo ciclo della pipeline di ingestione ===")

    await reconcile_outbox(app_state.db_pool, app_state.miniflux_client)

    async with app_state.db_pool.acquire() as conn:
        processed_today = await conn.fetchval(
            "SELECT count(*) FROM articles WHERE date(created_at) = CURRENT_DATE"
        )
        if processed_today >= LLM_RPD:
            logger.warning(
                "LIMITE RPD RAGGIUNTO: processati %s/%s articoli oggi. "
                "Il ciclo andrà in ibernazione per non superare il Rate Limit giornaliero.",
                processed_today,
                LLM_RPD,
            )
            return

    entries = await app_state.miniflux_client.fetch_unread_entries(limit=MINIFLUX_LIMIT)
    if not entries:
        logger.info("Nessun articolo non letto presente in Miniflux.")
        return

    remaining_rpd = LLM_RPD - processed_today
    if len(entries) > remaining_rpd:
        logger.info(
            "Riduzione lotto da %d a %d per rispettare il limite RPD.",
            len(entries),
            remaining_rpd,
        )
        entries = entries[:remaining_rpd]

    success_count = 0
    failure_count = 0

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(process_single_entry(app_state, entry)) for entry in entries]

    for task in tasks:
        if task.result():
            success_count += 1
        else:
            failure_count += 1

    logger.info(
        "=== Ciclo della pipeline completato: %d elaborati/saltati, %d errori ===",
        success_count,
        failure_count,
    )


async def run_pipeline_loop(app_state: AppState) -> None:
    """Loop infinito demone (Level 1). Polling ogni 900 secondi."""
    logger.info("Demone pipeline in background avviato con successo.")

    try:
        await app_state.miniflux_client.refresh_all_feeds()
    except Exception as refresh_err:
        logger.warning("Refresh forzato fallito all'avvio: %s", refresh_err)

    while True:
        try:
            await run_pipeline_cycle(app_state)
        except Exception as cycle_err:
            logger.error(
                "Errore critico durante l'esecuzione del ciclo pipeline: %s",
                cycle_err,
                exc_info=True,
            )
        finally:
            logger.info("Attesa di 15 minuti prima del prossimo ciclo di polling...")
            await asyncio.sleep(900)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """init pool → migrations → vault → httpx + clients → reconcile → pipeline; reverse on shutdown."""
    setup_logging()
    logger.info("Avvio del server FastAPI. Inizializzazione moduli Core...")

    try:
        state.db_pool = await init_pool(DATABASE_URL)
        await bootstrap_database(state.db_pool)

        initialize_vault_directories(OBSIDIAN_VAULT_PATH)

        state.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=float(MINIFLUX_CONNECT_TIMEOUT),
                read=float(MINIFLUX_READ_TIMEOUT),
                write=float(MINIFLUX_READ_TIMEOUT),
                pool=float(MINIFLUX_CONNECT_TIMEOUT),
            ),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=True,
        )
        state.miniflux_client = MinifluxClient(
            MINIFLUX_API_URL,
            MINIFLUX_API_KEY,
            http_client=state.http_client,
        )
        state.classification_client = ClassificationClient()

        await reconcile_outbox(state.db_pool, state.miniflux_client)

        state.pipeline_task = asyncio.create_task(
            run_pipeline_loop(state),
            name="radar-ingest-daemon",
        )

        logger.info(
            "Bootstrap completato. MAX_MINIFLUX_RESPONSE_BYTES=%s. Demone avviato.",
            MAX_MINIFLUX_RESPONSE_BYTES,
        )
    except Exception as init_err:
        logger.critical("Errore critico all'avvio del lifespan: %s", init_err, exc_info=True)
        if state.http_client is not None:
            await state.http_client.aclose()
            state.http_client = None
        if state.db_pool is not None:
            await state.db_pool.close()
            state.db_pool = None
        raise

    yield

    logger.info("Arresto del server FastAPI in corso...")
    if state.pipeline_task:
        state.pipeline_task.cancel()
        try:
            await state.pipeline_task
        except asyncio.CancelledError:
            logger.info("Background loop cancellato correttamente.")

    if state.http_client is not None:
        await state.http_client.aclose()
        state.http_client = None
        logger.info("httpx.AsyncClient chiuso correttamente.")

    if state.db_pool:
        await state.db_pool.close()
        logger.info("Pool connessioni PostgreSQL chiuso correttamente.")

    logger.info("Radar Backend arrestato.")


app = FastAPI(
    title="Radar Informativo Globale — API",
    description="Backend API del Radar geopolitico ed infrastrutturale.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "radar-backend"}


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
