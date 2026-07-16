"""Unit tests for complexity heuristic (lane quorum v2.2)."""

from app.classification.complexity import Lane, score_complexity


def test_short_mono_country_is_simple() -> None:
    r = score_complexity(
        "Tensione in Germania sul nucleare",
        "Berlino discute il futuro energetico del paese con operatori locali.",
    )
    assert r.lane == Lane.SIMPLE
    assert "G" not in r.families or len(r.families & {"G", "E", "L", "X"}) == 0


def test_multi_country_short_is_borderline() -> None:
    r = score_complexity(
        "USA e Cina a confronto",
        "Washington and Beijing discuss tariffs. United States and China trade talks continue.",
    )
    assert "G" in r.families
    positive = r.families & {"G", "E", "L", "X"}
    if positive == {"G"}:
        assert r.lane == Lane.BORDERLINE


def test_geo_and_orgs_is_complex() -> None:
    body = (
        "United States and China and Germany meet at a NATO summit. "
        "Acme Corp. Ltd. and Beta GmbH and Gamma SpA and Delta Inc. join supply talks."
    )
    r = score_complexity("Summit internazionale", body)
    assert r.lane == Lane.COMPLEX
    assert len(r.families & {"G", "E", "L", "X"}) >= 2


def test_long_mono_us_length_only_is_simple() -> None:
    """L alone is not schema-extraction risk → SIMPLE (v2.2)."""
    body = ("The United States economy report continues. " * 200)
    assert len(body) >= 6000
    r = score_complexity("US jobs report", body)
    positive = r.families & {"G", "E", "L", "X"}
    assert "L" in positive
    assert "G" not in positive
    assert r.lane == Lane.SIMPLE
    assert "l_alone_simple" in r.signals


def test_geo_marker_short_body_ignored() -> None:
    """geo_marker alone on short HN-style body must not elevate to G."""
    r = score_complexity(
        "Bad support is a 3T problem",
        "We fixed international support for startups. Inc. Ltd. Corp. only two orgs here.",
    )
    assert "G" not in r.families
    assert r.lane == Lane.SIMPLE
    assert "geo_marker_ignored_short_body" in r.signals


def test_geo_marker_long_body_counts() -> None:
    body = ("NATO multilateral summit discussions continue. " * 40)
    assert len(body) >= 1500
    r = score_complexity("Summit notes", body)
    assert "G" in r.families
    assert r.lane in (Lane.BORDERLINE, Lane.COMPLEX)


def test_title_mono_body_multi_detects_g_from_body() -> None:
    r = score_complexity(
        "Mercati in rialzo",
        "Tensioni tra Russia e Ukraine e Iran complicano i corridoi energetici.",
    )
    assert "G" in r.families


def test_negative_clip_forces_simple() -> None:
    r = score_complexity("Hi", "Short.")
    assert r.lane == Lane.SIMPLE
    assert "N" in r.families
