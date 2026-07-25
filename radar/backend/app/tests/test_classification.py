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
from app.classification.validator import GeopoliticalArticleSchema, get_fallback_article
from app.core.config import ConfigError


def _client_with_mock_quota() -> tuple[ClassificationClient, AsyncMock]:
    """Gemini-only client; routing off so tests non dipendono da .env live."""
    from app.core.llm_lanes import LlmLaneConfig

    quota = AsyncMock()
    quota.reserve = AsyncMock(side_effect=[1, 2, 3, 4, 5, 6, 7, 8])
    quota.complete = AsyncMock()
    quota.release = AsyncMock()
    quota.fail = AsyncMock()
    client = ClassificationClient(quota=quota)
    client._routing_mode = "off"
    client._shadow = False
    client._escalate = False
    client._complex_unavailable = True
    client._simple = LlmLaneConfig(
        lane="simple",
        provider="gemini",
        model="gemini-2.5-flash",
        api_key="test-key",
        base_url="",
        rpm=30,
        tpm=0,
        rpd=100,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.0,
        timeout=60.0,
        reasoning_effort="high",
        fallbacks=(),
    )
    client._simple_provider = "gemini"
    client._simple_model = "gemini-2.5-flash"
    client.model = "gemini-2.5-flash"
    if client.client is None:
        client.client = MagicMock()
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
        "related_countries": "Nessuno",
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
        "related_countries": "Nessuno",
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
        "related_countries": "Nessuno",
        "relevance_level": "alto",
    }
    with pytest.raises(ValidationError):
        GeopoliticalArticleSchema(**data)


def test_schema_first_tag_validation() -> None:
    """Verifica che il primo tag debba corrispondere a primary_category e che il fallback sia valido."""
    base_data = {
        "title": "Titolo",
        "summary": "Riassunto.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com",
        "country_code": "IT",
        "latitude": 41.87,
        "longitude": 12.56,
        "companies_involved": "Nessuno",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "related_countries": "Nessuno",
        "relevance_level": 1,
    }

    # Match OK
    data_ok = {**base_data, "tags": "Tecnologia, Semiconduttori", "primary_category": "Tecnologia"}
    article = GeopoliticalArticleSchema(**data_ok)
    assert article.primary_category == "Tecnologia"

    # Mismatch primo tag REJECT
    data_mismatch = {**base_data, "tags": "Geopolitica, Tecnologia", "primary_category": "Tecnologia"}
    with pytest.raises(ValidationError, match="primo tag"):
        GeopoliticalArticleSchema(**data_mismatch)

    # Empty tags or Nessuno REJECT
    data_empty = {**base_data, "tags": "Nessuno", "primary_category": "Tecnologia"}
    with pytest.raises(ValidationError, match="tags deve iniziare con primary_category"):
        GeopoliticalArticleSchema(**data_empty)

    # Fallback get_fallback_article ancora valido (tags=primary)
    fallback = get_fallback_article("Titolo fallback", "https://example.com/fallback", "2026-07-16")
    assert fallback.primary_category == "Infrastrutture"
    assert fallback.tags == "Infrastrutture"
    assert fallback.companies_involved == "Nessuno"
    assert fallback.infrastructural_entities == "Nessuno"
    assert fallback.related_countries == "Nessuno"


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
    err_rpm = genai_errors.APIError(
        429,
        {"error": {"message": "429 RESOURCE_EXHAUSTED. You exceeded your current quota"}},
    )
    assert classify_provider_error(err_rpm) == ErrorClass.RETRYABLE
    err_rpd = genai_errors.APIError(
        429,
        {"error": {"message": "daily quota exceeded / requests per day"}},
    )
    assert classify_provider_error(err_rpd) == ErrorClass.HARD_COOLDOWN
    err_free_tier = genai_errors.APIError(
        429,
        {
            "error": {
                "message": (
                    "Quota exceeded for metric: generativelanguage.googleapis.com/"
                    "generate_content_free_tier_requests, limit: 500, model: gemini-3.1-flash-lite"
                )
            }
        },
    )
    assert classify_provider_error(err_free_tier) == ErrorClass.HARD_COOLDOWN

    err_401 = genai_errors.APIError(401, {"error": {"message": "auth"}})
    assert classify_provider_error(err_401) == ErrorClass.FATAL

    err_404 = genai_errors.APIError(404, {"error": {"message": "model not found"}})
    assert classify_provider_error(err_404) == ErrorClass.HARD_COOLDOWN


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

        res = await client.classify_article(
            title="Nuova fab TSMC",
            content="Contenuto dell'articolo",
            url="https://example.com/tsmc",
            date="2026-06-24",
        )
        article = res.article

        assert article.primary_category == "Tecnologia"
        assert article.country_code == "DE"
        assert article.relevance_level == 3
        assert mock_gen.call_count == 1
        quota.reserve.assert_awaited()
        quota.complete.assert_awaited_once()


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

        res = await client.classify_article(
            title="Nuova fab TSMC",
            content="Contenuto dell'articolo",
            url="https://example.com/tsmc",
            date="2026-06-24",
        )
        article = res.article

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

        res = await client.classify_article(
            title="Titolo originale",
            content="Contenuto dell'articolo",
            url="https://example.com/test",
            date="2026-06-24",
        )
        article = res.article

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

        res = await client.classify_article(
            title="Auth fail",
            content="x",
            url="https://example.com/a",
            date="2026-06-24",
        )
        article = res.article

        assert mock_gen.call_count == 1
        assert article.country_code == "XX"
        quota.fail.assert_awaited()


