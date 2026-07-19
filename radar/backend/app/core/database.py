"""
Bootstrap pool asyncpg e handoff alle migrazioni ordinate.

``init_pool``: retry su race di avvio Postgres (compose restart parallelo ignora
depends_on health). ``bootstrap_database``: delegano a ``run_migrations`` —
niente CREATE TABLE ad-hoc.

@see docs/01 startup; docs/02 persistence; backend rule asyncpg.
"""

import asyncio
import logging

import asyncpg

from app.core.config import DATABASE_URL
from app.core.migrations import run_migrations

logger = logging.getLogger("radar.database")

# Compose restart parallelo ignora l'ordine health di depends_on; Postgres può
# essere ancora in "starting up" quando backend/worker chiamano create_pool.
_POOL_STARTUP_ATTEMPTS = 10
_POOL_STARTUP_BASE_DELAY_S = 0.5


def _is_transient_db_startup_error(exc: BaseException) -> bool:
    """True se l'errore è tipico di DB non ancora pronto (retry); altrimenti fail-fast."""
    if isinstance(exc, asyncpg.CannotConnectNowError):
        return True
    if isinstance(exc, (ConnectionRefusedError, ConnectionResetError, TimeoutError)):
        return True
    # asyncpg a volte wrappa refusal OS durante il boot del container.
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {111, 61, 10061}:
        return True
    msg = str(exc).lower()
    return "the database system is starting up" in msg or "connection refused" in msg


async def init_pool(db_url: str | None = None) -> asyncpg.Pool:
    """
    Crea e restituisce il pool asyncpg (Lifespan FastAPI / worker).

    Retry brevi su race di startup Postgres; errori non transienti falliscono subito.
    ``min_size=2`` / ``max_size=10``; ``command_timeout=300`` (LLM locale tiene
    connessioni/lock per minuti; 60s causava TimeoutError su advisory_lock).
    """
    url = db_url or DATABASE_URL
    logger.info("Inizializzazione del pool database PostgreSQL...")
    last_err: BaseException | None = None

    for attempt in range(1, _POOL_STARTUP_ATTEMPTS + 1):
        try:
            pool = await asyncpg.create_pool(
                url,
                min_size=2,
                max_size=10,
                command_timeout=300.0,
            )
            if pool is None:
                raise RuntimeError("Impossibile creare il pool asyncpg (restituito None)")
            if attempt > 1:
                logger.info(
                    "Pool database inizializzato con successo dopo %s tentativi.",
                    attempt,
                )
            else:
                logger.info("Pool database inizializzato con successo.")
            return pool
        except Exception as e:
            last_err = e
            if attempt >= _POOL_STARTUP_ATTEMPTS or not _is_transient_db_startup_error(e):
                logger.error("Errore critico durante l'inizializzazione del pool DB: %s", e)
                raise
            delay = min(_POOL_STARTUP_BASE_DELAY_S * attempt, 3.0)
            logger.warning(
                "DB non pronto (tentativo %s/%s): %s — retry tra %.1fs",
                attempt,
                _POOL_STARTUP_ATTEMPTS,
                e,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_err is not None
    raise last_err


async def bootstrap_database(pool: asyncpg.Pool) -> None:
    """
    Allinea lo schema eseguendo le migrazioni ordinate con verifica checksum.
    Sostituisce il vecchio bootstrap ad-hoc ``CREATE TABLE IF NOT EXISTS``.
    """
    logger.info("Bootstrap database: avvio run_migrations...")
    await run_migrations(pool)
    logger.info("Bootstrap database completato con successo.")
