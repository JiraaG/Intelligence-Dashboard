import logging
import asyncpg
from app.core.config import DATABASE_URL

logger = logging.getLogger("radar.database")

async def init_pool(db_url: str = None) -> asyncpg.Pool:
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
            command_timeout=60.0
        )
        if pool is None:
            raise RuntimeError("Impossibile creare il pool asyncpg (restituito None)")
        logger.info("Pool database inizializzato con successo.")
        return pool
    except Exception as e:
        logger.error(f"Errore critico durante l'inizializzazione del pool DB: {e}")
        raise

async def bootstrap_database(pool: asyncpg.Pool) -> None:
    """
    Esegue le istruzioni DDL necessarie a creare tabelle e indici.
    Utilizza SQL puro ed esegue l'operazione in modo idempotente (IF NOT EXISTS).
    """
    logger.info("Inizio bootstrap e validazione dello schema database...")
    ddl_queries = [
        # 1. Tabella articles
        """
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            published_at DATE NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            country_code CHAR(2) NOT NULL DEFAULT 'XX',
            latitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            longitude DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            primary_category VARCHAR(50) NOT NULL CHECK (primary_category IN ('Nucleare', 'Elettronica', 'Chip', 'Acqua', 'Energia', 'Infrastrutture')),
            sentiment VARCHAR(20) NOT NULL CHECK (sentiment IN ('Positivo', 'Neutrale', 'Negativo')),
            relevance_level INTEGER NOT NULL CHECK (relevance_level BETWEEN 1 AND 5),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        # 2. Tabella companies
        """
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
        """,
        # 3. Tabella tags
        """
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
        """,
        # 4. Tabella article_companies (junction)
        """
        CREATE TABLE IF NOT EXISTS article_companies (
            article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            PRIMARY KEY (article_id, company_id)
        );
        """,
        # 5. Tabella article_tags (junction)
        """
        CREATE TABLE IF NOT EXISTS article_tags (
            article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (article_id, tag_id)
        );
        """,
        # 6. Indici di ricerca
        "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles (published_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_articles_geo_date ON articles (published_at, latitude, longitude);",
        "CREATE INDEX IF NOT EXISTS idx_articles_country_date ON articles (country_code, published_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles (primary_category, published_at DESC);",
        # 7. Colonne addizionali post-inizializzazione
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS infrastructural_entities TEXT[] NOT NULL DEFAULT '{}';",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS feed_title TEXT NOT NULL DEFAULT 'RSS Feed';"
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            for query in ddl_queries:
                await conn.execute(query)
                
    logger.info("Bootstrap database completato con successo.")
