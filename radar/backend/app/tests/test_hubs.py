"""Unit tests Fase G: hub notes sotto ``_meta/``."""

from __future__ import annotations

from pathlib import Path

from app.classification.validator import GeopoliticalArticleSchema
from app.commit.factory import generate_markdown_content
from app.commit.hubs import (
    HubSpec,
    hubs_from_article,
    hubs_from_markdown,
    upsert_hub_notes,
    upsert_hubs_for_payload,
)


def _article(**overrides) -> GeopoliticalArticleSchema:
    data = {
        "title": "TAP gas",
        "summary": "Forniture.",
        "published_at": "2026-07-27",
        "source_url": "https://example.com/tap-hub-test",
        "country_code": "IT",
        "latitude": 41.9,
        "longitude": 12.5,
        "companies_involved": "Eni, SOCAR",
        "tags": "Energia, gasdotto, lng",
        "primary_category": "Energia",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Gasdotto TAP",
        "related_countries": "AZ, CN",
        "relevance_level": 3,
    }
    data.update(overrides)
    return GeopoliticalArticleSchema(**data)


def test_hubs_from_article_layers() -> None:
    hubs = hubs_from_article(_article())
    by_kind: dict[str, set[str]] = {}
    for hub in hubs:
        by_kind.setdefault(hub.kind, set()).add(hub.name)
    assert by_kind["country"] == {"IT", "AZ", "CN"}
    assert by_kind["category"] == {"Energia"}
    assert by_kind["company"] == {"Eni", "SOCAR"}
    assert by_kind["entity"] == {"Gasdotto TAP"}
    # Tag "Energia" collides with category SoT → skipped as tag hub
    assert by_kind["tag"] == {"gasdotto", "lng"}


def test_hubs_from_markdown_roundtrip() -> None:
    md = generate_markdown_content(_article())
    hubs = hubs_from_markdown(md)
    names = {(h.kind, h.name) for h in hubs}
    assert ("country", "IT") in names
    assert ("country", "AZ") in names
    assert ("category", "Energia") in names
    assert ("company", "Eni") in names
    assert ("entity", "Gasdotto TAP") in names
    assert ("tag", "gasdotto") in names


def test_upsert_hub_notes_containment_and_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    specs = [
        HubSpec(kind="country", name="IT"),
        HubSpec(kind="company", name="Eni"),
        HubSpec(kind="tag", name="gasdotto"),
    ]
    assert upsert_hub_notes(specs, vault_path=str(vault)) == 3
    it_path = vault / "_meta" / "countries" / "IT.md"
    eni_path = vault / "_meta" / "companies" / "Eni.md"
    assert it_path.is_file()
    assert eni_path.is_file()
    assert "type: country" in it_path.read_text(encoding="utf-8")
    assert "iso: IT" in it_path.read_text(encoding="utf-8")
    # idempotent rewrite
    assert upsert_hub_notes(specs, vault_path=str(vault)) == 3
    assert (vault / "_meta" / "companies" / "Eni.md.lock").exists()


def test_upsert_hubs_for_payload(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    md = generate_markdown_content(_article())
    written = upsert_hubs_for_payload(md, vault_path=str(vault))
    assert written >= 5
    assert (vault / "_meta" / "countries" / "IT.md").is_file()
    assert (vault / "_meta" / "entities" / "Gasdotto TAP.md").is_file()


def test_hub_rejects_path_traversal_name(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    specs = hubs_from_article(
        _article(
            companies_involved="../evil",
            infrastructural_entities="Nessuno",
            tags="Energia",
        )
    )
    company_names = [h.name for h in specs if h.kind == "company"]
    assert company_names == []
