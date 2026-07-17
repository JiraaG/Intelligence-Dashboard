# validator.py — Pydantic Schema Validation & Fallback

from __future__ import annotations

import json
import math
import re
from datetime import date
from typing import Any, Literal, Self

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

ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
# Soft remap: game / entertainment reviews often mislabeled as Geopolitica/Infrastrutture.
_GAME_REVIEW_HINT = re.compile(
    r"(videogioc\w*|video\s*game|videogame|game\s*review|"
    r"recensione.{0,40}(gioco|game)|ps5|xbox|nintendo|steam\b|"
    r"\bpc,\s*ps5\b|\bunreal\b|\bunity\b)",
    re.IGNORECASE | re.DOTALL,
)
# Soft remap: philosophy / explicit non-news fluff must not stay in Geopolitica.
_OFFTOPIC_GEOPOLITICA_HINT = re.compile(
    r"non\s+(presenta|contiene)\s+informazioni\s+geopolitic|"
    r"nessun[ao]?\s+informazione\s+geopolitic|"
    r"concetti?\s+filosofic|"
    r"fallacia\s+determinist|"
    r"\bfilosofia\b|"
    r"no\s+geopolitical\s+(content|information|relevance)",
    re.IGNORECASE,
)

# ISO 3166-1 alpha-2 (~249) + sentinel XX for undetermined geography.
ISO_ALPHA2_CODES: frozenset[str] = frozenset(
    {
        "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR", "AS", "AT", "AU", "AW", "AX", "AZ",
        "BA", "BB", "BD", "BE", "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ", "BR", "BS",
        "BT", "BV", "BW", "BY", "BZ",
        "CA", "CC", "CD", "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN", "CO", "CR", "CU", "CV", "CW",
        "CX", "CY", "CZ",
        "DE", "DJ", "DK", "DM", "DO", "DZ",
        "EC", "EE", "EG", "EH", "ER", "ES", "ET",
        "FI", "FJ", "FK", "FM", "FO", "FR",
        "GA", "GB", "GD", "GE", "GF", "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT",
        "GU", "GW", "GY",
        "HK", "HM", "HN", "HR", "HT", "HU",
        "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT",
        "JE", "JM", "JO", "JP",
        "KE", "KG", "KH", "KI", "KM", "KN", "KP", "KR", "KW", "KY", "KZ",
        "LA", "LB", "LC", "LI", "LK", "LR", "LS", "LT", "LU", "LV", "LY",
        "MA", "MC", "MD", "ME", "MF", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MQ", "MR", "MS",
        "MT", "MU", "MV", "MW", "MX", "MY", "MZ",
        "NA", "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU", "NZ",
        "OM",
        "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM", "PN", "PR", "PS", "PT", "PW", "PY",
        "QA",
        "RE", "RO", "RS", "RU", "RW",
        "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI", "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS",
        "ST", "SV", "SX", "SY", "SZ",
        "TC", "TD", "TF", "TG", "TH", "TJ", "TK", "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW", "TZ",
        "UA", "UG", "UM", "US", "UY", "UZ",
        "VA", "VC", "VE", "VG", "VI", "VN", "VU",
        "WF", "WS",
        "YE", "YT",
        "ZA", "ZM", "ZW",
        "XX",
    }
)


