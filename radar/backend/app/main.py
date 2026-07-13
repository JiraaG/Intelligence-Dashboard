"""
Radar Informativo Globale — Backend FastAPI App
Coordinatore e API Router centrale conforme all'architettura ECC.

Pipeline: Miniflux RSS → Sanitizzazione HTML → Deduplicazione URL →
          Google Gemini (Structured Output) → PostgreSQL & Vault Obsidian
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List

import asyncpg
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Configurazione e Core
from app.core.config import (
    DATABASE_URL,
    OBSIDIAN_VAULT_PATH,
    MINIFLUX_API_URL,
    MINIFLUX_API_KEY,
    MINIFLUX_LIMIT,
    LLM_RPD
)
from app.core.database import init_pool, bootstrap_database
from app.core.logging import setup_logging

# Layer E: Extraction
from app.extraction.client import MinifluxClient
from app.extraction.parser import strip_html_tags
from app.extraction.state import is_article_duplicate

# Layer C: Classification
from app.classification.client import ClassificationClient
from app.classification.validator import GeopoliticalArticleSchema

# Layer C: Commit
from app.commit.db_commit import commit_article_to_db
from app.commit.factory import generate_markdown_content
from app.commit.router import initialize_vault_directories, get_article_file_path
from app.commit.lock import write_file_with_lock

# Logger centrale
logger = logging.getLogger("radar.main")

class AppState:
    """Contenitore per lo stato globale condiviso dell'applicazione."""
    def __init__(self) -> None:
        self.db_pool: Optional[asyncpg.Pool] = None
        self.miniflux_client: Optional[MinifluxClient] = None
        self.classification_client: Optional[ClassificationClient] = None
        self.pipeline_task: Optional[asyncio.Task] = None

# Istanza dello stato globale
state = AppState()


async def process_single_entry(app_state: AppState, entry: dict) -> bool:
    """
    Elabora un singolo articolo: deduplicazione, sanitizzazione, LLM e commit.
    Ritorna True in caso di completamento (incluso skip per duplicato), False in caso di errore.
    """
    entry_id = entry.get("id")
    source_url = entry.get("url", "").strip()
    title = entry.get("title", "N/A").strip()
    raw_content = entry.get("content", "") or entry.get("summary", "") or ""
    published_at_raw = entry.get("published_at", "")
    published_date = published_at_raw.split("T")[0] if "T" in published_at_raw else published_at_raw
    feed_title = entry.get("feed", {}).get("title", "RSS Feed").strip()

    if not source_url:
        logger.warning("Articolo saltato: URL sorgente mancante o nullo.")
        return False

    try:
        # Step A: Deduplicazione (Acquisizione connessione spot dal pool)
        async with app_state.db_pool.acquire() as conn:
            is_dup = await is_article_duplicate(conn, source_url)
        
        if is_dup:
            logger.info(f"Articolo duplicato rilevato: '{title[:50]}'. Marcatura come letto su Miniflux...")
            if entry_id:
                await app_state.miniflux_client.mark_as_read([entry_id])
            return True

        # Step B: Sanitizzazione HTML
        clean_content = strip_html_tags(raw_content)

        # Step C: Estrazione LLM
        extracted_article = await app_state.classification_client.classify_article(
            title=title,
            content=clean_content,
            url=source_url,
            date=published_date
        )

        # Step D: Relational Database Commit
        async with app_state.db_pool.acquire() as conn:
            article_id = await commit_article_to_db(conn, extracted_article, feed_title)

        # Step E: File System Markdown Commit
        md_content = generate_markdown_content(extracted_article)
        file_path = get_article_file_path(extracted_article, vault_path=OBSIDIAN_VAULT_PATH)
        write_file_with_lock(file_path, md_content)

        # Step F: Marcatura lettura su Miniflux
        if entry_id:
            await app_state.miniflux_client.mark_as_read([entry_id])

        logger.info(f"Articolo elaborato e committato correttamente [ID={article_id}]: '{extracted_article.title[:50]}'")
        return True

    except Exception as article_err:
        logger.error(
            f"Errore durante l'elaborazione del singolo articolo '{title[:50]}': {article_err}",
            exc_info=True
        )
        return False

