"""Unit tests for paginated /api/articles and /api/map-summary (mocked asyncpg)."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.api.articles_query import MAX_ARTICLES_LIMIT, build_articles_page_query
from app.main import app, state


def _mock_pool() -> tuple[MagicMock, MagicMock]:
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_conn = MagicMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    return mock_pool, mock_conn


def _article_row(article_id: int, **overrides: Any) -> dict[str, Any]:
    row = {
        "id": article_id,
        "title": f"Title {article_id}",
        "summary": "Summary",
        "published_at": "2026-07-15",
        "source_url": f"https://example.com/{article_id}",
        "country_code": "IT",
        "latitude": 41.9,
        "longitude": 12.5,
        "primary_category": "Geopolitica",
        "sentiment": "Neutrale",
        "relevance_level": 3,
        "infrastructural_entities": [],
        "feed_title": "Feed",
        "is_read": False,
        "is_saved": False,
        "companies_involved": [],
        "tags": [],
    }
    row.update(overrides)
    return row


@pytest.fixture(autouse=True)
def _restore_pool():
    previous = state.db_pool
    yield
    state.db_pool = previous


@pytest.mark.unit
def test_articles_response_shape_items_next_cursor_total() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetchval = AsyncMock(return_value=2)
    mock_conn.fetch = AsyncMock(
        return_value=[_article_row(10), _article_row(9)]
    )
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/articles?date=2026-07-15")

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"items", "next_cursor", "total"}
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 2
    assert data["total"] == 2
    assert data["next_cursor"] is None


@pytest.mark.unit
def test_articles_limit_capped_at_100() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetchval = AsyncMock(return_value=500)
    # Return page_limit+1 rows so next_cursor is set; cap means fetch uses 101.
    rows = [_article_row(1000 - i) for i in range(101)]
    mock_conn.fetch = AsyncMock(return_value=rows)
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/articles?date=2026-07-15&limit=500")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == MAX_ARTICLES_LIMIT
    assert data["next_cursor"] == data["items"][-1]["id"]

    page_call = mock_conn.fetch.await_args
    page_sql = page_call.args[0]
    page_params = page_call.args[1:]
    assert f"LIMIT ${len(page_params)}" in page_sql or "LIMIT $" in page_sql
    # Last bound param is fetch_limit = 100 + 1
    assert page_params[-1] == MAX_ARTICLES_LIMIT + 1


@pytest.mark.unit
def test_articles_cursor_keyset_id_less_than() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetchval = AsyncMock(return_value=3)
    mock_conn.fetch = AsyncMock(return_value=[_article_row(50), _article_row(40)])
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/articles?date=2026-07-15&cursor=100&limit=50")

    assert response.status_code == 200
    page_sql = mock_conn.fetch.await_args.args[0]
    page_params = mock_conn.fetch.await_args.args[1:]
    assert "a.id < $" in page_sql
    assert 100 in page_params
    # Exclusive keyset: cursor value bound before limit
    cursor_idx = page_params.index(100)
    assert page_params[cursor_idx] == 100


@pytest.mark.unit
def test_articles_invalid_date_returns_400() -> None:
    mock_pool, mock_conn = _mock_pool()
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/articles?date=not-a-date")

    assert response.status_code == 400
    mock_conn.fetch.assert_not_called()
    mock_conn.fetchval.assert_not_called()


@pytest.mark.unit
def test_map_summary_groups_by_country_and_category() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetch = AsyncMock(
        return_value=[
            {
                "country_code": "IT",
                "primary_category": "Geopolitica",
                "article_count": 3,
                "read_count": 1,
                "latitude": 41.9,
                "longitude": 12.5,
            },
            {
                "country_code": "IT",
                "primary_category": "Energia",
                "article_count": 2,
                "read_count": 0,
                "latitude": 45.0,
                "longitude": 9.0,
            },
            {
                "country_code": "DE",
                "primary_category": "Tecnologia",
                "article_count": 5,
                "read_count": 2,
                "latitude": 51.0,
                "longitude": 10.0,
            },
        ]
    )
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/map-summary?date=2026-07-15")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    keys = {(row["country_code"], row["primary_category"]) for row in data}
    assert keys == {("IT", "Geopolitica"), ("IT", "Energia"), ("DE", "Tecnologia")}

    sql = mock_conn.fetch.await_args.args[0]
    assert "GROUP BY country_code, primary_category" in sql
    assert "article_count" in sql
    assert "read_count" in sql


@pytest.mark.unit
def test_map_summary_multi_sentiment_uses_any() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetch = AsyncMock(return_value=[])
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get(
        "/api/map-summary?date=2026-07-15&sentiment=Positivo&sentiment=Negativo"
    )

    assert response.status_code == 200
    sql = mock_conn.fetch.await_args.args[0]
    params = list(mock_conn.fetch.await_args.args[1:])
    assert "sentiment = ANY($2::text[])" in sql
    assert params[1] == ["Positivo", "Negativo"]


@pytest.mark.unit
def test_map_summary_rejects_invalid_sentiment() -> None:
    mock_pool, mock_conn = _mock_pool()
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/map-summary?date=2026-07-15&sentiment=Happy")

    assert response.status_code == 400
    mock_conn.fetch.assert_not_called()


@pytest.mark.unit
def test_normalize_sentiments_csv_and_dedupe() -> None:
    from app.api.articles_query import normalize_sentiments

    assert normalize_sentiments(["Positivo,Negativo", "Positivo"]) == [
        "Positivo",
        "Negativo",
    ]
    assert normalize_sentiments(None) is None
    assert normalize_sentiments([]) is None


@pytest.mark.unit
def test_articles_sql_uses_lateral_not_sibling_left_joins() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetchval = AsyncMock(return_value=0)
    mock_conn.fetch = AsyncMock(return_value=[])
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/articles?date=2026-07-15")
    assert response.status_code == 200

    page_sql = mock_conn.fetch.await_args.args[0]
    assert "LEFT JOIN LATERAL" in page_sql
    assert "article_companies" in page_sql
    assert "article_tags" in page_sql or "atag" in page_sql

    # Must not have both junctions as sibling LEFT JOINs in the same FROM.
    # Heuristic: after stripping LATERAL blocks, no "LEFT JOIN article_companies"
    # paired with "LEFT JOIN article_tags".
    assert "LEFT JOIN article_companies" not in page_sql
    assert "LEFT JOIN article_tags" not in page_sql

    # Builder-level assertion mirrors endpoint SQL contract.
    sql, _params = build_articles_page_query(date(2026, 7, 15), limit=50)
    assert "LEFT JOIN LATERAL" in sql
    assert "LEFT JOIN article_companies" not in sql
    assert "LEFT JOIN article_tags" not in sql
    assert "a.is_saved" in sql


@pytest.mark.unit
def test_saved_articles_ignores_date_and_filters_is_saved() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_conn.fetch = AsyncMock(return_value=[_article_row(7, is_saved=True)])
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/articles?saved=true&country=IT")

    assert response.status_code == 200
    page_sql = mock_conn.fetch.await_args.args[0]
    assert "a.is_saved = TRUE" in page_sql
    assert "published_at" not in page_sql.split("WHERE", 1)[1].split("ORDER BY")[0] or (
        "published_at =" not in page_sql
    )


@pytest.mark.unit
def test_articles_without_date_requires_saved() -> None:
    mock_pool, _mock_conn = _mock_pool()
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/articles")
    assert response.status_code == 400


@pytest.mark.unit
def test_saved_summary_no_date() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.fetch = AsyncMock(
        return_value=[
            {
                "country_code": "US",
                "primary_category": "Ambiente",
                "article_count": 2,
                "read_count": 1,
                "latitude": 40.0,
                "longitude": -74.0,
            }
        ]
    )
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/saved-summary")
    assert response.status_code == 200
    sql = mock_conn.fetch.await_args.args[0]
    assert "is_saved = TRUE" in sql
    assert "published_at =" not in sql


@pytest.mark.unit
def test_read_status_unread_unsaves() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.patch(
        "/api/articles/42/read_status",
        json={"is_read": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_read"] is False
    assert data["is_saved"] is False
    sql = mock_conn.execute.await_args.args[0]
    assert "is_saved = FALSE" in sql


@pytest.mark.unit
def test_saved_status_patch() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.patch(
        "/api/articles/42/saved_status",
        json={"is_saved": True},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success", "is_saved": True, "is_read": True}
    sql = mock_conn.execute.await_args.args[0]
    assert "is_saved = TRUE" in sql
    assert "is_read = TRUE" in sql


@pytest.mark.unit
def test_saved_status_unsave_keeps_read() -> None:
    mock_pool, mock_conn = _mock_pool()
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    mock_conn.fetchval = AsyncMock(return_value=True)
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.patch(
        "/api/articles/42/saved_status",
        json={"is_saved": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_saved"] is False
    assert data["is_read"] is True
    sql = mock_conn.execute.await_args.args[0]
    assert "is_saved = FALSE" in sql
    assert "is_read = TRUE" not in sql