@pytest.mark.asyncio
async def test_hard_cooldown_switches_to_fallback_model() -> None:
    """404 model → cooldown primary; secondary Gemini succeeds."""
    from google.genai import errors as genai_errors

    from app.core.llm_lanes import LlmLaneConfig

    client, quota = _client_with_mock_quota()
    client._simple = LlmLaneConfig(
        lane="simple",
        provider="gemini",
        model="gemini-primary",
        api_key="test-key",
        base_url="",
        rpm=10,
        tpm=0,
        rpd=100,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.0,
        timeout=60.0,
        reasoning_effort="high",
        fallbacks=("gemini-secondary",),
    )
    client._simple_provider = "gemini"
    client._simple_model = "gemini-primary"
    client.model = "gemini-primary"

    with patch.object(client, "_generate_content", new_callable=AsyncMock) as mock_gen, patch(
        "asyncio.sleep", new_callable=AsyncMock
    ):
        good = MagicMock()
        good.text = json.dumps({
            "title": "OK",
            "summary": "Sommario lungo abbastanza per lo schema minimo.",
            "published_at": "2026-06-24",
            "source_url": "https://example.com/ok",
            "country_code": "DE",
            "latitude": 51.0,
            "longitude": 13.0,
            "companies_involved": "Nessuno",
            "tags": "Tecnologia",
            "primary_category": "Tecnologia",
            "sentiment": "Neutrale",
            "infrastructural_entities": "Nessuno",
            "relevance_level": 2,
        })
        good.usage_metadata = MagicMock(total_token_count=100)
        mock_gen.side_effect = [
            genai_errors.APIError(404, {"error": {"message": "model not found"}}),
            good,
        ]

        res = await client.classify_article(
            title="Switch model",
            content="body",
            url="https://example.com/ok",
            date="2026-06-24",
        )
        article = res.article
        assert article.country_code == "DE"
        assert mock_gen.call_count == 2
        assert await client.cooldown.is_cooling_down("gemini", "gemini-primary") is True


@pytest.mark.asyncio
async def test_short_429_does_not_write_cooldown() -> None:
    from google.genai import errors as genai_errors

    client, quota = _client_with_mock_quota()
    err = genai_errors.APIError(429, {"error": {"message": "rate"}})
    err.response = MagicMock()
    err.response.headers = {"Retry-After": "1"}

    good = MagicMock()
    good.text = json.dumps({
        "title": "OK",
        "summary": "Sommario lungo abbastanza per lo schema minimo.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/ok",
        "country_code": "IT",
        "latitude": 41.0,
        "longitude": 12.0,
        "companies_involved": "Nessuno",
        "tags": "Geopolitica",
        "primary_category": "Geopolitica",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 2,
    })
    good.usage_metadata = MagicMock(total_token_count=50)

    with patch.object(client, "_generate_content", new_callable=AsyncMock) as mock_gen, patch(
        "asyncio.sleep", new_callable=AsyncMock
    ):
        mock_gen.side_effect = [err, good]
        res = await client.classify_article(
            title="Retry after",
            content="body",
            url="https://example.com/ok",
            date="2026-06-24",
        )
        article = res.article
        assert article.country_code == "IT"
        assert await client.cooldown.is_cooling_down("gemini", client.model) is False