async def run_pipeline_cycle(app_state: AppState) -> None:
    """
    Esegue un singolo ciclo completo della pipeline (Level 2).
    Applica il limite RPD, preleva gli articoli non letti ed elabora in modo concorrente (TaskGroup).
    """
    logger.info("=== Avvio di un nuovo ciclo della pipeline di ingestione ===")
    
    # Controllo soglia RPD (Requests Per Day) dal DB
    async with app_state.db_pool.acquire() as conn:
        processed_today = await conn.fetchval(
            "SELECT count(*) FROM articles WHERE date(created_at) = CURRENT_DATE"
        )
        if processed_today >= LLM_RPD:
            logger.warning(
                f"LIMITE RPD RAGGIUNTO: processati {processed_today}/{LLM_RPD} articoli oggi. "
                "Il ciclo andrà in ibernazione per non superare il Rate Limit giornaliero."
            )
            return

    # 1. Recupero degli articoli da Miniflux
    entries = await app_state.miniflux_client.fetch_unread_entries(limit=MINIFLUX_LIMIT)
    if not entries:
        logger.info("Nessun articolo non letto presente in Miniflux.")
        return

    # Limita l'ingestione se gli articoli recuperati supererebbero l'RPD residuo
    remaining_rpd = LLM_RPD - processed_today
    if len(entries) > remaining_rpd:
        logger.info(f"Riduzione lotto da {len(entries)} a {remaining_rpd} per rispettare il limite RPD.")
        entries = entries[:remaining_rpd]

    # 2. Elaborazione concorrente degli articoli
    success_count = 0
    failure_count = 0

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(process_single_entry(app_state, entry)) for entry in entries]

    for task in tasks:
        if task.result():
            success_count += 1
        else:
            failure_count += 1

    logger.info(f"=== Ciclo della pipeline completato: {success_count} elaborati/saltati, {failure_count} errori ===")


async def run_pipeline_loop(app_state: AppState) -> None:
    """
    Loop infinito del demone in background (Level 1).
    Cattura tutte le eccezioni per garantire che il thread non muoia mai.
    Esegue il polling ogni 15 minuti (900 secondi) come da requisiti PRD.
    """
    logger.info("Demone pipeline in background avviato con successo.")
    
    # Eseguiamo un refresh forzato dei feed al primo avvio
    # per garantire che Miniflux sia sincronizzato dopo un riavvio del PC/container.
    try:
        await app_state.miniflux_client.refresh_all_feeds()
    except Exception as refresh_err:
        logger.warning(f"Refresh forzato fallito all'avvio: {refresh_err}")

    while True:
        try:
            await run_pipeline_cycle(app_state)
        except Exception as cycle_err:
            logger.error(f"Errore critico durante l'esecuzione del ciclo pipeline: {cycle_err}", exc_info=True)
        finally:
            logger.info("Attesa di 15 minuti prima del prossimo ciclo di polling...")
            await asyncio.sleep(900)


# ── FastAPI Lifespan ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Inizializzazione dello stato globale e dei servizi all'avvio e spegnimento."""
    # Avvio (Startup)
    setup_logging()
    logger.info("Avvio del server FastAPI. Inizializzazione moduli Core...")

    try:
        # Inizializzazione Database
        state.db_pool = await init_pool(DATABASE_URL)
        await bootstrap_database(state.db_pool)

        # Inizializzazione Vault Obsidian
        initialize_vault_directories(OBSIDIAN_VAULT_PATH)

        # Inizializzazione Client Esterni
        state.miniflux_client = MinifluxClient(MINIFLUX_API_URL, MINIFLUX_API_KEY)
        state.classification_client = ClassificationClient()

        # Avvio del demone asincrono non bloccante
        state.pipeline_task = asyncio.create_task(
            run_pipeline_loop(state),
            name="radar-ingest-daemon"
        )
        
        logger.info("Bootstrap completato con successo. Demone avviato in background.")
    except Exception as init_err:
        logger.critical(f"Errore critico all'avvio del lifespan: {init_err}", exc_info=True)
        raise init_err

    yield

    # Spegnimento (Shutdown)
    logger.info("Arresto del server FastAPI in corso...")
    if state.pipeline_task:
        state.pipeline_task.cancel()
        try:
            await state.pipeline_task
        except asyncio.CancelledError:
            logger.info("Background loop cancellato correttamente.")

    if state.db_pool:
        await state.db_pool.close()
        logger.info("Pool connessioni PostgreSQL chiuso correttamente.")

    logger.info("Radar Backend arrestato.")


