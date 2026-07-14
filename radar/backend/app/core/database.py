import logging

import asyncpg

from app.core.config import DATABASE_URL
from app.core.migrations import run_migrations

logger = logging.getLogger("radar.database")


async def init_pool(db_url: str | None = None) -> asyncpg.Pool:
    """
    Inizializza e restituisce direttamente il pool di connessioni asyncpg.
    Questo disaccoppiamento facilita l'integrazione nel Lifespan di FastAPI.
    """
    url = db_url or DATABASE_URL
    logger.info("Inizializzazione del pool database PostgreSQL...")
    try:
        pool = await asyncpg.create_pool(
            url,
            min_size=2,
            max_size=10,
            command_timeout=60.0,
        )
        if pool is None:
            raise RuntimeError("Impossibile creare il pool asyncpg (restituito None)")
        logger.info("Pool database inizializzato con successo.")
        return pool
    except Exception as e:
        logger.error("Errore critico durante l'inizializzazione del pool DB: %s", e)
        raise


async def bootstrap_database(pool: asyncpg.Pool) -> None:
    """
    Allinea lo schema PostgreSQL eseguendo le migrazioni ordinate con verifica checksum.
    Sostituisce il precedente bootstrap ad-hoc CREATE TABLE IF NOT EXISTS.
    """
    logger.info("Bootstrap database: avvio run_migrations...")
    await run_migrations(pool)
    logger.info("Bootstrap database completato con successo.")
