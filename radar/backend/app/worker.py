"""
Radar Informativo Globale — demone ingest (Compose ``radar-worker``).

Possiede: polling Miniflux, coda entry bounded, semafori PARSE/DB/Gemini-SDK,
advisory lock di leadership (session-level), soft-trim ``LLM_SIMPLE.rpd``,
heartbeat leader e shutdown ordinato. Non è l'API (``main.py`` resta API-only).

Due famiglie di advisory lock PostgreSQL (non confonderle):
  - leadership: 1-arg ``WORKER_ADVISORY_LOCK_KEY`` su ``lock_conn`` dedicata;
  - per-URL: 2-arg ``(ns, sha256)`` sulla connessione pool durante l'entry.

SoT:
    .agents/AGENTS.md §3; docs/01–02; skill radar-quota-ledger (soft-trim).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import signal
import struct
import time
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import httpx

from app.classification.client import ClassificationClient
from app.classification.ollama_lifecycle import (
    maybe_unload_simple_ollama,
    should_manage_ollama_vram,
)
from app.classification.quality_compare import compare_articles_quality
from app.classification.quota import compute_day_window
from app.commit.db_commit import commit_article_to_db, replace_article_in_place
from app.commit.factory import generate_markdown_content
from app.commit.outbox import process_outbox_row, reconcile_outbox
from app.commit.router import get_article_file_path, initialize_vault_directories
from app.core.config import (
    DATABASE_URL,
    LLM_API_KEY,
    LLM_COMPLEX,
    LLM_ROUTING_MODE,
    LLM_SIMPLE,
    MAX_MINIFLUX_RESPONSE_BYTES,
    MINIFLUX_API_KEY,
    CONTENT_HASH_DEDUP_ENABLED,
    CONTENT_HASH_LOOKBACK_HOURS,
    MINIFLUX_API_URL,
    MINIFLUX_CONNECT_TIMEOUT,
    MINIFLUX_LIMIT,
    MINIFLUX_READ_TIMEOUT,
    OBSIDIAN_VAULT_PATH,
    OLLAMA_UNLOAD_DEBOUNCE_SECONDS,
    RADAR_TIME_ZONE,
    SEMANTIC_DEDUP_DIRECT_DISTANCE,
    SEMANTIC_DEDUP_DIRECT_MIN_WORDS,
    SEMANTIC_DEDUP_DIRECT_TITLE_SIM,
    SEMANTIC_DEDUP_DIRECT_SHADOW,
    SEMANTIC_DEDUP_ENABLED,
    SEMANTIC_QUALITY_REPLACE_HINT_RATIO,
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
from app.extraction.embedder import generate_embedding
from app.extraction.entry_validation import ValidatedMinifluxEntry
from app.extraction.parser import strip_html_tags
from app.extraction.semantic_dedup import (
    compute_content_sha256,
    find_article_by_content_hash,
    find_near_duplicate,
    record_dedup_event,
    title_token_jaccard,
)
from app.extraction.state import is_article_duplicate

logger = logging.getLogger("radar.worker")


class WorkerState:
    """Stato mutabile di un processo worker: pool, client, semafori, leadership."""

    def __init__(self) -> None:
        self.db_pool: Optional[asyncpg.Pool] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.miniflux_client: Optional[MinifluxClient] = None
        self.classification_client: Optional[ClassificationClient] = None
        self.parse_sem: Optional[asyncio.Semaphore] = None
        self.db_sem: Optional[asyncio.Semaphore] = None
        # Cap concurrency Gemini SDK (enforced in ClassificationClient, non qui).
        self.gemini_sem: Optional[asyncio.Semaphore] = None
        self.consumer_tasks: list[asyncio.Task] = []
        # Connessione dedicata che detiene il lock di leadership (non dal pool).
        self.lock_conn: Optional[asyncpg.Connection] = None
        self.lock_held: bool = False
        self.heartbeat_task: Optional[asyncio.Task] = None
        # Fase B
        self.listen_conn: Optional[asyncpg.Connection] = None
        self.wake_event: asyncio.Event = asyncio.Event()
        self._trigger_callback: Any = None


def build_worker_semaphores(
    *,
    parse_concurrency: int = WORKER_PARSE_CONCURRENCY,
    db_concurrency: int = WORKER_DB_CONCURRENCY,
    gemini_concurrency: int = WORKER_GEMINI_CONCURRENCY,
) -> tuple[asyncio.Semaphore, asyncio.Semaphore, asyncio.Semaphore]:
    """Crea semafori PARSE / DB / Gemini-SDK (esportato per i test)."""
    return (
        asyncio.Semaphore(parse_concurrency),
        asyncio.Semaphore(db_concurrency),
        asyncio.Semaphore(gemini_concurrency),
    )


def get_url_lock_keys(url: str) -> tuple[int, int]:
    """Chiave advisory 2-arg stabile ``(namespace, url_hash int32)`` per serializzare lo stesso URL.

    Namespace magico distinto da ``WORKER_ADVISORY_LOCK_KEY`` (leadership 1-arg).
    """
    ns = 777_666_555
    h = hashlib.sha256(url.encode("utf-8")).digest()
    url_hash = struct.unpack("!i", h[:4])[0]
    return ns, url_hash


async def try_acquire_advisory_lock(conn: asyncpg.Connection, key: int) -> bool:
    """Tentativo non bloccante di leadership (``pg_try_advisory_lock`` 1-arg)."""
    return bool(await conn.fetchval("SELECT pg_try_advisory_lock($1)", key))


async def release_advisory_lock(conn: asyncpg.Connection, key: int) -> bool:
    """Rilascia leadership; ``False`` se questa sessione non la deteneva."""
    return bool(await conn.fetchval("SELECT pg_advisory_unlock($1)", key))


async def acquire_advisory_lock_with_retry(
    conn: asyncpg.Connection,
    key: int,
    *,
    backoff_seconds: float = float(WORKER_ADVISORY_LOCK_BACKOFF_SECONDS),
) -> None:
    """Attende la leadership senza uscire dal processo.

    I non-leader restano vivi e ritentano (evita flapping Compose su exit).
    ``CancelledError`` mid-sleep: il chiamante chiude ``lock_conn`` se il lock
    non era ancora acquisito — questo helper non tiene il lock durante lo sleep.
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
    """Shutdown ordinato: HB → consumer (bounded) → httpx → unlock leadership → pool.

    Nessuno sleep qui (lo sleep di poll sta fuori da qualsiasi ``finally`` di shutdown).
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

    # Profilo F: best-effort unload VRAM (no debounce) prima di chiudere httpx.
    try:
        await maybe_unload_simple_ollama(reason="shutdown")
    except Exception as unload_err:
        logger.warning("ollama_unload shutdown failed: %s", unload_err)

    if state.http_client is not None:
        await state.http_client.aclose()
        state.http_client = None
        logger.info("httpx.AsyncClient chiuso.")

    # Fase B: Ferma il trigger listener prima di chiudere la connessione/pool
    await stop_postgres_trigger_listener(state)

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
        try:
            await state.lock_conn.close()
        except Exception as lock_close_err:
            logger.warning("Errore chiusura lock_conn: %s", lock_close_err)
        state.lock_conn = None

    if state.db_pool is not None:
        await state.db_pool.close()
        state.db_pool = None
        logger.info("Pool PostgreSQL chiuso.")


async def start_postgres_trigger_listener(state: WorkerState) -> None:
    """LISTEN dedicato su radar_worker_trigger (mai dal pool)."""
    assert state.listen_conn is None
    state.wake_event = asyncio.Event()
    state.listen_conn = await asyncpg.connect(DATABASE_URL)

    def _callback(_conn: asyncpg.Connection, _pid: int, _channel: str, _payload: str) -> None:
        state.wake_event.set()

    state._trigger_callback = _callback
    await state.listen_conn.add_listener("radar_worker_trigger", _callback)
    logger.info("LISTEN attivo sul canale radar_worker_trigger.")


async def stop_postgres_trigger_listener(state: WorkerState) -> None:
    if state.listen_conn is None:
        return
    try:
        if state._trigger_callback is not None:
            await state.listen_conn.remove_listener(
                "radar_worker_trigger",
                state._trigger_callback,
            )
    except Exception as err:
        logger.debug("remove_listener: %s", err)
    try:
        await state.listen_conn.close()
    except Exception as err:
        logger.warning("Chiusura listen_conn: %s", err)
    state.listen_conn = None
    state._trigger_callback = None


def resolve_geo_method(article: GeopoliticalArticleSchema) -> str:
    """Determina il metodo di risoluzione geografica (C4).

    Valori ammessi: 'llm_extracted' | 'centroid_fallback' | 'unchanged'.
    """
    if article.country_code == "XX" or (article.latitude == 0.0 and article.longitude == 0.0):
        return "centroid_fallback"
    return "llm_extracted"


async def process_single_entry(state: WorkerState, entry: ValidatedMinifluxEntry) -> bool:
    """Pipeline per-entry: lock URL → dedup → sanitize → classify → commit+outbox → vault.

    Usa semafori PARSE/DB; Gemini-SDK capped nel client. ``True`` = ok/skip,
    ``False`` = errore livello-3 (il ciclo continua). ``CancelledError`` ri-lanciato.
    """
    assert state.db_pool is not None
    assert state.miniflux_client is not None
    assert state.classification_client is not None
    assert state.parse_sem is not None
    assert state.db_sem is not None
    assert state.gemini_sem is not None

    pipeline_start = time.monotonic()
    entry_id = entry.id
    source_url = entry.source_url
    title = entry.title
    published_date = entry.published_at
    feed_title = entry.feed_title

    lock_acquired = False
    lock_ns, lock_key = get_url_lock_keys(source_url)

    try:
        async with state.db_sem:
            async with state.db_pool.acquire() as conn:
                try:
                    # Lock per-URL bloccante (2-arg): serializza TOCTOU dedup/commit sullo stesso URL.
                    # timeout lungo: con LLM locale la sessione che detiene il lock resta occupata
                    # minuti; il default pool command_timeout=60s faceva crashare i waiter.
                    await conn.execute(
                        "SELECT pg_advisory_lock($1, $2)",
                        lock_ns,
                        lock_key,
                        timeout=900.0,
                    )
                    lock_acquired = True

                    is_dup = await is_article_duplicate(conn, source_url)

                    if is_dup:
                        # T-P0-01: mark-read solo se vault durable (outbox completed)
                        # o legacy senza outbox ma file vault presente — mai mark-read cieco.
                        row = await conn.fetchrow(
                            """
                            SELECT
                                a.id,
                                o.status AS outbox_status,
                                a.primary_category,
                                a.country_code,
                                a.published_at,
                                a.title,
                                a.source_url
                            FROM articles a
                            LEFT JOIN article_outbox o ON o.article_id = a.id
                            WHERE a.source_url = $1
                            """,
                            source_url,
                        )

                        if row is None:
                            logger.warning(
                                "Duplicato rilevato per '%s' ma non trovato nel DB: skip mark-read.",
                                title[:50],
                            )
                            return True

                        # Registra evento dedup URL exact (C3)
                        await record_dedup_event(
                            conn,
                            incoming_url=source_url,
                            existing_article_id=row.get("id"),
                            winner="existing",
                            cosine_distance=None,
                            dedup_kind="url_exact",
                            action_taken="kept_existing",
                            feed_id=entry.feed_id,
                            incoming_miniflux_entry_id=entry.id,
                        )

                        outbox_status = row["outbox_status"]

                        if outbox_status == "completed":
                            logger.info(
                                "Duplicato con vault completed: mark-read Miniflux per '%s'.",
                                title[:50],
                            )
                            await state.miniflux_client.mark_as_read([entry_id])
                        elif outbox_status in ("pending", "failed", "writing"):
                            logger.warning(
                                "Duplicato DB ma outbox status=%r per '%s': skip mark-read; "
                                "attendo reconcile.",
                                outbox_status,
                                title[:50],
                            )
                        else:
                            # outbox_status is None: legacy / nessuna riga outbox → check file vault.
                            from pathlib import Path

                            from app.classification.validator import GeopoliticalArticleSchema

                            pub_date = row["published_at"]
                            pub_date_str = (
                                pub_date.isoformat()
                                if hasattr(pub_date, "isoformat")
                                else str(pub_date)
                            )

                            temp_schema = GeopoliticalArticleSchema(
                                title=row["title"],
                                summary="dummy",
                                published_at=pub_date_str,
                                source_url=row["source_url"],
                                country_code=row["country_code"],
                                latitude=0.0,
                                longitude=0.0,
                                companies_involved="Nessuno",
                                tags=f"{row['primary_category']}, dummy",
                                primary_category=row["primary_category"],
                                sentiment="Neutrale",
                                infrastructural_entities="Nessuno",
                                related_countries="Nessuno",
                                relevance_level=3,
                            )
                            try:
                                # Schema minimo solo per ricostruire lo stesso path di router.
                                vault_path = get_article_file_path(
                                    temp_schema, vault_path=OBSIDIAN_VAULT_PATH
                                )
                                file_exists = await asyncio.to_thread(Path(vault_path).is_file)
                            except Exception as path_err:
                                logger.error(
                                    "Errore durante il calcolo/verifica del path del Vault "
                                    "per il duplicato '%s': %s",
                                    title[:50],
                                    path_err,
                                )
                                file_exists = False

                            if file_exists:
                                logger.info(
                                    "Duplicato legacy: file Vault presente. "
                                    "Marcatura come letto su Miniflux per '%s'.",
                                    title[:50],
                                )
                                await state.miniflux_client.mark_as_read([entry_id])
                            else:
                                logger.warning(
                                    "Duplicato DB legacy ma file Vault mancante per '%s': "
                                    "skip mark-read.",
                                    title[:50],
                                )
                        return True

                    async with state.parse_sem:
                        clean_content = strip_html_tags(entry.content)

                    # M6. Deduplicazione per Content Hash SHA-256 (0 embed, 0 LLM)
                    content_sha256 = compute_content_sha256(title, clean_content)
                    if CONTENT_HASH_DEDUP_ENABLED:
                        hash_match = await find_article_by_content_hash(
                            conn, content_sha256, lookback_hours=CONTENT_HASH_LOOKBACK_HOURS
                        )
                        if hash_match is not None:
                            await record_dedup_event(
                                conn,
                                incoming_url=source_url,
                                existing_article_id=hash_match.id,
                                winner="existing",
                                cosine_distance=0.0,
                                same_story=True,
                                confidence=1.0,
                                reason="Content hash SHA-256 match",
                                dedup_kind="content_hash",
                                action_taken="kept_existing_content_hash",
                                feed_id=entry.feed_id,
                                incoming_miniflux_entry_id=entry.id,
                            )
                            logger.info(
                                "Content hash dedup: kept_existing_content_hash per '%s' (vs '%s')",
                                title[:40],
                                hash_match.title[:40],
                            )
                            await state.miniflux_client.mark_as_read([entry_id])
                            return True

                    # 1. Deduplicazione semantica pre-LLM (embeddings + pgvector)
                    embed_start = time.monotonic()
                    embedding = (
                        await asyncio.to_thread(generate_embedding, title, clean_content)
                        if SEMANTIC_DEDUP_ENABLED
                        else None
                    )
                    embed_time_ms = int((time.monotonic() - embed_start) * 1000) if embedding is not None else None

                    candidate = (
                        await find_near_duplicate(conn, embedding)
                        if embedding
                        else None
                    )

                    if candidate is not None:
                        # M5 Direct Bypass High-Sim check
                        clean_words_count = len(clean_content.split())
                        t_jaccard = title_token_jaccard(title, candidate.title)
                        is_high_sim = (
                            candidate.distance <= SEMANTIC_DEDUP_DIRECT_DISTANCE
                            and clean_words_count >= SEMANTIC_DEDUP_DIRECT_MIN_WORDS
                            and t_jaccard >= SEMANTIC_DEDUP_DIRECT_TITLE_SIM
                        )

                        if is_high_sim and SEMANTIC_DEDUP_DIRECT_SHADOW:
                            logger.info(
                                "M5 Direct Bypass SHADOW: candidate dist=%.4f, words=%d, title_jaccard=%.4f (would bypass quality compare)",
                                candidate.distance,
                                clean_words_count,
                                t_jaccard,
                            )
                        elif is_high_sim:
                            len_existing = len(candidate.body_excerpt or candidate.summary or "")
                            len_incoming = len(clean_content)
                            is_much_longer = len_incoming > (len_existing * SEMANTIC_QUALITY_REPLACE_HINT_RATIO)

                            if is_much_longer:
                                logger.info(
                                    "M5 Direct Bypass: replace incoming (len_inc=%d > len_exist=%d * %.2f) per '%s'",
                                    len_incoming,
                                    len_existing,
                                    SEMANTIC_QUALITY_REPLACE_HINT_RATIO,
                                    title[:40],
                                )
                                cls_res = await state.classification_client.classify_article(
                                    title=title,
                                    content=clean_content,
                                    url=source_url,
                                    date=published_date,
                                    miniflux_entry_id=entry_id,
                                )
                                extracted_article = cls_res.article.model_copy(
                                    update={
                                        "source_url": source_url,
                                        "published_at": published_date,
                                    }
                                )
                                md_content = generate_markdown_content(extracted_article)
                                file_path = get_article_file_path(extracted_article, vault_path=OBSIDIAN_VAULT_PATH)

                                clean_chars = len(clean_content)
                                clean_words = clean_words_count
                                pipeline_lat_ms = int((time.monotonic() - pipeline_start) * 1000)
                                geo_method = resolve_geo_method(extracted_article)

                                await replace_article_in_place(
                                    conn,
                                    existing_article_id=candidate.id,
                                    article=extracted_article,
                                    feed_title=feed_title,
                                    outbox_target_path=file_path,
                                    outbox_payload=md_content,
                                    miniflux_entry_id=entry_id,
                                    body_excerpt=clean_content[:8000],
                                    embedding=embedding,
                                    feed_id=entry.feed_id,
                                    feed_domain=entry.feed_domain,
                                    classification_lane=cls_res.classification_lane,
                                    classified_by_model=cls_res.classified_by_model,
                                    classified_by_provider=cls_res.classified_by_provider,
                                    was_escalated=cls_res.was_escalated,
                                    dedup_kind="semantic_vector",
                                    dedup_match_article_id=candidate.id,
                                    dedup_action="replaced_direct_vector",
                                    clean_text_chars=clean_chars,
                                    clean_text_words=clean_words,
                                    embedding_time_ms=embed_time_ms,
                                    pipeline_latency_ms=pipeline_lat_ms,
                                    geo_resolution_method=geo_method,
                                    content_sha256=content_sha256,
                                )

                                await conn.execute(
                                    "UPDATE llm_request_ledger SET article_id = $1 WHERE miniflux_entry_id = $2 AND article_id IS NULL",
                                    candidate.id,
                                    entry_id,
                                )

                                await record_dedup_event(
                                    conn,
                                    incoming_url=source_url,
                                    existing_article_id=candidate.id,
                                    winner="incoming",
                                    cosine_distance=candidate.distance,
                                    same_story=True,
                                    confidence=1.0,
                                    reason="M5 direct bypass replace (longer text)",
                                    dedup_kind="semantic_vector",
                                    action_taken="replaced_direct_vector",
                                    feed_id=entry.feed_id,
                                    incoming_miniflux_entry_id=entry.id,
                                )

                                notify_payload = json.dumps(
                                    {
                                        "article_id": str(candidate.id),
                                        "country_code": extracted_article.country_code,
                                        "primary_category": extracted_article.primary_category,
                                        "published_at": extracted_article.published_at,
                                    },
                                    separators=(",", ":"),
                                )
                                await conn.execute(
                                    "SELECT pg_notify($1, $2)",
                                    "radar_article_processed",
                                    notify_payload,
                                )

                                outbox_row = await conn.fetchrow(
                                    """
                                    SELECT id, article_id, target_path, payload, payload_checksum,
                                           attempt_count, miniflux_entry_id, status
                                    FROM article_outbox
                                    WHERE article_id = $1
                                      AND status IN ('pending', 'failed')
                                    """,
                                    candidate.id,
                                )
                                if outbox_row is not None:
                                    ok = await process_outbox_row(
                                        state.db_pool, outbox_row, state.miniflux_client
                                    )
                                    if not ok:
                                        logger.error(
                                            "Replace in-place M5 bypass riuscito ma Vault/outbox fallito per article_id=%s",
                                            candidate.id,
                                        )
                                        return False

                                logger.info(
                                    "M5 Direct Bypass: articolo sostituito in-place [ID=%s]: '%s'",
                                    candidate.id,
                                    extracted_article.title[:50],
                                )
                                return True
                            else:
                                logger.info(
                                    "M5 Direct Bypass: keep existing per '%s' (dist=%.4f, title_jaccard=%.4f)",
                                    title[:40],
                                    candidate.distance,
                                    t_jaccard,
                                )
                                await record_dedup_event(
                                    conn,
                                    incoming_url=source_url,
                                    existing_article_id=candidate.id,
                                    winner="existing",
                                    cosine_distance=candidate.distance,
                                    same_story=True,
                                    confidence=1.0,
                                    reason="M5 direct bypass keep",
                                    dedup_kind="semantic_vector",
                                    action_taken="kept_existing_direct_vector",
                                    feed_id=entry.feed_id,
                                    incoming_miniflux_entry_id=entry.id,
                                )
                                await state.miniflux_client.mark_as_read([entry_id])
                                return True

                        # Near-dup rilevato (non bypassed): 1x scontro di qualità su lane COMPLEX
                        cmp_result = await compare_articles_quality(
                            state.db_pool,
                            existing_title=candidate.title,
                            existing_text=candidate.body_excerpt or candidate.summary,
                            incoming_title=title,
                            incoming_text=clean_content,
                            incoming_url=source_url,
                            miniflux_entry_id=entry_id,
                        )

                        if cmp_result.same_story and cmp_result.winner == "existing":
                            # Articolo esistente vince: keep existing, mark-read incoming
                            await record_dedup_event(
                                conn,
                                incoming_url=source_url,
                                existing_article_id=candidate.id,
                                winner="existing",
                                cosine_distance=candidate.distance,
                                same_story=True,
                                confidence=cmp_result.confidence,
                                reason=cmp_result.reason,
                                dedup_kind="semantic_vector",
                                action_taken="kept_existing",
                                feed_id=entry.feed_id,
                                incoming_miniflux_entry_id=entry.id,
                            )
                            logger.info(
                                "Semantic dedup: keep existing per '%s' (vs '%s')",
                                title[:40],
                                candidate.title[:40],
                            )
                            await state.miniflux_client.mark_as_read([entry_id])
                            return True

                        elif cmp_result.same_story and cmp_result.winner == "incoming":
                            # Articolo incoming vince: classify incoming + replace in-place stesso ID
                            cls_res = await state.classification_client.classify_article(
                                title=title,
                                content=clean_content,
                                url=source_url,
                                date=published_date,
                                miniflux_entry_id=entry_id,
                            )
                            extracted_article = cls_res.article.model_copy(
                                update={
                                    "source_url": source_url,
                                    "published_at": published_date,
                                }
                            )
                            md_content = generate_markdown_content(extracted_article)
                            file_path = get_article_file_path(extracted_article, vault_path=OBSIDIAN_VAULT_PATH)

                            clean_chars = len(clean_content)
                            clean_words = len(clean_content.split())
                            pipeline_lat_ms = int((time.monotonic() - pipeline_start) * 1000)
                            geo_method = resolve_geo_method(extracted_article)

                            await replace_article_in_place(
                                conn,
                                existing_article_id=candidate.id,
                                article=extracted_article,
                                feed_title=feed_title,
                                outbox_target_path=file_path,
                                outbox_payload=md_content,
                                miniflux_entry_id=entry_id,
                                body_excerpt=clean_content[:8000],
                                embedding=embedding,
                                feed_id=entry.feed_id,
                                feed_domain=entry.feed_domain,
                                classification_lane=cls_res.classification_lane,
                                classified_by_model=cls_res.classified_by_model,
                                classified_by_provider=cls_res.classified_by_provider,
                                was_escalated=cls_res.was_escalated,
                                dedup_kind="semantic_vector",
                                dedup_match_article_id=candidate.id,
                                dedup_action="replaced_in_place",
                                clean_text_chars=clean_chars,
                                clean_text_words=clean_words,
                                embedding_time_ms=embed_time_ms,
                                pipeline_latency_ms=pipeline_lat_ms,
                                geo_resolution_method=geo_method,
                                content_sha256=content_sha256,
                            )

                            # Post-commit ledger link (C2)
                            await conn.execute(
                                "UPDATE llm_request_ledger SET article_id = $1 WHERE miniflux_entry_id = $2 AND article_id IS NULL",
                                candidate.id,
                                entry_id,
                            )

                            await record_dedup_event(
                                conn,
                                incoming_url=source_url,
                                existing_article_id=candidate.id,
                                winner="incoming",
                                cosine_distance=candidate.distance,
                                same_story=True,
                                confidence=cmp_result.confidence,
                                reason=cmp_result.reason,
                                dedup_kind="semantic_vector",
                                action_taken="replaced_in_place",
                                feed_id=entry.feed_id,
                                incoming_miniflux_entry_id=entry.id,
                            )

                            notify_payload = json.dumps(
                                {
                                    "article_id": str(candidate.id),
                                    "country_code": extracted_article.country_code,
                                    "primary_category": extracted_article.primary_category,
                                    "published_at": extracted_article.published_at,
                                },
                                separators=(",", ":"),
                            )
                            await conn.execute(
                                "SELECT pg_notify($1, $2)",
                                "radar_article_processed",
                                notify_payload,
                            )

                            outbox_row = await conn.fetchrow(
                                """
                                SELECT id, article_id, target_path, payload, payload_checksum,
                                       attempt_count, miniflux_entry_id, status
                                FROM article_outbox
                                WHERE article_id = $1
                                  AND status IN ('pending', 'failed')
                                """,
                                candidate.id,
                            )
                            if outbox_row is not None:
                                ok = await process_outbox_row(
                                    state.db_pool, outbox_row, state.miniflux_client
                                )
                                if not ok:
                                    logger.error(
                                        "Replace in-place riuscito ma Vault/outbox fallito per article_id=%s",
                                        candidate.id,
                                    )
                                    return False

                            logger.info(
                                "Articolo sostituito in-place con successo [ID=%s]: '%s'",
                                candidate.id,
                                extracted_article.title[:50],
                            )
                            return True

                        else:
                            # same_story == False: storie diverse, registra evento e procedi a classify normale
                            await record_dedup_event(
                                conn,
                                incoming_url=source_url,
                                existing_article_id=candidate.id,
                                winner="keep_new",
                                cosine_distance=candidate.distance,
                                same_story=False,
                                confidence=cmp_result.confidence,
                                reason=cmp_result.reason,
                                dedup_kind="semantic_vector",
                                action_taken="kept_new",
                                feed_id=entry.feed_id,
                                incoming_miniflux_entry_id=entry.id,
                            )

                    # Nessun near-dup (o same_story==False): classificazione standard
                    cls_res = await state.classification_client.classify_article(
                        title=title,
                        content=clean_content,
                        url=source_url,
                        date=published_date,
                        miniflux_entry_id=entry_id,
                    )

                    # Ground truth Miniflux: URL/data non fidati all'LLM.
                    extracted_article = cls_res.article.model_copy(
                        update={
                            "source_url": source_url,
                            "published_at": published_date,
                        }
                    )

                    md_content = generate_markdown_content(extracted_article)
                    file_path = get_article_file_path(extracted_article, vault_path=OBSIDIAN_VAULT_PATH)

                    clean_chars = len(clean_content)
                    clean_words = len(clean_content.split())
                    pipeline_lat_ms = int((time.monotonic() - pipeline_start) * 1000)
                    geo_method = resolve_geo_method(extracted_article)

                    dedup_k = "semantic_vector" if candidate is not None else "none"
                    dedup_m = candidate.id if candidate is not None else None
                    dedup_act = "kept_new" if candidate is not None else "inserted_new"

                    article_id = await commit_article_to_db(
                        conn,
                        extracted_article,
                        feed_title,
                        outbox_target_path=file_path,
                        outbox_payload=md_content,
                        miniflux_entry_id=entry_id,
                        body_excerpt=clean_content[:8000],
                        embedding=embedding,
                        feed_id=entry.feed_id,
                        feed_domain=entry.feed_domain,
                        classification_lane=cls_res.classification_lane,
                        classified_by_model=cls_res.classified_by_model,
                        classified_by_provider=cls_res.classified_by_provider,
                        was_escalated=cls_res.was_escalated,
                        dedup_kind=dedup_k,
                        dedup_match_article_id=dedup_m,
                        dedup_action=dedup_act,
                        clean_text_chars=clean_chars,
                        clean_text_words=clean_words,
                        embedding_time_ms=embed_time_ms,
                        pipeline_latency_ms=pipeline_lat_ms,
                        geo_resolution_method=geo_method,
                        content_sha256=content_sha256,
                    )

                    # Post-commit ledger link (C2)
                    await conn.execute(
                        "UPDATE llm_request_ledger SET article_id = $1 WHERE miniflux_entry_id = $2 AND article_id IS NULL",
                        article_id,
                        entry_id,
                    )

                    # Fase B: Notifica processed per lo streaming SSE del frontend
                    notify_payload = json.dumps(
                        {
                            "article_id": str(article_id),
                            "country_code": extracted_article.country_code,
                            "primary_category": extracted_article.primary_category,
                            "published_at": extracted_article.published_at,
                        },
                        separators=(",", ":"),
                    )
                    await conn.execute(
                        "SELECT pg_notify($1, $2)",
                        "radar_article_processed",
                        notify_payload,
                    )

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

                finally:
                    if lock_acquired:
                        try:
                            await conn.execute("SELECT pg_advisory_unlock($1, $2)", lock_ns, lock_key)
                            logger.debug("Advisory lock rilasciato per URL: %s", source_url)
                        except Exception as unlock_err:
                            logger.warning(
                                "Rilascio advisory lock fallito per URL %s: %s",
                                source_url,
                                unlock_err,
                            )

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
    """Consumer coda bounded: elabora entry fino a cancel; sempre ``task_done``."""
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


async def _ledger_model_rpd_used(pool: asyncpg.Pool, model: str) -> int:
    """Conta righe ledger attive per un modello specifico nel giorno half-open RADAR_TIME_ZONE."""
    day_start, day_end = compute_day_window(datetime.now(timezone.utc), RADAR_TIME_ZONE)
    async with pool.acquire() as conn:
        used = await conn.fetchval(
            """
            SELECT COUNT(*)::INT
            FROM llm_request_ledger
            WHERE created_at >= $1
              AND created_at < $2
              AND status = ANY($3::text[])
              AND model = $4
            """,
            day_start,
            day_end,
            ["reserved", "completed", "failed"],
            model,
        )
    return int(used or 0)


async def _ledger_simple_rpd_used(pool: asyncpg.Pool) -> int:
    """Conta righe ledger attive della lane SIMPLE nel giorno half-open RADAR_TIME_ZONE.

    Mantenuto per retrocompatibilità e patch nei test.
    """
    day_start, day_end = compute_day_window(datetime.now(timezone.utc), RADAR_TIME_ZONE)
    async with pool.acquire() as conn:
        used = await conn.fetchval(
            """
            SELECT COUNT(*)::INT
            FROM llm_request_ledger
            WHERE created_at >= $1
              AND created_at < $2
              AND status = ANY($3::text[])
              AND (
                    purpose = 'classify:simple'
                 OR (
                        (purpose IS NULL OR purpose = 'classify_article')
                    AND (model IS NULL OR model NOT ILIKE '%deepseek%')
                 )
              )
            """,
            day_start,
            day_end,
            ["reserved", "completed", "failed"],
        )
    return int(used or 0)


async def run_pipeline_cycle(state: WorkerState) -> None:
    """Un ciclo ingest: reconcile → soft-trim catena SIMPLE → fetch → coda + N consumer.

    Mai ``TaskGroup`` su tutte le entry. Hard RPM/TPM/RPD restano in
    ``QuotaLedger.reserve`` per-model. Soft-trim: ``rpd==0`` = unmanaged (off);
    tutti i modelli SIMPLE esauriti senza residual COMPLEX → iberna ciclo;
    con residual → bypass failover. Lot reduction usa la somma dei residui catena.
    """
    assert state.db_pool is not None
    assert state.miniflux_client is not None

    logger.info("=== Avvio di un nuovo ciclo della pipeline di ingestione ===")

    await reconcile_outbox(state.db_pool, state.miniflux_client)

    # Soft-trim per-model sulla catena SIMPLE (LLM_SIMPLE.models).
    # RPD=0 su un modello = unmanaged (soft-trim off per quel modello).
    from app.core.llm_lanes import limits_for_model

    simple_models = LLM_SIMPLE.models
    model_caps: dict[str, int] = {}
    model_used: dict[str, int] = {}
    model_residuals: dict[str, int] = {}
    any_unmanaged = False
    total_simple_residual = 0

    for m in simple_models:
        _rpm_cap, _tpm_cap, rpd_cap = limits_for_model(LLM_SIMPLE, m)
        model_caps[m] = rpd_cap
        if rpd_cap == 0:
            any_unmanaged = True
        else:
            used = await _ledger_model_rpd_used(state.db_pool, m)
            model_used[m] = used
            res = max(0, rpd_cap - used)
            model_residuals[m] = res
            total_simple_residual += res

    simple_has_residual = any_unmanaged or (total_simple_residual > 0)

    has_complex_residual = (
        LLM_ROUTING_MODE == "complexity"
        and (
            LLM_SIMPLE.provider != LLM_COMPLEX.provider
            or LLM_SIMPLE.model != LLM_COMPLEX.model
            or LLM_SIMPLE.reasoning_effort != LLM_COMPLEX.reasoning_effort
        )
    )

    if not simple_has_residual and not has_complex_residual:
        summary_str = ", ".join(
            f"{m}:{model_used.get(m, 0)}/{model_caps.get(m, 0)}" for m in simple_models
        )
        logger.warning(
            "LIMITE RPD CATENA SIMPLE RAGGIUNTO (ledger): tutti i modelli SIMPLE esauriti (%s). "
            "Ciclo in ibernazione (nessun residual COMPLEX distinto).",
            summary_str,
        )
        return

    if not simple_has_residual and has_complex_residual:
        summary_str = ", ".join(
            f"{m}:{model_used.get(m, 0)}/{model_caps.get(m, 0)}" for m in simple_models
        )
        logger.warning(
            "LIMITE RPD CATENA SIMPLE RAGGIUNTO (ledger): tutti i modelli SIMPLE esauriti (%s) — "
            "soft-trim bypass: residual COMPLEX disponibile (%s/%s); ciclo prosegue per failover.",
            summary_str,
            LLM_COMPLEX.provider,
            LLM_COMPLEX.model,
        )

    entries = await state.miniflux_client.fetch_unread_entries(limit=MINIFLUX_LIMIT)
    if not entries:
        logger.info("Nessun articolo non letto presente in Miniflux.")
        return

    if not any_unmanaged and not has_complex_residual and total_simple_residual > 0:
        if len(entries) > total_simple_residual:
            logger.info(
                "Riduzione lotto da %d a %d per soft-trim RPD catena SIMPLE (residuo catena: %d).",
                len(entries),
                total_simple_residual,
                total_simple_residual,
            )
            entries = entries[:total_simple_residual]

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
    """UPSERT periodico ``worker_heartbeat`` finché questo processo è leader.

    ``CancelledError`` ri-lanciato; altri errori solo log — il loop continua
    (readiness API dipende dalla freshness di questo heartbeat).
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


