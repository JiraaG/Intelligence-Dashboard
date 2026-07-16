"""Durable RPM/TPM/RPD quota ledger backed by llm_request_ledger (asyncpg).

Limits are **per classification lane** (simple / complex), from LlmLaneConfig:
- LLM_SIMPLE_RPM / TPM / RPD
- LLM_COMPLEX_RPM / TPM / RPD

Semantics: ``0`` on a dimension = unmanaged (no wait / no day hibernation for that
dimension on that lane). Budget USD soft-cap when ``budget_usd_day > 0``.
Reservations are tagged ``purpose=classify:{lane}`` so SIMPLE and COMPLEX never
share the same RPM/TPM/RPD counters.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

import asyncpg

from app.core.config import (
    ESTIMATED_TOKENS_PER_REQUEST,
    LLM_COMPLEX,
    LLM_SIMPLE,
    RADAR_TIME_ZONE,
    RADAR_TIME_ZONE_NAME,
)
from app.core.llm_lanes import LANE_COMPLEX, LANE_SIMPLE, LlmLaneConfig

logger = logging.getLogger("radar.classification.quota")

QUOTA_ADVISORY_LOCK_KEY = 883_421_017
_ACTIVE_STATUSES = ("reserved", "completed", "failed")

SleepFn = Callable[[float], Awaitable[None]]
MonotonicFn = Callable[[], float]
UtcNowFn = Callable[[], datetime]


class QuotaBudgetExceeded(Exception):
    """Lane daily USD soft-cap reached — caller should skip this provider."""


def compute_day_window(
    now_utc: datetime,
    tz: ZoneInfo | timezone,
) -> tuple[datetime, datetime]:
    """Half-open local-day window [day_start, next_day) expressed in UTC."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    local = now_utc.astimezone(tz)
    day_start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day_local = day_start_local + timedelta(days=1)
    return (
        day_start_local.astimezone(timezone.utc),
        next_day_local.astimezone(timezone.utc),
    )


def _normalize_lane(lane: str | None) -> str:
    value = (lane or LANE_SIMPLE).strip().lower()
    return value if value in {LANE_SIMPLE, LANE_COMPLEX} else LANE_SIMPLE


def purpose_for_lane(lane: str) -> str:
    return f"classify:{_normalize_lane(lane)}"


def estimate_usd(tokens: int, usd_per_1m: float) -> float:
    if tokens <= 0 or usd_per_1m <= 0:
        return 0.0
    return (float(tokens) / 1_000_000.0) * float(usd_per_1m)


@dataclass(frozen=True, slots=True)
class _ReserveOutcome:
    reservation_id: int | None
    wait_seconds: float


@dataclass(frozen=True, slots=True)
class _LaneLimits:
    rpm: int
    tpm: int
    rpd: int
    budget_usd_day: float
    usd_per_1m_tokens: float


def _limits_from_cfg(cfg: LlmLaneConfig) -> _LaneLimits:
    return _LaneLimits(
        rpm=cfg.rpm,
        tpm=cfg.tpm,
        rpd=cfg.rpd,
        budget_usd_day=float(cfg.budget_usd_day),
        usd_per_1m_tokens=float(cfg.usd_per_1m_tokens),
    )


