"""Hub notes Obsidian sotto ``_meta/`` (Fase G) — stub per backlink/grafo.

Radar resta SoT: hub auto-generati, idempotenti, path containment sul vault.
Chiamati dopo write vault durable in ``process_outbox_row`` (prima del mark-read
completato resta invariato: hubs non bloccano ``completed``).

SoT:
    radar_overview_and_upgrades.md §G; commit/wikilinks.py; commit/lock.py.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

import yaml

from app.classification.validator import PRIMARY_CATEGORIES, GeopoliticalArticleSchema, parse_csv_list
from app.commit.lock import write_file_with_lock
from app.commit.wikilinks import hub_note_stem, sanitize_wiki_target
from app.core.config import OBSIDIAN_VAULT_PATH

logger = logging.getLogger("radar.commit.hubs")

HubKind = Literal["country", "category", "company", "entity", "tag"]

META_ROOT = "_meta"
META_SUBDIRS: tuple[str, ...] = (
    "countries",
    "categories",
    "companies",
    "entities",
    "tags",
)

_KIND_TO_SUBDIR: dict[HubKind, str] = {
    "country": "countries",
    "category": "categories",
    "company": "companies",
    "entity": "entities",
    "tag": "tags",
}

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


@dataclass(frozen=True)
class HubSpec:
    """Target hub: kind + nome nota (allineato a ``[[name]]``)."""

    kind: HubKind
    name: str


def meta_subdir_paths(vault_root: Path) -> list[Path]:
    """Path assoluti delle sottocartelle ``_meta/*``."""
    return [vault_root / META_ROOT / sub for sub in META_SUBDIRS]


def ensure_meta_directories(vault_path: str | None = None) -> None:
    """Crea ``_meta/{countries,categories,companies,entities,tags}`` se mancanti."""
    root = Path(vault_path or OBSIDIAN_VAULT_PATH)
    meta = root / META_ROOT
    meta.mkdir(parents=True, exist_ok=True)
    for sub in META_SUBDIRS:
        (meta / sub).mkdir(parents=True, exist_ok=True)


def seed_category_hubs(vault_path: str | None = None) -> int:
    """Pre-seed hub per le 15 ``PRIMARY_CATEGORIES``. Ritorna quante note scritte."""
    ensure_meta_directories(vault_path)
    specs = [HubSpec(kind="category", name=cat) for cat in PRIMARY_CATEGORIES]
    return upsert_hub_notes(specs, vault_path=vault_path)


def hubs_from_article(article: GeopoliticalArticleSchema) -> list[HubSpec]:
    """Deriva hub specs dallo schema classificato (CSV → liste)."""
    related = parse_csv_list(article.related_countries)
    companies = parse_csv_list(article.companies_involved)
    entities = parse_csv_list(article.infrastructural_entities)
    tags = parse_csv_list(article.tags)
    return _dedupe_specs(
        [
            _country_spec(article.country_code),
            *(_country_spec(code) for code in related),
            _category_spec(article.primary_category),
            *(_named_spec("company", c) for c in companies),
            *(_named_spec("entity", e) for e in entities),
            *(_named_spec("tag", t) for t in tags),
        ]
    )


def hubs_from_markdown(payload: str) -> list[HubSpec]:
    """Deriva hub specs dal payload Markdown outbox (frontmatter YAML).

    Entità: wiki-link sotto la sezione Entità Infrastrutturali, oppure
    ``[[…]]`` nel body non già classificati come country/category/company/tag.
    """
    frontmatter, body = _split_frontmatter(payload)
    specs: list[HubSpec | None] = []

    country = frontmatter.get("country")
    if isinstance(country, str):
        specs.append(_country_spec(country))

    related = frontmatter.get("related_countries") or []
    if isinstance(related, str):
        related = parse_csv_list(related)
    if isinstance(related, list):
        for code in related:
            if isinstance(code, str):
                specs.append(_country_spec(code))

    category = frontmatter.get("category")
    if isinstance(category, str):
        specs.append(_category_spec(category))

    for key, kind in (("companies", "company"), ("tags", "tag")):
        values = frontmatter.get(key) or []
        if isinstance(values, str):
            values = parse_csv_list(values)
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str):
                    specs.append(_named_spec(kind, value))  # type: ignore[arg-type]

    known_names = {
        s.name
        for s in specs
        if s is not None
    }
    for entity_name in _entity_targets_from_body(body):
        if entity_name not in known_names:
            specs.append(_named_spec("entity", entity_name))

    return _dedupe_specs(specs)


def upsert_hub_notes(
    hubs: Iterable[HubSpec],
    *,
    vault_path: str | None = None,
) -> int:
    """Scrive/sovrascrive stub hub sotto ``_meta/`` con lock atomico.

    Returns:
        Numero di note scritte con successo.
    Raises:
        ValueError: path hub fuori dal vault (traversal).
    """
    vault_root = Path(vault_path or OBSIDIAN_VAULT_PATH).resolve()
    ensure_meta_directories(str(vault_root))
    written = 0
    for hub in hubs:
        path = _hub_file_path(vault_root, hub)
        content = _render_hub_markdown(hub)
        try:
            write_file_with_lock(str(path), content)
            written += 1
        except Exception:
            logger.error(
                "Scrittura hub fallita kind=%s name=%s path=%s",
                hub.kind,
                hub.name,
                path,
                exc_info=True,
            )
            raise
    if written:
        logger.debug("Hub notes upsert: %s file sotto %s", written, vault_root / META_ROOT)
    return written


def upsert_hubs_for_payload(payload: str, *, vault_path: str | None = None) -> int:
    """Parse payload outbox → upsert hub. Best-effort wrapper per outbox."""
    hubs = hubs_from_markdown(payload)
    if not hubs:
        return 0
    return upsert_hub_notes(hubs, vault_path=vault_path)


def _country_spec(code: str) -> HubSpec | None:
    target = sanitize_wiki_target(code)
    if target is None:
        return None
    normalized = target.upper()
    if not re.fullmatch(r"[A-Z]{2}|XX", normalized):
        return None
    if normalized == "XX":
        return None
    return HubSpec(kind="country", name=normalized)


def _category_spec(category: str) -> HubSpec | None:
    target = sanitize_wiki_target(category)
    if target is None or target not in PRIMARY_CATEGORIES:
        return None
    return HubSpec(kind="category", name=target)


def _named_spec(kind: HubKind, raw: str) -> HubSpec | None:
    target = sanitize_wiki_target(raw)
    if target is None:
        return None
    # Evita hub company/tag/entity che collidono con ISO o categorie SoT.
    if kind != "country" and re.fullmatch(r"[A-Z]{2}|XX", target.upper()) and len(target) == 2:
        return None
    if kind != "category" and target in PRIMARY_CATEGORIES:
        return None
    return HubSpec(kind=kind, name=target)


def _dedupe_specs(specs: Iterable[HubSpec | None]) -> list[HubSpec]:
    seen: set[tuple[HubKind, str]] = set()
    out: list[HubSpec] = []
    for spec in specs:
        if spec is None:
            continue
        key = (spec.kind, spec.name.casefold())
        if key in seen:
            continue
        seen.add(key)
        out.append(spec)
    return out


def _hub_file_path(vault_root: Path, hub: HubSpec) -> Path:
    stem = hub_note_stem(hub.name)
    if stem is None:
        raise ValueError(f"Hub name non sanitizzabile: {hub.name!r}")
    subdir = _KIND_TO_SUBDIR[hub.kind]
    final_path = (vault_root / META_ROOT / subdir / f"{stem}.md").resolve()
    try:
        final_path.relative_to(vault_root)
    except ValueError as exc:
        raise ValueError(
            f"Percorso hub {final_path} fuoriesce dal vault root {vault_root}"
        ) from exc
    # Deve restare sotto _meta/<subdir>/
    try:
        final_path.relative_to((vault_root / META_ROOT / subdir).resolve())
    except ValueError as exc:
        raise ValueError(
            f"Percorso hub {final_path} fuori da {META_ROOT}/{subdir}"
        ) from exc
    return final_path


def _render_hub_markdown(hub: HubSpec) -> str:
    """Template minimale stub (YAML safe_dump + titolo)."""
    meta: dict[str, str] = {
        "type": hub.kind,
        "name": hub.name,
    }
    if hub.kind == "country":
        meta["iso"] = hub.name
    fm = yaml.safe_dump(
        meta,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip("\n")
    title = hub.name
    return f"---\n{fm}\n---\n\n# {title}\n\n"


def _split_frontmatter(payload: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(payload)
    if not match:
        return {}, payload
    raw_yaml = match.group(1)
    try:
        loaded = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        logger.warning("Frontmatter YAML non parseabile per hub upsert")
        return {}, payload[match.end() :]
    if not isinstance(loaded, dict):
        return {}, payload[match.end() :]
    return loaded, payload[match.end() :]


def _entity_targets_from_body(body: str) -> list[str]:
    """Estrae target ``[[…]]`` dalla sezione Entità Infrastrutturali."""
    marker = "# Entità Infrastrutturali"
    idx = body.find(marker)
    if idx < 0:
        return []
    section = body[idx + len(marker) :]
    next_heading = re.search(r"\n---\n|\n# ", section)
    if next_heading:
        section = section[: next_heading.start()]
    targets: list[str] = []
    for match in re.finditer(r"\[\[([^\[\]]+)\]\]", section):
        target = sanitize_wiki_target(match.group(1))
        if target is not None:
            targets.append(target)
    return targets
