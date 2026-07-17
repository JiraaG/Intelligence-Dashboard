"""
Heartbeat del worker leader per readiness Phase 3 (``GET /health/ready``).

Solo il processo che detiene l'advisory lock di leadership deve fare UPSERT.
``/health/live`` = processo su; ``/health/ready`` = pool + migrazione 004+ +
heartbeat fresco. Conteggio outbox è riportato ma **non** fallisce ready da solo
(reconcile atteso).

@see docs/02 §health; runbook live vs ready.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger("radar.heartbeat")

# Riga singleton: uno solo leader scrive (id fisso = 1).
HEARTBEAT_ROW_ID = 1


async def upsert_worker_heartbeat(
    pool: asyncpg.Pool,
    *,
    status: str = "running",
    detail: str | None = None,
) -> None:
    """
    UPSERT della riga heartbeat singleton.
    Chiamare solo dal leader (advisory lock) — altrimenti ready può mentire.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO worker_heartbeat (id, updated_at, status, leader_pid, detail)
            VALUES ($1, NOW(), $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET
                updated_at = EXCLUDED.updated_at,
                status = EXCLUDED.status,
                leader_pid = EXCLUDED.leader_pid,
                detail = EXCLUDED.detail
            """,
            HEARTBEAT_ROW_ID,
            status,
            os.getpid(),
            detail,
        )


async def fetch_worker_heartbeat(conn: asyncpg.Connection) -> asyncpg.Record | None:
    """Ritorna la riga heartbeat singleton, o None se tabella/riga assente."""
    return await conn.fetchrow(
        """
        SELECT id, updated_at, status, leader_pid, detail
        FROM worker_heartbeat
        WHERE id = $1
        """,
        HEARTBEAT_ROW_ID,
    )


def heartbeat_age_seconds(updated_at: datetime, *, now: datetime | None = None) -> float:
    """Età del timestamp heartbeat in secondi (UTC-aware; naive → UTC)."""
    clock = now or datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return max(0.0, (clock - updated_at).total_seconds())


async def evaluate_readiness(
    pool: asyncpg.Pool,
    *,
    stale_seconds: int,
    required_migration_prefix: str = "004_",
) -> tuple[bool, dict[str, Any]]:
    """
    Ready quando: pool ok, migrazione ``004_``+ applicata, heartbeat più fresco
    di ``stale_seconds``.

    Contatori outbox pending/writing/failed sono nel JSON di dettaglio ma **non**
    falliscono readiness da soli (reconcile è atteso); heartbeat missing/stale sì.

    @see runbook: 503 ready al boot ~30–90s finché il worker scrive; non restartare API.
    """
    details: dict[str, Any] = {
        "pool": False,
        "migrations_ok": False,
        "heartbeat_ok": False,
        "heartbeat_age_seconds": None,
        "heartbeat_status": None,
        "outbox_pending": 0,
        "outbox_writing": 0,
        "outbox_failed": 0,
        "reasons": [],
    }

    try:
        async with pool.acquire() as conn:
            details["pool"] = True

            applied = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM schema_migrations
                    WHERE version LIKE $1
                )
                """,
                f"{required_migration_prefix}%",
            )
            details["migrations_ok"] = bool(applied)
            if not applied:
                details["reasons"].append("migration_004_missing")

            row = await fetch_worker_heartbeat(conn)
            if row is None:
                details["reasons"].append("heartbeat_missing")
            else:
                age = heartbeat_age_seconds(row["updated_at"])
                details["heartbeat_age_seconds"] = round(age, 1)
                details["heartbeat_status"] = row["status"]
                if age <= float(stale_seconds):
                    details["heartbeat_ok"] = True
                else:
                    details["reasons"].append("heartbeat_stale")

            counts = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE status = 'writing') AS writing,
                    COUNT(*) FILTER (WHERE status = 'failed') AS failed
                FROM article_outbox
                """
            )
            if counts is not None:
                details["outbox_pending"] = int(counts["pending"] or 0)
                details["outbox_writing"] = int(counts["writing"] or 0)
                details["outbox_failed"] = int(counts["failed"] or 0)

    except Exception as exc:
        logger.warning("evaluate_readiness fallita: %s", exc)
        details["reasons"].append(f"error:{type(exc).__name__}")
        return False, details

    ready = (
        details["pool"]
        and details["migrations_ok"]
        and details["heartbeat_ok"]
    )
    return ready, details
