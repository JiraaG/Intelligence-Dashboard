"""Catalogo feed: merge seed RO + Miniflux live; toggle disabled.

SoT: plan_impl_fonti_feed_management.md §4.2–4.3; skill radar-api-contract.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.core.config import MINIFLUX_FEEDS_SEED_PATH

logger = logging.getLogger("radar.api.feeds")


def normalize_feed_url(url: str) -> str:
    """Normalizza URL feed per match seed↔live (strip trailing slash)."""
    return str(url or "").strip().rstrip("/")


def find_live_feed(
    live_by_url: dict[str, dict[str, Any]], seed_url: str
) -> dict[str, Any] | None:
    """Match feed live per URL normalizzata + euristica Guardian /uk/."""
    key = normalize_feed_url(seed_url)
    if not key:
        return None
    if key in live_by_url:
        return live_by_url[key]
    alt = key.replace("://www.theguardian.com/", "://www.theguardian.com/uk/", 1)
    if alt != key and alt in live_by_url:
        return live_by_url[alt]
    for stored, feed in live_by_url.items():
        if stored == key or stored.endswith(key) or key.endswith(stored):
            return feed
    return None


def load_seed_feeds(seed_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Carica lista feed dallo seed JSON (RO). Assente/errore → []."""
    candidate_paths: list[Path] = []
    path_hint = seed_path or MINIFLUX_FEEDS_SEED_PATH
    if path_hint:
        candidate_paths.append(Path(str(path_hint)))
    candidate_paths.extend(
        [
            Path("/app/config/miniflux-feeds.seed.json"),
            Path("config/miniflux-feeds.seed.json"),
            Path("../config/miniflux-feeds.seed.json"),
            Path("../../config/miniflux-feeds.seed.json"),
        ]
    )
    found: Path | None = None
    for p in candidate_paths:
        if p.exists() and p.is_file():
            found = p
            break
    if found is None:
        logger.warning("Seed Miniflux non trovato per /api/feeds")
        return []
    try:
        data = json.loads(found.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Errore lettura seed %s: %s", found, exc)
        return []
    feeds = data.get("feeds", [])
    if not isinstance(feeds, list):
        return []
    return [f for f in feeds if isinstance(f, dict)]


def seed_enabled(spec: dict[str, Any]) -> bool:
    """Campo ``enabled`` opzionale: assente = True."""
    if "enabled" not in spec:
        return True
    return bool(spec.get("enabled"))


def _live_category_title(live: dict[str, Any]) -> str:
    cat = live.get("category")
    if isinstance(cat, dict):
        title = str(cat.get("title") or "").strip()
        if title:
            return title
    return "Altro"


def _feed_item_from_seed_and_live(
    spec: dict[str, Any], live: dict[str, Any] | None
) -> dict[str, Any]:
    enabled = seed_enabled(spec)
    category = str(spec.get("category") or "Altro")
    title = str(spec.get("title") or spec.get("feed_url") or "")
    feed_url = str(spec.get("feed_url") or "")
    scraper = str(spec.get("scraper_rules") or "")
    crawler = bool(spec.get("crawler", True))

    if live is None:
        return {
            "id": None,
            "title": title,
            "feed_url": feed_url,
            "site_url": "",
            "category": category,
            "scraper_rules": scraper,
            "crawler": crawler,
            "disabled": not enabled,
            "enabled_in_seed": enabled,
            "in_seed": True,
            "parsing_error_count": 0,
            "parsing_error_msg": "",
            "checked_at": None,
            "next_check_at": None,
        }

    err_count = int(live.get("parsing_error_count") or 0)
    return {
        "id": int(live["id"]) if live.get("id") is not None else None,
        "title": str(live.get("title") or title),
        "feed_url": str(live.get("feed_url") or feed_url),
        "site_url": str(live.get("site_url") or ""),
        "category": category,
        "scraper_rules": str(live.get("scraper_rules") or scraper),
        "crawler": bool(live.get("crawler", crawler)),
        "disabled": bool(live.get("disabled", False)),
        "enabled_in_seed": enabled,
        "in_seed": True,
        "parsing_error_count": err_count,
        "parsing_error_msg": str(live.get("parsing_error_message") or live.get("parsing_error_msg") or ""),
        "checked_at": live.get("checked_at"),
        "next_check_at": live.get("next_check_at"),
    }


def _feed_item_from_live_only(live: dict[str, Any]) -> dict[str, Any]:
    err_count = int(live.get("parsing_error_count") or 0)
    return {
        "id": int(live["id"]) if live.get("id") is not None else None,
        "title": str(live.get("title") or live.get("feed_url") or ""),
        "feed_url": str(live.get("feed_url") or ""),
        "site_url": str(live.get("site_url") or ""),
        "category": _live_category_title(live),
        "scraper_rules": str(live.get("scraper_rules") or ""),
        "crawler": bool(live.get("crawler", False)),
        "disabled": bool(live.get("disabled", False)),
        "enabled_in_seed": True,
        "in_seed": False,
        "parsing_error_count": err_count,
        "parsing_error_msg": str(live.get("parsing_error_message") or live.get("parsing_error_msg") or ""),
        "checked_at": live.get("checked_at"),
        "next_check_at": live.get("next_check_at"),
    }


def merge_feeds_catalog(
    seed_feeds: list[dict[str, Any]],
    live_feeds: list[dict[str, Any]],
) -> dict[str, Any]:
    """Unisce seed + live in groups per category con conteggi attivi/errori."""
    live_by_url: dict[str, dict[str, Any]] = {}
    for live in live_feeds:
        url = normalize_feed_url(str(live.get("feed_url") or ""))
        if url:
            live_by_url[url] = live

    matched_live_ids: set[int] = set()
    items: list[dict[str, Any]] = []

    for spec in seed_feeds:
        live = find_live_feed(live_by_url, str(spec.get("feed_url") or ""))
        item = _feed_item_from_seed_and_live(spec, live)
        if live is not None and live.get("id") is not None:
            matched_live_ids.add(int(live["id"]))
        items.append(item)

    for live in live_feeds:
        live_id = live.get("id")
        if live_id is not None and int(live_id) in matched_live_ids:
            continue
        items.append(_feed_item_from_live_only(live))

    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_cat[str(item["category"])].append(item)

    groups: list[dict[str, Any]] = []
    for category in sorted(by_cat.keys(), key=lambda c: c.lower()):
        feeds = sorted(by_cat[category], key=lambda f: str(f.get("title") or "").lower())
        groups.append({"category": category, "feeds": feeds})

    total_count = len(items)
    active_count = sum(1 for i in items if not i.get("disabled"))
    error_count = sum(1 for i in items if int(i.get("parsing_error_count") or 0) > 0)

    return {
        "active_count": active_count,
        "total_count": total_count,
        "error_count": error_count,
        "groups": groups,
    }


def require_feed_admin_token(
    configured_token: str,
    provided_header: str | None,
) -> None:
    """Se ``configured_token`` non vuoto, richiede header uguale; altrimenti no-op.

    Raises:
        PermissionError: token richiesto ma assente/errato (mappato a 401 dal caller).
    """
    expected = (configured_token or "").strip()
    if not expected:
        return
    got = (provided_header or "").strip()
    if got != expected:
        raise PermissionError("invalid_or_missing_feed_admin_token")
