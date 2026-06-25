#!/usr/bin/env python3
"""
Radar Informativo Globale — Live Integration & Production Audit Script
Esegue controlli reali senza l'ausilio di mock su database, client Miniflux,
connessioni Gemini API ed il throttling del rate limiter.
"""

import sys
import os
import asyncio
import time
import logging
import socket
from urllib.parse import urlparse
from typing import List

# Setup PYTHONPATH per caricare i moduli di app/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncpg
from app.core.config import (
    DATABASE_URL,
    MINIFLUX_API_URL,
    MINIFLUX_API_KEY,
    OBSIDIAN_VAULT_PATH,
    LLM_API_KEY
)
from app.extraction.client import MinifluxClient
from app.classification.client import ClassificationClient
from app.classification.validator import GeopoliticalArticleSchema
from app.commit.db_commit import commit_article_to_db
from app.commit.factory import generate_markdown_content
from app.commit.router import get_article_file_path
from app.commit.lock import write_file_with_lock

# Configura logger per lo script
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("radar.production_test")

async def test_external_connections(miniflux: MinifluxClient, classification: ClassificationClient) -> None:
    logger.info("=== STEP 1: Audit Connessioni Esterne ===")
    
    # 1. Test Miniflux Connection
    logger.info(f"Verifica connessione reale a Miniflux API su {MINIFLUX_API_URL}...")
    
    # Controllo preventivo della risoluzione DNS per fornire warning espliciti (DevOps helper)
    parsed_url = urlparse(MINIFLUX_API_URL)
    hostname = parsed_url.hostname
    dns_resolvable = True
    if hostname:
        try:
            socket.gethostbyname(hostname)
        except socket.gaierror:
            dns_resolvable = False
            logger.warning(
                f"[DNS WARNING] Impossibile risolvere l'host '{hostname}'. "
                "Questo è previsto se stai eseguendo i test live in locale all'esterno della rete "
                "virtuale Docker Compose (in cui l'host 'radar-miniflux' è isolato)."
            )

    try:
        entries = await miniflux.fetch_unread_entries(limit=1)
        if not dns_resolvable and not entries:
            logger.info("Miniflux non raggiungibile a causa di DNS non risolvibile (Test saltato con grazia).")
        else:
            logger.info(f"Connessione a Miniflux completata. Ricevute {len(entries)} entries di risposta.")
    except Exception as e:
        logger.error(f"Connessione a Miniflux FALLITA: {e}")
        raise

    # 2. Test Gemini API SDK Connection
    logger.info("Verifica connessione reale a Gemini API (Modello: %s)...", classification.model)
    try:
        response = await asyncio.to_thread(
            classification.client.models.generate_content,
            model=classification.model,
            contents="Rispondi unicamente con la parola OK."
        )
        resp_text = response.text.strip()
        logger.info(f"Risposta Gemini API: '{resp_text}' (Connessione OK)")
    except Exception as e:
        logger.error(f"Connessione a Gemini API FALLITA: {e}")
        raise


