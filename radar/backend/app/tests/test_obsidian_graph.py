"""Unit tests Fase G: seed/sync Obsidian Graph colorGroups hub-centric."""

from __future__ import annotations

import json
from pathlib import Path

from app.classification.validator import PRIMARY_CATEGORIES
from app.commit.obsidian_graph import (
    CATEGORY_HEX,
    COUNTRY_HEX,
    SECONDARY_HEX,
    build_color_groups,
    ensure_obsidian_graph_config,
    hex_to_obsidian_rgb,
)
from app.commit.router import initialize_vault_directories


def test_hex_to_obsidian_rgb() -> None:
    assert hex_to_obsidian_rgb("#00f0ff") == (0 << 16) | (240 << 8) | 255
    assert hex_to_obsidian_rgb("a855f7") == (168 << 16) | (85 << 8) | 247


def test_build_color_groups_order_and_coverage() -> None:
    groups = build_color_groups()
    assert len(groups) == 15 + 1 + 3
    for i, cat in enumerate(PRIMARY_CATEGORIES):
        assert groups[i]["query"] == f"path:_meta/categories/{cat}"
        assert groups[i]["color"]["rgb"] == hex_to_obsidian_rgb(CATEGORY_HEX[cat])
    assert groups[15]["query"] == "path:_meta/countries"
    assert groups[15]["color"]["rgb"] == hex_to_obsidian_rgb(COUNTRY_HEX)
    for j, sub in enumerate(("companies", "entities", "tags")):
        assert groups[16 + j]["query"] == f"path:_meta/{sub}"
        assert groups[16 + j]["color"]["rgb"] == hex_to_obsidian_rgb(SECONDARY_HEX)


def test_initialize_vault_seeds_graph_json(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    initialize_vault_directories(vault_path=str(vault))
    graph_path = vault / ".obsidian" / "graph.json"
    assert graph_path.is_file()
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert data["showOrphans"] is False
    assert data["hideUnresolved"] is True
    assert data["showTags"] is False
    queries = [g["query"] for g in data["colorGroups"]]
    assert len(queries) == 19
    assert "path:_meta/countries" in queries
    for cat in PRIMARY_CATEGORIES:
        assert f"path:_meta/categories/{cat}" in queries


def test_ensure_preserves_scale_and_forces(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    initialize_vault_directories(vault_path=str(vault))
    graph_path = vault / ".obsidian" / "graph.json"
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    data["scale"] = 0.42
    data["centerStrength"] = 0.77
    data["repelStrength"] = 3
    data["colorGroups"] = []
    data["showOrphans"] = True
    graph_path.write_text(json.dumps(data), encoding="utf-8")

    ensure_obsidian_graph_config(str(vault))
    synced = json.loads(graph_path.read_text(encoding="utf-8"))
    assert synced["scale"] == 0.42
    assert synced["centerStrength"] == 0.77
    assert synced["repelStrength"] == 3
    assert len(synced["colorGroups"]) == 19
    assert synced["showOrphans"] is False
    assert synced["hideUnresolved"] is True
