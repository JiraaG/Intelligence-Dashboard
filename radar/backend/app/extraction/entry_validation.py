"""Validazione e normalizzazione dei payload entry Miniflux.

Confine input: dict grezzo API → ``ValidatedMinifluxEntry`` immutabile, oppure
``EntryValidationError`` (il chiamante isola per-entry senza abortire il batch).
URL canonico prima di dedup/persistenza; content con fallback su summary e cap byte.

SoT:
    .agents/AGENTS.md §3 dedup pre-LLM; docs/01_getting_started.md §6 ingest;
    radar/.ecc/rules/backend.md (sanitize / bound).
"""

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
    """Entry Miniflux già validata; campi stabili per dedup, parse e commit.

    ``source_url`` è canonico (scheme/host lower, no fragment, slash trailing tolto).
    ``published_at`` è solo la parte data ``YYYY-MM-DD``.
    ``content`` può essere HTML grezzo (sanitize successiva in ``parser``).
    """

    id: int
    source_url: str
    title: str
    content: str
    published_at: str
    feed_title: str
    feed_id: int | None = None
    feed_domain: str | None = None


class EntryValidationError(ValueError):
    """Entry Miniflux malformata: va saltata, non deve far fallire le sorelle."""


def normalize_source_url(url: str) -> str:
    """Normalizza l'URL una sola volta prima di deduplicazione e persistenza.

    Lowercase di scheme/host, trim whitespace, rimozione slash finale (tranne root),
    scarto del fragment per identità stabile su ``articles.source_url``.

    Args:
        url: URL grezzo dal campo Miniflux ``url``.
    Returns:
        URL canonico http/https, lunghezza ≤ 2048.
    Raises:
        EntryValidationError: tipo errato, vuoto, schema non http(s), host assente,
            o lunghezza eccessiva.
    SoT:
        AGENTS.md §3 (dedup su URL); skill llm-json-extraction (overwrite source_url).
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
            "",  # fragment scartato: non fa parte dell'identità stabile
        )
    )
    if len(normalized) > 2048:
        raise EntryValidationError("source_url supera 2048 caratteri")
    return normalized


def _parse_published_date(raw: object) -> str:
    """Estrae ``YYYY-MM-DD`` da timestamp ISO Miniflux (con o senza ``T``).

    Raises:
        EntryValidationError: assente, non stringa, o data non ISO valida.
    """
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
    """Id Miniflux intero positivo; rifiuta ``bool`` (sottotipo di ``int`` in Python)."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise EntryValidationError(f"id entry non valido: {raw!r}")
    if raw <= 0:
        raise EntryValidationError(f"id entry non positivo: {raw}")
    return raw


def _validate_title(raw: object) -> str:
    """Titolo non vuoto dopo strip; tetto 2000 caratteri (protezione payload)."""
    if not isinstance(raw, str):
        raise EntryValidationError("title deve essere una stringa")
    title = raw.strip()
    if not title:
        raise EntryValidationError("title vuoto")
    if len(title) > 2000:
        raise EntryValidationError("title troppo lungo")
    return title


def _validate_feed_title(raw_feed: object) -> str:
    """Titolo feed da oggetto ``feed``; default ``RSS Feed`` se assente/vuoto."""
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


def _extract_feed_id(raw_feed: object) -> int | None:
    """Estrae ID numerico feed da Miniflux ``feed.id`` se presente."""
    if isinstance(raw_feed, dict):
        fid = raw_feed.get("id")
        if isinstance(fid, int) and not isinstance(fid, bool) and fid > 0:
            return fid
    return None


def _extract_feed_domain(raw_feed: object, source_url: str) -> str | None:
    """Estrae dominio host da ``feed.site_url`` / ``feed.feed_url`` o fallback su ``source_url``."""
    if isinstance(raw_feed, dict):
        for candidate_key in ("site_url", "feed_url"):
            url_val = raw_feed.get(candidate_key)
            if isinstance(url_val, str) and url_val.strip():
                try:
                    parts = urlsplit(url_val.strip())
                    if parts.netloc:
                        return parts.netloc.lower()
                except Exception:
                    pass
    if source_url:
        try:
            parts = urlsplit(source_url)
            if parts.netloc:
                return parts.netloc.lower()
        except Exception:
            pass
    return None


def _validate_content(raw_entry: dict) -> str:
    """Corpo entry: ``content``, altrimenti ``summary``, altrimenti stringa vuota.

    Confronta la lunghezza in byte UTF-8 con ``MAX_ENTRY_CONTENT_BYTES`` prima
    del parse HTML (secondo check anche in ``parser.strip_html_tags``).
    """
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
    """Valida un dict entry Miniflux grezzo in struttura immutabile.

    Args:
        raw: Oggetto JSON entry dalla lista ``entries``.
    Returns:
        ``ValidatedMinifluxEntry`` pronto per dedup/sanitize/LLM.
    Raises:
        EntryValidationError: payload malformato — il chiamante deve isolare
            l'entry me continuare con le sorelle.
    SoT:
        docs/01 §6; llm-json-extraction (confine input non fidato).
    """
    if not isinstance(raw, dict):
        raise EntryValidationError("entry non è un oggetto JSON")

    entry_id = _validate_entry_id(raw.get("id"))
    source_url = normalize_source_url(raw.get("url", ""))
    title = _validate_title(raw.get("title"))
    published_at = _parse_published_date(raw.get("published_at"))
    raw_feed = raw.get("feed")
    feed_title = _validate_feed_title(raw_feed)
    feed_id = _extract_feed_id(raw_feed)
    feed_domain = _extract_feed_domain(raw_feed, source_url)
    content = _validate_content(raw)

    return ValidatedMinifluxEntry(
        id=entry_id,
        source_url=source_url,
        title=title,
        content=content,
        published_at=published_at,
        feed_title=feed_title,
        feed_id=feed_id,
        feed_domain=feed_domain,
    )


def parse_iso_date_or_today(value: str) -> date:
    """Parse ``YYYY-MM-DD`` per binding DB; se invalida, oggi (fail-soft al commit).

    Usata da ``commit/db_commit`` su ``published_at`` già normalizzato in teoria;
    il fallback a ``date.today()`` evita di far fallire l'intera transazione per
    una data residuale non ISO.
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return date.today()