async def _wait_interval(state: WorkerState, interval: float) -> None:
    """Attesa wake NOTIFY o timeout poll di sicurezza (Fase B)."""
    try:
        await asyncio.wait_for(state.wake_event.wait(), timeout=interval)
        logger.info("Risveglio da radar_worker_trigger.")
    except asyncio.TimeoutError:
        logger.info("Timeout poll di sicurezza: avvio ciclo periodico.")


async def maybe_unload_ollama_after_cycle(state: WorkerState) -> None:
    """Dopo un ciclo: debounce breve, poi unload VRAM se nessun wake (Profilo F).

    Se ``wake_event`` scatta durante il debounce, salta l'unload per tenere il
    modello caldo sul ciclo successivo. Non-F / auto-unload off → no-op.
    """
    if not should_manage_ollama_vram():
        return
    debounce = float(OLLAMA_UNLOAD_DEBOUNCE_SECONDS)
    if debounce > 0:
        logger.info(
            "ollama_unload debounce %ss (skip se wake NOTIFY)...",
            int(debounce),
        )
        try:
            await asyncio.wait_for(state.wake_event.wait(), timeout=debounce)
            logger.info(
                "ollama_unload skipped: wake durante debounce (modello resta caldo)."
            )
            return
        except asyncio.TimeoutError:
            pass
    await maybe_unload_simple_ollama(reason="end_of_cycle")


