# factory.py — fabbrica Markdown Obsidian (frontmatter YAML + corpo).
#
# Usata da outbox/lock dopo il commit DB: produce il contenuto vault stabile
# (safe_dump, liste flow per Leaflet/Obsidian). Truncamento sicuro se campi lunghi.
# @see commit/router.py, commit/outbox.py; AGENTS vault.

from __future__ import annotations

import yaml

from app.classification.validator import GeopoliticalArticleSchema, parse_csv_list

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


def generate_markdown_content(article: GeopoliticalArticleSchema) -> str:
    """
    Articolo geopolitico → Markdown con YAML frontmatter Obsidian.

    - ``location`` = [lat, lon]; tags/companies da ``parse_csv_list`` (schema Pydantic CSV str).
    - Corpo: riassunto + elenco entità infrastrutturali (o placeholder se vuoto).
    - Truncation a livelli summary / entities / body intero.
    """
    tags_list = parse_csv_list(article.tags)
    companies_list = parse_csv_list(article.companies_involved)
    entities_list = parse_csv_list(article.infrastructural_entities)

    summary = _truncate_text(article.summary, MAX_SUMMARY_CHARS, "summary")

    if entities_list:
        entities_markdown = "\n".join(f"- {entity.strip()}" for entity in entities_list if entity.strip())
    else:
        entities_markdown = "- Nessun asset fisico specifico menzionato."

    entities_markdown = _truncate_text(entities_markdown, MAX_ENTITIES_FIELD_CHARS, "entità infrastrutturali")

    body = f"# Riassunto\n\n{summary}\n\n# Entità Infrastrutturali\n\n{entities_markdown}\n"
    if len(body) > MAX_MARKDOWN_BODY_CHARS:
        body = _truncate_text(body, MAX_MARKDOWN_BODY_CHARS, "corpo Markdown")

    frontmatter_yaml = _dump_frontmatter(
        {
            "title": article.title,
            "location": [article.latitude, article.longitude],
            "country": article.country_code,
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
