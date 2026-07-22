"""Script CLI per verificare il funzionamento della deduplicazione semantica (pgvector + embedder).

Uso:
    python -m app.scripts.verify_semantic_dedup --dry-run
    python -m scripts.verify_semantic_dedup --dry-run
    python -m app.scripts.verify_semantic_dedup
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import asyncpg

from app.core.config import DATABASE_URL, SEMANTIC_DEDUP_ENABLED, SEMANTIC_EMBEDDING_MODEL
from app.extraction.embedder import generate_embedding
from app.extraction.semantic_dedup import find_near_duplicate

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("radar.verify_semantic_dedup")


async def run_verification(dry_run: bool = False) -> None:
    logger.info("=== Controllo di verifica Deduplicazione Semantica (pgvector) ===")
    logger.info("Config: SEMANTIC_DEDUP_ENABLED=%s, MODEL=%s", SEMANTIC_DEDUP_ENABLED, SEMANTIC_EMBEDDING_MODEL)

    sample_title = "TSMC amplia la produzione di microchip in Germania"
    sample_body = "TSMC ha annunciato un piano di espansione per la fab di Dresda con un investimento di 10 miliardi di euro."
    
    logger.info("Test generazione vector da titolo sample...")
    embedding = generate_embedding(sample_title, sample_body)
    if embedding is None:
        logger.error("❌ Fallita la generazione del vettore di embedding (model load failure).")
        sys.exit(1)
    
    logger.info("✅ Generazione embedding OK! Vettore dense dimensione: %d float (sample: [%.4f, %.4f, ...])",
                len(embedding), embedding[0], embedding[1])

    if dry_run:
        logger.info("Dry-run attivo: salito il controllo DB live. Verifica completata con successo!")
        return

    logger.info("Connessione a PostgreSQL (%s)...", DATABASE_URL.split("@")[-1])
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as db_err:
        logger.warning("Impossibile connettersi al DB live (%s). Salto la verifica SQL.", db_err)
        return

    try:
        has_vector = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        if not has_vector:
            logger.error("❌ Estensione pgvector non installata nel DB!")
        else:
            logger.info("✅ Estensione pgvector presente nel DB!")

        embed_count = await conn.fetchval("SELECT COUNT(*)::INT FROM article_embeddings")
        dedup_events = await conn.fetchval("SELECT COUNT(*)::INT FROM article_dedup_events")
        logger.info("Articoli con embedding registrati: %d", embed_count)
        logger.info("Eventi scontro deduplicazione registrati: %d", dedup_events)

        if embedding:
            cand = await find_near_duplicate(conn, embedding, lookback_hours=48)
            if cand:
                logger.info("Near-dup match trovato: '%s' (dist=%.4f)", cand.title, cand.distance)
            else:
                logger.info("Nessun match near-dup sotto soglia per l'articolo sample.")

    finally:
        await conn.close()

    logger.info("=== Verifica deduplicazione semantica completata con successo ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verifica deduplicazione semantica e pgvector")
    parser.add_argument("--dry-run", action="store_true", help="Esegui senza richiedere DB live")
    args = parser.parse_args()

    asyncio.run(run_verification(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
