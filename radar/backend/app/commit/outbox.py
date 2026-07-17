"""Reconcile outbox: proiezione Vault durable + mark-read Miniflux differito.

Ordine vincolante: claim → checksum → write vault → ``completed`` → mark-read.
Mark-read fallito lascia ``miniflux_marked_at`` NULL per retry. Righe ``writing``
stale tornano ``pending`` dopo ``OUTBOX_STALE_WRITING_SECONDS``.

SoT:
    docs/02_architecture_and_backend.md; radar/docs/runbook.md (outbox).
"""

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
    """SHA-256 hex del payload UTF-8: rileva corruzione / race sul blob outbox."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def enqueue_outbox_row(
    conn: asyncpg.Connection,
    *,
    article_id: int,
    target_path: str,
    payload: str,
    miniflux_entry_id: int | None,
) -> None:
    """Inserisce o aggiorna una riga outbox **dentro** una transazione già aperta.

    Se lo status corrente è ``completed``, resta ``completed`` (non riapre il lavoro).
    Altrimenti forza ``pending`` e azzera errori / mark-read per un nuovo reconcile.
    """
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
            miniflux_marked_at = CASE
                WHEN article_outbox.status = 'completed' THEN article_outbox.miniflux_marked_at
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
    """``writing`` più vecchie della soglia → ``pending`` (crash mid-write).

    Returns:
        Numero di righe resettate (parse del tag ``UPDATE N`` asyncpg).
    """
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
    """Passa la riga a ``writing`` e incrementa ``attempt_count`` (claim ottimistico).

    Returns:
        Record claimed, oppure ``None`` se lo status non era claimabile.
    """
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
    """Vault durable: status ``completed``. Mark-read Miniflux avviene dopo."""
    await conn.execute(
        """
        UPDATE article_outbox
        SET status = 'completed',
            miniflux_marked_at = NULL,
            last_error = NULL,
            updated_at = NOW()
        WHERE id = $1
        """,
        outbox_id,
    )


async def _update_miniflux_marked_at(conn: asyncpg.Connection, outbox_id: int) -> None:
    """Registra mark-read Miniflux riuscito (retry se resta NULL)."""
    await conn.execute(
        """
        UPDATE article_outbox
        SET miniflux_marked_at = NOW(),
            updated_at = NOW()
        WHERE id = $1
        """,
        outbox_id,
    )


async def _mark_failed(conn: asyncpg.Connection, outbox_id: int, error: str) -> None:
    """Fallimento vault/checksum: status ``failed`` + ``last_error`` truncato."""
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
    """Proietta una riga outbox sul Vault; mark-read solo dopo ``completed``.

    Flusso: claim → verifica checksum → ``write_file_with_lock`` (thread) →
    ``completed`` → eventuale ``mark_as_read``. Errore mark-read: vault resta
    durable, ``miniflux_marked_at`` NULL per retry in ``reconcile_outbox``.

    Args:
        pool: Pool asyncpg (acquire brevi, non tiene lock per tutta la scrittura FS).
        row: Riga con almeno ``id`` (pending/failed tipicamente).
        miniflux_client: Opzionale; se assente salta mark-read.
    Returns:
        ``True`` se vault completed (mark-read può ancora essere in ritardo).
    SoT:
        docs/02; runbook (pending→writing→completed|failed).
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
            async with pool.acquire() as conn:
                await _update_miniflux_marked_at(conn, outbox_id)
        except Exception as mark_err:
            # Vault già durable; leave miniflux_marked_at NULL so reconcile ritenta mark-read.
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
    """Reconcile pending/failed/stale-writing e retry mark-read su completed orfani.

    Da chiamare all'avvio worker e prima di ogni fetch Miniflux. Limite 200 righe
    per ciclo per non bloccare il poll.

    Returns:
        Stats ``reset_stale`` / ``attempted`` / ``succeeded`` / ``failed``.
    SoT:
        runbook outbox; docs/02 (vault prima di mark-read).
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
        completed_rows = await conn.fetch(
            """
            SELECT id, article_id, miniflux_entry_id
            FROM article_outbox
            WHERE status = 'completed'
              AND miniflux_marked_at IS NULL
              AND miniflux_entry_id IS NOT NULL
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

    for row in completed_rows:
        outbox_id = row["id"]
        entry_id = row["miniflux_entry_id"]
        if miniflux_client is not None:
            stats["attempted"] += 1
            try:
                await miniflux_client.mark_as_read([int(entry_id)])
                async with pool.acquire() as conn:
                    await _update_miniflux_marked_at(conn, outbox_id)
                stats["succeeded"] += 1
                logger.info(
                    "Outbox retry mark-read completato per id=%s article_id=%s (entry_id=%s)",
                    outbox_id,
                    row["article_id"],
                    entry_id,
                )
            except Exception as retry_err:
                stats["failed"] += 1
                logger.warning(
                    "Outbox retry mark-read fallito per id=%s (entry_id=%s): %s",
                    outbox_id,
                    entry_id,
                    retry_err,
                )

    if stats["attempted"]:
        logger.info(
            "Outbox reconcile: attempted=%d succeeded=%d failed=%d",
            stats["attempted"],
            stats["succeeded"],
            stats["failed"],
        )
    return stats
