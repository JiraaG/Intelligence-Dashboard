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
    maybe_unload_ollama_after_cycle,
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

    async def fake_wait_interval(state: Any, interval: float) -> bool:
        if interval >= 10:
            poll_entered.set()
        await asyncio.Event().wait()
        return False

    with (
        patch("app.worker.run_pipeline_cycle", new_callable=AsyncMock, return_value=False),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 900),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 0),
        patch("app.worker._wait_interval", side_effect=fake_wait_interval),
        patch("app.worker.maybe_unload_ollama_after_cycle", new_callable=AsyncMock),
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

    async def blocking_cycle(_state: WorkerState) -> bool:
        processing.set()
        await asyncio.Event().wait()
        return False

    with (
        patch("app.worker.run_pipeline_cycle", side_effect=blocking_cycle),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 3600),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 0),
        patch("app.worker.maybe_unload_ollama_after_cycle", new_callable=AsyncMock),
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

    async def empty_cycle(_state: WorkerState) -> bool:
        nonlocal cycles
        cycles += 1
        return False

    async def fake_wait_interval(state: Any, interval: float) -> bool:
        poll_entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        return False

    with (
        patch("app.worker.run_pipeline_cycle", side_effect=empty_cycle),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 60),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 0),
        patch("app.worker._wait_interval", side_effect=fake_wait_interval),
        patch("app.worker.maybe_unload_ollama_after_cycle", new_callable=AsyncMock),
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

    async def cancel_cycle(_state: WorkerState) -> bool:
        raise asyncio.CancelledError()

    with (
        patch("app.worker.run_pipeline_cycle", side_effect=cancel_cycle),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 60),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 0),
        patch("app.worker.maybe_unload_ollama_after_cycle", new_callable=AsyncMock),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pipeline_loop_calls_unload_once_per_drain_before_wait() -> None:
    """Dopo la fase di drain, chiama maybe_unload_ollama_after_cycle 1 volta prima del wait."""
    state = _make_state()
    unload = AsyncMock()
    poll_entered = asyncio.Event()

    async def fake_wait_interval(_state: Any, _interval: float) -> bool:
        poll_entered.set()
        await asyncio.Event().wait()
        return False

    with (
        patch("app.worker.run_pipeline_cycle", new_callable=AsyncMock, return_value=False),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 60),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 0),
        patch("app.worker._wait_interval", side_effect=fake_wait_interval),
        patch("app.worker.maybe_unload_ollama_after_cycle", unload),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        await asyncio.wait_for(poll_entered.wait(), timeout=2.0)
        unload.assert_awaited_once()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)



@pytest.mark.unit
@pytest.mark.asyncio
async def test_eager_drain_multiple_batches_before_single_wait() -> None:
    """Eager drain: 2 lotti con entries poi empty -> 1 solo wait, 1 solo unload."""
    state = _make_state()
    poll_entered = asyncio.Event()
    unload = AsyncMock()
    cycle_mock = AsyncMock(side_effect=[True, True, False])

    async def fake_wait_interval(_state: Any, _interval: float) -> bool:
        poll_entered.set()
        await asyncio.Event().wait()
        return False

    with (
        patch("app.worker.run_pipeline_cycle", cycle_mock),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 60),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 0),
        patch("app.worker._wait_interval", side_effect=fake_wait_interval) as mock_wait,
        patch("app.worker.maybe_unload_ollama_after_cycle", unload),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        await asyncio.wait_for(poll_entered.wait(), timeout=2.0)
        assert cycle_mock.call_count == 3
        mock_wait.assert_called_once()
        unload.assert_called_once()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_selective_settle_boot_vs_notify_wake() -> None:
    """R5: Boot/timeout usano settle=True; NOTIFY wake usa settle=False."""
    state = _make_state()
    drain_calls: list[bool] = []
    poll_entered = asyncio.Event()
    wait_count = 0

    async def fake_drain_unread(_state: WorkerState, *, settle: bool = True) -> None:
        drain_calls.append(settle)

    async def fake_wait_interval(_state: Any, _interval: float) -> bool:
        nonlocal wait_count
        wait_count += 1
        if wait_count == 1:
            # Primo wait: svegliato da wake NOTIFY
            return True
        else:
            # Secondo wait: blocca
            poll_entered.set()
            await asyncio.Event().wait()
            return False

    with (
        patch("app.worker._drain_unread", side_effect=fake_drain_unread),
        patch("app.worker.WORKER_POLL_INTERVAL_SECONDS", 60),
        patch("app.worker._wait_interval", side_effect=fake_wait_interval),
        patch("app.worker.maybe_unload_ollama_after_cycle", new_callable=AsyncMock),
    ):
        task = asyncio.create_task(run_pipeline_loop(state))
        await asyncio.wait_for(poll_entered.wait(), timeout=2.0)
        # 1° drain (boot) -> settle=True; 2° drain (post-wake NOTIFY) -> settle=False
        assert drain_calls == [True, False]
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2.0)