class GeopoliticalArticleSchema(BaseModel):
    """
    Schema di validazione Pydantic ed estrazione strutturata dei dati.
    Strict mode: categorie, sentiment e date invalidi sono REJECTED (no coerce silenzioso).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str = Field(
        max_length=120,
        description="Titolo normalizzato privo di elementi di clickbait. Massimo 120 caratteri.",
    )
    summary: str = Field(
        max_length=2000,
        description="Sintesi esecutiva densa di informazioni di massimo due frasi.",
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
    relevance_level: int = Field(
        ge=1,
        le=5,
        description="Grado di rilevanza geopolitica dell'articolo da 1 a 5.",
    )

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: str) -> str:
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
        if not isinstance(value, str) or not SOURCE_URL_PATTERN.match(value):
            raise ValueError("source_url deve iniziare con http:// o https://")
        if len(value) > 2048:
            raise ValueError("source_url supera i 2048 caratteri")
        return value

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("country_code deve essere una stringa")
        if value == "XX":
            return "XX"
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country_code deve essere un codice ISO Alpha-2 valido o 'XX'")
        normalized = value.upper()
        if normalized not in ISO_ALPHA2_CODES:
            raise ValueError(f"country_code '{value}' non è un codice ISO Alpha-2 riconosciuto")
        return normalized

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
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
        if not isinstance(value, float):
            raise ValueError("longitude deve essere un float")
        if not math.isfinite(value):
            raise ValueError("longitude deve essere un numero finito")
        if value < -180.0 or value > 180.0:
            raise ValueError("longitude deve essere compresa tra -180 e 180")
        return value

    @model_validator(mode="after")
    def first_tag_matches_primary(self) -> Self:
        first = (self.tags.split(",")[0].strip() if self.tags else "")
        if first.lower() in {"nessuno", "nessuna", "none", ""}:
            raise ValueError("tags deve iniziare con primary_category")
        if first != self.primary_category:
            raise ValueError(
                f"primo tag {first!r} != primary_category {self.primary_category!r}"
            )
        return self


def normalize_llm_json_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Provider-side shape fixes before strict Pydantic validate.
    Does not change GeopoliticalArticleSchema; flattens common DeepSeek quirks
    (nested coordinates, category alias, int lat/lon, float relevance).
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

    for junk in ("reasoning", "reasoning_content", "confidence", "sources", "analysis"):
        out.pop(junk, None)

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

    # Soft-normalize published_at: accept ISO datetime → YYYY-MM-DD.
    pa = out.get("published_at")
    if isinstance(pa, str):
        pa_stripped = pa.strip()
        if len(pa_stripped) >= 10 and ISO_DATE_PATTERN.match(pa_stripped[:10]):
            out["published_at"] = pa_stripped[:10]

    # Soft-clamp string lengths to schema limits (Gemma/DeepSeek verbosity).
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

    # Soft remap: game/software reviews must not land in Geopolitica/Sicurezza/Infrastrutture.
    # Same for philosophy / explicit "no geopolitical content" fluff.
    pc = out.get("primary_category")
    if isinstance(pc, str) and pc in ("Geopolitica", "Sicurezza", "Infrastrutture"):
        hint_blob = " ".join(
            str(out.get(k) or "")
            for k in ("title", "summary", "tags", "companies_involved", "infrastructural_entities")
        )
        if _GAME_REVIEW_HINT.search(hint_blob) or _OFFTOPIC_GEOPOLITICA_HINT.search(
            hint_blob
        ):
            out["primary_category"] = "Tecnologia"

    # Enforce schema rule: first CSV tag must equal primary_category.
    pc = out.get("primary_category")
    tags = out.get("tags")
    if isinstance(pc, str) and pc in PRIMARY_CATEGORIES:
        if not isinstance(tags, str) or not tags.strip():
            out["tags"] = pc
        else:
            parts = [x.strip() for x in tags.split(",") if x.strip()]
            if not parts or parts[0] != pc:
                rest = [p for p in parts if p != pc]
                out["tags"] = ", ".join([pc, *rest]) if rest else pc

    return out


def parse_llm_article_json(
    text: str | None,
    *,
    source_url: str | None = None,
    published_at: str | None = None,
) -> GeopoliticalArticleSchema:
    """
    Parse model JSON → normalize quirks → strict GeopoliticalArticleSchema.

    Optional source_url / published_at override Miniflux ground truth before
    validate (fixes Gemma truncating dates / inventing URLs).

    Raises pydantic.ValidationError (not bare JSONDecodeError) so the client
    correction / escalate path runs instead of blind retries.
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
        # Strip optional ```json fences Gemma sometimes emits.
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
            # Extra data / trailing junk: take the first JSON value.
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
    return GeopoliticalArticleSchema.model_validate(raw)


def parse_csv_list(val: str) -> list[str]:
    """Trasforma una stringa separata da virgole in una lista, gestendo i valori vuoti/Nessuno."""
    if not val:
        return []
    if val.strip().lower() in ["nessuno", "nessuna", "nessun", "none", "n/a", ""]:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


def _normalize_fallback_date(published_at: str) -> str:
    if not published_at or not ISO_DATE_PATTERN.match(published_at):
        return "2000-01-01"
    try:
        date.fromisoformat(published_at)
    except ValueError:
        return "2000-01-01"
    return published_at


def get_fallback_article(title: str, source_url: str, published_at: str) -> GeopoliticalArticleSchema:
    """
    Costruisce un GeopoliticalArticleSchema con dati di fallback sicuri e neutri.
    Evita crash della pipeline in caso di errori API irrecuperabili.
    """
    clean_date = _normalize_fallback_date(published_at)
    safe_url = source_url if SOURCE_URL_PATTERN.match(source_url or "") else "https://example.com/unknown"

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
        relevance_level=1,
    )
