"""Unit tests for ModelCooldownStore (in-memory, no Postgres)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.classification.cooldown import ModelCooldownStore


@pytest.mark.asyncio
async def test_set_and_is_cooling_down_memory() -> None:
    fixed = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    store = ModelCooldownStore(pool=None, clock=lambda: fixed, default_hours=24)
    assert await store.is_cooling_down("gemini", "gemini-3.5-flash") is False
    until = await store.set_cooldown("gemini", "gemini-3.5-flash", reason="429 daily")
    assert until == fixed + timedelta(hours=24)
    assert await store.is_cooling_down("gemini", "gemini-3.5-flash") is True


@pytest.mark.asyncio
async def test_expired_clears() -> None:
    start = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    clock = {"now": start}

    def _now() -> datetime:
        return clock["now"]

    store = ModelCooldownStore(pool=None, clock=_now, default_hours=1)
    await store.set_cooldown("deepseek", "deepseek-v4-flash", reason="402")
    assert await store.is_cooling_down("deepseek", "deepseek-v4-flash") is True
    clock["now"] = start + timedelta(hours=2)
    assert await store.is_cooling_down("deepseek", "deepseek-v4-flash") is False
    deleted = await store.clear_expired()
    assert deleted >= 1
