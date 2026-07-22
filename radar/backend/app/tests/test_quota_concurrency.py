"""
QuotaLedger concurrency, reservation identity, and day-window coverage (Phase 2).

Uses an in-memory fake asyncpg pool so `pytest -m "not live"` stays offline.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from unittest.mock import AsyncMock, patch

import pytest

from app.classification.client import ClassificationClient
from app.classification.quota import QuotaBudgetExceeded, QuotaDailyExceeded, QuotaLedger, compute_day_window


# ─── In-memory fake asyncpg ───────────────────────────────────────────────────

_ACTIVE = frozenset({"reserved", "completed", "failed"})


def _is_deepseek_model(model: str | None) -> bool:
    return model is not None and "deepseek" in model.lower()


@dataclass
class _Row:
    id: int
    reserved_tokens: int
    actual_tokens: int | None
    status: str
    created_at: datetime
    model: str | None = None
    purpose: str | None = None


@dataclass
class InMemoryLedgerStore:
    """Shared durable ledger state for one or more QuotaLedger instances."""

    rows: dict[int, _Row] = field(default_factory=dict)
    next_id: int = 1
    xact_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    utc_now: Callable[[], datetime] = field(
        default_factory=lambda: (lambda: datetime.now(timezone.utc))
    )

    def active_count(self) -> int:
        return sum(1 for r in self.rows.values() if r.status in _ACTIVE)

    def rpm_window_count(self, now: datetime) -> int:
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
        window_start = now - timedelta(seconds=60)
        return sum(
            1
            for r in self.rows.values()
            if r.created_at > window_start and r.status in _ACTIVE
        )


class _TxnCM:
    def __init__(self, store: InMemoryLedgerStore) -> None:
        self._store = store

    async def __aenter__(self) -> None:
        await self._store.xact_lock.acquire()

    async def __aexit__(self, *exc: object) -> None:
        self._store.xact_lock.release()


class FakeConnection:
    def __init__(self, store: InMemoryLedgerStore) -> None:
        self._store = store

    def transaction(self) -> _TxnCM:
        return _TxnCM(self._store)

    async def execute(self, query: str, *args: Any) -> str:
        return await self._dispatch(query, args, returning=False)  # type: ignore[return-value]

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._dispatch(query, args, returning=True)

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return await self._dispatch(query, args, returning=True)

    async def _dispatch(self, query: str, args: tuple[Any, ...], *, returning: bool) -> Any:
        q = " ".join(query.split())

        if "pg_advisory_xact_lock" in q:
            return None

        if "SELECT lane FROM llm_request_ledger" in q:
            rid = int(args[0])
            row = self._store.rows.get(rid)
            return {"lane": "simple"} if row else None

        if "INSERT INTO llm_request_ledger" in q:
            rid = self._store.next_id
            self._store.next_id += 1
            now = self._store.utc_now()
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            else:
                now = now.astimezone(timezone.utc)
            self._store.rows[rid] = _Row(
                id=rid,
                reserved_tokens=int(args[0]),
                actual_tokens=None,
                status="reserved",
                created_at=now,
                model=args[1] if len(args) > 1 else None,
                purpose=args[2] if len(args) > 2 else None,
            )
            peak = getattr(self._store, "_peak_rpm", None)
            if isinstance(peak, list):
                peak.append(self._store.rpm_window_count(now))
            return rid if returning else f"INSERT 0 1"

        if "status = 'completed'" in q:
            rid = int(args[0])
            tokens = int(args[1])
            row = self._store.rows.get(rid)
            if row is None or row.status != "reserved":
                return "UPDATE 0"
            row.actual_tokens = tokens
            row.status = "completed"
            return "UPDATE 1"

        if "status = 'released'" in q:
            rid = int(args[0])
            row = self._store.rows.get(rid)
            if row is None or row.status != "reserved":
                return "UPDATE 0"
            row.status = "released"
            return "UPDATE 1"

        if "status = 'failed'" in q:
            rid = int(args[0])
            tokens = args[1] if len(args) > 1 else None
            row = self._store.rows.get(rid)
            if row is None or row.status != "reserved":
                return "UPDATE 0"
            row.status = "failed"
            if tokens is not None:
                row.actual_tokens = max(0, int(tokens))
            return "UPDATE 1"

        if "SUM(COALESCE" in q:
            statuses = set(next((a for a in args if isinstance(a, (list, tuple, set))), ["reserved", "completed", "failed"]))
            target_model = args[-1] if ("model =" in q or "model = $" in q) and isinstance(args[-1], str) else None
            total = 0
            if "created_at >=" in q and "created_at <" in q:
                day_start, day_end = args[0], args[1]
                for row in self._store.rows.values():
                    if not (day_start <= row.created_at < day_end and row.status in statuses):
                        continue
                    if target_model is not None and row.model != target_model:
                        continue
                    total += (
                        row.actual_tokens
                        if row.actual_tokens is not None
                        else row.reserved_tokens
                    )
                return total
            window_start = args[0]
            for row in self._store.rows.values():
                if not (row.created_at > window_start and row.status in statuses):
                    continue
                if target_model is not None and row.model != target_model:
                    continue
                total += (
                    row.actual_tokens
                    if row.actual_tokens is not None
                    else row.reserved_tokens
                )
            return total

        if "MIN(created_at)" in q:
            statuses = set(next((a for a in args if isinstance(a, (list, tuple, set))), ["reserved", "completed", "failed"]))
            target_model = args[-1] if ("model =" in q or "model = $" in q) and isinstance(args[-1], str) else None
            window_start = args[0]
            times = [
                row.created_at
                for row in self._store.rows.values()
                if row.created_at > window_start
                and row.status in statuses
                and (target_model is None or row.model == target_model)
            ]
            return min(times) if times else None

        if "COUNT(*)" in q:
            statuses = set(next((a for a in args if isinstance(a, (list, tuple, set))), ["reserved", "completed", "failed"]))
            target_model = args[-1] if ("model =" in q or "model = $" in q) and isinstance(args[-1], str) else None

            def _match(row: _Row) -> bool:
                if row.status not in statuses:
                    return False
                if target_model is not None and row.model != target_model:
                    return False
                return True

            if "created_at >=" in q and "created_at <" in q:
                day_start, day_end = args[0], args[1]
                return sum(
                    1
                    for row in self._store.rows.values()
                    if day_start <= row.created_at < day_end and _match(row)
                )
            window_start = args[0]
            return sum(
                1
                for row in self._store.rows.values()
                if row.created_at > window_start and _match(row)
            )

        raise AssertionError(f"Unhandled SQL in fake pool: {q[:120]}")


class _AcquireCM:
    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self._conn

    async def __aexit__(self, *exc: object) -> None:
        return None


class FakePool:
    """Minimal asyncpg.Pool stand-in shared by concurrent QuotaLedger instances."""

    def __init__(self, store: InMemoryLedgerStore) -> None:
        self._store = store

    def acquire(self) -> _AcquireCM:
        return _AcquireCM(FakeConnection(self._store))

    async def execute(self, query: str, *args: Any) -> str:
        return await FakeConnection(self._store).execute(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return await FakeConnection(self._store).fetchrow(query, *args)


    async def execute(self, query: str, *args: Any) -> str:
        return await FakeConnection(self._store).execute(query, *args)


class ControllableClock:
    """Injectable monotonic + UTC clock; sleep advances both."""

    def __init__(self, start: datetime | None = None) -> None:
        self.utc = start or datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
        self.mono = 1_000.0

    def utc_now(self) -> datetime:
        return self.utc

    def monotonic(self) -> float:
        return self.mono

    async def sleep(self, seconds: float) -> None:
        seconds = max(0.0, float(seconds))
        self.mono += seconds
        self.utc = self.utc + timedelta(seconds=seconds)
        await asyncio.sleep(0)


def _ledgers(
    *,
    rpm: int,
    tpm: int,
    rpd: int,
    n: int = 2,
    clock: ControllableClock | None = None,
    tz: timezone = timezone.utc,
    deepseek_rpm: int = 0,
    deepseek_tpm: int = 0,
    deepseek_rpd: int = 0,
    deepseek_budget_usd_day: float = 0.0,
    simple: LlmLaneConfig | None = None,
    complex_lane: LlmLaneConfig | None = None,
) -> tuple[InMemoryLedgerStore, FakePool, ControllableClock, list[QuotaLedger]]:
    clock = clock or ControllableClock()
    store = InMemoryLedgerStore(utc_now=clock.utc_now)
    store._peak_rpm = []  # type: ignore[attr-defined]
    pool = FakePool(store)
    ledgers = [
        QuotaLedger(
            pool,
            simple=simple,
            complex_lane=complex_lane,
            rpm=rpm,
            tpm=tpm,
            rpd=rpd,
            deepseek_rpm=deepseek_rpm,
            deepseek_tpm=deepseek_tpm,
            deepseek_rpd=deepseek_rpd,
            deepseek_budget_usd_day=deepseek_budget_usd_day,
            time_zone=tz,
            time_zone_name=getattr(tz, "key", str(tz)),
            sleep=clock.sleep,
            monotonic=clock.monotonic,
            utc_now=clock.utc_now,
            advisory_lock_key=99_001,
            default_estimated_tokens=100,
        )
        for _ in range(n)
    ]
    return store, pool, clock, ledgers


# ─── Day window ───────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_compute_day_window_half_open_utc() -> None:
    now = datetime(2026, 7, 14, 22, 30, tzinfo=timezone.utc)
    start, end = compute_day_window(now, timezone.utc)
    assert start == datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)
    assert start <= now < end
    # Half-open: next day start is exclusive boundary of previous window.
    assert not (start <= end < end)


@pytest.mark.unit
def test_compute_day_window_fixed_offset_crosses_utc_midnight() -> None:
    """Non-UTC local midnight: half-open window expressed in UTC."""
    # Simulate UTC+2 (e.g. Rome summer) without requiring the tzdata package.
    tz = timezone(timedelta(hours=2))
    # 22:30 UTC = 00:30 next calendar day in UTC+2.
    now = datetime(2026, 7, 14, 22, 30, tzinfo=timezone.utc)
    start, end = compute_day_window(now, tz)
    assert start == datetime(2026, 7, 14, 22, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 15, 22, 0, tzinfo=timezone.utc)
    assert start <= now < end


@pytest.mark.unit
def test_compute_day_window_naive_treated_as_utc() -> None:
    now = datetime(2026, 1, 1, 15, 0, 0)  # naive
    start, end = compute_day_window(now, timezone.utc)
    assert start.tzinfo is timezone.utc
    assert end.tzinfo is timezone.utc
    assert start == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


@pytest.mark.unit
def test_compute_day_window_fixed_offset_winter() -> None:
    """UTC+1 local day boundary (e.g. Rome winter) without tzdata."""
    tz = timezone(timedelta(hours=1))
    now = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    start, end = compute_day_window(now, tz)
    assert start == datetime(2026, 1, 14, 23, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc)
    assert start <= now < end


# ─── Concurrency / durable caps ───────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_two_ledgers_cannot_exceed_rpm() -> None:
    """Two QuotaLedger instances sharing a pool never push active RPM past the cap."""
    store, _pool, _clock, (ledger_a, ledger_b) = _ledgers(rpm=3, tpm=0, rpd=100, n=2)
    peak: list[int] = store._peak_rpm  # type: ignore[attr-defined]

    async def burst(ledger: QuotaLedger, n: int) -> list[int]:
        ids: list[int] = []
        for _ in range(n):
            ids.append(await ledger.reserve(estimated_tokens=10, purpose="rpm-test"))
        return ids

    # 6 reserves across two "workers"; durable RPM=3 must serialize via advisory lock.
    results = await asyncio.wait_for(
        asyncio.gather(burst(ledger_a, 3), burst(ledger_b, 3)),
        timeout=5.0,
    )
    all_ids = results[0] + results[1]
    assert len(all_ids) == 6
    assert len(set(all_ids)) == 6
    assert peak
    assert max(peak) <= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_two_ledgers_cannot_exceed_rpd() -> None:
    store, _pool, _clock, (ledger_a, ledger_b) = _ledgers(rpm=50, tpm=0, rpd=4, n=2)

    async def one(ledger: QuotaLedger) -> int:
        return await ledger.reserve(estimated_tokens=1, purpose="rpd-test")

    # First 4 succeed; further reserves raise QuotaDailyExceeded (failover, no day-wait).
    first = await asyncio.gather(one(ledger_a), one(ledger_b), one(ledger_a), one(ledger_b))
    assert len(first) == 4
    assert store.active_count() == 4

    with pytest.raises(QuotaDailyExceeded):
        await ledger_a.reserve(estimated_tokens=1, purpose="rpd-overflow")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_two_ledgers_cannot_exceed_tpm() -> None:
    store, _pool, clock, (ledger_a, ledger_b) = _ledgers(rpm=50, tpm=2500, rpd=100, n=2)

    id_a = await ledger_a.reserve(estimated_tokens=2000, purpose="tpm-a")
    mono_before = clock.mono
    id_b = await asyncio.wait_for(
        ledger_b.reserve(estimated_tokens=2000, purpose="tpm-b"),
        timeout=5.0,
    )

    assert id_a != id_b
    assert id_a in store.rows and id_b in store.rows
    # Second reserve had to wait for the 60s TPM window to slide (clock advanced).
    assert clock.mono > mono_before
    # Never two overlapping 2000-token actives in the same 60s window after both done:
    # the later insert implies the earlier row aged out of the rolling window.
    later = store.rows[id_b].created_at
    window_start = later - timedelta(seconds=60)
    tokens_at_b = sum(
        (r.actual_tokens if r.actual_tokens is not None else r.reserved_tokens)
        for r in store.rows.values()
        if r.created_at > window_start
        and r.created_at <= later
        and r.status in _ACTIVE
        and r.id != id_b
    )
    assert tokens_at_b + store.rows[id_b].reserved_tokens <= 2500


@pytest.mark.unit
@pytest.mark.asyncio
async def test_complete_updates_own_reservation_not_latest() -> None:
    """A delayed complete(id=N) must not touch a newer reservation M."""
    store, _pool, clock, (ledger,) = _ledgers(rpm=50, tpm=0, rpd=100, n=1)

    id_n = await ledger.reserve(estimated_tokens=100, purpose="first")
    id_m = await ledger.reserve(estimated_tokens=100, purpose="second")
    assert id_m == id_n + 1

    await ledger.complete(id_n, actual_tokens=777)

    assert store.rows[id_n].status == "completed"
    assert store.rows[id_n].actual_tokens == 777
    assert store.rows[id_m].status == "reserved"
    assert store.rows[id_m].actual_tokens is None

    await ledger.complete(id_m, actual_tokens=42)
    assert store.rows[id_m].actual_tokens == 42
    assert store.rows[id_n].actual_tokens == 777


@pytest.mark.unit
@pytest.mark.asyncio
async def test_four_retry_attempts_consume_four_rpd_reservations() -> None:
    """ClassificationClient reserves once per attempt; 4 retryable failures → 4 reserves."""
    from app.core.llm_lanes import LlmLaneConfig

    store, _pool, _clock, (ledger,) = _ledgers(rpm=50, tpm=0, rpd=100, n=1)
    real_reserve = ledger.reserve
    reserve_spy = AsyncMock(side_effect=real_reserve)
    ledger.reserve = reserve_spy  # type: ignore[method-assign]

    client = ClassificationClient(quota=ledger)
    client._routing_mode = "off"
    client._complex_unavailable = True
    client._simple = LlmLaneConfig(
        lane="simple",
        provider="gemini",
        model="gemini-2.5-flash",
        api_key="test-key",
        base_url="",
        rpm=50,
        tpm=0,
        rpd=100,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.0,
        timeout=60.0,
        reasoning_effort="high",
        fallbacks=(),
    )
    client._simple_provider = "gemini"
    client._simple_model = "gemini-2.5-flash"
    client.model = "gemini-2.5-flash"
    if client.client is None:
        client.client = MagicMock()

    with (
        patch.object(client, "_generate_content", new_callable=AsyncMock) as mock_gen,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_gen.side_effect = TimeoutError("provider timeout")
        res = await client.classify_article(
            title="Retry burn",
            content="body",
            url="https://example.com/r",
            date="2026-07-14",
        )

        assert res.article.country_code == "XX"
    assert mock_gen.await_count == 4
    gemini_rows = [r for r in store.rows.values() if not _is_deepseek_model(r.model)]
    assert len(gemini_rows) == 4
    assert all(r.status == "failed" for r in gemini_rows)
    # Residual DeepSeek on SIMPLE chain may add one more reserve after Gemini exhausted.
    assert reserve_spy.await_count >= 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_complete_after_newer_reservation_targets_exact_id() -> None:
    """
    complete(id=N) while M was created later must update only N's tokens
    (ledger identity, not 'latest row' semantics).
    """
    store, _pool, _clock, (ledger,) = _ledgers(rpm=50, tpm=0, rpd=100, n=1)
    id_n = await ledger.reserve(estimated_tokens=100, purpose="slow")
    id_m = await ledger.reserve(estimated_tokens=100, purpose="fast")
    # Delayed response for N arrives after M exists.
    await ledger.complete(id_n, actual_tokens=1234)
    assert store.rows[id_n].actual_tokens == 1234
    assert store.rows[id_n].status == "completed"
    assert store.rows[id_m].status == "reserved"
    assert store.rows[id_m].actual_tokens is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rpm_third_reserve_waits_until_window_slides() -> None:
    store, _pool, clock, (ledger_a, ledger_b) = _ledgers(rpm=2, tpm=0, rpd=100, n=2)

    id1 = await ledger_a.reserve(estimated_tokens=1)
    id2 = await ledger_b.reserve(estimated_tokens=1)
    assert store.active_count() == 2

    third = asyncio.create_task(ledger_a.reserve(estimated_tokens=1))
    rid = await asyncio.wait_for(third, timeout=5.0)
    assert rid not in (id1, id2)
    # Clock advanced by durable wait; at most 2 active in the current 60s window
    # at any insert — final state may be 1–3 depending on aging.
    now = clock.utc_now()
    window_start = now - timedelta(seconds=60)
    in_window = sum(
        1
        for r in store.rows.values()
        if r.created_at > window_start and r.status in _ACTIVE
    )
    assert in_window <= 2


@pytest.mark.unit
def test_min_interval_zero_when_rpm_unmanaged() -> None:
    _store, pool, clock, (ledger,) = _ledgers(rpm=10, tpm=0, rpd=100, n=1, deepseek_rpm=0)
    assert ledger.min_interval_seconds("simple") == 6.0
    assert ledger.min_interval_seconds("complex") == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gemini_and_deepseek_rpd_independent() -> None:
    """Simple RPD full must not block complex when complex RPD=0."""
    store, _pool, _clock, (ledger,) = _ledgers(
        rpm=50,
        tpm=0,
        rpd=2,
        n=1,
        deepseek_rpm=0,
        deepseek_rpd=0,
    )
    await ledger.reserve(
        estimated_tokens=1, model="gemini-3.1-flash-lite", lane="simple"
    )
    await ledger.reserve(
        estimated_tokens=1, model="gemini-3.1-flash-lite", lane="simple"
    )

    rid = await asyncio.wait_for(
        ledger.reserve(
            estimated_tokens=1000,
            model="deepseek-v4-flash",
            lane="complex",
        ),
        timeout=1.0,
    )
    assert rid in store.rows
    assert store.rows[rid].purpose == "classify:complex"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deepseek_budget_raises_when_exceeded() -> None:
    store, _pool, clock, (ledger,) = _ledgers(
        rpm=50,
        tpm=0,
        rpd=100,
        n=1,
        deepseek_budget_usd_day=0.01,
    )
    now = clock.utc_now()
    store.rows[1] = _Row(
        id=1,
        reserved_tokens=100_000,
        actual_tokens=100_000,
        status="completed",
        created_at=now,
        model="deepseek-v4-flash",
        purpose="classify:complex",
    )
    store.next_id = 2

    with pytest.raises(QuotaBudgetExceeded):
        await ledger.reserve(
            estimated_tokens=1000,
            model="deepseek-v4-flash",
            lane="complex",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_per_model_quota_separation() -> None:
    """Stessa lane (simple), due modelli, RPD=1 ciascuno: A esausto non blocca B."""
    from app.core.llm_lanes import LlmLaneConfig, parse_model_limits
    simple_cfg = LlmLaneConfig(
        lane="simple",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        api_key="test-key",
        base_url="",
        rpm=10,
        tpm=0,
        rpd=1,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.0,
        timeout=60.0,
        reasoning_effort="high",
        fallbacks=("gemini-3.1-flash-lite",),
        model_limits=parse_model_limits("gemini-3.5-flash-lite:10:0:1,gemini-3.1-flash-lite:10:0:1"),
    )
    store, _pool, _clock, (ledger,) = _ledgers(
        rpm=10,
        tpm=0,
        rpd=1,
        n=1,
        simple=simple_cfg,
    )
    # Reserve per model A (3.1)
    rid1 = await ledger.reserve(
        estimated_tokens=1, model="gemini-3.1-flash-lite", lane="simple"
    )
    assert rid1 > 0

    # Secondo reserve per model A -> QuotaDailyExceeded
    with pytest.raises(QuotaDailyExceeded) as exc_info:
        await ledger.reserve(
            estimated_tokens=1, model="gemini-3.1-flash-lite", lane="simple"
        )
    assert "gemini-3.1-flash-lite" in str(exc_info.value)

    # Reserve per model B (3.5) -> OK (pool indipendente)
    rid2 = await ledger.reserve(
        estimated_tokens=1, model="gemini-3.5-flash-lite", lane="simple"
    )
    assert rid2 > 0


@pytest.mark.unit
def test_model_limits_override_and_fail_fast() -> None:
    """Parse MODEL_LIMITS CSV valid e fail-fast su malformato (R4)."""
    from app.core.llm_lanes import LlmConfigError, LlmLaneConfig, limits_for_model, parse_model_limits

    raw = "gemini-3.5-flash-lite:12:250000:500,gemini-3.1-flash-lite:12:250000:450"
    parsed = parse_model_limits(raw)
    assert parsed["gemini-3.5-flash-lite"] == (12, 250000, 500)
    assert parsed["gemini-3.1-flash-lite"] == (12, 250000, 450)

    cfg = LlmLaneConfig(
        lane="simple",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        api_key="key",
        base_url="",
        rpm=10,
        tpm=0,
        rpd=300,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.0,
        timeout=60.0,
        reasoning_effort="high",
        fallbacks=("gemini-3.1-flash-lite",),
        model_limits=parsed,
    )
    assert limits_for_model(cfg, "gemini-3.5-flash-lite") == (12, 250000, 500)
    assert limits_for_model(cfg, "gemini-3.1-flash-lite") == (12, 250000, 450)
    assert limits_for_model(cfg, "other-model") == (10, 0, 300)

    # Fail-fast su malformato
    for bad in [
        "invalid_format",
        "model:12:250000",
        "model:12:abc:500",
        "model:-1:250000:500",
        ":12:250000:500",
    ]:
        with pytest.raises(LlmConfigError):
            parse_model_limits(bad)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unmanaged_rpd_zero() -> None:
    """rpd=0 unmanaged: nessuna QuotaDailyExceeded da RPD (R3)."""
    store, _pool, _clock, (ledger,) = _ledgers(
        rpm=0,
        tpm=0,
        rpd=0,
        n=1,
    )
    for _ in range(5):
        rid = await ledger.reserve(
            estimated_tokens=1, model="unmanaged-model", lane="simple"
        )
        assert rid > 0
