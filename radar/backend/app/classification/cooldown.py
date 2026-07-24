"""
Cooldown durable modelli LLM (hard-fail tipicamente 24h).

Persistenza: tabella ``llm_model_cooldown`` (migrazione 009).
Senza pool (unit test): mappa in-memory equivalente.
Chiamato dal classification client su HARD_COOLDOWN / residual — questo modulo
è solo storage (set / query / clear expired), non decide la policy di errore.

@see SoT LLM §4.7; radar-quota-ledger.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import asyncpg

logger = logging.getLogger("radar.classification.cooldown")


class ModelCooldownStore:
    """
    Salta modelli finché ``until_ts`` è nel futuro (UTC).

    Con ``pool``: SQL ``llm_model_cooldown`` (chiave provider+model).
    Senza pool (test): dict in memoria — stesso contratto async.
    ``clock`` iniettabile per test di expiry.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        default_hours: int = 24,
    ) -> None:
        self.pool = pool
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._default_hours = default_hours
        self._memory: dict[tuple[str, str], tuple[datetime, str | None]] = {}

    def _now(self) -> datetime:
        """Ora wall-clock in UTC aware (naive → assume UTC)."""
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    async def is_cooling_down(self, provider: str, model: str) -> bool:
        """True se esiste un ``until_ts`` strettamente successivo a ora."""
        until = await self.get_until(provider, model)
        if until is None:
            return False
        return until > self._now()

    async def get_until(self, provider: str, model: str) -> datetime | None:
        """
        Scadenza cooldown per (provider, model), o None se assente.
        Timestamp DB naive → tz UTC per confronti sicuri.
        """
        if self.pool is None:
            entry = self._memory.get((provider, model))
            return entry[0] if entry else None

        row = await self.pool.fetchrow(
            """
            SELECT until_ts
            FROM llm_model_cooldown
            WHERE provider = $1 AND model = $2
            """,
            provider,
            model,
        )
        if row is None:
            return None
        until = row["until_ts"]
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until

    async def set_cooldown(
        self,
        provider: str,
        model: str,
        *,
        reason: str | None = None,
        hours: int | None = None,
    ) -> datetime:
        """
        UPSERT cooldown: ``until = now + hours`` (default 24h SoT).
        Ritorna ``until_ts`` effettivo. Log WARNING (SQL o memory).
        """
        hrs = hours if hours is not None else self._default_hours
        until = self._now() + timedelta(hours=hrs)
        if self.pool is None:
            self._memory[(provider, model)] = (until, reason)
            logger.warning(
                "Cooldown in-memory %s/%s until %s (%s)",
                provider,
                model,
                until.isoformat(),
                reason,
            )
            return until

        await self.pool.execute(
            """
            INSERT INTO llm_model_cooldown (provider, model, until_ts, reason, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (provider, model) DO UPDATE
            SET until_ts = EXCLUDED.until_ts,
                reason = EXCLUDED.reason,
                updated_at = NOW()
            """,
            provider,
            model,
            until,
            reason,
        )
        logger.warning(
            "Cooldown SQL %s/%s until %s (%s)",
            provider,
            model,
            until.isoformat(),
            reason,
        )
        return until

    async def clear_expired(self) -> int:
        """
        Elimina entry con ``until_ts <= now``.
        Ritorna il numero di righe rimosse (best-effort su status string asyncpg).
        """
        now = self._now()
        if self.pool is None:
            before = len(self._memory)
            self._memory = {k: v for k, v in self._memory.items() if v[0] > now}
            return before - len(self._memory)

        result = await self.pool.execute(
            "DELETE FROM llm_model_cooldown WHERE until_ts <= $1",
            now,
        )
        # asyncpg restituisce status tipo "DELETE 3"
        try:
            return int(str(result).split()[-1])
        except (ValueError, IndexError):
            return 0

    async def list_active(self) -> list[dict[str, Any]]:
        """Restituisce le entry di cooldown correntemente attive."""
        now = self._now()
        if self.pool is None:
            active: list[dict[str, Any]] = []
            for (provider, model), (until, reason) in self._memory.items():
                if until > now:
                    active.append({
                        "provider": provider,
                        "model": model,
                        "until_ts": until,
                        "reason": reason,
                    })
            return active

        rows = await self.pool.fetch(
            """
            SELECT provider, model, until_ts, reason
            FROM llm_model_cooldown
            WHERE until_ts > $1
            ORDER BY until_ts DESC
            """,
            now,
        )
        result: list[dict[str, Any]] = []
        for r in rows:
            until = r["until_ts"]
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            result.append({
                "provider": r["provider"],
                "model": r["model"],
                "until_ts": until,
                "reason": r["reason"],
            })
        return result
