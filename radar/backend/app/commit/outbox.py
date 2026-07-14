"""Outbox reconcile: durable Vault projection + deferred Miniflux mark-read."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import TYPE_CHECKING, Optional

import asyncpg

from app.commit.lock import write_file_with_lock
from app.core.config import OUTBOX_STALE_WRITING_SECONDS

if TYPE_CHECKING:
    from app.extraction.client import MinifluxClient

logger = logging.getLogger("radar.commit.outbox")


def payload_checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def enqueue_outbox_row(
    conn: asyncpg.Connection,
    *,
    article_id: int,
    target_path: str,
    payload: str,
    miniflux_entry_id: int | None,
) -> None:
    """Insert or refresh an outbox row inside an existing transaction."""
    checksum = payload_checksum(payload)
    await conn.execute(
        """
        INSERT INTO article_outbox (
            article_id, target_path, payload, payload_checksum,
            status, attempt_count, last_error, miniflux_entry_id
        )
        VALUES ($1, $2, $3, $4, 'pending', 0, NULL, $5)
        ON CONFLICT (article_id) DO UPDATE SET
            target_path = EXCLUDED.target_path,
            payload = EXCLUDED.payload,
            payload_checksum = EXCLUDED.payload_checksum,
            status = CASE
                WHEN article_outbox.status = 'completed' THEN 'completed'
                ELSE 'pending'
            END,
            last_error = CASE
                WHEN article_outbox.status = 'completed' THEN article_outbox.last_error
                ELSE NULL
            END,
            miniflux_entry_id = COALESCE(EXCLUDED.miniflux_entry_id, article_outbox.miniflux_entry_id),
            updated_at = NOW()
        """,
        article_id,
        target_path,
        payload,
        checksum,
        miniflux_entry_id,
    )


async def _reset_stale_writing(conn: asyncpg.Connection) -> int:
    result = await conn.execute(
        """
        UPDATE article_outbox
        SET status = 'pending',
            last_error = COALESCE(last_error, '') || ' [stale writing reset]',
            updated_at = NOW()
        WHERE status = 'writing'
          AND updated_at < NOW() - ($1 * INTERVAL '1 second')
        """,
        OUTBOX_STALE_WRITING_SECONDS,
    )
    # asyncpg returns e.g. "UPDATE 2"
    try:
        return int(result.split()[-1])
    except (IndexError, ValueError):
        return 0


async def _claim_row(conn: asyncpg.Connection, outbox_id: int) -> Optional[asyncpg.Record]:
    return await conn.fetchrow(
        """
        UPDATE article_outbox
        SET status = 'writing',
            attempt_count = attempt_count + 1,
            updated_at = NOW()
        WHERE id = $1
          AND status IN ('pending', 'failed', 'writing')
        RETURNING id, article_id, target_path, payload, payload_checksum,
                  attempt_count, miniflux_entry_id
        """,
        outbox_id,
    )


async def _mark_completed(conn: asyncpg.Connection, outbox_id: int) -> None:
    await conn.execute(
        """
        UPDATE article_outbox
        SET status = 'completed',
            last_error = NULL,
            updated_at = NOW()
        WHERE id = $1
        """,
        outbox_id,
    )


async def _mark_failed(conn: asyncpg.Connection, outbox_id: int, error: str) -> None:
    await conn.execute(
        """
        UPDATE article_outbox
        SET status = 'failed',
            last_error = $2,
            updated_at = NOW()
        WHERE id = $1
        """,
        outbox_id,
        error[:4000],
    )


async def process_outbox_row(
    pool: asyncpg.Pool,
    row: asyncpg.Record,
    miniflux_client: Optional["MinifluxClient"] = None,
) -> bool:
    """
    Write Vault projection for one outbox row and mark Miniflux read only after durable completed.
    Returns True on success.
    """
    outbox_id = row["id"]

    async with pool.acquire() as conn:
        claimed = await _claim_row(conn, outbox_id)
        if claimed is None:
            return False

    target_path = claimed["target_path"]
    payload = claimed["payload"]
    expected_checksum = claimed["payload_checksum"]
    actual_checksum = payload_checksum(payload)
    if actual_checksum != expected_checksum:
        async with pool.acquire() as conn:
            await _mark_failed(
                conn,
                outbox_id,
                f"payload_checksum mismatch: expected {expected_checksum}, got {actual_checksum}",
            )
        return False

    try:
        await asyncio.to_thread(write_file_with_lock, target_path, payload)
    except Exception as write_err:
        logger.error(
            "Scrittura Vault fallita per outbox id=%s article_id=%s: %s",
            outbox_id,
            claimed["article_id"],
            write_err,
            exc_info=True,
        )
        async with pool.acquire() as conn:
            await _mark_failed(conn, outbox_id, f"vault write failed: {write_err}")
        return False

    async with pool.acquire() as conn:
        await _mark_completed(conn, outbox_id)

    entry_id = claimed["miniflux_entry_id"]
    if entry_id is not None and miniflux_client is not None:
        try:
            await miniflux_client.mark_as_read([int(entry_id)])
        except Exception as mark_err:
            # Vault already durable; mark-read can retry on next reconcile via completed rows...
            # Completed rows are not re-processed. Log and leave Miniflux unread for ops visibility.
            logger.warning(
                "Outbox id=%s completed ma mark-read Miniflux fallito (entry_id=%s): %s",
                outbox_id,
                entry_id,
                mark_err,
            )

    logger.info(
        "Outbox completato id=%s article_id=%s path=%s",
        outbox_id,
        claimed["article_id"],
        target_path,
    )
    return True


async def reconcile_outbox(
    pool: asyncpg.Pool,
    miniflux_client: Optional["MinifluxClient"] = None,
) -> dict[str, int]:
    """
    Reconcile pending / failed / stale-writing outbox rows.
    Call on startup and before every Miniflux fetch.
    """
    stats = {"reset_stale": 0, "attempted": 0, "succeeded": 0, "failed": 0}

    async with pool.acquire() as conn:
        stats["reset_stale"] = await _reset_stale_writing(conn)
        rows = await conn.fetch(
            """
            SELECT id, article_id, target_path, payload, payload_checksum,
                   attempt_count, miniflux_entry_id, status
            FROM article_outbox
            WHERE status IN ('pending', 'failed')
            ORDER BY updated_at ASC
            LIMIT 200
            """
        )

    if stats["reset_stale"]:
        logger.info("Outbox: resettate %d righe writing stale", stats["reset_stale"])

    for row in rows:
        stats["attempted"] += 1
        ok = await process_outbox_row(pool, row, miniflux_client)
        if ok:
            stats["succeeded"] += 1
        else:
            stats["failed"] += 1

    if stats["attempted"]:
        logger.info(
            "Outbox reconcile: attempted=%d succeeded=%d failed=%d",
            stats["attempted"],
            stats["succeeded"],
            stats["failed"],
        )
    return stats
