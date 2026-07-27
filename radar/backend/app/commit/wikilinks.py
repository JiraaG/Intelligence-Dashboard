"""Wiki-link Obsidian: sanitize target + format ``[[Note]]`` (Fase G).

Punto unico di verità per regole di escaping: factory e hubs riusano queste
funzioni pure (niente I/O). Target invalidi → testo plain (no ``[[ ]]``).

SoT:
    radar_overview_and_upgrades.md §G; AGENTS vault.
"""

from __future__ import annotations

import re
from typing import Iterable

MAX_WIKI_TARGET_CHARS = 120

# Caratteri che rompono la sintassi wiki-link o abilitano path/alias/heading abuse.
_FORBIDDEN_CHARS = frozenset("[]|#/\\\r\n\t")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_wiki_target(raw: str, *, max_chars: int = MAX_WIKI_TARGET_CHARS) -> str | None:
    """Normalizza un target wiki-link oppure ``None`` se non sicuro/usabile.

    - Strip spazi; rifiuta vuoto.
    - Rifiuta ``[]|#/\\`` e control chars (path traversal / breakout Obsidian).
    - Collassa whitespace interni a uno spazio.
    - Trunca a ``max_chars``.
    """
    if not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    if _CONTROL_RE.search(cleaned):
        return None

    if any(ch in _FORBIDDEN_CHARS for ch in cleaned):
        return None

    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip()
    if not cleaned:
        return None
    return cleaned


def format_wiki_link(raw: str) -> str:
    """Restituisce ``[[Target]]`` se sanitizzabile, altrimenti il testo plain strippato."""
    target = sanitize_wiki_target(raw)
    if target is None:
        return raw.strip() if isinstance(raw, str) else ""
    return f"[[{target}]]"


def format_wiki_link_list(values: Iterable[str], *, empty: str = "Nessuno") -> str:
    """Unisce target in ``[[A]], [[B]]``; ``empty`` se nessun target valido/non vuoto."""
    links: list[str] = []
    for value in values:
        text = value.strip() if isinstance(value, str) else ""
        if not text:
            continue
        links.append(format_wiki_link(text))
    if not links:
        return empty
    return ", ".join(links)


def hub_note_stem(raw: str) -> str | None:
    """Stem filename hub (senza ``.md``) allineato al target ``[[…]]``.

    Riusa ``sanitize_wiki_target``; sostituisce solo caratteri FS residui
    (``:*?\"<>|``) con ``-`` senza lowercasing, così Obsidian risolve per basename.
    """
    target = sanitize_wiki_target(raw)
    if target is None:
        return None
    stem = re.sub(r'[:*?"<>|]', "-", target)
    stem = re.sub(r"-+", "-", stem).strip("-. ")
    return stem or None
