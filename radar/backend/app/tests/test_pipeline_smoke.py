"""
Test di smoke per la pipeline backend del Radar Informativo Globale.
Verifica che i componenti core siano importabili e le strutture dati siano valide.
Include i test per la validazione degli endpoint REST di FastAPI con filtri avanzati.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg


# ─── Test 1: Importabilità del modulo principale ──────────────────────────────

def test_main_module_importable():
    """Il modulo main.py deve essere importabile senza errori di sintassi o import."""
    try:
        import app.main  # noqa: F401
    except ImportError as e:
        pytest.fail(f"Impossibile importare app.main: {e}")


# ─── Test 2: Schema Pydantic — Validazione campo obbligatorio ─────────────────

def test_geopolitical_schema_valid_article():
    """GeopoliticalArticleSchema deve accettare un articolo ben formato."""
    from app.classification.validator import GeopoliticalArticleSchema

    data = {
        "title": "Test: Nuovo impianto TSMC in Sassonia",
        "summary": "TSMC inaugura la prima fab europea. La Germania punta sulla sovranità tecnologica.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc-test",
        "country_code": "DE",
        "latitude": 51.1657,
        "longitude": 10.4515,
        "companies_involved": "TSMC, Infineon",
        "tags": "Tecnologia, Semiconduttori",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Fabbrica TSMC",
        "relevance_level": 3,
    }
    article = GeopoliticalArticleSchema(**data)
    assert article.country_code == "DE"
    assert article.primary_category == "Tecnologia"
    assert article.latitude == 51.1657


def test_geopolitical_schema_rejects_invalid_category():
    """GeopoliticalArticleSchema deve rifiutare una categoria non valida (strict)."""
    from pydantic import ValidationError
    from app.classification.validator import GeopoliticalArticleSchema

    data = {
        "title": "Articolo di test",
        "summary": "Riassunto di test.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/test-invalid",
        "country_code": "IT",
        "latitude": 41.8719,
        "longitude": 12.5674,
        "companies_involved": "Nessuno",
        "tags": "Test",
        "primary_category": "CATEGORIA_NON_ESISTENTE",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 2,
    }
    with pytest.raises(ValidationError):
        GeopoliticalArticleSchema(**data)


# ─── Test 3: Funzione strip_html ─────────────────────────────────────────────

def test_strip_html_removes_tags():
    """strip_html_tags deve rimuovere i tag HTML e decodificare le entità."""
    from app.extraction.parser import strip_html_tags

    html = "<p>Articolo <strong>importante</strong> sul &amp; mercato dei chip.</p>"
    result = strip_html_tags(html)
    assert "<p>" not in result
    assert "<strong>" not in result
    assert "&amp;" not in result
    assert "importante" in result
    assert "& mercato" in result


def test_strip_html_handles_empty_string():
    """strip_html_tags deve gestire stringhe vuote senza eccezioni."""
    from app.extraction.parser import strip_html_tags

    result = strip_html_tags("")
    assert result == ""


# ─── Test 4: Endpoint REST FastAPI ───────────────────────────────────────────

def test_health_check_endpoint():
    """Verifica che l'endpoint health ritorni 200 OK."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    with patch("app.main.lifespan") as mock_lifespan:
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "radar-backend"}


@pytest.mark.asyncio
async def test_get_articles_endpoint_success() -> None:
    """Verifica che l'endpoint get_articles risponda correttamente ed interroghi il DB applicando i filtri."""
    from fastapi.testclient import TestClient
    from app.main import app, state
    
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_conn = MagicMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    mock_conn.fetch = AsyncMock(return_value=[
        {
            "id": 1,
            "title": "Notizia Geopolitica",
            "summary": "Riassunto.",
            "published_at": "2026-06-24",
            "source_url": "https://example.com",
            "country_code": "DE",
            "latitude": 51.0,
            "longitude": 13.0,
            "primary_category": "Chip",
            "sentiment": "Positivo",
            "relevance_level": 3,
            "companies": ["TSMC"],
            "tags": ["Chip", "Sassonia"]
        }
    ])
    
    state.db_pool = mock_pool
    
    client = TestClient(app)
    response = client.get("/api/articles?date=2026-06-24&sentiment=Positivo&relevance_level=3")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Notizia Geopolitica"
    assert data[0]["companies"] == ["TSMC"]
    assert data[0]["sentiment"] == "Positivo"
    assert data[0]["relevance_level"] == 3
    
    mock_conn.fetch.assert_called_once()
    called_query = mock_conn.fetch.call_args[0][0]
    assert "a.published_at = $1" in called_query
    assert "a.sentiment = $2" in called_query
    assert "a.relevance_level = $3" in called_query


@pytest.mark.asyncio
async def test_get_countries_endpoint_success() -> None:
    """Verifica l'endpoint get_countries_summary con i filtri applicati."""
    from fastapi.testclient import TestClient
    from app.main import app, state
    
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_conn = MagicMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    mock_conn.fetch = AsyncMock(return_value=[
        {
            "country_code": "DE",
            "categories": ["Chip"],
            "article_count": 1
        }
    ])
    
    state.db_pool = mock_pool
    
    client = TestClient(app)
    response = client.get("/api/countries?date=2026-06-24&sentiment=Positivo")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_code"] == "DE"
    assert data[0]["article_count"] == 1
    
    mock_conn.fetch.assert_called_once()
    called_query = mock_conn.fetch.call_args[0][0]
    assert "country_code" in called_query
    assert "sentiment = $2" in called_query
