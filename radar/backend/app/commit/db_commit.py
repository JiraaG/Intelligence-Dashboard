"""Atomic relational DB commit with outbox enqueue."""

from __future__ import annotations

import logging
from datetime import date, datetime

import asyncpg

from app.classification.validator import GeopoliticalArticleSchema, parse_csv_list
from app.commit.outbox import enqueue_outbox_row
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
) -> int:
    """
    Inserimento atomico articolo + relazioni + riga outbox in una sola transazione.
    L'URL viene normalizzato una sola volta prima del dedup/ON CONFLICT.
    """
    logger.info("Salvataggio relazionale nel DB per l'articolo: '%s'", article.title[:50])

    entities_list = parse_csv_list(article.infrastructural_entities)
    companies_list = parse_csv_list(article.companies_involved)
    tags_list = parse_csv_list(article.tags)

    normalized_url = normalize_source_url(article.source_url)

    async with conn.transaction():
        insert_article_query = """
            INSERT INTO articles
                (title, summary, published_at, source_url, country_code,
                 latitude, longitude, primary_category, sentiment, relevance_level,
                 infrastructural_entities, feed_title)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
        )

        if article_id is None:
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
            await conn.execute(
                "INSERT INTO companies (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                clean_company,
            )
            company_id = await conn.fetchval(
                "SELECT id FROM companies WHERE name = $1",
                clean_company,
            )
            await conn.execute(
                "INSERT INTO article_companies (article_id, company_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                article_id,
                company_id,
            )

        for tag in tags_list:
            clean_tag = tag.strip()
            if not clean_tag:
                continue
            await conn.execute(
                "INSERT INTO tags (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                clean_tag,
            )
            tag_id = await conn.fetchval(
                "SELECT id FROM tags WHERE name = $1",
                clean_tag,
            )
            await conn.execute(
                "INSERT INTO article_tags (article_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                article_id,
                tag_id,
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
