"""
Builder SQL per lista articoli day-scoped / saved, map-summary e countries.

Companies/tags via ``LEFT JOIN LATERAL`` — mai due LEFT JOIN sibling di
``article_companies`` + ``article_tags`` nello stesso FROM (rischio cartesiano).

SoT:
    skill radar-api-contract; docs/02 API Phase 5.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional, Sequence

from fastapi import HTTPException

DEFAULT_ARTICLES_LIMIT = 50
MAX_ARTICLES_LIMIT = 100

ALLOWED_SENTIMENTS = frozenset({"Positivo", "Neutrale", "Negativo"})

# Coord finite: esclude NULL e NaN (``x = x`` falso per NaN) e fuori range geografico.
_FINITE_LAT_LON_FILTER = (
    "latitude IS NOT NULL "
    "AND longitude IS NOT NULL "
    "AND latitude = latitude "
    "AND longitude = longitude "
    "AND latitude BETWEEN -90 AND 90 "
    "AND longitude BETWEEN -180 AND 180"
)


def parse_published_date(raw: str) -> date:
    """Parse ``YYYY-MM-DD`` (accetta anche ``/``). HTTP 400 se invalida."""
    try:
        return datetime.strptime(raw.replace("/", "-"), "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Formato data non valido. Usa il formato ISO YYYY-MM-DD.",
        ) from exc


def normalize_sentiments(
    raw: Optional[str | Sequence[str]],
) -> Optional[list[str]]:
    """Normalizza query ``sentiment`` (singolo, ripetuto o CSV) a lista dedup SoT.

    Returns:
        ``None`` se assente/vuoto; altrimenti lista ordinata di valori ammessi.
    Raises:
        HTTPException 400 se compare un valore fuori da ``ALLOWED_SENTIMENTS``.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        tokens = [raw]
    else:
        tokens = list(raw)

    expanded: list[str] = []
    for token in tokens:
        expanded.extend(part.strip() for part in token.split(",") if part.strip())

    if not expanded:
        return None

    invalid = sorted({value for value in expanded if value not in ALLOWED_SENTIMENTS})
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=(
                "Sentiment non valido. Usa Positivo, Neutrale o Negativo "
                f"(ricevuto: {', '.join(invalid)})."
            ),
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for value in expanded:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def clamp_articles_limit(limit: int) -> int:
    """Clamp page size a ``[1, MAX_ARTICLES_LIMIT]`` (contratto FE ≤ 100)."""
    if limit < 1:
        return 1
    return min(limit, MAX_ARTICLES_LIMIT)


def _append_optional_filters(
    query_parts: list[str],
    params: list[Any],
    *,
    sentiment: Optional[Sequence[str]],
    relevance_level: Optional[int],
    country: Optional[str] = None,
    category: Optional[str] = None,
    column_prefix: str = "",
) -> None:
    """Appende filtri AND dinamici; il prossimo placeholder è ``len(params)+1``."""
    if country:
        params.append(country.upper())
        query_parts.append(f"AND {column_prefix}country_code = ${len(params)}")
    if category:
        params.append(category)
        query_parts.append(f"AND {column_prefix}primary_category = ${len(params)}")
    if sentiment:
        if len(sentiment) == 1:
            params.append(sentiment[0])
            query_parts.append(f"AND {column_prefix}sentiment = ${len(params)}")
        else:
            params.append(list(sentiment))
            query_parts.append(
                f"AND {column_prefix}sentiment = ANY(${len(params)}::text[])"
            )
    if relevance_level is not None:
        params.append(relevance_level)
        query_parts.append(f"AND {column_prefix}relevance_level = ${len(params)}")


def build_articles_count_query(
    pub_date: Optional[date] = None,
    *,
    sentiment: Optional[Sequence[str]] = None,
    relevance_level: Optional[int] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
    saved_only: bool = False,
) -> tuple[str, list[Any]]:
    """``COUNT(*)`` articoli filtrati (giorno e/o ``is_saved``; senza cursor)."""
    params: list[Any] = []
    parts = ["SELECT COUNT(*) FROM articles a WHERE TRUE"]
    if saved_only:
        parts.append("AND a.is_saved = TRUE")
    if pub_date is not None:
        params.append(pub_date)
        parts.append(f"AND a.published_at = ${len(params)}")
    _append_optional_filters(
        parts,
        params,
        sentiment=sentiment,
        relevance_level=relevance_level,
        country=country,
        category=category,
        column_prefix="a.",
    )
    return " ".join(parts), params


