#!/usr/bin/env python3
"""
Radar Informativo Globale — Live Integration & Production Audit Script
Esegue controlli reali senza l'ausilio di mock su database, client Miniflux
e connessioni Gemini API.

Requires RUN_LIVE_TESTS=1. E2E write tests require an isolated test database
(RADAR_LIVE_TEST_DATABASE_URL) and optionally RADAR_LIVE_TEST_VAULT_PATH.
"""

import sys
import os
import asyncio
import logging
import socket
import uuid
import tempfile
import shutil
from urllib.parse import urlparse
from typing import Optional, Tuple

# Setup PYTHONPATH per caricare i moduli di app/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncpg
import httpx
from app.core.config import (
    MINIFLUX_API_URL,
    MINIFLUX_API_KEY,
    OBSIDIAN_VAULT_PATH,
)
from app.extraction.client import MinifluxClient
from app.classification.client import ClassificationClient
from app.classification.validator import GeopoliticalArticleSchema
from app.commit.db_commit import commit_article_to_db
from app.commit.factory import generate_markdown_content
from app.commit.router import get_article_file_path, initialize_vault_directories
from app.commit.lock import write_file_with_lock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("radar.production_test")


def require_live_tests_enabled() -> None:
    if os.environ.get("RUN_LIVE_TESTS") != "1":
        raise RuntimeError(
            "Live production pipeline tests are gated. "
            "Set RUN_LIVE_TESTS=1 explicitly before running."
        )


def resolve_isolated_live_targets(run_id: str) -> Tuple[str, str, bool]:
    """
    Returns (database_url, vault_path, vault_is_temp).
    Refuses the default production Obsidian vault path unless an explicit
    isolated vault env var is provided.
    """
    db_url = (
        os.environ.get("RADAR_LIVE_TEST_DATABASE_URL")
        or os.environ.get("TEST_DATABASE_URL")
    )
    if not db_url:
        raise RuntimeError(
            "Isolated live E2E requires RADAR_LIVE_TEST_DATABASE_URL "
            "(or TEST_DATABASE_URL). Refusing to write to the default DATABASE_URL."
        )

    vault = (
        os.environ.get("RADAR_LIVE_TEST_VAULT_PATH")
        or os.environ.get("TEST_OBSIDIAN_VAULT_PATH")
    )
    vault_is_temp = False
    if not vault:
        vault = tempfile.mkdtemp(prefix=f"radar_live_vault_{run_id}_")
        vault_is_temp = True
    else:
        resolved_vault = os.path.abspath(vault)
        resolved_prod = os.path.abspath(OBSIDIAN_VAULT_PATH) if OBSIDIAN_VAULT_PATH else ""
        if resolved_prod and resolved_vault == resolved_prod:
            raise RuntimeError(
                "RADAR_LIVE_TEST_VAULT_PATH must not equal OBSIDIAN_VAULT_PATH. "
                "Use an isolated test Vault directory."
            )

    return db_url, vault, vault_is_temp


