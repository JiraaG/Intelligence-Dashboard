"""Validazione Pydantic strict + normalizzazione quirks provider + fallback.

Schema: CSV restano ``str`` (FE fa ``string[]`` solo post-API). Nessun campo
``reasoning``. Fence markdown e override Miniflux di URL/data prima del validate.

SoT:
    skill llm-json-extraction; radar-api-contract (CSV str → array FE).
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from typing import Any, Literal
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PRIMARY_CATEGORIES = (
    "Nucleare",
    "Energia",
    "Infrastrutture",
    "Geopolitica",
    "Economia",
    "Tecnologia",
    "Spazio",
    "Ambiente",
    "Salute",
    "Sicurezza",
)

SENTIMENT_VALUES = ("Positivo", "Neutrale", "Negativo")

# Alias comuni da modelli locali EN / varianti → contratto italiano Radar.
_CATEGORY_ALIASES: dict[str, str] = {
    "science & technology": "Tecnologia",
    "science and technology": "Tecnologia",
    "tech": "Tecnologia",
    "technology": "Tecnologia",
    "tecnologia": "Tecnologia",
    "space": "Spazio",
    "spazio": "Spazio",
    "health": "Salute",
    "salute": "Salute",
    "security": "Sicurezza",
    "sicurezza": "Sicurezza",
    "environment": "Ambiente",
    "ambiente": "Ambiente",
    "economy": "Economia",
    "economia": "Economia",
    "geopolitics": "Geopolitica",
    "geopolitica": "Geopolitica",
    "politics": "Geopolitica",
    "nuclear": "Nucleare",
    "nucleare": "Nucleare",
    "energy": "Energia",
    "energia": "Energia",
    "infrastructure": "Infrastrutture",
    "infrastructures": "Infrastrutture",
    "infrastrutture": "Infrastrutture",
}

_SENTIMENT_ALIASES: dict[str, str] = {
    "positive": "Positivo",
    "positivo": "Positivo",
    "negative": "Negativo",
    "negativo": "Negativo",
    "neutral": "Neutrale",
    "neutrale": "Neutrale",
    "neutro": "Neutrale",
}

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
# Soft remap: recensioni game/entertainment spesso etichettate Geopolitica/Infrastrutture.
_GAME_REVIEW_HINT = re.compile(
    r"(videogioc\w*|video\s*game|videogame|game\s*review|"
    r"recensione.{0,40}(gioco|game)|ps5|xbox|nintendo|steam\b|"
    r"\bpc,\s*ps5\b|\bunreal\b|\bunity\b)",
    re.IGNORECASE | re.DOTALL,
)
# Soft remap: filosofia / fluff non-news non devono restare in Geopolitica.
_OFFTOPIC_GEOPOLITICA_HINT = re.compile(
    r"non\s+(presenta|contiene)\s+informazioni\s+geopolitic|"
    r"nessun[ao]?\s+informazione\s+geopolitic|"
    r"concetti?\s+filosofic|"
    r"fallacia\s+determinist|"
    r"\bfilosofia\b|"
    r"no\s+geopolitical\s+(content|information|relevance)",
    re.IGNORECASE,
)
# Se il pezzo ha segnali politici forti, non applicare soft-remap off-topic
# (evita false positive tipo "filosofia politica" / ministro + filosofia).
_POLITICAL_CONTENT_HINT = re.compile(
    r"\b(elezion\w*|parlamento|ministro|ministero|governo|scandalo|"
    r"surrogacy|surrogazione|legislativ\w*|senato|camera\s+dei\s+deputati|"
    r"president\w*|diplomazi\w*|sanzion\w*)\b",
    re.IGNORECASE,
)
# Soft remap inverso: sport/cronaca giudiziaria non devono restare in Tecnologia.
_SPORT_LEGAL_HINT = re.compile(
    r"\b(ciclist\w*|olimpic\w*|atleta|atlet\w*|patente|squalifica|"
    r"colpevole|guida\s+durante|processo\s+penale|omicidio|"
    r"sportiv\w*|calciator\w*|tennis|formula\s*1)\b",
    re.IGNORECASE,
)
# Soft remap: disastri/incendi con luogo non devono restare in Tecnologia.
_DISASTER_HINT = re.compile(
    r"\b(incend\w*|alluvion\w*|terremot\w*|uragan\w*|tifone|inondaz\w*|"
    r"disastro\s+natural|flood|wildfire|earthquake)\b",
    re.IGNORECASE,
)
# Sport/evento senza politica forte (Gemma → Geopolitica ★ alti).
_SPORT_EVENT_HINT = re.compile(
    r"\b(maraton\w*|corridor\w*|world\s*cup|mondiali|half[\s-]?time|"
    r"partita\s+di\s+calcio|olimpiadi|sportiv\w*)\b",
    re.IGNORECASE,
)
# Fatto cinetico → Sicurezza, non Geopolitica.
_KINETIC_SECURITY_HINT = re.compile(
    r"\b(attacc\w*\s+(missil|aere|drone|milit)|bombard\w*|raid\s+(aere|us|usa|israel)|"
    r"soldat\w*.{0,30}(uccis|mort|kill)|missile|sparator\w*|drone\s+strike|"
    r"attacchi?\s+reciproc)\b",
    re.IGNORECASE | re.DOTALL,
)
_MARITIME_HINT = re.compile(
    r"\b(traghetto|ferry|naufrag\w*|affonda|capovol\w*|passeggeri.{0,20}mare)\b",
    re.IGNORECASE | re.DOTALL,
)
# Protagonista US in conflitti bilaterali (Gemma spesso mette IR/JO come primary).
_US_ACTOR_VICTIM_HINT = re.compile(
    r"(soldat[ei].{0,60}(american|statunitens)|"
    r"(american|statunitens)\w*.{0,40}soldat|"
    r"american\s+soldiers|u\.?s\.?\s+soldiers|"
    r"attacchi?\s+reciproc\w*.{0,40}(stati\s+uniti|usa|u\.?s\.?)|"
    r"(stati\s+uniti|usa).{0,40}(iran|attacc))",
    re.IGNORECASE | re.DOTALL,
)
_IRAN_MENTION_HINT = re.compile(r"\b(iran|teheran|tehran)\b", re.IGNORECASE)

# Centroidi nazionali usati solo su swap soft di country_code (prompt SoT).
_COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "US": (37.09, -95.71),
    "IR": (32.43, 53.69),
    "JO": (30.59, 36.24),
    "KW": (29.31, 47.48),
    "IT": (41.87, 12.57),
    "GB": (55.38, -3.44),
    "DE": (51.17, 10.45),
    "UA": (48.38, 31.17),
}

# ISO 3166-1 alpha-2 (~249) + sentinel XX per geografia indeterminata.
ISO_ALPHA2_CODES: frozenset[str] = frozenset(
    {
        "AD",
        "AE",
        "AF",
        "AG",
        "AI",
        "AL",
        "AM",
        "AO",
        "AQ",
        "AR",
        "AS",
        "AT",
        "AU",
        "AW",
        "AX",
        "AZ",
        "BA",
        "BB",
        "BD",
        "BE",
        "BF",
        "BG",
        "BH",
        "BI",
        "BJ",
        "BL",
        "BM",
        "BN",
        "BO",
        "BQ",
        "BR",
        "BS",
        "BT",
        "BV",
        "BW",
        "BY",
        "BZ",
        "CA",
        "CC",
        "CD",
        "CF",
        "CG",
        "CH",
        "CI",
        "CK",
        "CL",
        "CM",
        "CN",
        "CO",
        "CR",
        "CU",
        "CV",
        "CW",
        "CX",
        "CY",
        "CZ",
        "DE",
        "DJ",
        "DK",
        "DM",
        "DO",
        "DZ",
        "EC",
        "EE",
        "EG",
        "EH",
        "ER",
        "ES",
        "ET",
        "FI",
        "FJ",
        "FK",
        "FM",
        "FO",
        "FR",
        "GA",
        "GB",
        "GD",
        "GE",
        "GF",
        "GG",
        "GH",
        "GI",
        "GL",
        "GM",
        "GN",
        "GP",
        "GQ",
        "GR",
        "GS",
        "GT",
        "GU",
        "GW",
        "GY",
        "HK",
        "HM",
        "HN",
        "HR",
        "HT",
        "HU",
        "ID",
        "IE",
        "IL",
        "IM",
        "IN",
        "IO",
        "IQ",
        "IR",
        "IS",
        "IT",
        "JE",
        "JM",
        "JO",
        "JP",
        "KE",
        "KG",
        "KH",
        "KI",
        "KM",
        "KN",
        "KP",
        "KR",
        "KW",
        "KY",
        "KZ",
        "LA",
        "LB",
        "LC",
        "LI",
        "LK",
        "LR",
        "LS",
        "LT",
        "LU",
        "LV",
        "LY",
        "MA",
        "MC",
        "MD",
        "ME",
        "MF",
        "MG",
        "MH",
        "MK",
        "ML",
        "MM",
        "MN",
        "MO",
        "MP",
        "MQ",
        "MR",
        "MS",
        "MT",
        "MU",
        "MV",
        "MW",
        "MX",
        "MY",
        "MZ",
        "NA",
        "NC",
        "NE",
        "NF",
        "NG",
        "NI",
        "NL",
        "NO",
        "NP",
        "NR",
        "NU",
        "NZ",
        "OM",
        "PA",
        "PE",
        "PF",
        "PG",
        "PH",
        "PK",
        "PL",
        "PM",
        "PN",
        "PR",
        "PS",
        "PT",
        "PW",
        "PY",
        "QA",
        "RE",
        "RO",
        "RS",
        "RU",
        "RW",
        "SA",
        "SB",
        "SC",
        "SD",
        "SE",
        "SG",
        "SH",
        "SI",
        "SJ",
        "SK",
        "SL",
        "SM",
        "SN",
        "SO",
        "SR",
        "SS",
        "ST",
        "SV",
        "SX",
        "SY",
        "SZ",
        "TC",
        "TD",
        "TF",
        "TG",
        "TH",
        "TJ",
        "TK",
        "TL",
        "TM",
        "TN",
        "TO",
        "TR",
        "TT",
        "TV",
        "TW",
        "TZ",
        "UA",
        "UG",
        "UM",
        "US",
        "UY",
        "UZ",
        "VA",
        "VC",
        "VE",
        "VG",
        "VI",
        "VN",
        "VU",
        "WF",
        "WS",
        "YE",
        "YT",
        "ZA",
        "ZM",
        "ZW",
        "XX",
    }
)


class GeopoliticalArticleSchema(BaseModel):
    """Contratto output strutturato LLM: strict, extra forbid, CSV come ``str``.

    Categorie/sentiment/date invalidi → REJECT (niente coerce silenzioso).
    SoT: skill llm-json-extraction (schema immutabile; no ``List[str]`` qui).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str = Field(
        max_length=120,
        description="Titolo normalizzato privo di elementi di clickbait. Massimo 120 caratteri.",
    )
    summary: str = Field(
        max_length=2000,
        description=(
            "Briefing esecutivo denso (max due frasi; tipicamente 220–420 caratteri): "
            "fatti principali (attori, azione, luogo, cifre/nomi rilevanti), non parafrasi vaga."
        ),
    )
    published_at: str = Field(
        description="Data di pubblicazione dell'articolo in formato ISO YYYY-MM-DD.",
    )
    source_url: str = Field(
        max_length=2048,
        description="URL originale dell'articolo, invariato.",
    )
    country_code: str = Field(
        description="Codice ISO Alpha-2 della nazione coinvolta (es. IT, US, CN). Usa 'XX' se non determinabile.",
    )
    latitude: float = Field(
        description="Latitudine geografica in gradi decimali.",
    )
    longitude: float = Field(
        description="Longitudine geografica in gradi decimali.",
    )
    companies_involved: str = Field(
        max_length=2000,
        description="Stringa CSV delle aziende. Scrivi 'Nessuno' se nessuna.",
    )
    tags: str = Field(
        max_length=2000,
        description="Stringa CSV dei tag semantici. Il primo tag deve essere la primary_category.",
    )
    primary_category: Literal[
        "Nucleare",
        "Energia",
        "Infrastrutture",
        "Geopolitica",
        "Economia",
        "Tecnologia",
        "Spazio",
        "Ambiente",
        "Salute",
        "Sicurezza",
    ] = Field(
        description="Macro-categoria principale scelta rigorosamente tra le 10 categorie geopolitiche.",
    )
    sentiment: Literal["Positivo", "Neutrale", "Negativo"] = Field(
        description="Sentiment strategico legato alla notizia.",
    )
    infrastructural_entities: str = Field(
        max_length=2000,
        description="Stringa CSV di asset fisici. Scrivi 'Nessuno' se nessuno.",
    )
    related_countries: str = Field(
        max_length=2000,
        description="Stringa CSV dei codici ISO Alpha-2 dei paesi secondari coinvolti. Scrivi 'Nessuno' se nessuno.",
    )
    relevance_level: int = Field(
        ge=1,
        le=5,
        description="Grado di rilevanza geopolitica dell'articolo da 1 a 5.",
    )

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: str) -> str:
        """Accetta solo ``YYYY-MM-DD`` calendario-valido."""
        if not isinstance(value, str) or not ISO_DATE_PATTERN.match(value):
            raise ValueError("published_at deve essere in formato ISO YYYY-MM-DD")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("published_at non è una data valida") from exc
        return value

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        """URL http(s) ≤ 2048; nessun coerce di schemi diversi."""
        if not isinstance(value, str) or not SOURCE_URL_PATTERN.match(value):
            raise ValueError("source_url deve iniziare con http:// o https://")
        if len(value) > 2048:
            raise ValueError("source_url supera i 2048 caratteri")
        return value

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        """ISO Alpha-2 in allowlist, oppure sentinel ``XX``."""
        if not isinstance(value, str):
            raise ValueError("country_code deve essere una stringa")
        if value == "XX":
            return "XX"
        if len(value) != 2 or not value.isalpha():
            raise ValueError(
                "country_code deve essere un codice ISO Alpha-2 valido o 'XX'"
            )
        normalized = value.upper()
        if normalized not in ISO_ALPHA2_CODES:
            raise ValueError(
                f"country_code '{value}' non è un codice ISO Alpha-2 riconosciuto"
            )
        return normalized

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        """Float finito in [-90, 90]; strict rifiuta int non-float."""
        if not isinstance(value, float):
            raise ValueError("latitude deve essere un float")
        if not math.isfinite(value):
            raise ValueError("latitude deve essere un numero finito")
        if value < -90.0 or value > 90.0:
            raise ValueError("latitude deve essere compresa tra -90 e 90")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        """Float finito in [-180, 180]."""
        if not isinstance(value, float):
            raise ValueError("longitude deve essere un float")
        if not math.isfinite(value):
            raise ValueError("longitude deve essere un numero finito")
        if value < -180.0 or value > 180.0:
            raise ValueError("longitude deve essere compresa tra -180 e 180")
        return value

    @field_validator("related_countries")
    @classmethod
    def validate_related_countries(cls, value: str) -> str:
        """Stringa CSV di codici ISO Alpha-2 validi (o Nessuno)."""
        if not isinstance(value, str):
            raise ValueError("related_countries deve essere una stringa")
        return value

    @model_validator(mode="after")
    def first_tag_matches_primary(self) -> Self:
        """Invariante schema: primo CSV tag == ``primary_category`` (non Nessuno)."""
        first = self.tags.split(",")[0].strip() if self.tags else ""
        if first.lower() in {"nessuno", "nessuna", "none", ""}:
            raise ValueError("tags deve iniziare con primary_category")
        if first != self.primary_category:
            raise ValueError(
                f"primo tag {first!r} != primary_category {self.primary_category!r}"
            )
        return self

    @model_validator(mode="after")
    def validate_related_countries_constraints(self) -> Self:
        """Invariante: related_countries non contiene country_code, XX, codici invalidi o duplicati, max 5."""
        primary = self.country_code
        related_list = parse_csv_list(self.related_countries)

        seen = set()
        for c in related_list:
            if c == "XX":
                raise ValueError(
                    "related_countries non deve contenere il codice di fallback 'XX'"
                )
            if c == primary:
                raise ValueError(
                    f"related_countries non deve contenere il paese primario '{primary}'"
                )
            if c not in ISO_ALPHA2_CODES:
                raise ValueError(f"related_countries contiene codice non ISO '{c}'")
            if c in seen:
                raise ValueError(f"related_countries contiene codici duplicati: '{c}'")
            seen.add(c)

        if len(related_list) > 5:
            raise ValueError("related_countries non deve contenere più di 5 codici")

        return self


