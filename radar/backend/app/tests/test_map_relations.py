"""Unit tests for /api/map-relations and related_countries query construction."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.api.articles_query import build_map_relations_query
from app.main import app, state


def _mock_pool() -> tuple[MagicMock, MagicMock]:
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_conn = MagicMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    return mock_pool, mock_conn


@pytest.fixture(autouse=True)
def _restore_pool():
    previous = state.db_pool
    yield
    state.db_pool = previous


def test_build_map_relations_query_basic() -> None:
    pub_date = date(2026, 7, 15)
    sql, params = build_map_relations_query(pub_date)
    
    assert "LEAST(a.country_code, r.related)" in sql
    assert "GREATEST(a.country_code, r.related)" in sql
    assert "unnest(a.related_countries)" in sql
    assert "a.country_code <> 'XX'" in sql
    assert "r.related <> 'XX'" in sql
    assert "r.related <> a.country_code" in sql
    assert params == [pub_date]


def test_build_map_relations_query_with_filters() -> None:
    pub_date = date(2026, 7, 15)
    sql, params = build_map_relations_query(
        pub_date,
        sentiment=["Positivo", "Negativo"],
        relevance_level=4,
    )
    
    assert "a.sentiment = ANY($2::text[])" in sql
    assert "a.relevance_level = $3" in sql
    assert params == [pub_date, ["Positivo", "Negativo"], 4]


def test_get_map_relations_api_success() -> None:
    mock_pool, mock_conn = _mock_pool()
    state.db_pool = mock_pool
    
    db_rows = [
        {
            "source_country": "IT",
            "target_country": "US",
            "primary_category": "Tecnologia",
            "volume": 3,
        },
        {
            "source_country": "CN",
            "target_country": "DE",
            "primary_category": "Energia",
            "volume": 1,
        }
    ]
    mock_conn.fetch = AsyncMock(return_value=db_rows)
    
    client = TestClient(app)
    response = client.get("/api/map-relations?date=2026-07-15")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["source_country"] == "IT"
    assert data[0]["target_country"] == "US"
    assert data[0]["volume"] == 3
    assert data[1]["source_country"] == "CN"
    assert data[1]["target_country"] == "DE"
    assert data[1]["volume"] == 1


def test_get_map_relations_invalid_date() -> None:
    mock_pool, mock_conn = _mock_pool()
    state.db_pool = mock_pool

    client = TestClient(app)
    response = client.get("/api/map-relations?date=2026-13-45")
    assert response.status_code == 400
    assert "ISO YYYY-MM-DD" in response.json()["detail"]
