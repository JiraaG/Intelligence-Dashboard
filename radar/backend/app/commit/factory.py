# factory.py — fabbrica Markdown Obsidian (frontmatter YAML + corpo).
#
# Usata da outbox/lock dopo il commit DB: produce il contenuto vault stabile
# (safe_dump, liste flow per Leaflet/Obsidian). Fase G: wiki-link nel corpo
# (paesi, categoria, aziende, entità, tag) via commit/wikilinks.py.
# @see commit/router.py, commit/outbox.py, commit/hubs.py; AGENTS vault.

from __future__ import annotations

import yaml

from app.classification.validator import GeopoliticalArticleSchema, parse_csv_list
from app.commit.wikilinks import format_wiki_link, format_wiki_link_list

MAX_MARKDOWN_BODY_CHARS = 50_000
MAX_SUMMARY_CHARS = 2000
MAX_ENTITIES_FIELD_CHARS = 2000


class _FlowList(list):
    """Lista serializzata in flow style YAML ([a, b]) per compatibilità Obsidian/Leaflet."""


def _represent_flow_list(dumper: yaml.SafeDumper, data: _FlowList) -> yaml.nodes.SequenceNode:
    """Representer SafeDumper: sequenza in linea, non block-style."""
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


yaml.SafeDumper.add_representer(_FlowList, _represent_flow_list)


def _truncate_text(text: str, max_chars: int, label: str) -> str:
    """
    Taglia ``text`` a ``max_chars`` includendo un suffisso esplicito di troncamento.
    Evita note vault giganti da summary/entità LLM verbose.
    """
    if len(text) <= max_chars:
        return text
    suffix = f"\n\n[... troncato: {label} supera {max_chars} caratteri]"
    keep = max(0, max_chars - len(suffix))
    return text[:keep] + suffix


def _dump_frontmatter(frontmatter: dict) -> str:
    """
    Serializza l'intero mapping frontmatter con ``yaml.safe_dump``
    (niente f-string YAML manuali — escaping/unicode sicuri).
    Ordine chiavi fisso; location/tags/companies in flow via ``_FlowList``.
    """
    serializable = {
        "title": frontmatter["title"],
        "location": _FlowList(frontmatter["location"]),
        "country": frontmatter["country"],
        "related_countries": _FlowList(frontmatter["related_countries"]),
        "category": frontmatter["category"],
        "tags": _FlowList(frontmatter["tags"]),
        "companies": _FlowList(frontmatter["companies"]),
        "sentiment": frontmatter["sentiment"],
        "relevance": frontmatter["relevance"],
        "published": frontmatter["published"],
        "source": frontmatter["source"],
    }

    return yaml.safe_dump(
        serializable,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip("\n")


def _build_relational_footer(
    *,
    country_code: str,
    related_countries: list[str],
    primary_category: str,
    companies: list[str],
    tags: list[str],
) -> str:
    """Sezione Raccordo Relazionale con wiki-link (Fase G)."""
    related_wiki = format_wiki_link_list(related_countries, empty="Nessuno")
    companies_wiki = format_wiki_link_list(companies, empty="Nessuna")
    tags_wiki = format_wiki_link_list(tags, empty="Nessuno")
    return (
        "\n\n---\n"
        "**Raccordo Relazionale:**\n"
        f"- Nazione: {format_wiki_link(country_code)}\n"
        f"- Paesi correlati: {related_wiki}\n"
        f"- Categoria: {format_wiki_link(primary_category)}\n"
        f"- Aziende: {companies_wiki}\n"
        f"- Tag: {tags_wiki}\n"
    )


def generate_markdown_content(article: GeopoliticalArticleSchema) -> str:
    """
    Articolo geopolitico → Markdown con YAML frontmatter Obsidian.

    - ``location`` = [lat, lon]; tags/companies da ``parse_csv_list`` (schema Pydantic CSV str).
    - Corpo: riassunto + entità come ``[[wiki-link]]`` + footer raccordo (Fase G).
    - Truncation a livelli summary / entities / body intero.
    """
    tags_list = parse_csv_list(article.tags)
    companies_list = parse_csv_list(article.companies_involved)
    entities_list = parse_csv_list(article.infrastructural_entities)
    related_countries_list = parse_csv_list(article.related_countries)

    summary = _truncate_text(article.summary, MAX_SUMMARY_CHARS, "summary")

    if entities_list:
        entity_lines = [
            f"- {format_wiki_link(entity.strip())}"
            for entity in entities_list
            if entity.strip()
        ]
        entities_markdown = "\n".join(entity_lines) if entity_lines else (
            "- Nessun asset fisico specifico menzionato."
        )
    else:
        entities_markdown = "- Nessun asset fisico specifico menzionato."

    entities_markdown = _truncate_text(
        entities_markdown, MAX_ENTITIES_FIELD_CHARS, "entità infrastrutturali"
    )

    wiki_footer = _build_relational_footer(
        country_code=article.country_code,
        related_countries=related_countries_list,
        primary_category=article.primary_category,
        companies=companies_list,
        tags=tags_list,
    )

    body = (
        f"# Riassunto\n\n{summary}\n\n"
        f"# Entità Infrastrutturali\n\n{entities_markdown}"
        f"{wiki_footer}"
    )
    if len(body) > MAX_MARKDOWN_BODY_CHARS:
        body = _truncate_text(body, MAX_MARKDOWN_BODY_CHARS, "corpo Markdown")

    frontmatter_yaml = _dump_frontmatter(
        {
            "title": article.title,
            "location": [article.latitude, article.longitude],
            "country": article.country_code,
            "related_countries": related_countries_list,
            "category": article.primary_category,
            "tags": tags_list,
            "companies": companies_list,
            "sentiment": article.sentiment,
            "relevance": article.relevance_level,
            "published": article.published_at,
            "source": article.source_url,
        }
    )

    return f"---\n{frontmatter_yaml}\n---\n\n{body}"
