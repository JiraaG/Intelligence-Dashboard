"""Phase 1 input-boundary tests: vault paths, YAML frontmatter, Miniflux, schema."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import yaml
from pydantic import ValidationError

from app.classification.validator import GeopoliticalArticleSchema
from app.commit.factory import generate_markdown_content
from app.commit.router import get_article_file_path
from app.core.config import MAX_MINIFLUX_RESPONSE_BYTES
from app.extraction.client import MinifluxClient, MinifluxResponseTooLarge
from app.extraction.entry_validation import EntryValidationError, validate_miniflux_entry

EXPECTED_FRONTMATTER_KEYS = frozenset(
    {
        "title",
        "location",
        "country",
        "related_countries",
        "category",
        "tags",
        "companies",
        "sentiment",
        "relevance",
        "published",
        "source",
    }
)


def _base_article(**overrides) -> GeopoliticalArticleSchema:
    data = {
        "title": "Articolo di test",
        "summary": "Sintesi di prova per i boundary test.",
        "published_at": "2026-07-14",
        "source_url": "https://example.com/article",
        "country_code": "IT",
        "latitude": 41.9,
        "longitude": 12.5,
        "companies_involved": "Nessuno",
        "tags": "Geopolitica",
        "primary_category": "Geopolitica",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "related_countries": "Nessuno",
        "relevance_level": 3,
    }
    data.update(overrides)
    return GeopoliticalArticleSchema(**data)


def _parse_frontmatter(md: str) -> dict:
    assert md.startswith("---\n")
    end = md.find("\n---\n", 4)
    assert end != -1
    return yaml.safe_load(md[4:end])


# ─── Path traversal / vault containment ──────────────────────────────────────


@pytest.mark.unit
def test_path_traversal_in_title_stays_in_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    article = _base_article(title="../../etc/passwd")
    path = Path(get_article_file_path(article, vault_path=str(vault))).resolve()
    assert path.is_relative_to(vault.resolve())
    assert ".." not in path.parts


@pytest.mark.unit
def test_path_traversal_in_date_raises_or_stays_contained(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    # Bypass Pydantic ISO check to probe router containment.
    article = GeopoliticalArticleSchema.model_construct(
        title="Safe Title",
        summary="x",
        published_at="../escape",
        source_url="https://example.com/x",
        country_code="IT",
        latitude=41.9,
        longitude=12.5,
        companies_involved="Nessuno",
        tags="Geopolitica",
        primary_category="Geopolitica",
        sentiment="Neutrale",
        infrastructural_entities="Nessuno",
        relevance_level=3,
    )
    try:
        path = Path(get_article_file_path(article, vault_path=str(vault))).resolve()
    except ValueError:
        return
    assert path.is_relative_to(vault.resolve())


@pytest.mark.unit
def test_path_traversal_in_category_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    article = GeopoliticalArticleSchema.model_construct(
        title="Titolo",
        summary="x",
        published_at="2026-07-14",
        source_url="https://example.com/x",
        country_code="IT",
        latitude=41.9,
        longitude=12.5,
        companies_involved="Nessuno",
        tags="Geopolitica",
        primary_category="Geopolitica/../../tmp",
        sentiment="Neutrale",
        infrastructural_entities="Nessuno",
        relevance_level=3,
    )
    with pytest.raises(ValueError, match="Categoria non valida"):
        get_article_file_path(article, vault_path=str(vault))


@pytest.mark.unit
def test_path_traversal_in_country_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    article = GeopoliticalArticleSchema.model_construct(
        title="Titolo",
        summary="x",
        published_at="2026-07-14",
        source_url="https://example.com/x",
        country_code="../",
        latitude=41.9,
        longitude=12.5,
        companies_involved="Nessuno",
        tags="Geopolitica",
        primary_category="Geopolitica",
        sentiment="Neutrale",
        infrastructural_entities="Nessuno",
        relevance_level=3,
    )
    with pytest.raises(ValueError, match="country_code non valido"):
        get_article_file_path(article, vault_path=str(vault))


@pytest.mark.unit
def test_path_traversal_via_url_stays_in_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    article = _base_article(
        source_url="https://example.com/../../etc/passwd",
        title="URL Traversal Probe",
    )
    path = Path(get_article_file_path(article, vault_path=str(vault))).resolve()
    assert path.is_relative_to(vault.resolve())
    assert path.suffix == ".md"
    # URL contributes only a hex hash suffix, not path segments.
    assert "etc" not in path.parts
    assert "passwd" not in path.name


# ─── YAML frontmatter injection ──────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    "evil_title",
    [
        'Quote " injection\nevil: true',
        "Newline\nevil: injected",
        "Backslash \\n evil: true",
        "Colon: value\nevil: yes",
        "Dash - list\n- evil",
        "Anchor &foo\nevil: 1",
    ],
)
def test_yaml_injection_cannot_add_frontmatter_keys(evil_title: str) -> None:
    article = _base_article(title=evil_title[:120])
    md = generate_markdown_content(article)
    frontmatter = _parse_frontmatter(md)

    assert set(frontmatter.keys()) == EXPECTED_FRONTMATTER_KEYS
    assert "evil" not in frontmatter
    assert frontmatter["title"] == article.title


@pytest.mark.unit
def test_yaml_injection_in_tags_and_companies() -> None:
    article = _base_article(
        tags='Geopolitica, "evil: true", \ninjected',
        companies_involved="Acme\\n evil: 1, Beta",
    )
    md = generate_markdown_content(article)
    frontmatter = _parse_frontmatter(md)
    assert set(frontmatter.keys()) == EXPECTED_FRONTMATTER_KEYS
    assert "evil" not in frontmatter
    assert "injected" not in frontmatter or isinstance(frontmatter.get("tags"), list)


# ─── Miniflux entry validation ───────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not-a-dict",
        {"id": -1, "url": "https://example.com/a", "title": "T", "published_at": "2026-07-14"},
        {"id": 1, "url": "ftp://evil", "title": "T", "published_at": "2026-07-14"},
        {"id": 1, "url": "https://example.com/a", "title": "", "published_at": "2026-07-14"},
        {"id": 1, "url": "https://example.com/a", "title": "T", "published_at": "not-a-date"},
        {"id": 1, "url": "https://example.com/a", "title": "T", "published_at": "2026-07-14", "feed": "bad"},
        {"id": True, "url": "https://example.com/a", "title": "T", "published_at": "2026-07-14"},
    ],
)
def test_invalid_miniflux_payloads_rejected(payload: object) -> None:
    with pytest.raises(EntryValidationError):
        validate_miniflux_entry(payload)


# ─── Response size limit ─────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_miniflux_client_rejects_oversized_body() -> None:
    mock_http = MagicMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Length": str(MAX_MINIFLUX_RESPONSE_BYTES + 1)}
    mock_response.raise_for_status = MagicMock()
    mock_response.request = MagicMock()

    async def _aiter_bytes():
        yield b"x"
        if False:  # pragma: no cover
            yield b""

    mock_response.aiter_bytes = _aiter_bytes

    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    stream_cm.__aexit__ = AsyncMock(return_value=False)
    mock_http.stream.return_value = stream_cm

    client = MinifluxClient(
        api_url="http://mock-miniflux",
        api_key="mock_key",
        http_client=mock_http,
    )

    with pytest.raises(MinifluxResponseTooLarge):
        await client._request("GET", "/v1/entries")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_miniflux_client_rejects_oversized_streamed_chunks() -> None:
    mock_http = MagicMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()
    mock_response.request = MagicMock()

    chunk = b"y" * 64_000

    async def _aiter_bytes():
        total = 0
        while total <= MAX_MINIFLUX_RESPONSE_BYTES:
            total += len(chunk)
            yield chunk

    mock_response.aiter_bytes = _aiter_bytes

    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
    stream_cm.__aexit__ = AsyncMock(return_value=False)
    mock_http.stream.return_value = stream_cm

    client = MinifluxClient(
        api_url="http://mock-miniflux",
        api_key="mock_key",
        http_client=mock_http,
    )

    with patch("app.extraction.client.MINIFLUX_MAX_RETRIES", 0):
        with pytest.raises(MinifluxResponseTooLarge):
            await client._request("GET", "/v1/entries")


# ─── Strict GeopoliticalArticleSchema ────────────────────────────────────────


@pytest.mark.unit
def test_schema_rejects_bad_category() -> None:
    with pytest.raises(ValidationError):
        _base_article(primary_category="InvalidCategory")  # type: ignore[arg-type]


@pytest.mark.unit
def test_schema_rejects_bad_sentiment() -> None:
    with pytest.raises(ValidationError):
        _base_article(sentiment="Happy")  # type: ignore[arg-type]


@pytest.mark.unit
def test_schema_rejects_bad_date() -> None:
    with pytest.raises(ValidationError):
        _base_article(published_at="14/07/2026")


@pytest.mark.unit
def test_schema_rejects_non_http_url() -> None:
    with pytest.raises(ValidationError):
        _base_article(source_url="ftp://example.com/file")


@pytest.mark.unit
def test_schema_rejects_latitude_out_of_range() -> None:
    with pytest.raises(ValidationError):
        _base_article(latitude=91.0)


@pytest.mark.unit
def test_schema_no_silent_coerce_category_or_sentiment() -> None:
    """Strict mode: wrong types/values raise — they are not coerced."""
    with pytest.raises(ValidationError):
        GeopoliticalArticleSchema(
            title="T",
            summary="S",
            published_at="2026-07-14",
            source_url="https://example.com/a",
            country_code="IT",
            latitude=1.0,
            longitude=2.0,
            companies_involved="Nessuno",
            tags="Geopolitica",
            primary_category="geopolitica",  # wrong case — not coerced
            sentiment="neutrale",
            infrastructural_entities="Nessuno",
            related_countries="Nessuno",
            relevance_level=3,
        )
