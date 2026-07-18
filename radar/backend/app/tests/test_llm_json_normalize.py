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
    out = normalize_llm_json_dict(_valid_payload(published_at="2026-07-16T12:30:00Z"))
    assert out["published_at"] == "2026-07-16"


def test_parse_empty_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        parse_llm_article_json(None)
    with pytest.raises(ValidationError):
        parse_llm_article_json("")


def test_parse_extra_data_takes_first_object() -> None:
    raw = _valid_payload()
    blob = json.dumps(raw) + '\n{"extra": true}'
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
    raw = _valid_payload(
        country_code="IT", related_countries="FR, IT, XX, INVALID, DE, FR"
    )
    out = normalize_llm_json_dict(raw)
    assert out["related_countries"] == "FR, DE"


def test_normalize_related_countries_limits_to_5() -> None:
    raw = _valid_payload(
        country_code="IT", related_countries="FR, DE, US, ES, PT, GR, JP"
    )
    out = normalize_llm_json_dict(raw)
    assert out["related_countries"] == "FR, DE, US, ES, PT"


def test_normalize_related_countries_empty_to_nessuno() -> None:
    raw = _valid_payload(country_code="IT", related_countries="XX, IT, INVALID")
    out = normalize_llm_json_dict(raw)
    assert out["related_countries"] == "Nessuno"


def test_normalize_political_with_filosofia_stays_geopolitica() -> None:
    """W2: soft-remap off-topic non deve toccare pezzi politici (anti false-positive)."""
    out = normalize_llm_json_dict(
        _valid_payload(
            title="Spahn e la filosofia della surrogazione in parlamento",
            summary=(
                "Il ministro discute una proposta legislativa sulla surrogazione. "
                "Il dibattito riguarda governance e salute pubblica in Germania."
            ),
            tags="Geopolitica, Germania, surrogacy",
            primary_category="Geopolitica",
            country_code="DE",
            latitude=51.16,
            longitude=10.45,
            relevance_level=3,
        )
    )
    assert out["primary_category"] == "Geopolitica"
    assert out["country_code"] == "DE"
    assert out["tags"].startswith("Geopolitica")


def test_normalize_sport_legal_not_tecnologia() -> None:
    """Sport/cronaca giudiziaria non devono restare in Tecnologia."""
    out = normalize_llm_json_dict(
        _valid_payload(
            title="Ciclista olimpico Rohan Dennis si dichiara colpevole di guida",
            summary=(
                "L'atleta australiano ammette di aver guidato durante la "
                "sospensione della patente dopo un incidente."
            ),
            tags="Tecnologia, sport, Australia",
            primary_category="Tecnologia",
            country_code="AU",
            latitude=-25.27,
            longitude=133.77,
            relevance_level=1,
        )
    )
    assert out["primary_category"] == "Geopolitica"
    assert out["tags"].startswith("Geopolitica")
    assert out["country_code"] == "AU"


def test_normalize_does_not_invent_country_code() -> None:
    """Normalize non inventa ISO: XX resta XX anche con titolo geolocalizzabile."""
    out = normalize_llm_json_dict(
        _valid_payload(
            title="Caso Epstein: nuove carte giudiziarie negli Stati Uniti",
            summary="Documenti processuali emersi a New York sul caso Epstein.",
            tags="Geopolitica, Stati Uniti",
            primary_category="Geopolitica",
            country_code="XX",
            latitude=0.0,
            longitude=0.0,
        )
    )
    assert out["country_code"] == "XX"
    assert out["primary_category"] == "Geopolitica"


