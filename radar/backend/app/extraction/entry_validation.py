"""Validation and normalization of Miniflux entry payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit

from app.core.config import MAX_ENTRY_CONTENT_BYTES

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HTTP_SCHEME = re.compile(r"^https?$", re.IGNORECASE)


@dataclass(frozen=True)
class ValidatedMinifluxEntry:
    id: int
    source_url: str
    title: str
    content: str
    published_at: str
    feed_title: str


class EntryValidationError(ValueError):
    """Raised when a Miniflux entry is malformed and must be skipped."""


def normalize_source_url(url: str) -> str:
    """
    Normalize a source URL once before deduplication and persistence.
    Lowercases scheme/host, strips whitespace and trailing slash (except root).
    """
    if not isinstance(url, str):
        raise EntryValidationError("source_url deve essere una stringa")

    cleaned = url.strip()
    if not cleaned:
        raise EntryValidationError("source_url vuoto")

    parts = urlsplit(cleaned)
    if not _HTTP_SCHEME.match(parts.scheme or ""):
        raise EntryValidationError(f"source_url deve usare http/https: {cleaned!r}")
    if not parts.netloc:
        raise EntryValidationError(f"source_url senza host: {cleaned!r}")

    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            parts.query,
            "",  # fragment discarded for stable identity
        )
    )
    if len(normalized) > 2048:
        raise EntryValidationError("source_url supera 2048 caratteri")
    return normalized


def _parse_published_date(raw: object) -> str:
    if raw is None:
        raise EntryValidationError("published_at mancante")
    if not isinstance(raw, str):
        raise EntryValidationError("published_at deve essere una stringa")

    text = raw.strip()
    if not text:
        raise EntryValidationError("published_at vuoto")

    if "T" in text:
        date_part = text.split("T", 1)[0]
    else:
        date_part = text[:10]

    if not _ISO_DATE.match(date_part):
        raise EntryValidationError(f"published_at non ISO: {raw!r}")

    try:
        date.fromisoformat(date_part)
    except ValueError as exc:
        raise EntryValidationError(f"published_at data non valida: {raw!r}") from exc

    return date_part


def _validate_entry_id(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise EntryValidationError(f"id entry non valido: {raw!r}")
    if raw <= 0:
        raise EntryValidationError(f"id entry non positivo: {raw}")
    return raw


def _validate_title(raw: object) -> str:
    if not isinstance(raw, str):
        raise EntryValidationError("title deve essere una stringa")
    title = raw.strip()
    if not title:
        raise EntryValidationError("title vuoto")
    if len(title) > 2000:
        raise EntryValidationError("title troppo lungo")
    return title


def _validate_feed_title(raw_feed: object) -> str:
    if raw_feed is None:
        return "RSS Feed"
    if not isinstance(raw_feed, dict):
        raise EntryValidationError("campo feed deve essere un oggetto")
    title = raw_feed.get("title", "RSS Feed")
    if title is None:
        return "RSS Feed"
    if not isinstance(title, str):
        raise EntryValidationError("feed.title deve essere una stringa")
    cleaned = title.strip() or "RSS Feed"
    if len(cleaned) > 500:
        raise EntryValidationError("feed.title troppo lungo")
    return cleaned


def _validate_content(raw_entry: dict) -> str:
    content = raw_entry.get("content")
    if content is None or content == "":
        content = raw_entry.get("summary")
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise EntryValidationError("content/summary deve essere una stringa")

    content_bytes = len(content.encode("utf-8"))
    if content_bytes > MAX_ENTRY_CONTENT_BYTES:
        raise EntryValidationError(
            f"contenuto entry supera MAX_ENTRY_CONTENT_BYTES "
            f"({content_bytes} > {MAX_ENTRY_CONTENT_BYTES})"
        )
    return content


def validate_miniflux_entry(raw: object) -> ValidatedMinifluxEntry:
    """
    Validate a raw Miniflux entry dict.
    Raises EntryValidationError on malformed payloads — callers must isolate per entry.
    """
    if not isinstance(raw, dict):
        raise EntryValidationError("entry non è un oggetto JSON")

    entry_id = _validate_entry_id(raw.get("id"))
    source_url = normalize_source_url(raw.get("url", ""))
    title = _validate_title(raw.get("title"))
    published_at = _parse_published_date(raw.get("published_at"))
    feed_title = _validate_feed_title(raw.get("feed"))
    content = _validate_content(raw)

    return ValidatedMinifluxEntry(
        id=entry_id,
        source_url=source_url,
        title=title,
        content=content,
        published_at=published_at,
        feed_title=feed_title,
    )


def parse_iso_date_or_today(value: str) -> date:
    """Parse YYYY-MM-DD; used by DB commit for published_at binding."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return date.today()
