"""Heuristic article complexity → routing lane (SIMPLE / BORDERLINE / COMPLEX).

Complexity = schema-extraction risk (ambiguous geo, multi-entity, non-Latin script),
not body length alone and not generic "IQ".

Families: G geo, E entities, L length, X script/language, N negative (anti-paid).
Lane (v2.2):
  - only L, or no strong families → SIMPLE
  - exactly 1 of {G, E, X} → BORDERLINE
  - ≥2 of {G, E, L, X} (L counts only in combination) → COMPLEX
Score is for logging only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Lane(str, Enum):
    SIMPLE = "SIMPLE"
    BORDERLINE = "BORDERLINE"
    COMPLEX = "COMPLEX"


# Min body length for geo_marker alone to count as G (avoids short HN pitch FPs).
_GEO_MARKER_MIN_BODY = 1500


# Top countries for Radar lexicon (EN + IT common forms).
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
        "EU",  # mapped as geo org hint
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
    lane: Lane
    families: frozenset[str]
    score: int
    signals: list[str] = field(default_factory=list)


def _count_countries(text: str, text_lower: str) -> tuple[int, list[str]]:
    found: list[str] = []
    for name in _COUNTRY_NAMES:
        if name in text_lower:
            found.append(name)
    # ISO only on original casing — avoid "il"/"un" → IL/UN after upper().
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
    return len(_ORG_SUFFIX.findall(text))


def _non_latin_ratio(sample: str) -> float:
    if not sample:
        return 0.0
    non_latin = sum(1 for c in sample if ord(c) > 0x024F and c.isalpha())
    letters = sum(1 for c in sample if c.isalpha())
    if letters == 0:
        return 0.0
    return non_latin / letters


def score_complexity(title: str, content: str) -> ComplexityResult:
    """
    Compute routing lane from title + sanitized body.

    Families: G geo, E entities, L length, X script/language, N negative (anti-paid).
    Lane v2.2: L-alone → SIMPLE; 1 of {G,E,X} → BORDERLINE; ≥2 (L only in combo) → COMPLEX.
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
    # ≥2 distinct countries → G even on short bodies; geo_marker alone needs length.
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
        # Length alone is not schema-extraction risk.
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
