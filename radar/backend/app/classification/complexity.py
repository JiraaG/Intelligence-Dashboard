"""Heuristic complessità articolo → lane di routing (SIMPLE / BORDERLINE / COMPLEX).

Complessità = rischio di estrazione schema (geo ambigua, multi-entità, script
non latino), **non** sola lunghezza del body e **non** un generico “QI”.

Famiglie: G geo, E entità, L lunghezza, X script/lingua, N negativa (anti-paid).
Lane (v2.2):
  - solo L, oppure nessuna famiglia forte → SIMPLE
  - esattamente 1 di {G, E, X} → BORDERLINE
  - ≥2 di {G, E, L, X} (L conta solo in combinazione) → COMPLEX
Lo score numerico è solo per logging.

SoT:
    plan-audit/complete/sot_llm_multi_model_fallback.md §4; .agents/AGENTS.md §3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Lane(str, Enum):
    """Fascia di routing heuristic (non confondere con quota_lane simple/complex)."""

    SIMPLE = "SIMPLE"
    BORDERLINE = "BORDERLINE"
    COMPLEX = "COMPLEX"


# Min body length perché un solo geo_marker conti come G (evita FP su pitch HN corti).
_GEO_MARKER_MIN_BODY = 1500


# Lexicon paesi Radar (forme EN + IT comuni) per famiglia G.
_COUNTRY_NAMES: frozenset[str] = frozenset(
    {
        "united states",
        "usa",
        "u.s.",
        "america",
        "stati uniti",
        "china",
        "cina",
        "russia",
        "ukraine",
        "ucraina",
        "israel",
        "israele",
        "iran",
        "germany",
        "germania",
        "france",
        "francia",
        "italy",
        "italia",
        "united kingdom",
        "britain",
        "uk",
        "regno unito",
        "japan",
        "giappone",
        "india",
        "brazil",
        "brasile",
        "canada",
        "australia",
        "mexico",
        "messico",
        "turkey",
        "turchia",
        "saudi arabia",
        "arabia saudita",
        "south korea",
        "corea del sud",
        "north korea",
        "corea del nord",
        "taiwan",
        "poland",
        "polonia",
        "spain",
        "spagna",
        "netherlands",
        "olanda",
        "paesi bassi",
        "sweden",
        "svezia",
        "norway",
        "norvegia",
        "finland",
        "finlandia",
        "switzerland",
        "svizzera",
        "austria",
        "belgium",
        "belgio",
        "greece",
        "grecia",
        "egypt",
        "egitto",
        "south africa",
        "sudafrica",
        "nigeria",
        "argentina",
        "chile",
        "cile",
        "colombia",
        "peru",
        "perù",
        "indonesia",
        "vietnam",
        "thailand",
        "thailandia",
        "philippines",
        "filippine",
        "pakistan",
        "bangladesh",
        "iraq",
        "syria",
        "siria",
        "lebanon",
        "libano",
        "jordan",
        "giordania",
        "qatar",
        "uae",
        "emirates",
        "emirati",
        "kuwait",
        "yemen",
        "libya",
        "libia",
        "sudan",
        "ethiopia",
        "etiopia",
        "kenya",
        "morocco",
        "marocco",
        "algeria",
        "tunisia",
        "hungary",
        "ungheria",
        "romania",
        "czech",
        "cechia",
        "slovakia",
        "slovacchia",
        "croatia",
        "croazia",
        "serbia",
        "belarus",
        "bielorussia",
        "kazakhstan",
        "kazakhstan",
        "azerbaijan",
        "georgia",
        "armenia",
    }
)

_ISO_ALLOWLIST: frozenset[str] = frozenset(
    {
        "US",
        "CN",
        "RU",
        "UA",
        "IL",
        "IR",
        "DE",
        "FR",
        "IT",
        "GB",
        "JP",
        "IN",
        "BR",
        "CA",
        "AU",
        "MX",
        "TR",
        "SA",
        "KR",
        "KP",
        "TW",
        "PL",
        "ES",
        "NL",
        "SE",
        "NO",
        "FI",
        "CH",
        "AT",
        "BE",
        "GR",
        "EG",
        "ZA",
        "NG",
        "AR",
        "CL",
        "CO",
        "PE",
        "ID",
        "VN",
        "TH",
        "PH",
        "PK",
        "BD",
        "IQ",
        "SY",
        "LB",
        "JO",
        "QA",
        "AE",
        "KW",
        "YE",
        "LY",
        "SD",
        "ET",
        "KE",
        "MA",
        "DZ",
        "TN",
        "HU",
        "RO",
        "CZ",
        "SK",
        "HR",
        "RS",
        "BY",
        "KZ",
        "AZ",
        "GE",
        "AM",
        "EU",  # hint org geo, non paese ISO classico
    }
)

_GEO_MARKERS = re.compile(
    r"\b("
    r"disputed|border|borderland|international|multilateral|summit|"
    r"nato|united\s+nations|\bun\b|opec|g7|g20|asean|brics|"
    r"confine|disputa|internazionale|multilaterale"
    r")\b",
    re.IGNORECASE,
)

_ORG_SUFFIX = re.compile(
    r"\b[\w&.-]+(?:\s+[\w&.-]+){0,3}\s+"
    r"(?:Inc\.?|Ltd\.?|LLC|GmbH|SpA|S\.p\.A\.|AG|Corp\.?|PLC|plc|SA|S\.A\.)\b"
)

_ISO_TOKEN = re.compile(r"\b([A-Z]{2})\b")


@dataclass(frozen=True)
class ComplexityResult:
    """Esito heuristic: lane di routing, famiglie attive, score e segnali di log."""

    lane: Lane
    families: frozenset[str]
    score: int
    signals: list[str] = field(default_factory=list)


def _count_countries(text: str, text_lower: str) -> tuple[int, list[str]]:
    """Conta paesi distinti (nomi lexicon ∪ ISO allowlist) e segnali di log.

    ISO solo sul casing originale: evita falsi ``il``/``un`` → IL/UN dopo upper().
    Returns:
        ``(n, signals)`` dove ``n = max(nomi, iso)``.
    """
    found: list[str] = []
    for name in _COUNTRY_NAMES:
        if name in text_lower:
            found.append(name)
    # ISO solo sul casing originale — evitare "il"/"un" → IL/UN dopo upper().
    iso_hits = [
        m.group(1)
        for m in _ISO_TOKEN.finditer(text)
        if m.group(1) in _ISO_ALLOWLIST
    ]
    iso_unique = sorted(set(iso_hits))
    name_hits = sorted({n for n in found})
    n = max(len(name_hits), len(iso_unique))
    signals: list[str] = []
    if name_hits:
        signals.append(f"countries={len(name_hits)}")
    if iso_unique:
        signals.append(f"iso={','.join(iso_unique[:6])}")
    return n, signals


def _count_orgs(text: str) -> int:
    """Conta match di suffissi societari (Inc/Ltd/…) per famiglia E."""
    return len(_ORG_SUFFIX.findall(text))


def _non_latin_ratio(sample: str) -> float:
    """Frazione di lettere oltre Latin Extended-A (soglia famiglia X)."""
    if not sample:
        return 0.0
    non_latin = sum(1 for c in sample if ord(c) > 0x024F and c.isalpha())
    letters = sum(1 for c in sample if c.isalpha())
    if letters == 0:
        return 0.0
    return non_latin / letters


def score_complexity(title: str, content: str) -> ComplexityResult:
    """Calcola la lane di routing da titolo + body già sanitizzato.

    Quorum v2.2 (non score-driven): L sola → SIMPLE; 1 di {G,E,X} → BORDERLINE;
    ≥2 famiglie positive (L solo in combo) → COMPLEX; clip N → SIMPLE.

    Args:
        title: Titolo entry.
        content: Testo piano post-``strip_html_tags`` (non HTML grezzo).
    Returns:
        ``ComplexityResult`` con lane, famiglie, score clampato 0–100, signals.
    SoT:
        SoT LLM §4.4 algoritmo v2.2.
    """
    title = title or ""
    content = content or ""
    blob = f"{title}\n{content}"
    blob_lower = blob.lower()
    signals: list[str] = []
    families: set[str] = set()
    score = 0

    body_len = len(content)
    if body_len >= 12_000:
        families.add("L")
        score += 30
        signals.append("len>=12000")
    elif body_len >= 6_000:
        families.add("L")
        score += 20
        signals.append("len>=6000")

    n_countries, geo_signals = _count_countries(blob, blob_lower)
    signals.extend(geo_signals)
    geo_marker = bool(_GEO_MARKERS.search(blob))
    # ≥2 paesi distinti → G anche su body corti; geo_marker da solo richiede lunghezza.
    if n_countries >= 2:
        families.add("G")
        score += 25
        signals.append("multi_country")
    elif geo_marker and body_len >= _GEO_MARKER_MIN_BODY:
        families.add("G")
        score += 25
        signals.append("geo_marker")
    elif geo_marker and body_len < _GEO_MARKER_MIN_BODY:
        signals.append("geo_marker_ignored_short_body")

    n_orgs = _count_orgs(blob)
    if n_orgs >= 3:
        families.add("E")
        score += 15
        signals.append(f"orgs={n_orgs}")

    sample = blob[:4000]
    ratio = _non_latin_ratio(sample)
    if ratio >= 0.15:
        families.add("X")
        score += 20
        signals.append(f"non_latin={ratio:.2f}")

    positive = families & {"G", "E", "L", "X"}
    strong = positive & {"G", "E", "X"}

    if len(title) < 40 and body_len < 800 and not positive:
        families.add("N")
        score = max(0, score - 15)
        signals.append("negative_clip")
        lane = Lane.SIMPLE
    elif positive == {"L"}:
        # Lunghezza da sola ≠ rischio estrazione schema (v2.2).
        signals.append("l_alone_simple")
        lane = Lane.SIMPLE
    elif len(positive) >= 2:
        lane = Lane.COMPLEX
    elif len(strong) == 1:
        lane = Lane.BORDERLINE
    else:
        lane = Lane.SIMPLE

    score = max(0, min(100, score))
    return ComplexityResult(
        lane=lane,
        families=frozenset(families),
        score=score,
        signals=signals,
    )
