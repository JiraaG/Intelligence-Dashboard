import logging
import asyncpg
from app.classification.validator import GeopoliticalArticleSchema

logger = logging.getLogger("radar.commit.db_commit")

async def commit_article_to_db(conn: asyncpg.Connection, article: GeopoliticalArticleSchema, feed_title: str = 'RSS Feed') -> int:
    """
    Esegue un inserimento atomico e relazionale dell'articolo geopolitico in PostgreSQL.
    Esegue l'upsert degli elementi connessi (aziende, tag) e ne popola le junction table.
    L'intera operazione deve avvenire all'interno di una transazione.
    """
    logger.info(f"Salvataggio relazionale nel DB per l'articolo: '{article.title[:50]}'")
    
    # Ricostruzione liste dalle stringhe
    from app.classification.validator import parse_csv_list
    entities_list = parse_csv_list(article.infrastructural_entities)
    companies_list = parse_csv_list(article.companies_involved)
    tags_list = parse_csv_list(article.tags)
    
    async with conn.transaction():
        # 1. Inserimento dell'articolo (ON CONFLICT DO NOTHING)
        insert_article_query = """
            INSERT INTO articles 
                (title, summary, published_at, source_url, country_code, 
                 latitude, longitude, primary_category, sentiment, relevance_level,
                 infrastructural_entities, feed_title)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (source_url) DO NOTHING
            RETURNING id
        """
        
        # Converti published_at (stringa YYYY-MM-DD) in un oggetto datetime.date per consentire il binding corretto in asyncpg
        from datetime import datetime, date
        try:
            pub_date = datetime.strptime(article.published_at, "%Y-%m-%d").date()
        except ValueError:
            pub_date = date.today()

        article_id = await conn.fetchval(
            insert_article_query,
            article.title,
            article.summary,
            pub_date,
            article.source_url,
            article.country_code,
            article.latitude,
            article.longitude,
            article.primary_category,
            article.sentiment,
            article.relevance_level,
            entities_list,
            feed_title
        )

        
        # Gestione del conflitto: se l'articolo esisteva già, recuperiamo il suo ID
        if article_id is None:
            logger.debug(f"Articolo già registrato via URL. Recupero ID esistente per: {article.source_url}")
            article_id = await conn.fetchval(
                "SELECT id FROM articles WHERE source_url = $1",
                article.source_url
            )
            
        if article_id is None:
            raise RuntimeError(f"Impossibile recuperare l'ID per l'articolo: {article.source_url}")

        # 2. Inserimento delle aziende coinvolte (Junction table)
        for company in companies_list:
            clean_company = company.strip()
            if not clean_company:
                continue
                
            # Upsert della company
            await conn.execute(
                "INSERT INTO companies (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                clean_company
            )
            company_id = await conn.fetchval(
                "SELECT id FROM companies WHERE name = $1",
                clean_company
            )
            # Associazione
            await conn.execute(
                "INSERT INTO article_companies (article_id, company_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                article_id,
                company_id
            )

        # 3. Inserimento dei tag semantici (Junction table)
        for tag in tags_list:
            clean_tag = tag.strip()
            if not clean_tag:
                continue
                
            # Upsert del tag
            await conn.execute(
                "INSERT INTO tags (name) VALUES ($1) ON CONFLICT (name) DO NOTHING",
                clean_tag
            )
            tag_id = await conn.fetchval(
                "SELECT id FROM tags WHERE name = $1",
                clean_tag
            )
            # Associazione
            await conn.execute(
                "INSERT INTO article_tags (article_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                article_id,
                tag_id
            )
            
        logger.info(f"Articolo inserito/aggiornato con successo [ID={article_id}]")
        return article_id