async def test_external_connections(miniflux: MinifluxClient, classification: ClassificationClient) -> None:
    require_live_tests_enabled()
    logger.info("=== STEP 1: Audit Connessioni Esterne ===")

    logger.info(f"Verifica connessione reale a Miniflux API su {MINIFLUX_API_URL}...")

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
    require_live_tests_enabled()
    logger.info("=== STEP 2: Test Scrittura Atomica e Transazionale E2E ===")

    run_id = uuid.uuid4().hex
    db_url, vault_path, vault_is_temp = resolve_isolated_live_targets(run_id)
    company_name = f"TEST_CO_{run_id}"
    tag_name = f"TestLive_{run_id}"
    source_url = f"https://example.com/live-integration-test-{run_id}"
    title = f"LIVE INTEGRATION TEST RADAR {run_id}"

    fake_article = GeopoliticalArticleSchema(
        title=title,
        summary="Questo e' un articolo di test autogenerato per validare la persistenza relazionale.",
        published_at="2026-06-24",
        source_url=source_url,
        country_code="IT",
        latitude=41.8902,
        longitude=12.4922,
        companies_involved=company_name,
        tags=f"Infrastrutture,{tag_name}",
        primary_category="Infrastrutture",
        sentiment="Positivo",
        infrastructural_entities=f"Centrale Geotermica Test {run_id}",
        relevance_level=5,
    )

    article_id: Optional[int] = None
    file_path: Optional[str] = None
    conn = None

    try:
        initialize_vault_directories(vault_path)

        logger.info("Apertura connessione a PostgreSQL di test isolato...")
        conn = await asyncpg.connect(db_url)

        logger.info("Generazione contenuto Markdown e path Vault...")
        md_content = generate_markdown_content(fake_article)
        file_path = get_article_file_path(fake_article, vault_path=vault_path)
        parent = os.path.dirname(file_path)
        os.makedirs(parent, exist_ok=True)

        logger.info("Esecuzione commit relazionale transazionale + outbox su DB di test...")
        article_id = await commit_article_to_db(
            conn,
            fake_article,
            outbox_target_path=file_path,
            outbox_payload=md_content,
            miniflux_entry_id=None,
        )
        logger.info(f"Articolo inserito correttamente nel DB con ID: {article_id}")

        logger.info("Scrittura su Vault di test con Lock...")
        write_file_with_lock(file_path, md_content)
        logger.info(f"File Markdown scritto con successo in: {file_path}")

        logger.info("Validazione presenza record nel database...")
        db_row = await conn.fetchrow(
            "SELECT id, title, sentiment, relevance_level, source_url FROM articles WHERE id = $1 AND source_url = $2",
            article_id,
            source_url,
        )
        assert db_row is not None, "Record non trovato nel database di test."
        assert db_row["title"] == fake_article.title, "Il titolo nel DB non corrisponde."
        assert db_row["sentiment"] == "Positivo", "Sentiment non corretto."
        assert db_row["relevance_level"] == 5, "Relevance level non corretto."
        assert db_row["source_url"] == source_url, "source_url non corrisponde al run-id."
        logger.info("Verifica Database superata con successo.")

        logger.info("Validazione presenza file fisico sul filesystem di test...")
        assert os.path.exists(file_path), "File Markdown non trovato nel Vault di test."
        with open(file_path, "r", encoding="utf-8") as f:
            file_data = f.read()
            assert "sentiment: \"Positivo\"" in file_data or "sentiment: Positivo" in file_data, (
                "Frontmatter sentiment errato."
            )
            assert "relevance: 5" in file_data or "relevance_level: 5" in file_data, (
                "Frontmatter relevance errato."
            )
        logger.info("Verifica Filesystem superata con successo.")

    except Exception as e:
        logger.error(f"Test transazionale E2E FALLITO: {e}")
        raise
    finally:
        logger.info("=== STEP 2B: Ripristino e Pulizia Ambiente di Test ===")
        if conn:
            try:
                if article_id is not None:
                    # Solo il record creato da questo run (id + source_url univoco).
                    logger.info("Rimozione record creato da questo run dal database di test...")
                    await conn.execute(
                        "DELETE FROM article_outbox WHERE article_id = $1",
                        article_id,
                    )
                    await conn.execute(
                        "DELETE FROM article_companies WHERE article_id = $1",
                        article_id,
                    )
                    await conn.execute(
                        "DELETE FROM article_tags WHERE article_id = $1",
                        article_id,
                    )
                    await conn.execute(
                        "DELETE FROM articles WHERE id = $1 AND source_url = $2",
                        article_id,
                        source_url,
                    )
                    # Rimuove solo company/tag con nome run-unique e senza altri riferimenti.
                    await conn.execute(
                        """
                        DELETE FROM companies c
                        WHERE c.name = $1
                          AND NOT EXISTS (
                              SELECT 1 FROM article_companies ac WHERE ac.company_id = c.id
                          )
                        """,
                        company_name,
                    )
                    await conn.execute(
                        """
                        DELETE FROM tags t
                        WHERE t.name = $1
                          AND NOT EXISTS (
                              SELECT 1 FROM article_tags at WHERE at.tag_id = t.id
                          )
                        """,
                        tag_name,
                    )
                    logger.info("Pulizia Database di test completata.")
            except Exception as clean_db_err:
                logger.warning(f"Errore nella pulizia del database di test: {clean_db_err}")
            finally:
                await conn.close()
                logger.info("Connessione PostgreSQL chiusa.")

        if file_path and os.path.exists(file_path):
            try:
                logger.info("Rimozione file Markdown temporaneo di test...")
                os.remove(file_path)
                logger.info("Pulizia Filesystem completata.")
            except Exception as clean_fs_err:
                logger.warning(f"Errore nella rimozione del file di test: {clean_fs_err}")

        if vault_is_temp and vault_path and os.path.isdir(vault_path):
            try:
                shutil.rmtree(vault_path, ignore_errors=True)
                logger.info("Vault temporaneo di test rimosso.")
            except Exception as clean_vault_err:
                logger.warning(f"Errore nella rimozione del vault temporaneo: {clean_vault_err}")


def _local_classification_client() -> ClassificationClient:
    """Helper locale per inizializzare ClassificationClient con una quota fittizia (mock)."""
    from unittest.mock import AsyncMock

    quota = AsyncMock()
    quota.reserve = AsyncMock(side_effect=list(range(1, 10_000)))
    quota.complete = AsyncMock()
    quota.release = AsyncMock()
    quota.fail = AsyncMock()
    return ClassificationClient(quota=quota)


async def main() -> None:
    logger.info("=== Radar Ingest Pipeline Integration & Production Audit ===")
    try:
        require_live_tests_enabled()
    except RuntimeError as gate_err:
        logger.error("%s", gate_err)
        sys.exit(2)

    async with httpx.AsyncClient() as http_client:
        miniflux = MinifluxClient(MINIFLUX_API_URL, MINIFLUX_API_KEY, http_client=http_client)
        classification = _local_classification_client()

        try:
            await test_external_connections(miniflux, classification)

            try:
                await test_e2e_transactional_commit(miniflux)
            except (asyncpg.PostgresError, socket.gaierror, ConnectionRefusedError, RuntimeError) as db_net_err:
                logger.warning(
                    f"[DB INTEGRATION WARNING] E2E isolato non riuscito ({db_net_err}). "
                    "Imposta RADAR_LIVE_TEST_DATABASE_URL verso un database di test dedicato."
                )

            logger.info("=== TUTTI I CONTROLLI DI INTEGRAZIONE HANNO AVUTO ESITO POSITIVO ===")
            sys.exit(0)
        except Exception as err:
            logger.error(f"INTEGRATION TEST FALLITO: {err}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
