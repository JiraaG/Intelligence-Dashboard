"""
Builder SQL per lista articoli day-scoped, map-summary e countries.

Companies/tags via ``LEFT JOIN LATERAL`` — mai due LEFT JOIN sibling di
``article_companies`` + ``article_tags`` nello stesso FROM (rischio cartesiano).

SoT:
    skill radar-api-contract; docs/02 API Phase 5.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from fastapi import HTTPException

DEFAULT_ARTICLES_LIMIT = 50
MAX_ARTICLES_LIMIT = 100

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


def clamp_articles_limit(limit: int) -> int:
    """Clamp page size a ``[1, MAX_ARTICLES_LIMIT]`` (contratto FE ≤ 100)."""
    if limit < 1:
        return 1
    return min(limit, MAX_ARTICLES_LIMIT)


def _append_optional_filters(
    query_parts: list[str],
    params: list[Any],
    *,
    sentiment: Optional[str],
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
        params.append(sentiment)
        query_parts.append(f"AND {column_prefix}sentiment = ${len(params)}")
    if relevance_level is not None:
        params.append(relevance_level)
        query_parts.append(f"AND {column_prefix}relevance_level = ${len(params)}")


def build_articles_count_query(
    pub_date: date,
    *,
    sentiment: Optional[str] = None,
    relevance_level: Optional[int] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
) -> tuple[str, list[Any]]:
    """``COUNT(*)`` articoli filtrati di un solo giorno (senza cursor)."""
    params: list[Any] = [pub_date]
    parts = ["SELECT COUNT(*) FROM articles a WHERE a.published_at = $1"]
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
    pub_date: date,
    *,
    sentiment: Optional[str] = None,
    relevance_level: Optional[int] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
    cursor: Optional[int] = None,
    limit: int,
) -> tuple[str, list[Any]]:
    """Pagina keyset di un giorno calendario (``id DESC``, ``id < cursor`` esclusivo).

    Companies/tags via LATERAL — niente doppio LEFT JOIN junction nel FROM.
    Returns:
        ``(sql, params)`` pronti per ``conn.fetch``.
    """
    params: list[Any] = [pub_date]
    parts = [
        """
        SELECT
            a.id, a.title, a.summary, a.published_at::text AS published_at, a.source_url,
            a.country_code, a.latitude, a.longitude, a.primary_category,
            a.sentiment, a.relevance_level, a.infrastructural_entities, a.feed_title,
            a.is_read,
            COALESCE(companies.names, '{}') AS companies_involved,
            COALESCE(tags.names, '{}') AS tags
        FROM articles a
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
        WHERE a.published_at = $1
        """
    ]
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
    sentiment: Optional[str] = None,
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
    sentiment: Optional[str] = None,
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
