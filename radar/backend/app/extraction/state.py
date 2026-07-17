"""Deduplicazione pre-LLM su ``articles.source_url``.

Deve girare **prima** di quota/reserve e chiamata provider: evita costi API
su URL già persistiti. Propaga gli errori DB al chiamante (non silenzia).

SoT:
    .agents/AGENTS.md §3 deduplicazione; skill llm-json-extraction flusso worker.
"""

import logging
import asyncpg

logger = logging.getLogger("radar.extraction.state")


async def is_article_duplicate(conn: asyncpg.Connection, url: str) -> bool:
    """True se ``source_url`` esiste già in ``articles`` (indice unico).

    Args:
        conn: Connessione asyncpg attiva (transazione del worker).
        url: URL già normalizzato da ``normalize_source_url``.
    Returns:
        ``True`` se duplicato; ``False`` se assente. URL vuoto → ``False`` con
        warning (non inventa un match; il chiamante dovrebbe aver validato prima).
    Raises:
        Exception: qualsiasi errore DB viene loggato e **ri-lanciato** — non
            trattare un fallimento di lettura come “non duplicato”.
    SoT:
        AGENTS.md §3; radar/.ecc/rules/backend.md (no LLM prima di SELECT EXISTS).
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
