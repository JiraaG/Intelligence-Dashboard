"""Unit tests Fase G: sanitize / format wiki-link."""

from __future__ import annotations

from app.commit.wikilinks import (
    format_wiki_link,
    format_wiki_link_list,
    hub_note_stem,
    sanitize_wiki_target,
)


def test_sanitize_accepts_plain_labels() -> None:
    assert sanitize_wiki_target("  Eni  ") == "Eni"
    assert sanitize_wiki_target("IT") == "IT"
    assert sanitize_wiki_target("Intelligenza Artificiale") == "Intelligenza Artificiale"


def test_sanitize_rejects_breakouts() -> None:
    assert sanitize_wiki_target("foo]]bar") is None
    assert sanitize_wiki_target("[[already") is None
    assert sanitize_wiki_target("a|b") is None
    assert sanitize_wiki_target("a#heading") is None
    assert sanitize_wiki_target("../etc") is None
    assert sanitize_wiki_target("a/b") is None
    assert sanitize_wiki_target("a\\b") is None
    assert sanitize_wiki_target("x\ny") is None
    assert sanitize_wiki_target("") is None
    assert sanitize_wiki_target("   ") is None


def test_sanitize_truncates() -> None:
    long = "A" * 200
    out = sanitize_wiki_target(long, max_chars=50)
    assert out is not None
    assert len(out) == 50


def test_format_wiki_link_fallback_plain() -> None:
    assert format_wiki_link("Eni") == "[[Eni]]"
    assert format_wiki_link("bad/path") == "bad/path"
    assert format_wiki_link("  ") == ""


def test_format_wiki_link_list() -> None:
    assert format_wiki_link_list(["Eni", "SOCAR"]) == "[[Eni]], [[SOCAR]]"
    assert format_wiki_link_list([]) == "Nessuno"
    assert format_wiki_link_list(["", "  "], empty="Nessuna") == "Nessuna"


def test_hub_note_stem_preserves_case() -> None:
    assert hub_note_stem("Eni") == "Eni"
    assert hub_note_stem("IT") == "IT"
    assert hub_note_stem("bad/path") is None
