"""Unit tests for worker heartbeat age and readiness evaluation (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.heartbeat import evaluate_readiness, heartbeat_age_seconds


@pytest.mark.unit
def test_heartbeat_age_seconds_aware() -> None:
    now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
    updated = now - timedelta(seconds=45)
    assert heartbeat_age_seconds(updated, now=now) == 45.0


@pytest.mark.unit
def test_heartbeat_age_seconds_naive_treated_as_utc() -> None:
    now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
    updated = datetime(2026, 7, 15, 11, 59, 0)  # naive
    assert heartbeat_age_seconds(updated, now=now) == 60.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_evaluate_readiness_fresh_heartbeat() -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=True)
    conn.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": 1,
                "updated_at": datetime.now(timezone.utc),
                "status": "running",
                "leader_pid": 42,
                "detail": None,
            },
            {"pending": 0, "writing": 0, "failed": 0},
        ]
    )

    pool = MagicMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__.return_value = conn
    acquire_cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=acquire_cm)

    ready, details = await evaluate_readiness(pool, stale_seconds=90)
    assert ready is True
    assert details["heartbeat_ok"] is True
    assert details["migrations_ok"] is True
    assert details["reasons"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_evaluate_readiness_stale_heartbeat() -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=True)
    conn.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": 1,
                "updated_at": datetime.now(timezone.utc) - timedelta(seconds=120),
                "status": "running",
                "leader_pid": 42,
                "detail": None,
            },
            {"pending": 1, "writing": 0, "failed": 0},
        ]
    )

    pool = MagicMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__.return_value = conn
    acquire_cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=acquire_cm)

    ready, details = await evaluate_readiness(pool, stale_seconds=90)
    assert ready is False
    assert details["heartbeat_ok"] is False
    assert "heartbeat_stale" in details["reasons"]
    assert details["outbox_pending"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_evaluate_readiness_missing_migration() -> None:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=False)
    conn.fetchrow = AsyncMock(
        side_effect=[
            None,
            {"pending": 0, "writing": 0, "failed": 0},
        ]
    )

    pool = MagicMock()
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__.return_value = conn
    acquire_cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=acquire_cm)

    ready, details = await evaluate_readiness(pool, stale_seconds=90)
    assert ready is False
    assert "migration_004_missing" in details["reasons"]
    assert "heartbeat_missing" in details["reasons"]
