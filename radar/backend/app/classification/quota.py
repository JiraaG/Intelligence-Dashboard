"""Durable RPM/TPM/RPD quota ledger backed by llm_request_ledger (asyncpg)."""

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
    LLM_RPD,
    LLM_RPM,
    LLM_TPM,
    RADAR_TIME_ZONE,
    RADAR_TIME_ZONE_NAME,
)

logger = logging.getLogger("radar.classification.quota")

# Session-agnostic xact lock: serializes reserve across worker processes.
QUOTA_ADVISORY_LOCK_KEY = 883_421_017

# Rows that still consume quota capacity (released does not).
_ACTIVE_STATUSES = ("reserved", "completed", "failed")

SleepFn = Callable[[float], Awaitable[None]]
MonotonicFn = Callable[[], float]
UtcNowFn = Callable[[], datetime]


def compute_day_window(
    now_utc: datetime,
    tz: ZoneInfo | timezone,
) -> tuple[datetime, datetime]:
    """
    Half-open local-day window [day_start, next_day) expressed in UTC.

    Never use date(created_at) = CURRENT_DATE — day boundaries follow RADAR_TIME_ZONE.
    """
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


@dataclass(frozen=True, slots=True)
class _ReserveOutcome:
    reservation_id: int | None
    wait_seconds: float