def test_chain_for_borderline_uses_complex_lane() -> None:
    """BORDERLINE must route to COMPLEX chain (thinking high), not SIMPLE."""
    from app.classification.complexity import Lane
    from app.core.llm_lanes import LlmLaneConfig

    client, _quota = _client_with_mock_quota()
    client._routing_mode = "complexity"
    client._complex_unavailable = False
    client._simple = LlmLaneConfig(
        lane="simple",
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        rpm=0,
        tpm=0,
        rpd=0,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.28,
        timeout=60.0,
        reasoning_effort="none",
        fallbacks=(),
    )
    client._complex = LlmLaneConfig(
        lane="complex",
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        rpm=0,
        tpm=0,
        rpd=0,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.28,
        timeout=60.0,
        reasoning_effort="high",
        fallbacks=(),
    )
    client._simple_provider = "deepseek"
    client._simple_model = "deepseek-v4-flash"
    client._complex_provider = "deepseek"
    client._complex_model = "deepseek-v4-flash"

    border = client._chain_for(Lane.BORDERLINE, force_simple=False)
    simple = client._chain_for(Lane.SIMPLE, force_simple=False)
    complex_chain = client._chain_for(Lane.COMPLEX, force_simple=False)

    assert border[0].quota_lane == "complex"
    assert simple[0].reasoning_effort == "none"
    assert simple[0].quota_lane == "simple"
    assert complex_chain[0].reasoning_effort == "high"


def test_chain_for_borderline_effort_split_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """When LLM_BORDERLINE_REASONING_EFFORT=none, BORDERLINE chain uses effort 'none' while COMPLEX uses 'high'."""
    from app.classification.complexity import Lane
    from app.core.llm_lanes import LlmLaneConfig

    monkeypatch.setattr("app.classification.client.LLM_BORDERLINE_REASONING_EFFORT", "none")

    client, _quota = _client_with_mock_quota()
    client._routing_mode = "complexity"
    client._complex_unavailable = False
    client._simple = LlmLaneConfig(
        lane="simple",
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        rpm=0,
        tpm=0,
        rpd=0,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.28,
        timeout=60.0,
        reasoning_effort="none",
        fallbacks=(),
    )
    client._complex = LlmLaneConfig(
        lane="complex",
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        rpm=0,
        tpm=0,
        rpd=0,
        budget_usd_day=0.0,
        usd_per_1m_tokens=0.28,
        timeout=60.0,
        reasoning_effort="high",
        fallbacks=(),
    )
    client._simple_provider = "deepseek"
    client._simple_model = "deepseek-v4-flash"
    client._complex_provider = "deepseek"
    client._complex_model = "deepseek-v4-flash"

    border = client._chain_for(Lane.BORDERLINE, force_simple=False)
    complex_chain = client._chain_for(Lane.COMPLEX, force_simple=False)

    assert border[0].reasoning_effort == "none"
    assert border[0].quota_lane == "complex"
    assert border[0].identity == ("deepseek", "deepseek-v4-flash", "none")
    assert complex_chain[0].reasoning_effort == "high"
    assert complex_chain[0].quota_lane == "complex"
    assert complex_chain[0].identity == ("deepseek", "deepseek-v4-flash", "high")


@pytest.mark.asyncio
async def test_borderline_escalation_triggers_high_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """C1: Escalation on BORDERLINE effort 'none' triggers a second run with escalate_ref effort 'high'."""
    from app.classification.complexity import Lane
    from app.classification.client import ClassificationResult
    from app.classification.validator import get_fallback_article
    from app.core.llm_lanes import LlmLaneConfig

    monkeypatch.setattr("app.classification.client.LLM_BORDERLINE_REASONING_EFFORT", "none")

    client, _quota = _client_with_mock_quota()
    client._routing_mode = "complexity"
    client._complex_unavailable = False
    client._escalate = True
    client._shadow = False
    client._simple = LlmLaneConfig(
        lane="simple", provider="deepseek", model="deepseek-v4-flash", api_key="sk-test",
        base_url="https://api.deepseek.com", rpm=0, tpm=0, rpd=0, budget_usd_day=0.0,
        usd_per_1m_tokens=0.28, timeout=60.0, reasoning_effort="none", fallbacks=(),
    )
    client._complex = LlmLaneConfig(
        lane="complex", provider="deepseek", model="deepseek-v4-flash", api_key="sk-test",
        base_url="https://api.deepseek.com", rpm=0, tpm=0, rpd=0, budget_usd_day=0.0,
        usd_per_1m_tokens=0.28, timeout=60.0, reasoning_effort="high", fallbacks=(),
    )

    recorded_runs: list[tuple[str, str, str, bool]] = []

    async def mock_run(ref, *, title, content, url, date, lane, max_attempts=None, miniflux_entry_id=None, was_escalated=False):
        recorded_runs.append((ref.provider, ref.model, ref.reasoning_effort, was_escalated))
        if not was_escalated:
            # First attempt fails with escalate outcome (validation fails >= 2)
            return None, "escalate"
        else:
            # Escalated attempt succeeds
            good = get_fallback_article(title, url, date)
            return ClassificationResult(
                article=good,
                classification_lane=ref.quota_lane,
                classified_by_model=ref.model,
                classified_by_provider=ref.provider,
                was_escalated=True,
            ), "ok"

    monkeypatch.setattr(client, "_run_model_attempts", mock_run)
    monkeypatch.setattr("app.classification.client.score_complexity", lambda title, content: type("C", (), {"lane": Lane.BORDERLINE, "families": {"G"}, "score": 25})())

    res = await client.classify_article(
        title="Multi-country crisis in Berlin and Paris",
        content="Long body content",
        url="https://example.com/borderline",
        date="2026-07-22",
    )

    assert res.was_escalated is True
    assert res.classified_by_model == "deepseek-v4-flash"
    assert len(recorded_runs) == 2
    # 1st attempt: BORDERLINE effort none, was_escalated=False
    assert recorded_runs[0] == ("deepseek", "deepseek-v4-flash", "none", False)
    # 2nd attempt: Escalated primary COMPLEX effort high, was_escalated=True
    assert recorded_runs[1] == ("deepseek", "deepseek-v4-flash", "high", True)


