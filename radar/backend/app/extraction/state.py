import logging
import asyncpg

logger = logging.getLogger("radar.extraction.state")

async def is_article_duplicate(conn: asyncpg.Connection, url: str) -> bool:
    """
    Interroga velocemente il database PostgreSQL tramite query SQL pura per verificare
    se l'URL dell'articolo fornito è già registrato nella tabella 'articles'.
    Utilizza l'indice unico sulla colonna 'source_url' per massimizzare la velocità.
    """
    if not url:
        logger.warning("Verifica duplicati chiamata con URL vuoto.")
        return False

    query = "SELECT EXISTS(SELECT 1 FROM articles WHERE source_url = $1)"
    try:
        result = await conn.fetchval(query, url)
        is_dup = bool(result)
        if is_dup:
            logger.debug(f"Rilevato articolo duplicato: {url}")
        return is_dup
    except Exception as e:
        logger.error(f"Errore durante la verifica duplicati nel database per URL {url}: {e}")
        raise
