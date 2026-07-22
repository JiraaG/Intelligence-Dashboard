"""Commit relazionale atomico + enqueue outbox nella stessa transazione.

Ordine durable (docs/02): INSERT articles/junction + riga ``article_outbox``
→ reconcile vault (altrove) → mark-read Miniflux solo se outbox ``completed``.
URL normalizzato una sola volta prima di dedup / ``ON CONFLICT``.

SoT:
    docs/02_architecture_and_backend.md (persistence); runbook outbox.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import asyncpg

from app.classification.validator import GeopoliticalArticleSchema, parse_csv_list
from app.commit.outbox import enqueue_outbox_row, force_reopen_outbox_row
from app.core.config import SEMANTIC_EMBEDDING_MODEL
from app.extraction.entry_validation import normalize_source_url

logger = logging.getLogger("radar.commit.db_commit")


async def commit_article_to_db(
    conn: asyncpg.Connection,
    article: GeopoliticalArticleSchema,
    feed_title: str = "RSS Feed",
    *,
    outbox_target_path: str,
    outbox_payload: str,
    miniflux_entry_id: int | None = None,
    body_excerpt: str = "",
    embedding: list[float] | None = None,
) -> Any:
    """Inserisce articolo + relazioni + outbox + embedding in **una** transazione.

    CSV schema → liste Python via ``parse_csv_list``; companies/tags diventano
    junction ``ON CONFLICT DO NOTHING``. Se ``source_url`` già presente
    (``ON CONFLICT DO NOTHING``), recupera l'id esistente e aggiorna comunque
    l'outbox (pending, salvo già ``completed`` — vedi ``enqueue_outbox_row``).

    Args:
        conn: Connessione asyncpg (transazione aperta qui).
        article: Schema Pydantic già validato.
        feed_title: Titolo feed Miniflux.
        outbox_target_path: Path vault assoluto (da ``get_article_file_path``).
        outbox_payload: Markdown da proiettare sul vault.
        miniflux_entry_id: Id entry per mark-read differito; può essere ``None``.
        body_excerpt: Estratto del testo sanitizzato (max 8000 char).
        embedding: Vettore di 384 float generato dall'embedder.
    Returns:
        ``articles.id`` (nuovo o già esistente).
    Raises:
        RuntimeError: impossibile risolvere id dopo conflict URL.
        EntryValidationError: URL non normalizzabile.
    Side-effects:
        Scrive tabelle relazionali + ``article_outbox``; **non** tocca il vault
        né Miniflux (compito di ``reconcile_outbox``).
    SoT:
        docs/02 persistence; runbook (mark-read solo post-completed).
    """
    logger.info("Salvataggio relazionale nel DB per l'articolo: '%s'", article.title[:50])

    entities_list = parse_csv_list(article.infrastructural_entities)
    companies_list = parse_csv_list(article.companies_involved)
    tags_list = parse_csv_list(article.tags)
    related_countries_list = parse_csv_list(article.related_countries)

    normalized_url = normalize_source_url(article.source_url)
    clean_body_excerpt = (body_excerpt or "")[:8000]

    async with conn.transaction():
        insert_article_query = """
            INSERT INTO articles
                (title, summary, published_at, source_url, country_code,
                 latitude, longitude, primary_category, sentiment, relevance_level,
                 infrastructural_entities, feed_title, related_countries, body_excerpt)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (source_url) DO NOTHING
            RETURNING id
        """

        try:
            pub_date = datetime.strptime(article.published_at, "%Y-%m-%d").date()
        except ValueError:
            pub_date = date.today()

        article_id = await conn.fetchval(
            insert_article_query,
            article.title,
            article.summary,
            pub_date,
            normalized_url,
            article.country_code,
            article.latitude,
            article.longitude,
            article.primary_category,
            article.sentiment,
            article.relevance_level,
            entities_list,
            feed_title,
            related_countries_list,
            clean_body_excerpt,
        )

        if article_id is None:
            # Conflict URL: riga già presente — recupera id per junction/outbox.
            logger.debug(
                "Articolo già registrato via URL. Recupero ID esistente per: %s",
                normalized_url,
            )
            article_id = await conn.fetchval(
                "SELECT id FROM articles WHERE source_url = $1",
                normalized_url,
            )

        if article_id is None:
            raise RuntimeError(f"Impossibile recuperare l'ID per l'articolo: {normalized_url}")

        for company in companies_list:
            clean_company = company.strip()
            if not clean_company:
                continue
            company_id = await conn.fetchval(
                """
                INSERT INTO companies (name) VALUES ($1)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                clean_company,
            )
            if company_id is None:
                logger.warning("Skip junction company senza id: %r", clean_company)
                continue
            await conn.execute(
                "INSERT INTO article_companies (article_id, company_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                article_id,
                company_id,
            )

        for tag in tags_list:
            clean_tag = tag.strip()
            if not clean_tag:
                continue
            tag_id = await conn.fetchval(
                """
                INSERT INTO tags (name) VALUES ($1)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                clean_tag,
            )
            if tag_id is None:
                logger.warning("Skip junction tag senza id: %r", clean_tag)
                continue
            await conn.execute(
                "INSERT INTO article_tags (article_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                article_id,
                tag_id,
            )

        if embedding:
            vector_str = f"[{','.join(str(x) for x in embedding)}]"
            text_hash = hashlib.sha256(f"{article.title} {article.summary}".encode("utf-8")).hexdigest()
            await conn.execute(
                """
                INSERT INTO article_embeddings (article_id, embedding, model_id, text_hash)
                VALUES ($1, $2::vector, $3, $4)
                ON CONFLICT (article_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    model_id = EXCLUDED.model_id,
                    text_hash = EXCLUDED.text_hash,
                    created_at = NOW()
                """,
                article_id,
                vector_str,
                SEMANTIC_EMBEDDING_MODEL,
                text_hash,
            )

        await enqueue_outbox_row(
            conn,
            article_id=article_id,
            target_path=outbox_target_path,
            payload=outbox_payload,
            miniflux_entry_id=miniflux_entry_id,
        )

        logger.info("Articolo inserito/aggiornato con successo [ID=%s] + outbox pending", article_id)
        return article_id


async def replace_article_in_place(
    conn: asyncpg.Connection,
    existing_article_id: Any,
    article: GeopoliticalArticleSchema,
    feed_title: str = "RSS Feed",
    *,
    outbox_target_path: str,
    outbox_payload: str,
    miniflux_entry_id: int | None = None,
    body_excerpt: str = "",
    embedding: list[float] | None = None,
) -> Any:
    """Sostituisce un articolo esistente nel DB con un nuovo articolo di qualità migliore (stesso ID).

    1. Rimuove il vecchio file Markdown dal vault se il percorso di destinazione è cambiato.
    2. Aggiorna i campi dell'articolo in ``articles``.
    3. Ricostruisce le associazioni (companies, tags).
    4. Aggiorna il vettore in ``article_embeddings``.
    5. Riapre l'outbox forzando lo stato a 'pending' tramite ``force_reopen_outbox_row``.
    """
    logger.info("Sostituzione in-place per l'articolo [ID=%s]: '%s'", existing_article_id, article.title[:50])

    entities_list = parse_csv_list(article.infrastructural_entities)
    companies_list = parse_csv_list(article.companies_involved)
    tags_list = parse_csv_list(article.tags)
    related_countries_list = parse_csv_list(article.related_countries)

    normalized_url = normalize_source_url(article.source_url)
    clean_body_excerpt = (body_excerpt or "")[:8000]

    try:
        pub_date = datetime.strptime(article.published_at, "%Y-%m-%d").date()
    except ValueError:
        pub_date = date.today()

    async with conn.transaction():
        # 1. Cleanup eventuale vecchio file Vault se target_path è cambiato
        old_outbox = await conn.fetchrow(
            "SELECT target_path FROM article_outbox WHERE article_id = $1",
            existing_article_id,
        )
        if old_outbox and old_outbox["target_path"] and old_outbox["target_path"] != outbox_target_path:
            old_file = Path(old_outbox["target_path"])
            try:
                if old_file.is_file():
                    old_file.unlink()
                    logger.info("Rimossa vecchia versione file Vault: %s", old_file)
            except Exception as unlink_err:
                logger.warning("Impossibile rimuovere il vecchio file Vault %s: %s", old_file, unlink_err)

        # 2. Aggiornamento riga articolo (conserva is_read e is_saved)
        await conn.execute(
            """
            UPDATE articles
            SET title = $1,
                summary = $2,
                published_at = $3,
                source_url = $4,
                country_code = $5,
                latitude = $6,
                longitude = $7,
                primary_category = $8,
                sentiment = $9,
                relevance_level = $10,
                infrastructural_entities = $11,
                feed_title = $12,
                related_countries = $13,
                body_excerpt = $14,
                updated_at = NOW()
            WHERE id = $15
            """,
            article.title,
            article.summary,
            pub_date,
            normalized_url,
            article.country_code,
            article.latitude,
            article.longitude,
            article.primary_category,
            article.sentiment,
            article.relevance_level,
            entities_list,
            feed_title,
            related_countries_list,
            clean_body_excerpt,
            existing_article_id,
        )

        # 3. Aggiornamento junction tables
        await conn.execute("DELETE FROM article_companies WHERE article_id = $1", existing_article_id)
        for company in companies_list:
            clean_company = company.strip()
            if not clean_company:
                continue
            company_id = await conn.fetchval(
                """
                INSERT INTO companies (name) VALUES ($1)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                clean_company,
            )
            if company_id is None:
                logger.warning("Skip junction company senza id (replace): %r", clean_company)
                continue
            await conn.execute(
                "INSERT INTO article_companies (article_id, company_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                existing_article_id,
                company_id,
            )

        await conn.execute("DELETE FROM article_tags WHERE article_id = $1", existing_article_id)
        for tag in tags_list:
            clean_tag = tag.strip()
            if not clean_tag:
                continue
            tag_id = await conn.fetchval(
                """
                INSERT INTO tags (name) VALUES ($1)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                clean_tag,
            )
            if tag_id is None:
                logger.warning("Skip junction tag senza id (replace): %r", clean_tag)
                continue
            await conn.execute(
                "INSERT INTO article_tags (article_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                existing_article_id,
                tag_id,
            )

        # 4. Aggiornamento embedding
        if embedding:
            vector_str = f"[{','.join(str(x) for x in embedding)}]"
            text_hash = hashlib.sha256(f"{article.title} {article.summary}".encode("utf-8")).hexdigest()
            await conn.execute(
                """
                INSERT INTO article_embeddings (article_id, embedding, model_id, text_hash)
                VALUES ($1, $2::vector, $3, $4)
                ON CONFLICT (article_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    model_id = EXCLUDED.model_id,
                    text_hash = EXCLUDED.text_hash,
                    created_at = NOW()
                """,
                existing_article_id,
                vector_str,
                SEMANTIC_EMBEDDING_MODEL,
                text_hash,
            )

        # 5. Riapertura outbox
        await force_reopen_outbox_row(
            conn,
            article_id=existing_article_id,
            target_path=outbox_target_path,
            payload=outbox_payload,
            miniflux_entry_id=miniflux_entry_id,
        )

        logger.info("Articolo [ID=%s] sostituito con successo in-place", existing_article_id)
        return existing_article_id