# Inizializzazione App FastAPI
app = FastAPI(
    title="Radar Informativo Globale — API",
    description="Backend API del Radar geopolitico ed infrastrutturale.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configurazione CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modificabile per restringere ad host specifici in prod
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Endpoint REST ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Healthcheck standard utilizzato per i controlli di stato Docker."""
    return {"status": "ok", "service": "radar-backend"}


@app.get("/api/articles")
async def get_articles(
    date: str,
    sentiment: Optional[str] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5)
):
    """
    Restituisce gli articoli geopolitici del giorno specificato.
    Supporta il filtraggio opzionale per sentiment e livello di rilevanza.
    Utilizza funzioni di aggregazione SQL per combinare tags e companies in liste piatte.
    """
    if not state.db_pool:
        return []

    # Validazione e parsing della data in un oggetto datetime.date per asyncpg
    from datetime import datetime
    try:
        pub_date = datetime.strptime(date.replace("/", "-"), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato data non valido. Usa il formato ISO YYYY-MM-DD."
        )

    # Costruzione dinamica della query SQL per massimizzare le performance
    query_parts = [
        """
        SELECT 
            a.id, a.title, a.summary, a.published_at::text AS published_at, a.source_url,
            a.country_code, a.latitude, a.longitude, a.primary_category,
            a.sentiment, a.relevance_level, a.infrastructural_entities, a.feed_title,
            a.is_read,
            COALESCE(array_agg(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL), '{}') AS companies_involved,
            COALESCE(array_agg(DISTINCT t.name) FILTER (WHERE t.name IS NOT NULL), '{}') AS tags
        FROM articles a
        LEFT JOIN article_companies ac ON ac.article_id = a.id
        LEFT JOIN companies c ON c.id = ac.company_id
        LEFT JOIN article_tags at2 ON at2.article_id = a.id
        LEFT JOIN tags t ON t.id = at2.tag_id
        WHERE a.published_at = $1
        """
    ]
    
    params = [pub_date]
    
    if sentiment:
        params.append(sentiment)
        query_parts.append(f"AND a.sentiment = ${len(params)}")
        
    if relevance_level is not None:
        params.append(relevance_level)
        query_parts.append(f"AND a.relevance_level = ${len(params)}")

    query_parts.append("GROUP BY a.id ORDER BY a.id DESC")
    final_query = " ".join(query_parts)

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(final_query, *params)
        
    return [dict(row) for row in rows]


@app.get("/api/countries")
async def get_countries_summary(
    date: str,
    sentiment: Optional[str] = Query(None),
    relevance_level: Optional[int] = Query(None, ge=1, le=5)
):
    """
    Restituisce l'aggregato delle categorie e del conteggio articoli per nazione in un determinato giorno.
    Abilita il pattern hatching multilivello e i tooltip riassuntivi sull'interfaccia Angular.
    """
    if not state.db_pool:
        return []

    # Validazione e parsing della data in un oggetto datetime.date per asyncpg
    from datetime import datetime
    try:
        pub_date = datetime.strptime(date.replace("/", "-"), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato data non valido. Usa il formato ISO YYYY-MM-DD."
        )

    query_parts = [
        """
        SELECT
            country_code,
            array_agg(DISTINCT primary_category) AS categories,
            COUNT(*) AS article_count
        FROM articles
        WHERE published_at = $1
        """
    ]
    
    params = [pub_date]
    
    if sentiment:
        params.append(sentiment)
        query_parts.append(f"AND sentiment = ${len(params)}")
        
    if relevance_level is not None:
        params.append(relevance_level)
        query_parts.append(f"AND relevance_level = ${len(params)}")

    query_parts.append("GROUP BY country_code")
    final_query = " ".join(query_parts)

    async with state.db_pool.acquire() as conn:
        rows = await conn.fetch(final_query, *params)
        
    return [dict(row) for row in rows]

from pydantic import BaseModel

class ReadStatusUpdate(BaseModel):
    is_read: bool

@app.patch("/api/articles/{article_id}/read_status")
async def update_article_read_status(article_id: int, status: ReadStatusUpdate):
    """
    Aggiorna lo stato letto/non letto di un articolo.
    """
    if not state.db_pool:
        raise HTTPException(status_code=500, detail="Database non disponibile")
        
    async with state.db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE articles SET is_read = $1, updated_at = NOW() WHERE id = $2",
            status.is_read, article_id
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Articolo non trovato")
            
    return {"status": "success", "is_read": status.is_read}
