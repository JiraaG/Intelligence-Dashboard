# validator.py — Pydantic Schema Validation & Fallback

from __future__ import annotations

import math
import re
from datetime import date
from typing import Literal, Self

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