@pytest.mark.unit
@pytest.mark.asyncio
async def test_maybe_unload_after_cycle_skips_on_wake() -> None:
    state = _make_state()
    state.wake_event.set()
    with (
        patch("app.worker.should_manage_ollama_vram", return_value=True),
        patch("app.worker.OLLAMA_UNLOAD_DEBOUNCE_SECONDS", 30),
        patch("app.worker.maybe_unload_simple_ollama", new_callable=AsyncMock) as unload,
    ):
        await maybe_unload_ollama_after_cycle(state)
        unload.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_maybe_unload_after_cycle_unloads_after_debounce() -> None:
    state = _make_state()
    with (
        patch("app.worker.should_manage_ollama_vram", return_value=True),
        patch("app.worker.OLLAMA_UNLOAD_DEBOUNCE_SECONDS", 0),
        patch("app.worker.maybe_unload_simple_ollama", new_callable=AsyncMock) as unload,
    ):
        await maybe_unload_ollama_after_cycle(state)
        unload.assert_awaited_once_with(reason="end_of_cycle")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_maybe_unload_after_cycle_noop_when_not_profilo_f() -> None:
    state = _make_state()
    with (
        patch("app.worker.should_manage_ollama_vram", return_value=False),
        patch("app.worker.maybe_unload_simple_ollama", new_callable=AsyncMock) as unload,
    ):
        await maybe_unload_ollama_after_cycle(state)
        unload.assert_not_awaited()


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

    with (
        patch("app.worker.WORKER_SHUTDOWN_TIMEOUT", 1),
        patch("app.worker.release_advisory_lock", new_callable=AsyncMock, return_value=True),
        patch("app.worker.stop_postgres_trigger_listener", new_callable=AsyncMock),
        patch("app.worker.maybe_unload_simple_ollama", new_callable=AsyncMock) as unload,
    ):
        started = time.monotonic()
        await asyncio.wait_for(
            shutdown_worker_resources(state, shutdown_timeout=1.0, lock_key=42),
            timeout=3.0,
        )
        assert time.monotonic() - started < 3.0

    unload.assert_awaited_once_with(reason="shutdown")
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_pipeline_cycle_returns_false_when_all_entries_fail() -> None:
    """Se tutte le entry nel lotto falliscono (success==0), run_pipeline_cycle ritorna False per evitare tight loop."""
    state = _make_state()
    entries = [_make_entry(1), _make_entry(2)]
    state.miniflux_client.fetch_unread_entries = AsyncMock(return_value=entries)

    async def failing_process(_state: WorkerState, _entry: ValidatedMinifluxEntry) -> bool:
        return False

    with (
        patch("app.worker.reconcile_outbox", new_callable=AsyncMock),
        patch("app.worker._ledger_model_rpd_used", new_callable=AsyncMock, return_value=0),
        patch("app.core.llm_lanes.limits_for_model", return_value=(0, 0, 100)),
        patch("app.worker.LLM_SIMPLE") as mock_simple,
        patch("app.worker.process_single_entry", side_effect=failing_process),
    ):
        mock_simple.models = ["test-model"]
        res = await run_pipeline_cycle(state)
        assert res is False