class QuotaLedger:
    """Transactional quota reservations keyed by classification lane."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        simple: LlmLaneConfig | None = None,
        complex_lane: LlmLaneConfig | None = None,
        rpm: int | None = None,
        tpm: int | None = None,
        rpd: int | None = None,
        deepseek_rpm: int | None = None,
        deepseek_tpm: int | None = None,
        deepseek_rpd: int | None = None,
        deepseek_budget_usd_day: float | None = None,
        time_zone: ZoneInfo | timezone = RADAR_TIME_ZONE,
        time_zone_name: str = RADAR_TIME_ZONE_NAME,
        sleep: SleepFn | None = None,
        monotonic: MonotonicFn | None = None,
        utc_now: UtcNowFn | None = None,
        advisory_lock_key: int = QUOTA_ADVISORY_LOCK_KEY,
        default_estimated_tokens: int = ESTIMATED_TOKENS_PER_REQUEST,
    ) -> None:
        simple_cfg = simple or LLM_SIMPLE
        complex_cfg = complex_lane or LLM_COMPLEX

        simple_limits = _limits_from_cfg(simple_cfg)
        complex_limits = _limits_from_cfg(complex_cfg)

        if rpm is not None or tpm is not None or rpd is not None:
            simple_limits = _LaneLimits(
                rpm=rpm if rpm is not None else simple_limits.rpm,
                tpm=tpm if tpm is not None else simple_limits.tpm,
                rpd=rpd if rpd is not None else simple_limits.rpd,
                budget_usd_day=simple_limits.budget_usd_day,
                usd_per_1m_tokens=simple_limits.usd_per_1m_tokens,
            )
        if (
            deepseek_rpm is not None
            or deepseek_tpm is not None
            or deepseek_rpd is not None
            or deepseek_budget_usd_day is not None
        ):
            complex_limits = _LaneLimits(
                rpm=deepseek_rpm if deepseek_rpm is not None else complex_limits.rpm,
                tpm=deepseek_tpm if deepseek_tpm is not None else complex_limits.tpm,
                rpd=deepseek_rpd if deepseek_rpd is not None else complex_limits.rpd,
                budget_usd_day=(
                    float(deepseek_budget_usd_day)
                    if deepseek_budget_usd_day is not None
                    else complex_limits.budget_usd_day
                ),
                usd_per_1m_tokens=complex_limits.usd_per_1m_tokens,
            )

        for name, value in (
            ("simple.rpm", simple_limits.rpm),
            ("simple.tpm", simple_limits.tpm),
            ("simple.rpd", simple_limits.rpd),
            ("complex.rpm", complex_limits.rpm),
            ("complex.tpm", complex_limits.tpm),
            ("complex.rpd", complex_limits.rpd),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0 (got {value})")
        if simple_limits.budget_usd_day < 0 or complex_limits.budget_usd_day < 0:
            raise ValueError("budget_usd_day must be >= 0")

        self._pool = pool
        self._limits = {
            LANE_SIMPLE: simple_limits,
            LANE_COMPLEX: complex_limits,
        }
        self._tz = time_zone
        self._tz_name = time_zone_name
        self._sleep: SleepFn = sleep or asyncio.sleep
        self._monotonic: MonotonicFn = monotonic or time.monotonic
        self._utc_now: UtcNowFn = utc_now or (lambda: datetime.now(timezone.utc))
        self._advisory_lock_key = advisory_lock_key
        self._default_estimated_tokens = default_estimated_tokens

        self._spacing_lock = asyncio.Lock()
        self._last_reserve_mono: dict[str, float] = {
            LANE_SIMPLE: 0.0,
            LANE_COMPLEX: 0.0,
        }

        s = self._limits[LANE_SIMPLE]
        c = self._limits[LANE_COMPLEX]
        logger.info(
            "QuotaLedger pronto simple(RPM=%s TPM=%s RPD=%s budget=%s) "
            "complex(RPM=%s TPM=%s RPD=%s budget=%s) tz=%s",
            s.rpm,
            s.tpm,
            s.rpd,
            s.budget_usd_day,
            c.rpm,
            c.tpm,
            c.rpd,
            c.budget_usd_day,
            time_zone_name,
        )

    def min_interval_seconds(self, lane: str = LANE_SIMPLE) -> float:
        rpm = self._limits[_normalize_lane(lane)].rpm
        if rpm <= 0:
            return 0.0
        return 60.0 / float(rpm)

    async def reserve(
        self,
        *,
        estimated_tokens: int | None = None,
        model: str | None = None,
        purpose: str | None = None,
        provider: str | None = None,
        lane: str | None = None,
    ) -> int:
        if lane is not None:
            quota_lane = _normalize_lane(lane)
        elif provider is not None:
            prov = (provider or "").strip().lower()
            quota_lane = (
                LANE_COMPLEX if prov in {"deepseek", "openai", "claude"} else LANE_SIMPLE
            )
        else:
            quota_lane = LANE_SIMPLE

        tokens = (
            self._default_estimated_tokens
            if estimated_tokens is None
            else max(0, int(estimated_tokens))
        )
        purpose_value = purpose_for_lane(quota_lane)

        while True:
            local_wait = await self._in_process_spacing_wait(quota_lane)
            if local_wait > 0:
                await self._sleep(local_wait)
                continue

            outcome = await self._try_reserve_once(
                estimated_tokens=tokens,
                model=model,
                purpose=purpose_value,
                lane=quota_lane,
            )
            if outcome.reservation_id is not None:
                async with self._spacing_lock:
                    self._last_reserve_mono[quota_lane] = self._monotonic()
                return outcome.reservation_id

            wait = max(0.05, outcome.wait_seconds)
            logger.info(
                "Quota window piena lane=%s (RPM/TPM/RPD). Attesa %.2fs (tz=%s)",
                quota_lane,
                wait,
                self._tz_name,
            )
            await self._sleep(wait)

    async def complete(self, reservation_id: int, actual_tokens: int) -> None:
        tokens = max(0, int(actual_tokens))
        result = await self._pool.execute(
            """
            UPDATE llm_request_ledger
            SET actual_tokens = $2,
                status = 'completed'
            WHERE id = $1
              AND status = 'reserved'
            """,
            reservation_id,
            tokens,
        )
        if result == "UPDATE 0":
            logger.warning(
                "complete: nessuna riga reserved per reservation_id=%s",
                reservation_id,
            )

    async def release(self, reservation_id: int) -> None:
        result = await self._pool.execute(
            """
            UPDATE llm_request_ledger
            SET status = 'released'
            WHERE id = $1
              AND status = 'reserved'
            """,
            reservation_id,
        )
        if result == "UPDATE 0":
            logger.warning(
                "release: nessuna riga reserved per reservation_id=%s",
                reservation_id,
            )

    async def fail(
        self,
        reservation_id: int,
        *,
        actual_tokens: int | None = None,
    ) -> None:
        tokens = None if actual_tokens is None else max(0, int(actual_tokens))
        result = await self._pool.execute(
            """
            UPDATE llm_request_ledger
            SET status = 'failed',
                actual_tokens = COALESCE($2, actual_tokens)
            WHERE id = $1
              AND status = 'reserved'
            """,
            reservation_id,
            tokens,
        )
        if result == "UPDATE 0":
            logger.warning(
                "fail: nessuna riga reserved per reservation_id=%s",
                reservation_id,
            )

    async def _in_process_spacing_wait(self, lane: str) -> float:
        interval = self.min_interval_seconds(lane)
        if interval <= 0.0:
            return 0.0
        async with self._spacing_lock:
            now = self._monotonic()
            last = self._last_reserve_mono.get(lane, 0.0)
            if last <= 0.0:
                return 0.0
            elapsed = now - last
            remaining = interval - elapsed
            return remaining if remaining > 0.0 else 0.0

    async def _try_reserve_once(
        self,
        *,
        estimated_tokens: int,
        model: str | None,
        purpose: str,
        lane: str,
    ) -> _ReserveOutcome:
        limits = self._limits[lane]
        purpose_exact = purpose_for_lane(lane)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock($1)",
                    self._advisory_lock_key,
                )

                now = self._utc_now()
                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
                else:
                    now = now.astimezone(timezone.utc)

                window_start = now - timedelta(seconds=60)
                day_start, day_end = compute_day_window(now, self._tz)

                if limits.budget_usd_day > 0:
                    spent = await self._lane_spend_usd(
                        conn,
                        lane=lane,
                        day_start=day_start,
                        day_end=day_end,
                        usd_per_1m=limits.usd_per_1m_tokens,
                    )
                    projected = spent + estimate_usd(
                        estimated_tokens, limits.usd_per_1m_tokens
                    )
                    if projected > limits.budget_usd_day:
                        raise QuotaBudgetExceeded(
                            f"lane={lane} budget ${limits.budget_usd_day:.2f}/day exceeded "
                            f"(spent~=${spent:.4f})"
                        )

                if limits.rpm > 0:
                    rpm_count = await conn.fetchval(
                        """
                        SELECT COUNT(*)::INT
                        FROM llm_request_ledger
                        WHERE created_at > $1
                          AND status = ANY($2::text[])
                          AND purpose = $3
                        """,
                        window_start,
                        list(_ACTIVE_STATUSES),
                        purpose_exact,
                    )
                    if int(rpm_count or 0) >= limits.rpm:
                        oldest = await conn.fetchval(
                            """
                            SELECT MIN(created_at)
                            FROM llm_request_ledger
                            WHERE created_at > $1
                              AND status = ANY($2::text[])
                              AND purpose = $3
                            """,
                            window_start,
                            list(_ACTIVE_STATUSES),
                            purpose_exact,
                        )
                        wait = 0.5
                        if oldest is not None:
                            wait = max(
                                0.05,
                                (oldest + timedelta(seconds=60) - now).total_seconds(),
                            )
                        return _ReserveOutcome(reservation_id=None, wait_seconds=wait)

                if limits.tpm > 0:
                    token_sum = await conn.fetchval(
                        """
                        SELECT COALESCE(
                            SUM(COALESCE(actual_tokens, reserved_tokens)),
                            0
                        )::BIGINT
                        FROM llm_request_ledger
                        WHERE created_at > $1
                          AND status = ANY($2::text[])
                          AND purpose = $3
                        """,
                        window_start,
                        list(_ACTIVE_STATUSES),
                        purpose_exact,
                    )
                    if int(token_sum or 0) + estimated_tokens > limits.tpm:
                        oldest = await conn.fetchval(
                            """
                            SELECT MIN(created_at)
                            FROM llm_request_ledger
                            WHERE created_at > $1
                              AND status = ANY($2::text[])
                              AND purpose = $3
                            """,
                            window_start,
                            list(_ACTIVE_STATUSES),
                            purpose_exact,
                        )
                        wait = 0.5
                        if oldest is not None:
                            wait = max(
                                0.05,
                                (oldest + timedelta(seconds=60) - now).total_seconds(),
                            )
                        return _ReserveOutcome(reservation_id=None, wait_seconds=wait)

                if limits.rpd > 0:
                    rpd_count = await conn.fetchval(
                        """
                        SELECT COUNT(*)::INT
                        FROM llm_request_ledger
                        WHERE created_at >= $1
                          AND created_at < $2
                          AND status = ANY($3::text[])
                          AND purpose = $4
                        """,
                        day_start,
                        day_end,
                        list(_ACTIVE_STATUSES),
                        purpose_exact,
                    )
                    if int(rpd_count or 0) >= limits.rpd:
                        wait = max(0.05, (day_end - now).total_seconds())
                        return _ReserveOutcome(reservation_id=None, wait_seconds=wait)

                reservation_id = await conn.fetchval(
                    """
                    INSERT INTO llm_request_ledger (
                        reserved_tokens,
                        status,
                        model,
                        purpose
                    )
                    VALUES ($1, 'reserved', $2, $3)
                    RETURNING id
                    """,
                    estimated_tokens,
                    model,
                    purpose,
                )
                if reservation_id is None:
                    raise RuntimeError("INSERT llm_request_ledger non ha restituito id")
                return _ReserveOutcome(
                    reservation_id=int(reservation_id),
                    wait_seconds=0.0,
                )

    async def _lane_spend_usd(
        self,
        conn: asyncpg.Connection,
        *,
        lane: str,
        day_start: datetime,
        day_end: datetime,
        usd_per_1m: float,
    ) -> float:
        purpose_exact = purpose_for_lane(lane)
        tokens = await conn.fetchval(
            """
            SELECT COALESCE(SUM(COALESCE(actual_tokens, reserved_tokens)), 0)::BIGINT
            FROM llm_request_ledger
            WHERE created_at >= $1
              AND created_at < $2
              AND status = ANY($3::text[])
              AND purpose = $4
            """,
            day_start,
            day_end,
            list(_ACTIVE_STATUSES),
            purpose_exact,
        )
        return estimate_usd(int(tokens or 0), usd_per_1m)