def test_borderline_default_unset_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """C2: Default BORDERLINE effort is 'high' when unset/default, matching COMPLEX effort."""
    from app.classification.complexity import Lane
    from app.core.llm_lanes import LlmLaneConfig

    monkeypatch.setattr("app.classification.client.LLM_BORDERLINE_REASONING_EFFORT", "high")

    client, _quota = _client_with_mock_quota()
    client._routing_mode = "complexity"
    client._complex_unavailable = False
    client._simple = LlmLaneConfig(
        lane="simple", provider="deepseek", model="deepseek-v4-flash", api_key="sk-test",
        base_url="https://api.deepseek.com", rpm=0, tpm=0, rpd=0, budget_usd_day=0.0,
        usd_per_1m_tokens=0.28, timeout=60.0, reasoning_effort="none", fallbacks=(),
    )
    client._complex = LlmLaneConfig(
        lane="complex", provider="deepseek", model="deepseek-v4-flash", api_key="sk-test",
        base_url="https://api.deepseek.com", rpm=0, tpm=0, rpd=0, budget_usd_day=0.0,
        usd_per_1m_tokens=0.28, timeout=60.0, reasoning_effort="high", fallbacks=(),
    )

    border = client._chain_for(Lane.BORDERLINE, force_simple=False)
    complex_chain = client._chain_for(Lane.COMPLEX, force_simple=False)

    assert border[0].reasoning_effort == "high"
    assert border[0].identity == complex_chain[0].identity


def test_extract_usage_tokens_deepseek_and_openai() -> None:
    """M1: Test estrazione token usage con prompt_cache_hit_tokens per DeepSeek e fallback OpenAI."""
    from app.classification.client import extract_usage_tokens

    # DeepSeek top-level prompt_cache_hit_tokens
    deepseek_usage = {
        "prompt_tokens": 1200,
        "completion_tokens": 150,
        "prompt_cache_hit_tokens": 1024,
        "prompt_cache_miss_tokens": 176,
    }
    p, c, cached = extract_usage_tokens(deepseek_usage, "deepseek")
    assert p == 1200
    assert c == 150
    assert cached == 1024

    # OpenAI-shaped details
    openai_usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 200,
        "prompt_tokens_details": {"cached_tokens": 512},
    }
    p, c, cached = extract_usage_tokens(openai_usage, "openai")
    assert p == 1000
    assert c == 200
    assert cached == 512

    # Usage senza cache (cached deve essere None, NON 0)
    nocache_usage = {
        "prompt_tokens": 800,
        "completion_tokens": 100,
    }
    p, c, cached = extract_usage_tokens(nocache_usage, "deepseek")
    assert p == 800
    assert c == 100
    assert cached is None

    # Response vuoto
    assert extract_usage_tokens(None, "deepseek") == (None, None, None)


def test_borderline_classification_lane_set_in_result() -> None:
    """Test that ClassificationResult sets classification_lane = 'borderline' when lane is BORDERLINE and not escalated."""
    from app.classification.client import ClassificationResult, _ModelRef
    from app.classification.complexity import Lane

    ref = _ModelRef("deepseek", "deepseek-v4-flash", "complex", "none")
    lane = Lane.BORDERLINE
    was_escalated = False

    eff_lane = lane.value.lower() if (lane == Lane.BORDERLINE and not was_escalated) else ref.quota_lane
    res = ClassificationResult(
        article=MagicMock(),
        classification_lane=eff_lane,
        classified_by_model=ref.model,
        classified_by_provider=ref.provider,
        was_escalated=was_escalated,
    )
    assert res.classification_lane == "borderline"