class QuotaLedger:
    """
    Transactional quota reservations for LLM provider attempts.

    - RPM: count of active rows in the last 60 seconds
    - TPM: sum of COALESCE(actual_tokens, reserved_tokens) in the last 60s (if TPM > 0)
    - RPD: count of active rows in the RADAR_TIME_ZONE half-open day window

    In-process spacing uses time.monotonic(); durable windows use UTC timestamps.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        rpm: int = LLM_RPM,
        tpm: int = LLM_TPM,
        rpd: int = LLM_RPD,
        time_zone: ZoneInfo | timezone = RADAR_TIME_ZONE,
        time_zone_name: str = RADAR_TIME_ZONE_NAME,
        sleep: SleepFn | None = None,
        monotonic: MonotonicFn | None = None,
        utc_now: UtcNowFn | None = None,
        advisory_lock_key: int = QUOTA_ADVISORY_LOCK_KEY,
        default_estimated_tokens: int = ESTIMATED_TOKENS_PER_REQUEST,
    ) -> None:
        if rpm < 1:
            raise ValueError(f"rpm must be >= 1 (got {rpm})")
        if tpm < 0:
            raise ValueError(f"tpm must be >= 0 (got {tpm})")
        if rpd < 1:
            raise ValueError(f"rpd must be >= 1 (got {rpd})")

        self._pool = pool
        self._rpm = rpm
        self._tpm = tpm
        self._rpd = rpd
        self._tz = time_zone
        self._tz_name = time_zone_name
        self._sleep: SleepFn = sleep or asyncio.sleep
        self._monotonic: MonotonicFn = monotonic or time.monotonic
        self._utc_now: UtcNowFn = utc_now or (lambda: datetime.now(timezone.utc))
        self._advisory_lock_key = advisory_lock_key
        self._default_estimated_tokens = default_estimated_tokens

        self._spacing_lock = asyncio.Lock()
        self._last_reserve_mono: float = 0.0

        logger.info(
            "QuotaLedger pronto (RPM=%s TPM=%s RPD=%s tz=%s)",
            rpm,
            tpm,
            rpd,
            time_zone_name,
        )

    @property
    def min_interval_seconds(self) -> float:
        """In-process RPM spacing interval derived from configured RPM."""
        return 60.0 / float(self._rpm)

    async def reserve(
        self,
        *,
        estimated_tokens: int | None = None,
        model: str | None = None,
        purpose: str | None = None,
    ) -> int:
        """
        Reserve RPM/TPM/RPD capacity. Blocks (sleep + re-check) until a row can be inserted.
        Returns the ledger reservation id for a later complete/release/fail on that exact row.
        """
        tokens = (
            self._default_estimated_tokens
            if estimated_tokens is None
            else max(0, int(estimated_tokens))
        )

        while True:
            local_wait = await self._in_process_spacing_wait()
            if local_wait > 0:
                logger.debug("Quota spacing in-process: attesa %.3fs", local_wait)
                await self._sleep(local_wait)
                continue

            outcome = await self._try_reserve_once(
                estimated_tokens=tokens,
                model=model,
                purpose=purpose,
            )
            if outcome.reservation_id is not None:
                async with self._spacing_lock:
                    self._last_reserve_mono = self._monotonic()
                return outcome.reservation_id

            wait = max(0.05, outcome.wait_seconds)
            logger.info(
                "Quota window piena (RPM/TPM/RPD). Attesa %.2fs poi re-check (tz=%s)",
                wait,
                self._tz_name,
            )
            await self._sleep(wait)

    async def complete(self, reservation_id: int, actual_tokens: int) -> None:
        """Mark the exact reservation completed and store measured token usage."""
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
        """Release capacity when the provider was never invoked (does not consume RPD/RPM)."""
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
        """Mark a reservation failed after the provider attempt started (still counts for RPM/RPD)."""
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

    async def _in_process_spacing_wait(self) -> float:
        async with self._spacing_lock:
            now = self._monotonic()
            if self._last_reserve_mono <= 0.0:
                return 0.0
            elapsed = now - self._last_reserve_mono
            remaining = self.min_interval_seconds - elapsed
            return remaining if remaining > 0.0 else 0.0

    async def _try_reserve_once(
        self,
        *,
        estimated_tokens: int,
        model: str | None,
        purpose: str | None,
    ) -> _ReserveOutcome:
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

                rpm_count = await conn.fetchval(
                    """
                    SELECT COUNT(*)::INT
                    FROM llm_request_ledger
                    WHERE created_at > $1
                      AND status = ANY($2::text[])
                    """,
                    window_start,
                    list(_ACTIVE_STATUSES),
                )
                if rpm_count is None:
                    rpm_count = 0
                if int(rpm_count) >= self._rpm:
                    oldest = await conn.fetchval(
                        """
                        SELECT MIN(created_at)
                        FROM llm_request_ledger
                        WHERE created_at > $1
                          AND status = ANY($2::text[])
                        """,
                        window_start,
                        list(_ACTIVE_STATUSES),
                    )
                    wait = 0.5
                    if oldest is not None:
                        wait = max(
                            0.05,
                            (oldest + timedelta(seconds=60) - now).total_seconds(),
                        )
                    return _ReserveOutcome(reservation_id=None, wait_seconds=wait)

                if self._tpm > 0:
                    token_sum = await conn.fetchval(
                        """
                        SELECT COALESCE(
                            SUM(COALESCE(actual_tokens, reserved_tokens)),
                            0
                        )::BIGINT
                        FROM llm_request_ledger
                        WHERE created_at > $1
                          AND status = ANY($2::text[])
                        """,
                        window_start,
                        list(_ACTIVE_STATUSES),
                    )
                    if token_sum is None:
                        token_sum = 0
                    if int(token_sum) + estimated_tokens > self._tpm:
                        oldest = await conn.fetchval(
                            """
                            SELECT MIN(created_at)
                            FROM llm_request_ledger
                            WHERE created_at > $1
                              AND status = ANY($2::text[])
                            """,
                            window_start,
                            list(_ACTIVE_STATUSES),
                        )
                        wait = 0.5
                        if oldest is not None:
                            wait = max(
                                0.05,
                                (oldest + timedelta(seconds=60) - now).total_seconds(),
                            )
                        return _ReserveOutcome(reservation_id=None, wait_seconds=wait)

                rpd_count = await conn.fetchval(
                    """
                    SELECT COUNT(*)::INT
                    FROM llm_request_ledger
                    WHERE created_at >= $1
                      AND created_at < $2
                      AND status = ANY($3::text[])
                    """,
                    day_start,
                    day_end,
                    list(_ACTIVE_STATUSES),
                )
                if rpd_count is None:
                    rpd_count = 0
                if int(rpd_count) >= self._rpd:
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
