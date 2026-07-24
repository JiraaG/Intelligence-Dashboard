"""Resolver feed_url da seed JSON Miniflux (title <-> feed_title).

SoT: plan_impl_finops_ui_metrics.md
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import MINIFLUX_FEEDS_SEED_PATH

logger = logging.getLogger("radar.api.feed_url_resolve")

_SEED_MAP: dict[str, str] | None = None


def _load_seed_map() -> dict[str, str]:
    global _SEED_MAP
    if _SEED_MAP is not None:
        return _SEED_MAP

    mapping: dict[str, str] = {}
    candidate_paths: list[Path] = []
    if MINIFLUX_FEEDS_SEED_PATH:
        candidate_paths.append(Path(MINIFLUX_FEEDS_SEED_PATH))
    candidate_paths.extend([
        Path("/app/config/miniflux-feeds.seed.json"),
        Path("config/miniflux-feeds.seed.json"),
        Path("../config/miniflux-feeds.seed.json"),
        Path("../../config/miniflux-feeds.seed.json"),
    ])

    found_path: Path | None = None
    for p in candidate_paths:
        if p.exists() and p.is_file():
            found_path = p
            break

    if not found_path:
        logger.warning("File seed Miniflux non trovato nei percorsi: %s", [str(p) for p in candidate_paths])
        _SEED_MAP = mapping
        return mapping

    try:
        data = json.loads(found_path.read_text(encoding="utf-8"))
        feeds = data.get("feeds", [])
        if isinstance(feeds, list):
            for item in feeds:
                if isinstance(item, dict):
                    title = item.get("title")
                    feed_url = item.get("feed_url")
                    if title and feed_url:
                        clean_title = str(title).strip()
                        url_val = str(feed_url).strip()
                        mapping[clean_title] = url_val
                        if clean_title.lower().startswith("feed:"):
                            no_prefix = clean_title[5:].strip()
                            mapping[no_prefix] = url_val
        logger.info("Seed map Miniflux caricata (%d entry) da %s", len(mapping), found_path)
    except Exception as exc:
        logger.error("Errore nel caricamento del file seed Miniflux %s: %s", found_path, exc)

    _SEED_MAP = mapping
    return mapping


def resolve_feed_url(feed_title: str | None) -> str | None:
    """Risolve feed_url dal titolo del feed Miniflux."""
    if not feed_title:
        return None
    seed_map = _load_seed_map()
    clean = str(feed_title).strip()
    if clean in seed_map:
        return seed_map[clean]
    if clean.lower().startswith("feed:"):
        no_prefix = clean[5:].strip()
        if no_prefix in seed_map:
            return seed_map[no_prefix]
    return None


def reset_seed_map_cache() -> None:
    """Utility per unit test."""
    global _SEED_MAP
    _SEED_MAP = None
