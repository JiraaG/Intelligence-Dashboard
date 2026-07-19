"""Contract tests sul SYSTEM_PROMPT (categorie, anti-XX, related/star).

Non invocano LLM: verificano che le regole vincolanti del piano
classification/geo/arcs siano presenti nel testo SoT ``prompts.py``.
"""

from __future__ import annotations

from app.classification.prompts import SYSTEM_PROMPT, build_user_prompt
from app.classification.validator import PRIMARY_CATEGORIES


def test_system_prompt_lists_all_ten_categories() -> None:
    for cat in PRIMARY_CATEGORIES:
        assert f"'{cat}'" in SYSTEM_PROMPT


def test_system_prompt_restricted_offtopic_fallback() -> None:
    assert "FALLBACK OFF-TOPIC (ristretto)" in SYSTEM_PROMPT
    assert "filosofia astratta" in SYSTEM_PROMPT
    assert "country_code 'XX'" in SYSTEM_PROMPT
    # Non deve restare la vecchia regola ampia soft-news→Tecnologia/XX senza limiti.
    assert "ANTI-PATTERN (vietati)" in SYSTEM_PROMPT
    assert "default comodo 'Tecnologia'" in SYSTEM_PROMPT
    assert "sport/cronaca giudiziaria" in SYSTEM_PROMPT


def test_system_prompt_category_disambiguation_and_tiebreak() -> None:
    assert "Tie-break:" in SYSTEM_PROMPT
    assert "scandali politici" in SYSTEM_PROMPT
    assert "salute pubblica" in SYSTEM_PROMPT
    assert "biotecnologie industriali" in SYSTEM_PROMPT


def test_system_prompt_geo_decision_tree_anti_xx() -> None:
    assert "protagonista/attore del pezzo" in SYSTEM_PROMPT
    assert "teatro/luogo del fatto" in SYSTEM_PROMPT
    assert "affiliation autori" in SYSTEM_PROMPT
    assert "NATO HQ" in SYSTEM_PROMPT
    assert "Non inventare codici ISO finti" in SYSTEM_PROMPT
    assert "SOLO se nessuno dei precedenti è supportato → 'XX'" in SYSTEM_PROMPT
    assert "attacchi reciproci USA–Iran" in SYSTEM_PROMPT
    assert "country_code US, related_countries IR,JO,KW" in SYSTEM_PROMPT


def test_system_prompt_related_multilateral_star_semantics() -> None:
    assert "max 5" in SYSTEM_PROMPT
    assert "related_countries" in SYSTEM_PROMPT
    assert "star primary↔ciascun related" in SYSTEM_PROMPT
    assert "non triangolo completo" in SYSTEM_PROMPT
    assert (
        "USA–Italia–Francia" in SYSTEM_PROMPT
        or "US, related_countries IT,FR" in SYSTEM_PROMPT
    )


def test_system_prompt_dense_summary_briefing() -> None:
    assert "briefing esecutivo DENSO" in SYSTEM_PROMPT
    assert "220–420" in SYSTEM_PROMPT
    assert "attori, azione, luogo/teatro" in SYSTEM_PROMPT
    assert "1ª frase = nucleo del fatto" in SYSTEM_PROMPT
    assert "riassunto generico/vago" in SYSTEM_PROMPT


def test_system_prompt_no_chain_of_thought_field() -> None:
    lower = SYSTEM_PROMPT.lower()
    assert "chain-of-thought" not in lower
    assert "campo reasoning" in lower  # esplicito: non esiste nello schema
    assert '"reasoning"' not in SYSTEM_PROMPT


def test_build_user_prompt_wraps_untrusted_article() -> None:
    out = build_user_prompt(
        title="Titolo",
        url="https://example.com/a",
        date="2026-07-18",
        content="Corpo",
    )
    assert "<untrusted_article>" in out
    assert "</untrusted_article>" in out
    assert "TITOLO: Titolo" in out
    assert "https://example.com/a" in out
    assert "2026-07-18" in out
    assert "Corpo" in out
