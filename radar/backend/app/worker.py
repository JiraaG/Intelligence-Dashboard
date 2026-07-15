"""
Radar Informativo Globale — ingest worker (Compose service ``radar-worker``).

Owns: Miniflux polling, bounded entry queue, PARSE/DB/GEMINI semaphores,
session-level PostgreSQL advisory lock, and bounded graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import httpx

from app.classification.client import ClassificationClient
from app.classification.quota import compute_day_window
from app.commit.db_commit import commit_article_to_db
from app.commit.factory import generate_markdown_content
from app.commit.outbox import process_outbox_row, reconcile_outbox
from app.commit.router import get_article_file_path, initialize_vault_directories
from app.core.config import (
    DATABASE_URL,
    LLM_API_KEY,
    LLM_RPD,
    MAX_MINIFLUX_RESPONSE_BYTES,
    MINIFLUX_API_KEY,
    MINIFLUX_API_URL,
    MINIFLUX_CONNECT_TIMEOUT,
    MINIFLUX_LIMIT,
    MINIFLUX_READ_TIMEOUT,
    OBSIDIAN_VAULT_PATH,
    RADAR_TIME_ZONE,
    WORKER_ADVISORY_LOCK_BACKOFF_SECONDS,
    WORKER_ADVISORY_LOCK_KEY,
    WORKER_DB_CONCURRENCY,
    WORKER_ENTRY_CONCURRENCY,
    WORKER_GEMINI_CONCURRENCY,
    WORKER_HEARTBEAT_INTERVAL_SECONDS,
    WORKER_PARSE_CONCURRENCY,
    WORKER_POLL_INTERVAL_SECONDS,
    WORKER_QUEUE_DEPTH,
    WORKER_SHUTDOWN_TIMEOUT,
)
from app.core.database import bootstrap_database, init_pool
from app.core.heartbeat import upsert_worker_heartbeat
from app.core.logging import setup_logging
from app.extraction.client import MinifluxClient
from app.extraction.entry_validation import ValidatedMinifluxEntry
from app.extraction.parser import strip_html_tags
from app.extraction.state import is_article_duplicate

logger = logging.getLogger("radar.worker")


class WorkerState:
    """Shared mutable state for one worker process lifetime."""

    def __init__(self) -> None:
        self.db_pool: Optional[asyncpg.Pool] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.miniflux_client: Optional[MinifluxClient] = None
        self.classification_client: Optional[ClassificationClient] = None
        self.parse_sem: Optional[asyncio.Semaphore] = None
        self.db_sem: Optional[asyncio.Semaphore] = None
        self.gemini_sem: Optional[asyncio.Semaphore] = None
        self.consumer_tasks: list[asyncio.Task] = []
        self.lock_conn: Optional[asyncpg.Connection] = None
        self.lock_held: bool = False
        self.heartbeat_task: Optional[asyncio.Task] = None


def build_worker_semaphores(
    *,
    parse_concurrency: int = WORKER_PARSE_CONCURRENCY,
    db_concurrency: int = WORKER_DB_CONCURRENCY,
    gemini_concurrency: int = WORKER_GEMINI_CONCURRENCY,
) -> tuple[asyncio.Semaphore, asyncio.Semaphore, asyncio.Semaphore]:
    """Create PARSE / DB / GEMINI semaphores (exported for tests)."""
    return (
        asyncio.Semaphore(parse_concurrency),
        asyncio.Semaphore(db_concurrency),
        asyncio.Semaphore(gemini_concurrency),
    )


async def try_acquire_advisory_lock(conn: asyncpg.Connection, key: int) -> bool:
    """Non-blocking session-level advisory lock attempt."""
    return bool(await conn.fetchval("SELECT pg_try_advisory_lock($1)", key))


async def release_advisory_lock(conn: asyncpg.Connection, key: int) -> bool:
    """Release session-level advisory lock; returns False if we did not hold it."""
    return bool(await conn.fetchval("SELECT pg_advisory_unlock($1)", key))


async def acquire_advisory_lock_with_retry(
    conn: asyncpg.Connection,
    key: int,
    *,
    backoff_seconds: float = float(WORKER_ADVISORY_LOCK_BACKOFF_SECONDS),
) -> None:
    """
    Block until leadership is acquired. Non-leaders stay alive and retry
    (Compose restart flap avoidance). CancelledError: release is caller's job
    only if lock was held; this helper never holds a lock across cancel mid-sleep.
    """
    while True:
        try:
            acquired = await try_acquire_advisory_lock(conn, key)
        except asyncio.CancelledError:
            raise

        if acquired:
            logger.info("Leadership acquisita (pg_try_advisory_lock key=%s).", key)
            return

        logger.warning(
            "Advisory lock non acquisita (key=%s): un altro worker detiene la leadership. "
            "Retry tra %.0fs — il processo resta in vita (no exit) per evitare flapping Compose.",
            key,
            backoff_seconds,
        )
        await asyncio.sleep(backoff_seconds)


async def shutdown_worker_resources(
    state: WorkerState,
    *,
    shutdown_timeout: float = float(WORKER_SHUTDOWN_TIMEOUT),
    lock_key: int = WORKER_ADVISORY_LOCK_KEY,
) -> None:
    """
    Ordered shutdown: cancel heartbeat + consumers → await (bounded) → close httpx →
    release advisory → close pool. No sleep.
    """
    if state.heartbeat_task is not None:
        state.heartbeat_task.cancel()
        try:
            await state.heartbeat_task
        except asyncio.CancelledError:
            pass
        except Exception as hb_err:
            logger.debug("Heartbeat task shutdown: %s", hb_err)
        state.heartbeat_task = None

    consumers = list(state.consumer_tasks)
    for task in consumers:
        task.cancel()

    if consumers:
        _done, pending = await asyncio.wait(consumers, timeout=shutdown_timeout)
        if pending:
            logger.warning(
                "Shutdown: %d consumer ancora attivi dopo %.0fs; proseguo chiusura risorse.",
                len(pending),
                shutdown_timeout,
            )
        state.consumer_tasks = []

    if state.http_client is not None:
        await state.http_client.aclose()
        state.http_client = None
        logger.info("httpx.AsyncClient chiuso.")

    if state.lock_conn is not None:
        if state.lock_held:
            try:
                released = await release_advisory_lock(state.lock_conn, lock_key)
                logger.info(
                    "Advisory lock rilasciata (key=%s, unlocked=%s).",
                    lock_key,
                    released,
                )
            except Exception as unlock_err:
                logger.warning("Rilascio advisory lock fallito: %s", unlock_err)
            state.lock_held = False
        await state.lock_conn.close()
        state.lock_conn = None

    if state.db_pool is not None:
        await state.db_pool.close()
        state.db_pool = None
        logger.info("Pool PostgreSQL chiuso.")


async def process_single_entry(state: WorkerState, entry: ValidatedMinifluxEntry) -> bool:
    """
    Dedup → sanitize → classify → commit+outbox → vault → mark-read.
    Uses PARSE / DB / GEMINI semaphores. Returns True on success/skip, False on error.
    """
    assert state.db_pool is not None
    assert state.miniflux_client is not None
    assert state.classification_client is not None
    assert state.parse_sem is not None
    assert state.db_sem is not None
    assert state.gemini_sem is not None

    entry_id = entry.id
    source_url = entry.source_url
    title = entry.title
    published_date = entry.published_at
    feed_title = entry.feed_title

    try:
        async with state.db_sem:
            async with state.db_pool.acquire() as conn:
                is_dup = await is_article_duplicate(conn, source_url)

        if is_dup:
            logger.info(
                "Articolo duplicato rilevato: '%s'. Marcatura come letto su Miniflux...",
                title[:50],
            )
            await state.miniflux_client.mark_as_read([entry_id])
            return True

        async with state.parse_sem:
            clean_content = strip_html_tags(entry.content)

        async with state.gemini_sem:
            extracted_article = await state.classification_client.classify_article(
                title=title,
                content=clean_content,
                url=source_url,
                date=published_date,
            )

        extracted_article = extracted_article.model_copy(
            update={
                "source_url": source_url,
                "published_at": published_date,
            }
        )

        md_content = generate_markdown_content(extracted_article)
        file_path = get_article_file_path(extracted_article, vault_path=OBSIDIAN_VAULT_PATH)

        async with state.db_sem:
            async with state.db_pool.acquire() as conn:
                article_id = await commit_article_to_db(
                    conn,
                    extracted_article,
                    feed_title,
                    outbox_target_path=file_path,
                    outbox_payload=md_content,
                    miniflux_entry_id=entry_id,
                )

        async with state.db_sem:
            async with state.db_pool.acquire() as conn:
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
            async with state.db_sem:
                ok = await process_outbox_row(
                    state.db_pool, outbox_row, state.miniflux_client
                )
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

    except asyncio.CancelledError:
        raise
    except Exception as article_err:
        logger.error(
            "Errore durante l'elaborazione del singolo articolo '%s': %s",
            title[:50],
            article_err,
            exc_info=True,
        )
        return False


async def _entry_consumer(
    state: WorkerState,
    queue: asyncio.Queue,
    results: dict[str, int],
    results_lock: asyncio.Lock,
) -> None:
    """Pull entries from the bounded queue until cancelled."""
    while True:
        entry: ValidatedMinifluxEntry = await queue.get()
        try:
            ok = await process_single_entry(state, entry)
            async with results_lock:
                if ok:
                    results["success"] += 1
                else:
                    results["failure"] += 1
        except asyncio.CancelledError:
            raise
        finally:
            queue.task_done()


async def _ledger_rpd_used(pool: asyncpg.Pool) -> int:
    """Count active llm_request_ledger rows in the RADAR_TIME_ZONE half-open day."""
    day_start, day_end = compute_day_window(datetime.now(timezone.utc), RADAR_TIME_ZONE)
    async with pool.acquire() as conn:
        used = await conn.fetchval(
            """
            SELECT COUNT(*)::INT
            FROM llm_request_ledger
            WHERE created_at >= $1
              AND created_at < $2
              AND status = ANY($3::text[])
            """,
            day_start,
            day_end,
            ["reserved", "completed", "failed"],
        )
    return int(used or 0)


async def run_pipeline_cycle(state: WorkerState) -> None:
    """
    One ingest cycle: reconcile → RPD soft-trim via ledger → fetch →
    bounded queue + N consumers (never TaskGroup-all-entries).
    Hard RPM/TPM/RPD enforcement remains in QuotaLedger.reserve per attempt.
    """
    assert state.db_pool is not None
    assert state.miniflux_client is not None

    logger.info("=== Avvio di un nuovo ciclo della pipeline di ingestione ===")

    await reconcile_outbox(state.db_pool, state.miniflux_client)

    processed_today = await _ledger_rpd_used(state.db_pool)
    if processed_today >= LLM_RPD:
        logger.warning(
            "LIMITE RPD RAGGIUNTO (ledger): %s/%s tentativi LLM oggi (tz window). "
            "Ciclo in ibernazione.",
            processed_today,
            LLM_RPD,
        )
        return

    entries = await state.miniflux_client.fetch_unread_entries(limit=MINIFLUX_LIMIT)
    if not entries:
        logger.info("Nessun articolo non letto presente in Miniflux.")
        return

    remaining_rpd = LLM_RPD - processed_today
    if len(entries) > remaining_rpd:
        logger.info(
            "Riduzione lotto da %d a %d per soft-trim RPD ledger.",
            len(entries),
            remaining_rpd,
        )
        entries = entries[:remaining_rpd]

    queue: asyncio.Queue = asyncio.Queue(maxsize=WORKER_QUEUE_DEPTH)
    results: dict[str, int] = {"success": 0, "failure": 0}
    results_lock = asyncio.Lock()

    consumers = [
        asyncio.create_task(
            _entry_consumer(state, queue, results, results_lock),
            name=f"radar-entry-consumer-{i}",
        )
        for i in range(WORKER_ENTRY_CONCURRENCY)
    ]
    state.consumer_tasks = list(consumers)

    try:
        for entry in entries:
            await queue.put(entry)
        await queue.join()
    except asyncio.CancelledError:
        raise
    finally:
        for task in consumers:
            task.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)
        state.consumer_tasks = []

    logger.info(
        "=== Ciclo della pipeline completato: %d elaborati/saltati, %d errori ===",
        results["success"],
        results["failure"],
    )


async def run_heartbeat_loop(
    state: WorkerState,
    *,
    interval_seconds: float = float(WORKER_HEARTBEAT_INTERVAL_SECONDS),
    status: str = "running",
    detail: str | None = None,
) -> None:
    """
    Periodically UPSERT worker_heartbeat while this process holds leadership.
    CancelledError is re-raised; other errors are logged and the loop continues.
    """
    assert state.db_pool is not None
    logger.info(
        "Heartbeat leader avviato (interval=%ss, status=%s).",
        interval_seconds,
        status,
    )
    while True:
        try:
            await upsert_worker_heartbeat(state.db_pool, status=status, detail=detail)
        except asyncio.CancelledError:
            raise
        except Exception as hb_err:
            logger.warning("Upsert worker_heartbeat fallito: %s", hb_err)
        await asyncio.sleep(interval_seconds)


async def run_pipeline_loop(state: WorkerState) -> None:
    """Daemon loop. Poll interval is awaited outside any finally (shutdown-safe)."""
    logger.info(
        "Demone pipeline avviato (poll=%ss, queue_depth=%s, entry_concurrency=%s).",
        WORKER_POLL_INTERVAL_SECONDS,
        WORKER_QUEUE_DEPTH,
        WORKER_ENTRY_CONCURRENCY,
    )

    try:
        await state.miniflux_client.refresh_all_feeds()
    except asyncio.CancelledError:
        raise
    except Exception as refresh_err:
        logger.warning("Refresh forzato fallito all'avvio: %s", refresh_err)

    while True:
        try:
            await run_pipeline_cycle(state)
        except asyncio.CancelledError:
            raise
        except Exception as cycle_err:
            logger.error(
                "Errore critico durante l'esecuzione del ciclo pipeline: %s",
                cycle_err,
                exc_info=True,
            )

        logger.info(
            "Attesa di %s secondi prima del prossimo ciclo di polling...",
            WORKER_POLL_INTERVAL_SECONDS,
        )
        await asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)


async def run_worker() -> None:
    """Bootstrap resources, acquire leadership, run loop; always re-raise CancelledError."""
    setup_logging()
    logger.info(
        "Avvio radar-worker. MAX_MINIFLUX_RESPONSE_BYTES=%s.",
        MAX_MINIFLUX_RESPONSE_BYTES,
    )

    state = WorkerState()
    ingest_enabled = bool(LLM_API_KEY)

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

        if ingest_enabled:
            state.classification_client = ClassificationClient(pool=state.db_pool)
        else:
            logger.error(
                "GEMINI_API_KEY/GOOGLE_API_KEY mancante: ingest LLM sospeso. "
                "API e frontend restano disponibili; il worker mantiene leadership + heartbeat."
            )

        parse_sem, db_sem, gemini_sem = build_worker_semaphores()
        state.parse_sem = parse_sem
        state.db_sem = db_sem
        state.gemini_sem = gemini_sem

        state.lock_conn = await asyncpg.connect(DATABASE_URL)
        try:
            await acquire_advisory_lock_with_retry(
                state.lock_conn,
                WORKER_ADVISORY_LOCK_KEY,
            )
            state.lock_held = True
        except asyncio.CancelledError:
            await state.lock_conn.close()
            state.lock_conn = None
            raise

        hb_status = "running" if ingest_enabled else "degraded"
        hb_detail = None if ingest_enabled else "missing_llm_api_key"
        await upsert_worker_heartbeat(state.db_pool, status=hb_status, detail=hb_detail)
        state.heartbeat_task = asyncio.create_task(
            run_heartbeat_loop(
                state,
                status=hb_status,
                detail=hb_detail,
            ),
            name="radar-worker-heartbeat",
        )

        if ingest_enabled:
            await run_pipeline_loop(state)
        else:
            # Stay alive for heartbeat / leadership without calling Gemini.
            while True:
                await asyncio.sleep(float(WORKER_POLL_INTERVAL_SECONDS))

    except asyncio.CancelledError:
        logger.info("Worker cancellato; avvio shutdown ordinato.")
        raise
    finally:
        await shutdown_worker_resources(state)
        logger.info("Radar worker arrestato.")


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, main_task: asyncio.Task) -> None:
    """Cancel the main task on SIGTERM/SIGINT (Docker stop / Ctrl+C)."""

    def _request_shutdown() -> None:
        logger.info("Segnale di shutdown ricevuto; cancellazione task principale.")
        main_task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except (NotImplementedError, RuntimeError):
            try:
                signal.signal(sig, lambda *_args: _request_shutdown())
            except (ValueError, OSError):
                logger.debug("Signal handler non installabile per %s", sig)


async def _async_main() -> None:
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()
    assert main_task is not None
    _install_signal_handlers(loop, main_task)
    await run_worker()


def main() -> None:
    """CLI entry: ``python -m app.worker``."""
    try:
        asyncio.run(_async_main())
    except asyncio.CancelledError:
        raise SystemExit(0) from None


if __name__ == "__main__":
    main()