def build_articles_page_query(
    pub_date: Optional[date] = None,
    *,
    sentiment: Optional[Sequence[str]] = None,
    relevance_level: Optional[int] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
    cursor: Optional[int] = None,
    limit: int,
    saved_only: bool = False,
) -> tuple[str, list[Any]]:
    """Pagina keyset (``id DESC``, ``id < cursor`` esclusivo).

    Day-scoped se ``pub_date`` valorizzata; vault salvati se ``saved_only``.
    Companies/tags via LATERAL — niente doppio LEFT JOIN junction nel FROM.
    Returns:
        ``(sql, params)`` pronti per ``conn.fetch``.
    """
    params: list[Any] = []
    parts = [
        """
        SELECT
            a.id, a.title, a.summary, a.published_at::text AS published_at, a.source_url,
            a.country_code, a.latitude, a.longitude, a.primary_category,
            a.sentiment, a.relevance_level, a.infrastructural_entities, a.feed_title,
            a.is_read, a.is_saved, a.related_countries,
            a.feed_id, a.feed_domain, a.classification_lane, a.classified_by_model,
            a.classified_by_provider, a.was_escalated, a.pipeline_latency_ms,
            a.embedding_time_ms, a.clean_text_chars, a.clean_text_words,
            llm.prompt_tokens, llm.completion_tokens, llm.cached_prompt_tokens,
            llm.estimated_cost_usd, llm.llm_execution_time_ms, llm.llm_request_count,
            COALESCE(companies.names, '{}') AS companies_involved,
            COALESCE(tags.names, '{}') AS tags
        FROM articles a
        LEFT JOIN LATERAL (
            SELECT
                COALESCE(SUM(l.prompt_tokens), 0)::BIGINT AS prompt_tokens,
                COALESCE(SUM(l.completion_tokens), 0)::BIGINT AS completion_tokens,
                COALESCE(SUM(l.cached_prompt_tokens), 0)::BIGINT AS cached_prompt_tokens,
                COALESCE(SUM(l.estimated_cost_usd), 0)::NUMERIC AS estimated_cost_usd,
                AVG(l.execution_time_ms)::FLOAT AS llm_execution_time_ms,
                COUNT(*)::INT AS llm_request_count
            FROM llm_request_ledger l
            WHERE l.article_id = a.id
              AND l.status = 'completed'
              AND (l.purpose LIKE 'classify:%' OR l.purpose = 'classify_article')
        ) llm ON TRUE
        LEFT JOIN LATERAL (
            SELECT COALESCE(array_agg(c.name ORDER BY c.name), '{}'::text[]) AS names
            FROM article_companies ac
            JOIN companies c ON c.id = ac.company_id
            WHERE ac.article_id = a.id
        ) companies ON TRUE
        LEFT JOIN LATERAL (
            SELECT COALESCE(array_agg(t.name ORDER BY t.name), '{}'::text[]) AS names
            FROM article_tags atag
            JOIN tags t ON t.id = atag.tag_id
            WHERE atag.article_id = a.id
        ) tags ON TRUE
        WHERE TRUE
        """
    ]
    if saved_only:
        parts.append("AND a.is_saved = TRUE")
    if pub_date is not None:
        params.append(pub_date)
        parts.append(f"AND a.published_at = ${len(params)}")
    _append_optional_filters(
        parts,
        params,
        sentiment=sentiment,
        relevance_level=relevance_level,
        country=country,
        category=category,
        column_prefix="a.",
    )
    if cursor is not None:
        params.append(cursor)
        parts.append(f"AND a.id < ${len(params)}")

    params.append(limit)
    parts.append(f"ORDER BY a.id DESC LIMIT ${len(params)}")
    return " ".join(parts), params


