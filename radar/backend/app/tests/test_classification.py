import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.classification.client import (
    ClassificationClient,
    ErrorClass,
    build_gemini_response_schema,
    classify_provider_error,
    extract_retry_after_seconds,
    sanitize_gemini_response_schema,
)
from app.classification.quota import compute_day_window
from app.classification.validator import GeopoliticalArticleSchema
from app.core.config import ConfigError


def _client_with_mock_quota() -> tuple[ClassificationClient, AsyncMock]:
    quota = AsyncMock()
    quota.reserve = AsyncMock(side_effect=[1, 2, 3, 4, 5, 6, 7, 8])
    quota.complete = AsyncMock()
    quota.release = AsyncMock()
    quota.fail = AsyncMock()
    client = ClassificationClient(quota=quota)
    return client, quota


# ─── Tests per lo Schema Pydantic ─────────────────────────────────────────────

def test_gemini_response_schema_strips_additional_properties() -> None:
    """Gemini rejects additionalProperties / additional_properties in response_schema."""
    raw = GeopoliticalArticleSchema.model_json_schema()
    assert "additionalProperties" in raw
    cleaned = build_gemini_response_schema()
    blob = json.dumps(cleaned)
    assert "additionalProperties" not in blob
    assert "additional_properties" not in blob
    assert "properties" in cleaned
    # Nested unsupported keys must also be removed.
    nested = sanitize_gemini_response_schema(
        {"type": "object", "additional_properties": False, "properties": {"a": {"additionalProperties": False}}}
    )
    assert "additional_properties" not in nested
    assert "additionalProperties" not in nested["properties"]["a"]


def test_schema_valid_article() -> None:
    """Verifica che GeopoliticalArticleSchema accetti e convalidi dati corretti."""
    data = {
        "title": "TSMC inaugura la prima fab a Dresda",
        "summary": "TSMC avvia la costruzione di un nuovo impianto da 10 miliardi in Germania. L'iniziativa punta a rafforzare l'indipendenza strategica europea.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc-germany",
        "country_code": "DE",
        "latitude": 51.0504,
        "longitude": 13.7373,
        "companies_involved": "TSMC, Infineon",
        "tags": "Tecnologia, Semiconduttori, Germania",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Fabbrica Dresda",
        "relevance_level": 4,
    }

    article = GeopoliticalArticleSchema(**data)
    assert article.country_code == "DE"
    assert article.primary_category == "Tecnologia"
    assert article.sentiment == "Positivo"
    assert article.relevance_level == 4
    assert "TSMC" in article.companies_involved


def test_schema_rejects_invalid_category() -> None:
    """Verifica che categorie non ammesse vengano rifiutate (strict, no coerce)."""
    data = {
        "title": "Titolo",
        "summary": "Riassunto.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com",
        "country_code": "IT",
        "latitude": 41.87,
        "longitude": 12.56,
        "companies_involved": "Nessuno",
        "tags": "Tag",
        "primary_category": "CATEGORIA_INVENTATA",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 1,
    }
    with pytest.raises(ValidationError):
        GeopoliticalArticleSchema(**data)


def test_schema_rejects_invalid_relevance() -> None:
    """Verifica che lo schema rifiuti relevance_level di tipo non intero."""
    data = {
        "title": "Titolo",
        "summary": "Riassunto.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com",
        "country_code": "IT",
        "latitude": 41.87,
        "longitude": 12.56,
        "companies_involved": "Nessuno",
        "tags": "Tag",
        "primary_category": "Infrastrutture",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "relevance_level": "alto",
    }
    with pytest.raises(ValidationError):
        GeopoliticalArticleSchema(**data)


def test_day_window_half_open_utc() -> None:
    """RPD usa [day_start, next_day) in timezone — non date(created_at)=CURRENT_DATE."""
    now = datetime(2026, 7, 14, 22, 30, tzinfo=timezone.utc)
    start, end = compute_day_window(now, timezone.utc)
    assert start == datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)
    assert start <= now < end


def test_classify_provider_error_policy() -> None:
    from google.genai import errors as genai_errors

    assert classify_provider_error(TimeoutError("deadline")) == ErrorClass.RETRYABLE
    assert classify_provider_error(ConfigError("bad")) == ErrorClass.FATAL

    err_429 = genai_errors.APIError(429, {"error": {"message": "rate"}})
    assert classify_provider_error(err_429) == ErrorClass.RETRYABLE

    err_401 = genai_errors.APIError(401, {"error": {"message": "auth"}})
    assert classify_provider_error(err_401) == ErrorClass.FATAL

    err_404 = genai_errors.APIError(404, {"error": {"message": "model not found"}})
    assert classify_provider_error(err_404) == ErrorClass.FATAL


