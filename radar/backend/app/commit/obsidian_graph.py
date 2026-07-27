"""Seed/sync Obsidian Graph (``.obsidian/graph.json``) — Fase G hub-centric.

Colori tipologici = SoT FE ``styles.scss`` ``--color-*``. Articoli restano
colore default (massa neutra); hub nazioni argento; company/entity/tag muted.

Radar sovrascrive solo ``colorGroups`` (+ flag display leggeri) su file
esistente, preservando scale/forces/camera utente.

SoT:
    radar/obsidian/graph.json (docs/ops mirror); radar_overview §G Graph visual.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.classification.validator import PRIMARY_CATEGORIES
from app.core.config import OBSIDIAN_VAULT_PATH

logger = logging.getLogger("radar.commit.obsidian_graph")

# Hex SoT allineati a radar/frontend/src/styles.scss (--color-*).
CATEGORY_HEX: dict[str, str] = {
    "Ambiente": "#2ecc71",
    "Cybersecurity": "#ff007f",
    "Difesa": "#dc2626",
    "Economia": "#00e676",
    "Energia": "#ffd700",
    "Finanza": "#76ff03",
    "Geopolitica": "#a855f7",
    "Infrastrutture": "#78909c",
    "Intelligenza Artificiale": "#00f5d4",
    "Materie Prime": "#f59e0b",
    "Nucleare": "#00f0ff",
    "Salute": "#ff1744",
    "Sicurezza": "#ff6d00",
    "Spazio": "#6366f1",
    "Tecnologia": "#2979ff",
}

COUNTRY_HEX = "#d0d7de"  # argento chiaro — distinto da Infrastrutture #78909c
SECONDARY_HEX = "#484f58"  # company / entity / tag muted

_FORCE_DEFAULTS: dict[str, Any] = {
    "centerStrength": 0.52,
    "repelStrength": 12,
    "linkStrength": 1,
    "linkDistance": 280,
}


def hex_to_obsidian_rgb(hex_color: str) -> int:
    """Converte ``#RRGGBB`` nell'intero RGB packed di Obsidian Graph."""
    raw = hex_color.strip().lstrip("#")
    if len(raw) != 6:
        raise ValueError(f"hex colore non valido: {hex_color!r}")
    r = int(raw[0:2], 16)
    g = int(raw[2:4], 16)
    b = int(raw[4:6], 16)
    return (r << 16) | (g << 8) | b


def _color_group(query: str, hex_color: str) -> dict[str, Any]:
    return {
        "query": query,
        "color": {"a": 1, "rgb": hex_to_obsidian_rgb(hex_color)},
    }


def build_color_groups() -> list[dict[str, Any]]:
    """Ordine: 15 hub categoria → countries → companies/entities/tags."""
    missing = [c for c in PRIMARY_CATEGORIES if c not in CATEGORY_HEX]
    if missing:
        raise RuntimeError(f"CATEGORY_HEX incompleto vs PRIMARY_CATEGORIES: {missing}")

    groups: list[dict[str, Any]] = []
    for cat in PRIMARY_CATEGORIES:
        groups.append(_color_group(f"path:_meta/categories/{cat}", CATEGORY_HEX[cat]))
    groups.append(_color_group("path:_meta/countries", COUNTRY_HEX))
    for sub in ("companies", "entities", "tags"):
        groups.append(_color_group(f"path:_meta/{sub}", SECONDARY_HEX))
    return groups


def build_default_graph_config() -> dict[str, Any]:
    """Template Graph completo per vault nuovi."""
    return {
        "collapse-filter": True,
        "search": "",
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": True,
        "showOrphans": False,
        "collapse-color-groups": False,
        "colorGroups": build_color_groups(),
        "collapse-display": True,
        "showArrow": False,
        "textFadeMultiplier": -0.5,
        "nodeSizeMultiplier": 1.15,
        "lineSizeMultiplier": 1,
        "collapse-forces": True,
        **_FORCE_DEFAULTS,
        "scale": 0.2,
        "close": True,
    }


def graph_json_path(vault_root: Path) -> Path:
    """Path ``{vault}/.obsidian/graph.json``."""
    return vault_root / ".obsidian" / "graph.json"


def ensure_obsidian_graph_config(vault_path: str | None = None) -> Path:
    """Crea o aggiorna ``.obsidian/graph.json`` (hub-centric colorGroups).

    - File assente → scrive template completo.
    - File presente → sync ``colorGroups`` + flag display leggeri; preserva
      scale / forces / camera e altre chiavi utente.

    Returns:
        Path del ``graph.json`` scritto.
    """
    root = Path(vault_path or OBSIDIAN_VAULT_PATH)
    obsidian_dir = root / ".obsidian"
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    target = graph_json_path(root)
    color_groups = build_color_groups()

    if not target.is_file():
        config = build_default_graph_config()
        _write_graph_json(target, config)
        logger.info(
            "Obsidian graph.json creato (colorGroups=%s) in %s",
            len(color_groups),
            target,
        )
        return target

    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "graph.json illeggibile (%s) — riscrivo template in %s",
            exc,
            target,
        )
        _write_graph_json(target, build_default_graph_config())
        return target

    if not isinstance(existing, dict):
        logger.warning("graph.json non-object — riscrivo template in %s", target)
        _write_graph_json(target, build_default_graph_config())
        return target

    existing["colorGroups"] = color_groups
    existing["showTags"] = False
    existing["showOrphans"] = False
    existing["hideUnresolved"] = True
    _write_graph_json(target, existing)
    logger.info(
        "Obsidian graph.json sync colorGroups=%s (scale/forces preservati) in %s",
        len(color_groups),
        target,
    )
    return target


def _write_graph_json(path: Path, config: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def export_template_dict() -> dict[str, Any]:
    """Espone il template per mirror docs ``radar/obsidian/graph.json``."""
    return build_default_graph_config()
