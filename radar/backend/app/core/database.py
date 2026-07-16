import asyncio
import logging

import asyncpg

from app.core.config import DATABASE_URL
from app.core.migrations import run_migrations

logger = logging.getLogger("radar.database")

# Parallel `docker compose restart` ignores depends_on health ordering; Postgres can
# still be in "starting up" when backend/worker call create_pool. Retry transient races.
_POOL_STARTUP_ATTEMPTS = 10
_POOL_STARTUP_BASE_DELAY_S = 0.5


def _is_transient_db_startup_error(exc: BaseException) -> bool:
    if isinstance(exc, asyncpg.CannotConnectNowError):
        return True
    if isinstance(exc, (ConnectionRefusedError, ConnectionResetError, TimeoutError)):
        return True
    # asyncpg sometimes wraps OS-level refusals during container boot.
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in {111, 61, 10061}:
        return True
    msg = str(exc).lower()
    return "the database system is starting up" in msg or "connection refused" in msg


async def init_pool(db_url: str | None = None) -> asyncpg.Pool:
    """
    Inizializza e restituisce direttamente il pool di connessioni asyncpg.
    Questo disaccoppiamento facilita l'integrazione nel Lifespan di FastAPI.

    Retries briefly on transient Postgres startup races (compose restart of all
    services in parallel). Non-transient errors fail immediately.
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
                command_timeout=60.0,
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
    Allinea lo schema PostgreSQL eseguendo le migrazioni ordinate con verifica checksum.
    Sostituisce il precedente bootstrap ad-hoc CREATE TABLE IF NOT EXISTS.
    """
    logger.info("Bootstrap database: avvio run_migrations...")
    await run_migrations(pool)
    logger.info("Bootstrap database completato con successo.")