@pytest.mark.parametrize(
    ("label", "payload", "expect_category", "expect_country", "expect_related"),
    [
        (
            "epstein",
            {
                "title": "Caso Epstein: archivi giudiziari USA",
                "summary": "Nuove carte processuali emerse a New York sul caso Epstein.",
                "tags": "Geopolitica, Stati Uniti, giustizia",
                "primary_category": "Geopolitica",
                "country_code": "US",
                "latitude": 40.71,
                "longitude": -74.0,
                "related_countries": "Nessuno",
                "relevance_level": 3,
            },
            "Geopolitica",
            "US",
            "Nessuno",
        ),
        (
            "spahn",
            {
                "title": "Spahn: dibattito sulla surrogazione in Germania",
                "summary": (
                    "Il ministro tedesco apre un confronto parlamentare sulla "
                    "surrogazione e la regolamentazione sanitaria."
                ),
                "tags": "Geopolitica, Germania, salute",
                "primary_category": "Geopolitica",
                "country_code": "DE",
                "latitude": 51.16,
                "longitude": 10.45,
                "related_countries": "Nessuno",
                "relevance_level": 3,
            },
            "Geopolitica",
            "DE",
            "Nessuno",
        ),
        (
            "ue_emissioni",
            {
                "title": "UE: nuova policy emissioni a Bruxelles",
                "summary": (
                    "La Commissione europea presenta a Bruxelles norme su emissioni; "
                    "coinvolti anche Italia e Francia."
                ),
                "tags": "Ambiente, Unione Europea, emissioni",
                "primary_category": "Ambiente",
                "country_code": "BE",
                "latitude": 50.85,
                "longitude": 4.35,
                "related_countries": "IT, FR",
                "relevance_level": 4,
            },
            "Ambiente",
            "BE",
            "IT, FR",
        ),
        (
            "trilaterale_us_it_fr",
            {
                "title": "Accordo trilaterale USA Italia Francia su chip",
                "summary": (
                    "Washington firma un accordo industriale con Roma e Parigi "
                    "sulla filiera dei semiconduttori."
                ),
                "tags": "Economia, semiconduttori, accordo",
                "primary_category": "Economia",
                "country_code": "US",
                "latitude": 38.9,
                "longitude": -77.0,
                "related_countries": "IT, FR",
                "relevance_level": 4,
            },
            "Economia",
            "US",
            "IT, FR",
        ),
        (
            "filosofia_pura_offtopic",
            {
                "title": "Analisi sulla fallacia deterministica",
                "summary": (
                    "L'articolo discute concetti filosofici relativi alla fallacia "
                    "deterministica. Il contenuto non presenta informazioni geopolitiche "
                    "o infrastrutturali rilevanti."
                ),
                "tags": "Tecnologia, filosofia",
                "primary_category": "Tecnologia",
                "country_code": "XX",
                "latitude": 0.0,
                "longitude": 0.0,
                "related_countries": "Nessuno",
                "relevance_level": 1,
            },
            "Tecnologia",
            "XX",
            "Nessuno",
        ),
        (
            "paper_mit",
            {
                "title": "Paper MIT su chip fotonici",
                "summary": (
                    "Ricercatori del MIT pubblicano uno studio su semiconduttori "
                    "fotonici per telecomunicazioni."
                ),
                "tags": "Tecnologia, semiconduttori, ricerca",
                "primary_category": "Tecnologia",
                "country_code": "US",
                "latitude": 42.36,
                "longitude": -71.09,
                "related_countries": "Nessuno",
                "relevance_level": 3,
            },
            "Tecnologia",
            "US",
            "Nessuno",
        ),
    ],
)
def test_golden_expected_prompt_outcomes_parse(
    label: str,
    payload: dict,
    expect_category: str,
    expect_country: str,
    expect_related: str,
) -> None:
    """Golden shape attesa dal prompt affinato (parse/normalize, non chiamata LLM).

    Documenta i case study del piano: Epstein, Spahn, UE, trilaterale, off-topic, paper.
    """
    del label  # usato solo per id pytest
    article = parse_llm_article_json(json.dumps(_valid_payload(**payload)))
    assert article.primary_category == expect_category
    assert article.country_code == expect_country
    assert article.related_countries == expect_related
    if expect_country == "XX":
        assert article.latitude == 0.0
        assert article.longitude == 0.0
    # Invarianti related
    related_parts = [
        p.strip()
        for p in article.related_countries.split(",")
        if p.strip() and p.strip().lower() != "nessuno"
    ]
    assert expect_country not in related_parts
    assert "XX" not in related_parts
    assert len(related_parts) <= 5