async def run_pipeline_loop(state: WorkerState) -> None:
    """Loop demone: ciclo + sleep di poll **fuori** da qualsiasi ``finally`` di shutdown.

    Livelli errore: demone sopravvive agli errori di ciclo; ``CancelledError`` sale.
    """
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

        state.wake_event.clear()
        try:
            await maybe_unload_ollama_after_cycle(state)
        except asyncio.CancelledError:
            raise
        except Exception as unload_err:
            logger.warning("ollama_unload end_of_cycle failed: %s", unload_err)

        logger.info(
            "Attesa wake NOTIFY o timeout poll (%ss)...",
            WORKER_POLL_INTERVAL_SECONDS,
        )
        await _wait_interval(state, float(WORKER_POLL_INTERVAL_SECONDS))


async def run_worker() -> None:
    """Bootstrap → leadership → heartbeat → pipeline (o degraded sleep); sempre shutdown.

    Gate ingest: ``bool(LLM_API_KEY)`` (alias boot da lane/legacy in ``config``).
    Senza chiave: leadership+heartbeat restano, nessuna classificazione (status degraded).
    """
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

        parse_sem, db_sem, gemini_sem = build_worker_semaphores()
        state.parse_sem = parse_sem
        state.db_sem = db_sem
        state.gemini_sem = gemini_sem

        if ingest_enabled:
            state.classification_client = ClassificationClient(
                pool=state.db_pool,
                gemini_sem=gemini_sem,
            )
        else:
            # Log storico Gemini-centrico: il gate reale è LLM_API_KEY (lane o legacy).
            logger.error(
                "GEMINI_API_KEY/GOOGLE_API_KEY mancante: ingest LLM sospeso. "
                "API e frontend restano disponibili; il worker mantiene leadership + heartbeat."
            )

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

        await start_postgres_trigger_listener(state)

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
            # Resta vivo per heartbeat/leadership senza chiamare provider LLM.
            while True:
                await asyncio.sleep(float(WORKER_POLL_INTERVAL_SECONDS))

    except asyncio.CancelledError:
        logger.info("Worker cancellato; avvio shutdown ordinato.")
        raise
    finally:
        await shutdown_worker_resources(state)
        logger.info("Radar worker arrestato.")


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, main_task: asyncio.Task) -> None:
    """Cancella il task principale su SIGTERM/SIGINT (Docker stop / Ctrl+C).

    Su Windows ``add_signal_handler`` può non essere supportato → fallback ``signal.signal``.
    """

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
    """Entry CLI: ``python -m app.worker``. Cancel → exit 0 (stop Docker pulito)."""
    try:
        asyncio.run(_async_main())
    except asyncio.CancelledError:
        raise SystemExit(0) from None


if __name__ == "__main__":
    main()