def test_extract_retry_after_header() -> None:
    from google.genai import errors as genai_errors

    exc = genai_errors.APIError(429, {"error": {"message": "rate"}})
    exc.response = MagicMock()
    exc.response.headers = {"Retry-After": "12"}
    assert extract_retry_after_seconds(exc) == 12.0


# ─── Tests per il Client e i Flussi di Fallback/Correzione ───────────────────

@pytest.mark.asyncio
async def test_client_requires_pool_or_quota() -> None:
    with pytest.raises(ValueError, match="pool"):
        ClassificationClient()


@pytest.mark.asyncio
async def test_client_classify_success() -> None:
    """Verifica il successo dell'estrazione al primo tentativo con dati corretti."""
    client, quota = _client_with_mock_quota()

    mock_gen_response = MagicMock()
    mock_gen_response.text = json.dumps({
        "title": "Nuova fab TSMC",
        "summary": "TSMC apre a Dresda.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc",
        "country_code": "DE",
        "latitude": 51.0,
        "longitude": 13.0,
        "companies_involved": "TSMC",
        "tags": "Tecnologia",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 3,
    })
    mock_gen_response.usage_metadata = MagicMock(total_token_count=1200)

    with patch.object(client, "_generate_content", new_callable=AsyncMock) as mock_gen, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_gen.return_value = mock_gen_response

        article = await client.classify_article(
            title="Nuova fab TSMC",
            content="Contenuto dell'articolo",
            url="https://example.com/tsmc",
            date="2026-06-24",
        )

        assert article.primary_category == "Tecnologia"
        assert article.country_code == "DE"
        assert article.relevance_level == 3
        assert mock_gen.call_count == 1
        quota.reserve.assert_awaited()
        quota.complete.assert_awaited_once_with(1, 1200)


@pytest.mark.asyncio
async def test_client_classify_retry_success() -> None:
    """Verifica che in caso di errore di validazione il Correction Loop effettui il tentativo di riparazione."""
    client, quota = _client_with_mock_quota()

    bad_response = MagicMock()
    bad_response.text = json.dumps({
        "title": "Nuova fab TSMC",
        "summary": "TSMC apre.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc",
        "latitude": 51.0,
        "longitude": 13.0,
        "companies_involved": "Nessuno",
        "tags": "Tecnologia",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 3,
    })
    bad_response.usage_metadata = MagicMock(total_token_count=800)

    good_response = MagicMock()
    good_response.text = json.dumps({
        "title": "Nuova fab TSMC",
        "summary": "TSMC apre.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc",
        "country_code": "DE",
        "latitude": 51.0,
        "longitude": 13.0,
        "companies_involved": "Nessuno",
        "tags": "Tecnologia",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 3,
    })
    good_response.usage_metadata = MagicMock(total_token_count=900)

    with patch.object(client, "_generate_content", new_callable=AsyncMock) as mock_gen, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_gen.side_effect = [bad_response, good_response]

        article = await client.classify_article(
            title="Nuova fab TSMC",
            content="Contenuto dell'articolo",
            url="https://example.com/tsmc",
            date="2026-06-24",
        )

        assert mock_gen.call_count == 2
        assert article.country_code == "DE"
        assert quota.reserve.await_count == 2
        assert quota.complete.await_count == 2


@pytest.mark.asyncio
async def test_client_classify_fallback_after_double_error() -> None:
    """Verifica che in caso di fallimenti continuati l'estrazione non crashi e ritorni il fallback."""
    client, quota = _client_with_mock_quota()

    bad_response = MagicMock()
    bad_response.text = "{'invalid_json': true}"
    bad_response.usage_metadata = None

    with patch.object(client, "_generate_content", new_callable=AsyncMock) as mock_gen, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_gen.side_effect = [bad_response] * 4

        article = await client.classify_article(
            title="Titolo originale",
            content="Contenuto dell'articolo",
            url="https://example.com/test",
            date="2026-06-24",
        )

        assert mock_gen.call_count == 4
        assert article.country_code == "XX"
        assert article.primary_category == "Infrastrutture"
        assert article.latitude == 0.0
        assert article.longitude == 0.0
        assert article.relevance_level == 1
        assert quota.reserve.await_count == 4


@pytest.mark.asyncio
async def test_client_fatal_auth_fails_fast() -> None:
    """Auth errors must not burn all correction attempts."""
    client, quota = _client_with_mock_quota()
    from google.genai import errors as genai_errors

    with patch.object(client, "_generate_content", new_callable=AsyncMock) as mock_gen, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_gen.side_effect = genai_errors.APIError(401, {"error": {"message": "bad key"}})

        article = await client.classify_article(
            title="Auth fail",
            content="x",
            url="https://example.com/a",
            date="2026-06-24",
        )

        assert mock_gen.call_count == 1
        assert article.country_code == "XX"
        quota.fail.assert_awaited()
