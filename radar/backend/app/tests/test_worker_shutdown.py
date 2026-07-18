"""
Worker shutdown, cancellation, and bounded-queue coverage (Phase 2).

Exercises real run_pipeline_loop / run_pipeline_cycle / shutdown_worker_resources
with Miniflux/Gemini/DB work mocked. Never marked live.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.extraction.entry_validation import ValidatedMinifluxEntry
from app.worker import (
    WorkerState,
    run_pipeline_cycle,
    run_pipeline_loop,
    shutdown_worker_resources,
)


def _make_entry(entry_id: int) -> ValidatedMinifluxEntry:
    return ValidatedMinifluxEntry(
        id=entry_id,
        source_url=f"https://example.com/article/{entry_id}",
        title=f"Title {entry_id}",
        content="<p>body</p>",
        published_at="2026-07-14",
        feed_title="Test Feed",
    )


def _make_state(*, with_resources: bool = False) -> WorkerState:
    state = WorkerState()
    state.db_pool = MagicMock()
    state.miniflux_client = AsyncMock()
    state.miniflux_client.refresh_all_feeds = AsyncMock()
    state.miniflux_client.fetch_unread_entries = AsyncMock(return_value=[])
    state.classification_client = AsyncMock()
    state.parse_sem = asyncio.Semaphore(8)
    state.db_sem = asyncio.Semaphore(4)
    state.gemini_sem = asyncio.Semaphore(2)
    if with_resources:
        state.http_client = AsyncMock()
        state.http_client.aclose = AsyncMock()
        state.db_pool.close = AsyncMock()
        state.lock_conn = AsyncMock()
        state.lock_conn.close = AsyncMock()
        state.lock_held = False
    return state


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_during_poll_wait_completes_quickly() -> None:
    """Cancel while awaiting poll sleep must finish in seconds (no hang)."""
    state = _make_state()
    poll_entered = asyncio.Event()

    async def fake_wait_interval(state: Any, interval: float) -> None:
        if interval >= 10:
            poll_entered.set()
        await asyncio.Event().wait()

    with (
        patch("app.worker.run_pipeline_cycle", new_callable=AsyncMock),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 900),
        patch("app.worker._wait_interval", side_effect=fake_wait_interval),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        await asyncio.wait_for(poll_entered.wait(), timeout=2.0)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)
        assert time.monotonic() - started < 2.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_while_processing_completes_quickly() -> None:
    """Cancel while a cycle is mid-work must re-raise CancelledError promptly."""
    state = _make_state()
    processing = asyncio.Event()

    async def blocking_cycle(_state: WorkerState) -> None:
        processing.set()
        await asyncio.Event().wait()

    with (
        patch("app.worker.run_pipeline_cycle", side_effect=blocking_cycle),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 3600),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        await asyncio.wait_for(processing.wait(), timeout=2.0)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)
        assert time.monotonic() - started < 2.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancel_when_idle_between_cycles() -> None:
    """Idle path (empty cycle then poll wait) cancels cleanly and re-raises."""
    state = _make_state()
    cycles = 0
    poll_entered = asyncio.Event()

    async def empty_cycle(_state: WorkerState) -> None:
        nonlocal cycles
        cycles += 1

    async def fake_wait_interval(state: Any, interval: float) -> None:
        poll_entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

    with (
        patch("app.worker.run_pipeline_cycle", side_effect=empty_cycle),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 60),
        patch("app.worker._wait_interval", side_effect=fake_wait_interval),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        await asyncio.wait_for(poll_entered.wait(), timeout=2.0)
        assert cycles >= 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancelled_error_not_swallowed_by_cycle_handler() -> None:
    """run_pipeline_loop must re-raise CancelledError from the cycle, not log-and-continue."""
    state = _make_state()

    async def cancel_cycle(_state: WorkerState) -> None:
        raise asyncio.CancelledError()

    with (
        patch("app.worker.run_pipeline_cycle", side_effect=cancel_cycle),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 60),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_worker_resources_cancels_consumers_bounded() -> None:
    """shutdown_worker_resources cancels consumers, awaits bounded, closes resources."""
    state = _make_state(with_resources=True)
    block = asyncio.Event()

    async def hanging_consumer() -> None:
        try:
            await block.wait()
        except asyncio.CancelledError:
            raise

    state.consumer_tasks = [
        asyncio.create_task(hanging_consumer(), name="test-consumer-0"),
        asyncio.create_task(hanging_consumer(), name="test-consumer-1"),
    ]
    state.lock_held = True
    state.lock_conn.fetchval = AsyncMock(return_value=True)
    http_client = state.http_client
    db_pool = state.db_pool
    lock_conn = state.lock_conn

    started = time.monotonic()
    await asyncio.wait_for(
        shutdown_worker_resources(state, shutdown_timeout=1.0, lock_key=42),
        timeout=3.0,
    )
    assert time.monotonic() - started < 3.0
    assert state.consumer_tasks == []
    http_client.aclose.assert_awaited()
    db_pool.close.assert_awaited()
    lock_conn.close.assert_awaited()
    assert state.lock_held is False
    assert state.http_client is None
    assert state.db_pool is None
    assert state.lock_conn is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ten_thousand_entries_never_spawn_ten_thousand_tasks() -> None:
    """
    A 10,000-entry Miniflux batch must use a bounded queue + N consumers —
    never a TaskGroup / create_task per entry.
    """
    state = _make_state()
    entries = [_make_entry(i) for i in range(10_000)]
    state.miniflux_client.fetch_unread_entries = AsyncMock(return_value=entries)

    concurrent = 0
    max_concurrent = 0
    processed = 0
    create_task_calls: list[str | None] = []
    queue_maxsizes: list[int] = []

    real_create_task = asyncio.create_task

    async def tracked_process(_state: WorkerState, _entry: ValidatedMinifluxEntry) -> bool:
        nonlocal concurrent, max_concurrent, processed
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        processed += 1
        concurrent -= 1
        return True

    def spy_create_task(coro: Any, **kwargs: Any) -> asyncio.Task:
        create_task_calls.append(kwargs.get("name"))
        return real_create_task(coro, **kwargs)

    class SpyQueue(asyncio.Queue):
        def __init__(self, maxsize: int = 0) -> None:
            queue_maxsizes.append(maxsize)
            super().__init__(maxsize=maxsize)

    entry_concurrency = 4
    queue_depth = 50

    with (
        patch("app.worker.reconcile_outbox", new_callable=AsyncMock),
        patch("app.worker._ledger_simple_rpd_used", new_callable=AsyncMock, return_value=0),
        patch("app.worker.LLM_SIMPLE") as mock_simple,
        patch("app.worker.WORKER_ENTRY_CONCURRENCY", entry_concurrency),
        patch("app.worker.WORKER_QUEUE_DEPTH", queue_depth),
        patch("app.worker.process_single_entry", side_effect=tracked_process),
        patch("app.worker.asyncio.create_task", side_effect=spy_create_task),
        patch("app.worker.asyncio.Queue", SpyQueue),
    ):
        mock_simple.rpd = 20_000
        await asyncio.wait_for(run_pipeline_cycle(state), timeout=30.0)

    assert queue_maxsizes == [queue_depth]
    assert len(create_task_calls) == entry_concurrency
    assert all(
        name is not None and name.startswith("radar-entry-consumer-")
        for name in create_task_calls
    )
    assert max_concurrent <= entry_concurrency
    assert processed == 10_000
    assert state.consumer_tasks == []
    # Sanity: never one task per entry (would be 10_000 create_task calls).
    assert len(create_task_calls) < 100