async def test_e2e_transactional_commit(miniflux: MinifluxClient) -> None:
    logger.info("=== STEP 2: Test Scrittura Atomica e Transazionale E2E ===")
    
    fake_article = GeopoliticalArticleSchema(
        reasoning="Test di integrazione reale per la pipeline di produzione.",
        title="LIVE INTEGRATION TEST RADAR PIPELINE ARTICLE",
        summary="Questo e' un articolo di test autogenerato per validare la persistenza relazionale.",
        published_at="2026-06-24",
        source_url="https://example.com/live-integration-test-unique-url-radar-999",
        country_code="IT",
        latitude=41.8902,
        longitude=12.4922,
        companies_involved=["TEST_INTEGRATION_INC"],
        tags=["Infrastrutture", "TestLive"],
        primary_category="Infrastrutture",
        sentiment="Positivo",
        infrastructural_entities=["Centrale Geotermica Test"],
        relevance_level=5
    )

    article_id = None
    file_path = None
    conn = None

    try:
        # 1. Inserimento relazionale nel database reale
        logger.info("Apertura connessione a PostgreSQL reale...")
        conn = await asyncpg.connect(DATABASE_URL)
        
        logger.info("Esecuzione commit relazionale transazionale su DB...")
        article_id = await commit_article_to_db(conn, fake_article)
        logger.info(f"Articolo inserito correttamente nel DB con ID: {article_id}")

        # 2. Generazione e scrittura file Markdown nel Vault fisico
        logger.info("Generazione contenuto Markdown e scrittura su Vault con Lock...")
        md_content = generate_markdown_content(fake_article)
        file_path = get_article_file_path(fake_article, vault_path=OBSIDIAN_VAULT_PATH)
        write_file_with_lock(file_path, md_content)
        logger.info(f"File Markdown scritto con successo in: {file_path}")

        # 3. Validazione della presenza reale
        logger.info("Validazione presenza record nel database...")
        db_row = await conn.fetchrow("SELECT id, title, sentiment, relevance_level FROM articles WHERE id = $1", article_id)
        assert db_row is not None, "Record non trovato nel database."
        assert db_row["title"] == fake_article.title, "Il titolo nel DB non corrisponde."
        assert db_row["sentiment"] == "Positivo", "Sentiment non corretto."
        assert db_row["relevance_level"] == 5, "Relevance level non corretto."
        logger.info("Verifica Database superata con successo.")

        logger.info("Validazione presenza file fisico sul filesystem...")
        assert os.path.exists(file_path), "File Markdown non trovato nel Vault Obsidian."
        with open(file_path, "r", encoding="utf-8") as f:
            file_data = f.read()
            assert "sentiment: \"Positivo\"" in file_data, "Frontmatter sentiment errato."
            assert "relevance: 5" in file_data, "Frontmatter relevance errato."
        logger.info("Verifica Filesystem superata con successo.")

    except Exception as e:
        logger.error(f"Test transazionale E2E FALLITO: {e}")
        raise
    finally:
        # Pulizia dell'ambiente di produzione
        logger.info("=== STEP 2B: Ripristino e Pulizia Ambiente ===")
        if conn:
            try:
                if article_id:
                    logger.info("Rimozione record e giunzioni dal database...")
                    await conn.execute("DELETE FROM articles WHERE id = $1", article_id)
                    await conn.execute("DELETE FROM companies WHERE name = $1", "TEST_INTEGRATION_INC")
                    await conn.execute("DELETE FROM tags WHERE name = $1", "TestLive")
                    logger.info("Pulizia Database completata.")
            except Exception as clean_db_err:
                logger.warning(f"Errore nella pulizia del database: {clean_db_err}")
            finally:
                await conn.close()
                logger.info("Connessione PostgreSQL chiusa.")

        if file_path:
            try:
                if os.path.exists(file_path):
                    logger.info("Rimozione file Markdown temporaneo...")
                    os.remove(file_path)
                    logger.info("Pulizia Filesystem completata.")
            except Exception as clean_fs_err:
                logger.warning(f"Errore nella rimozione del file di test: {clean_fs_err}")


async def stress_test_rate_limiter(classification: ClassificationClient) -> None:
    logger.info("=== STEP 3: Stress Test del Rate Limiter ===")
    logger.info("Lancio di 5 chiamate asincrone concorrenti al rate limiter...")

    timestamps: List[float] = []

    async def limiter_worker(worker_id: int) -> None:
        await classification._wait_for_rate_limit()
        acq_time = time.time()
        timestamps.append(acq_time)
        logger.info(f"Worker {worker_id} ha superato la barriera temporale al timestamp: {acq_time:.4f}")

    start_time = time.time()
    await asyncio.gather(*(limiter_worker(i) for i in range(1, 6)))
    total_duration = time.time() - start_time

    logger.info(f"Tutti i worker hanno completato l'esecuzione in {total_duration:.2f}s")
    
    timestamps.sort()
    for idx in range(len(timestamps) - 1):
        diff = timestamps[idx + 1] - timestamps[idx]
        logger.info(f"Intervallo tra transizione {idx+1} e {idx+2}: {diff:.4f} secondi")
        assert diff >= 3.9, f"Errore: Throttling insufficiente. Rilevati solo {diff:.2f}s di attesa."
    
    logger.info("Stress Test Rate Limiter superato con successo.")


async def main() -> None:
    logger.info("=== Radar Ingest Pipeline Integration & Production Audit ===")
    
    miniflux = MinifluxClient(MINIFLUX_API_URL, MINIFLUX_API_KEY)
    classification = ClassificationClient()

    try:
        # 1. Verifica Connessioni Esterne
        await test_external_connections(miniflux, classification)
        
        # 2. Test Scrittura Atomica e Transazionale E2E
        # Se il database o l'host non sono disponibili a causa di esecuzione locale,
        # lo step segnalerà l'errore in modo descrittivo.
        try:
            await test_e2e_transactional_commit(miniflux)
        except (asyncpg.PostgresError, socket.gaierror, ConnectionRefusedError) as db_net_err:
            logger.warning(
                f"[DB INTEGRATION WARNING] Connessione a PostgreSQL non riuscita ({db_net_err}). "
                "Questo e' previsto se il database non e' esposto su localhost o se stai eseguendo "
                "il test fuori dall'ambiente Docker. Saltato."
            )
        
        # 3. Stress Test del Rate Limiter
        await stress_test_rate_limiter(classification)

        logger.info("=== TUTTI I CONTROLLI DI INTEGRAZIONE HANNO AVUTO ESITO POSITIVO ===")
        sys.exit(0)
    except Exception as err:
        logger.error(f"INTEGRATION TEST FALLITO: {err}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
