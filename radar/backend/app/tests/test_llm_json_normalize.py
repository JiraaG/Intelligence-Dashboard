"""Tests for LLM JSON normalize / parse (DeepSeek shape quirks)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.classification.validator import normalize_llm_json_dict, parse_llm_article_json


def _valid_payload(**overrides: object) -> dict:
    base = {
        "title": "Titolo di prova abbastanza lungo",
        "summary": "Sommario esecutivo di due frasi. Seconda frase di contesto.",
        "published_at": "2026-07-16",
        "source_url": "https://example.com/a",
        "country_code": "us",
        "latitude": 37.09,
        "longitude": -95.71,
        "companies_involved": "Nessuno",
        "tags": "Tecnologia, AI",
        "primary_category": "Tecnologia",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "related_countries": "Nessuno",
        "relevance_level": 3,
    }
    base.update(overrides)
    return base


def test_normalize_flattens_coordinates_and_category() -> None:
    raw = _valid_payload()
    del raw["latitude"]
    del raw["longitude"]
    del raw["primary_category"]
    raw["coordinates"] = {"latitude": 41.87, "longitude": 12.57}
    raw["category"] = "Tecnologia"
    raw["tags"] = "Tecnologia, AI"
    out = normalize_llm_json_dict(raw)
    assert out["latitude"] == 41.87
    assert out["longitude"] == 12.57
    assert out["primary_category"] == "Tecnologia"
    assert "coordinates" not in out
    assert "category" not in out


def test_parse_llm_article_json_accepts_deepseek_quirks() -> None:
    raw = _valid_payload()
    del raw["latitude"]
    del raw["longitude"]
    del raw["primary_category"]
    raw["coordinates"] = {"lat": 0, "lon": 0}
    raw["category"] = "Tecnologia"
    raw["tags"] = "Tecnologia"
    raw["relevance_level"] = 2.0
    raw["country_code"] = "xx"
    article = parse_llm_article_json(json.dumps(raw))
    assert article.latitude == 0.0
    assert article.longitude == 0.0
    assert article.primary_category == "Tecnologia"
    assert article.country_code == "XX"
    assert article.relevance_level == 2


def test_parse_still_rejects_unknown_extra() -> None:
    raw = _valid_payload(mystery_field=True)
    with pytest.raises(ValidationError):
        parse_llm_article_json(json.dumps(raw))


def test_normalize_truncates_long_summary() -> None:
    out = normalize_llm_json_dict(_valid_payload(summary="x" * 2500))
    assert len(out["summary"]) == 2000


def test_normalize_game_review_not_geopolitica() -> None:
    out = normalize_llm_json_dict(
        _valid_payload(
            title="Denshattack! Recensione videogioco",
            tags="Geopolitica, Giappone, videogiochi, distopia",
            primary_category="Geopolitica",
        )
    )
    assert out["primary_category"] == "Tecnologia"
    assert out["tags"].startswith("Tecnologia")


def test_normalize_offtopic_philosophy_not_geopolitica() -> None:
    out = normalize_llm_json_dict(
        _valid_payload(
            title="Analisi sulla fallacia deterministica",
            summary=(
                "L'articolo discute concetti filosofici relativi alla fallacia "
                "deterministica. Il contenuto non presenta informazioni geopolitiche "
                "o infrastrutturali rilevanti."
            ),
            tags="Geopolitica, filosofia",
            primary_category="Geopolitica",
            country_code="XX",
            relevance_level=1,
        )
    )
    assert out["primary_category"] == "Tecnologia"
    assert out["tags"].startswith("Tecnologia")


def test_normalize_published_at_datetime() -> None:
    out = normalize_llm_json_dict(
        _valid_payload(published_at="2026-07-16T12:30:00Z")
    )
    assert out["published_at"] == "2026-07-16"


def test_parse_empty_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_llm_article_json(None)
    with pytest.raises(ValidationError):
        parse_llm_article_json("")


def test_parse_extra_data_takes_first_object() -> None:
    raw = _valid_payload()
    blob = json.dumps(raw) + "\n{\"extra\": true}"
    article = parse_llm_article_json(blob)
    assert article.primary_category == "Tecnologia"


def test_parse_ground_truth_overrides_bad_date() -> None:
    raw = _valid_payload(published_at="2-07-16")
    article = parse_llm_article_json(
        json.dumps(raw),
        source_url="https://example.com/real",
        published_at="2026-07-16",
    )
    assert article.published_at == "2026-07-16"
    assert article.source_url == "https://example.com/real"


def test_normalize_related_countries_list_to_csv() -> None:
    raw = _valid_payload(country_code="IT", related_countries=["FR", "de", "US"])
    out = normalize_llm_json_dict(raw)
    assert out["related_countries"] == "FR, DE, US"


def test_normalize_related_countries_drops_invalid_primary_xx() -> None:
    raw = _valid_payload(country_code="IT", related_countries="FR, IT, XX, INVALID, DE, FR")
    out = normalize_llm_json_dict(raw)
    assert out["related_countries"] == "FR, DE"


def test_normalize_related_countries_limits_to_5() -> None:
    raw = _valid_payload(country_code="IT", related_countries="FR, DE, US, ES, PT, GR, JP")
    out = normalize_llm_json_dict(raw)
    assert out["related_countries"] == "FR, DE, US, ES, PT"


def test_normalize_related_countries_empty_to_nessuno() -> None:
    raw = _valid_payload(country_code="IT", related_countries="XX, IT, INVALID")
    out = normalize_llm_json_dict(raw)
    assert out["related_countries"] == "Nessuno"