def build_map_summary_query(
    pub_date: date,
    *,
    sentiment: Optional[Sequence[str]] = None,
    relevance_level: Optional[int] = None,
) -> tuple[str, list[Any]]:
    """Aggregato ``country_code × primary_category`` con media lat/lon solo finite."""
    params: list[Any] = [pub_date]
    finite = _FINITE_LAT_LON_FILTER
    parts = [
        f"""
        SELECT
            country_code,
            primary_category,
            COUNT(*)::int AS article_count,
            COUNT(*) FILTER (WHERE is_read)::int AS read_count,
            COALESCE(AVG(latitude) FILTER (WHERE {finite}), 0.0) AS latitude,
            COALESCE(AVG(longitude) FILTER (WHERE {finite}), 0.0) AS longitude
        FROM articles
        WHERE published_at = $1
        """
    ]
    _append_optional_filters(
        parts,
        params,
        sentiment=sentiment,
        relevance_level=relevance_level,
        column_prefix="",
    )
    parts.append("GROUP BY country_code, primary_category")
    parts.append("ORDER BY country_code, primary_category")
    return " ".join(parts), params


def build_countries_summary_query(
    pub_date: date,
    *,
    sentiment: Optional[Sequence[str]] = None,
    relevance_level: Optional[int] = None,
) -> tuple[str, list[Any]]:
    """Aggregato compat per ``country_code`` (nessun join junction)."""
    params: list[Any] = [pub_date]
    parts = [
        """
        SELECT
            country_code,
            array_agg(DISTINCT primary_category) AS categories,
            COUNT(*)::int AS article_count
        FROM articles
        WHERE published_at = $1
        """
    ]
    _append_optional_filters(
        parts,
        params,
        sentiment=sentiment,
        relevance_level=relevance_level,
        column_prefix="",
    )
    parts.append("GROUP BY country_code")
    parts.append("ORDER BY country_code")
    return " ".join(parts), params


def build_saved_summary_query(
    *,
    sentiment: Optional[Sequence[str]] = None,
    relevance_level: Optional[int] = None,
) -> tuple[str, list[Any]]:
    """Aggregato ``country_code × primary_category`` per articoli ``is_saved`` (no date)."""
    params: list[Any] = []
    finite = _FINITE_LAT_LON_FILTER
    parts = [
        f"""
        SELECT
            country_code,
            primary_category,
            COUNT(*)::int AS article_count,
            COUNT(*) FILTER (WHERE is_read)::int AS read_count,
            COALESCE(AVG(latitude) FILTER (WHERE {finite}), 0.0) AS latitude,
            COALESCE(AVG(longitude) FILTER (WHERE {finite}), 0.0) AS longitude
        FROM articles
        WHERE is_saved = TRUE
        """
    ]
    _append_optional_filters(
        parts,
        params,
        sentiment=sentiment,
        relevance_level=relevance_level,
        column_prefix="",
    )
    parts.append("GROUP BY country_code, primary_category")
    parts.append("ORDER BY country_code, primary_category")
    return " ".join(parts), params


def build_map_relations_query(
    pub_date: date,
    *,
    sentiment: Optional[Sequence[str]] = None,
    relevance_level: Optional[int] = None,
) -> tuple[str, list[Any]]:
    """Undirected relations between country_code and unnested related_countries.

    Aggregates by source_country, target_country and primary_category, and filters out:
    - self loops (related_countries = country_code)
    - country_code = XX
    - related_countries = XX
    """
    params: list[Any] = [pub_date]
    parts = [
        """
        SELECT
            LEAST(a.country_code, r.related) AS source_country,
            GREATEST(a.country_code, r.related) AS target_country,
            a.primary_category,
            COUNT(*)::int AS volume
        FROM articles a
        CROSS JOIN LATERAL unnest(a.related_countries) AS r(related)
        WHERE a.published_at = $1
          AND a.country_code <> 'XX'
          AND r.related <> 'XX'
          AND r.related <> a.country_code
        """
    ]
    _append_optional_filters(
        parts,
        params,
        sentiment=sentiment,
        relevance_level=relevance_level,
        column_prefix="a.",
    )
    parts.append("GROUP BY 1, 2, 3")
    parts.append("ORDER BY volume DESC, source_country, target_country")
    return " ".join(parts), params