def normalize_llm_json_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Ripara shape comuni dei provider **prima** del validate strict.

    Non cambia ``GeopoliticalArticleSchema``: appiattisce coordinate annidate,
    alias categoria, int→float lat/lon, float→int relevance, clamp lunghezze,
    soft-remap game/filosofia → Tecnologia, allinea primo tag a primary.

    Args:
        data: Dict JSON già decodificato dal modello.
    Returns:
        Copia normalizzata pronta per ``model_validate``.
    """
    out = dict(data)

    for nest_key in ("coordinates", "coordinate", "coords", "geo", "location"):
        nest = out.pop(nest_key, None)
        if not isinstance(nest, dict):
            continue
        if "latitude" not in out:
            for key in ("latitude", "lat"):
                if key in nest:
                    out["latitude"] = nest[key]
                    break
        if "longitude" not in out:
            for key in ("longitude", "lon", "lng"):
                if key in nest:
                    out["longitude"] = nest[key]
                    break

    if "primary_category" not in out:
        for alt in ("category", "categoria", "primaryCategory"):
            if alt in out:
                out["primary_category"] = out.pop(alt)
                break
    else:
        out.pop("category", None)
        out.pop("categoria", None)

    # Gemma/locali: CSV attesi come str, ma spesso arrivano come list.
    for csv_key in (
        "companies_involved",
        "tags",
        "infrastructural_entities",
        "related_countries",
    ):
        val = out.get(csv_key)
        if isinstance(val, list):
            joined = ", ".join(str(x).strip() for x in val if str(x).strip())
            out[csv_key] = joined if joined else "Nessuno"

    pc_raw = out.get("primary_category")
    if isinstance(pc_raw, str):
        mapped = _CATEGORY_ALIASES.get(pc_raw.strip().lower())
        if mapped:
            out["primary_category"] = mapped

    sent_raw = out.get("sentiment")
    if isinstance(sent_raw, str):
        mapped_s = _SENTIMENT_ALIASES.get(sent_raw.strip().lower())
        if mapped_s:
            out["sentiment"] = mapped_s

    for junk in (
        "reasoning",
        "reasoning_content",
        "confidence",
        "sources",
        "sources_count",
        "analysis",
        "thought",
        "thinking",
    ):
        out.pop(junk, None)

    # Locale / modelli verbosi: drop chiavi fuori schema (extra=forbid).
    allowed = set(GeopoliticalArticleSchema.model_fields)
    for key in list(out):
        if key not in allowed:
            out.pop(key, None)

    for key in ("latitude", "longitude"):
        val = out.get(key)
        if isinstance(val, bool):
            continue
        if isinstance(val, int):
            out[key] = float(val)
        elif isinstance(val, str):
            try:
                out[key] = float(val.strip())
            except ValueError:
                pass

    rel = out.get("relevance_level")
    if isinstance(rel, bool):
        pass
    elif isinstance(rel, float) and rel.is_integer():
        out["relevance_level"] = int(rel)
    elif isinstance(rel, str) and rel.strip().isdigit():
        out["relevance_level"] = int(rel.strip())

    if isinstance(out.get("country_code"), str):
        out["country_code"] = out["country_code"].strip().upper()

    # Soft-normalize published_at: datetime ISO → YYYY-MM-DD.
    pa = out.get("published_at")
    if isinstance(pa, str):
        pa_stripped = pa.strip()
        if len(pa_stripped) >= 10 and ISO_DATE_PATTERN.match(pa_stripped[:10]):
            out["published_at"] = pa_stripped[:10]

    # Soft-clamp lunghezze stringa ai limiti schema (verbosità Gemma/DeepSeek).
    for key, limit in (
        ("title", 120),
        ("summary", 2000),
        ("companies_involved", 2000),
        ("tags", 2000),
        ("infrastructural_entities", 2000),
        ("source_url", 2048),
    ):
        val = out.get(key)
        if isinstance(val, str) and len(val) > limit:
            out[key] = val[:limit]

    # Soft remap: game/software e filosofia off-topic non restano in Geopolitica/…
    # Non inventare country_code qui. Non rimappare pezzi politici (anti false-positive).
    pc = out.get("primary_category")
    if isinstance(pc, str) and pc in ("Geopolitica", "Sicurezza", "Infrastrutture"):
        hint_blob = " ".join(
            str(out.get(k) or "")
            for k in (
                "title",
                "summary",
                "tags",
                "companies_involved",
                "infrastructural_entities",
            )
        )
        is_game = bool(_GAME_REVIEW_HINT.search(hint_blob))
        is_offtopic = bool(_OFFTOPIC_GEOPOLITICA_HINT.search(hint_blob))
        is_political = bool(_POLITICAL_CONTENT_HINT.search(hint_blob))
        if is_game or (is_offtopic and not is_political):
            out["primary_category"] = "Tecnologia"

    # Soft remap inverso: sport/cronaca giudiziaria / disastri non restano in Tecnologia.
    pc = out.get("primary_category")
    if isinstance(pc, str) and pc == "Tecnologia":
        hint_blob = " ".join(
            str(out.get(k) or "")
            for k in ("title", "summary", "tags", "companies_involved", "infrastructural_entities")
        )
        if _SPORT_LEGAL_HINT.search(hint_blob) and not _GAME_REVIEW_HINT.search(hint_blob):
            out["primary_category"] = "Geopolitica"
        elif _DISASTER_HINT.search(hint_blob) and not _GAME_REVIEW_HINT.search(hint_blob):
            out["primary_category"] = "Ambiente"
        elif _MARITIME_HINT.search(hint_blob):
            out["primary_category"] = "Infrastrutture"
        elif _KINETIC_SECURITY_HINT.search(hint_blob):
            out["primary_category"] = "Sicurezza"

    # Geopolitica troppo larga: cinetico → Sicurezza; sport puro → clamp relevance.
    pc = out.get("primary_category")
    hint_blob = " ".join(
        str(out.get(k) or "")
        for k in ("title", "summary", "tags", "companies_involved", "infrastructural_entities")
    )
    if isinstance(pc, str) and pc == "Geopolitica":
        if _KINETIC_SECURITY_HINT.search(hint_blob):
            out["primary_category"] = "Sicurezza"
        elif _SPORT_EVENT_HINT.search(hint_blob) and not _POLITICAL_CONTENT_HINT.search(
            hint_blob
        ):
            rel_now = out.get("relevance_level")
            if isinstance(rel_now, int) and rel_now > 2:
                out["relevance_level"] = 2
            elif isinstance(rel_now, str) and rel_now.strip().isdigit():
                out["relevance_level"] = min(2, int(rel_now.strip()))
    if isinstance(out.get("primary_category"), str) and out["primary_category"] == "Infrastrutture":
        if _MARITIME_HINT.search(hint_blob) and not out.get("infrastructural_entities"):
            pass  # leave entities to model; no invent
    # Soft-news / XX: non gonfiare relevance.
    if str(out.get("country_code") or "").upper() == "XX":
        rel_now = out.get("relevance_level")
        if isinstance(rel_now, int) and rel_now > 2:
            out["relevance_level"] = 2

    # companies_involved: niente stati/ISO scambiati per aziende; vuoto → Nessuno.
    co = out.get("companies_involved")
    if isinstance(co, str):
        parts = [x.strip() for x in co.split(",") if x.strip()]
        cleaned_co: list[str] = []
        for p in parts:
            up = p.upper()
            if up in {"NESSUNO", "NONE", "N/A"}:
                continue
            if len(up) == 2 and up in ISO_ALPHA2_CODES:
                continue
            if up in {
                "USA",
                "US",
                "UK",
                "UE",
                "EU",
                "ONU",
                "NATO",
                "IRAN",
                "RUSSIA",
                "CINA",
                "CHINA",
            }:
                continue
            cleaned_co.append(p)
        out["companies_involved"] = ", ".join(cleaned_co) if cleaned_co else "Nessuno"
    elif co is None:
        out["companies_involved"] = "Nessuno"

    # Soft fix country: conflitti US–Iran con vittime/attore US → primary US
    # (Gemma spesso ancora su IR/JO teatro o bersaglio).
    hint_geo = " ".join(
        str(out.get(k) or "")
        for k in ("title", "summary", "tags", "infrastructural_entities")
    )
    primary = str(out.get("country_code") or "").strip().upper()
    rc_raw = out.get("related_countries")
    if isinstance(rc_raw, list):
        related_set = {
            str(x).strip().upper()
            for x in rc_raw
            if str(x).strip() and str(x).strip().upper() in ISO_ALPHA2_CODES
        }
    elif isinstance(rc_raw, str):
        related_set = {
            x.strip().upper()
            for x in rc_raw.split(",")
            if x.strip() and x.strip().upper() in ISO_ALPHA2_CODES
        }
    else:
        related_set = set()
    if (
        _US_ACTOR_VICTIM_HINT.search(hint_geo)
        and _IRAN_MENTION_HINT.search(hint_geo)
        and primary in {"IR", "JO", "KW"}
        and ("US" in related_set or bool(re.search(r"\b(usa|u\.?s\.?a?|stati\s+uniti)\b", hint_geo, re.I)))
    ):
        old_primary = primary
        out["country_code"] = "US"
        related_set.discard("US")
        related_set.add(old_primary)
        # Controparte/teatro prima; ordine stabile senza sort alfabetico puro.
        ordered = [c for c in (old_primary, "IR", "JO", "KW") if c in related_set]
        ordered.extend(c for c in related_set if c not in ordered)
        out["related_countries"] = ", ".join(ordered[:5])
        lat_lon = _COUNTRY_CENTROIDS.get("US")
        if lat_lon is not None:
            out["latitude"], out["longitude"] = lat_lon

    # Regola schema: primo tag CSV = primary_category; dedupe e max 6 tag utili.
    pc = out.get("primary_category")
    tags = out.get("tags")
    if isinstance(pc, str) and pc in PRIMARY_CATEGORIES:
        parts: list[str] = []
        if isinstance(tags, str) and tags.strip():
            parts = [x.strip() for x in tags.split(",") if x.strip()]
        # Rimuovi vecchia categoria in testa/duplicati; ISO2 e nomi-paese ridondanti.
        _COUNTRY_TAG_NOISE = {
            "usa",
            "u.s.",
            "u.s.a.",
            "stati uniti",
            "iran",
            "russia",
            "ucraina",
            "cina",
            "china",
            "giordania",
            "kuwait",
            "cuba",
            "guyana",
            "argentina",
            "unione europea",
            "ue",
            "eu",
        }
        filtered: list[str] = []
        seen_tags: set[str] = set()
        for p in parts:
            if p == pc:
                continue
            up = p.upper()
            if len(up) == 2 and up in ISO_ALPHA2_CODES:
                continue
            if p.casefold() in _COUNTRY_TAG_NOISE:
                continue
            key = p.casefold()
            if key in seen_tags:
                continue
            seen_tags.add(key)
            filtered.append(p)
        out["tags"] = ", ".join([pc, *filtered[:5]])

    # Normalizza related_countries
    rc = out.get("related_countries")
    primary = str(out.get("country_code") or "").strip().upper()
    if isinstance(rc, list):
        rc = ", ".join(str(x) for x in rc if x)

    if isinstance(rc, str):
        parts = [x.strip().upper() for x in rc.split(",") if x.strip()]
        valid_parts = []
        seen = set()
        for p in parts:
            if p in ISO_ALPHA2_CODES and p != "XX" and p != primary and p not in seen:
                seen.add(p)
                valid_parts.append(p)
        if valid_parts:
            out["related_countries"] = ", ".join(valid_parts[:5])
        else:
            out["related_countries"] = "Nessuno"
    else:
        out["related_countries"] = "Nessuno"

    return out


def parse_llm_article_json(
    text: str | None,
    *,
    source_url: str | None = None,
    published_at: str | None = None,
    title: str | None = None,
) -> GeopoliticalArticleSchema:
    """Parse JSON modello → normalize quirks → validate strict.

    Opzionali ``source_url`` / ``published_at`` / ``title`` sovrascrivono o
    riempiono con ground truth Miniflux prima del validate (Gemma tronca date /
    inventa URL / omette title nei frammenti thinking).

    Raises:
        pydantic.ValidationError (anche su JSON vuoto/illeggibile) — il client
        usa correction/escalate invece di retry ciechi su ``JSONDecodeError``.
    SoT:
        llm-json-extraction; overwrite Miniflux su URL/data.
    """
    from pydantic import ValidationError as PydanticValidationError

    if text is None or not str(text).strip():
        raise PydanticValidationError.from_exception_data(
            "GeopoliticalArticleSchema",
            [
                {
                    "type": "value_error",
                    "loc": ("__json__",),
                    "input": text,
                    "ctx": {"error": ValueError("output JSON vuoto o assente")},
                }
            ],
        )

    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        # Strip fence opzionale ```json che Gemma emette a volte.
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        raw: Any
        try:
            raw = json.loads(cleaned)
        except json.JSONDecodeError:
            # Extra data / trailing junk: prendi il primo valore JSON.
            raw, _end = json.JSONDecoder().raw_decode(cleaned)
    except json.JSONDecodeError as exc:
        raise PydanticValidationError.from_exception_data(
            "GeopoliticalArticleSchema",
            [
                {
                    "type": "value_error",
                    "loc": ("__json__",),
                    "input": cleaned[:500],
                    "ctx": {"error": exc},
                }
            ],
        ) from exc

    if isinstance(raw, dict):
        raw = normalize_llm_json_dict(raw)
        if isinstance(source_url, str) and source_url.strip().lower().startswith(
            ("http://", "https://")
        ):
            raw["source_url"] = source_url.strip()[:2048]
        pub = (published_at or "").strip()
        if len(pub) >= 10 and ISO_DATE_PATTERN.match(pub[:10]):
            raw["published_at"] = pub[:10]
        # Gemma a volte omette title nei frammenti: ground truth Miniflux.
        if (not isinstance(raw.get("title"), str) or not str(raw.get("title")).strip()) and (
            isinstance(title, str) and title.strip()
        ):
            raw["title"] = title.strip()[:120]
    return GeopoliticalArticleSchema.model_validate(raw)


def parse_csv_list(val: str) -> list[str]:
    """CSV schema → lista Python; ``Nessuno``/vuoto → lista vuota (uso commit/API)."""
    if not val:
        return []
    if val.strip().lower() in ["nessuno", "nessuna", "nessun", "none", "n/a", ""]:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


def _normalize_fallback_date(published_at: str) -> str:
    """Data sicura per articolo fallback; invalida → ``2000-01-01``."""
    if not published_at or not ISO_DATE_PATTERN.match(published_at):
        return "2000-01-01"
    try:
        date.fromisoformat(published_at)
    except ValueError:
        return "2000-01-01"
    return published_at


def get_fallback_article(
    title: str, source_url: str, published_at: str
) -> GeopoliticalArticleSchema:
    """Articolo neutro di emergenza quando l'API LLM è irrecuperabile.

    Evita crash della pipeline: XX / 0,0 / Infrastrutture / relevance 1.
    Side-effects: nessuno verso rete/DB — solo costruzione in-memory.
    """
    clean_date = _normalize_fallback_date(published_at)
    safe_url = (
        source_url
        if SOURCE_URL_PATTERN.match(source_url or "")
        else "https://example.com/unknown"
    )

    return GeopoliticalArticleSchema(
        title=(title or "Articolo sconosciuto")[:120],
        summary="Errore di elaborazione automatica del testo. Notizia registrata con parametri di fallback.",
        published_at=clean_date,
        source_url=safe_url[:2048],
        country_code="XX",
        latitude=0.0,
        longitude=0.0,
        companies_involved="Nessuno",
        tags="Infrastrutture",
        primary_category="Infrastrutture",
        sentiment="Neutrale",
        infrastructural_entities="Nessuno",
        related_countries="Nessuno",
        relevance_level=1,
    )
