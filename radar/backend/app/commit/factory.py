# factory.py — Obsidian Markdown Document Factory

from app.classification.validator import GeopoliticalArticleSchema

def generate_markdown_content(article: GeopoliticalArticleSchema) -> str:
    """
    Rappresenta l'articolo geopolitico come testo Markdown strutturato,
    completo di YAML Frontmatter leggibile e compatibile con Obsidian.
    Configura le coordinate in lista singola per il plugin Leaflet.
    """
    # Formattazione liste piatte per tags e aziende inserendo apici doppi di protezione
    tags_flow = "[" + ", ".join(f'"{t}"' for t in article.tags) + "]"
    companies_flow = "[" + ", ".join(f'"{c}"' for c in article.companies_involved) + "]"
    
    # Formattazione delle entità infrastrutturali citate in forma di lista puntata
    entities_markdown = ""
    if article.infrastructural_entities:
        entities_markdown = "\n".join(f"- {entity.strip()}" for entity in article.infrastructural_entities if entity.strip())
    else:
        entities_markdown = "- Nessun asset fisico specifico menzionato."

    escaped_title = article.title.replace('"', '\\"')

    # Costruzione del template Markdown con Frontmatter
    markdown_content = f"""---
title: "{escaped_title}"
location: [{article.latitude}, {article.longitude}]
country: "{article.country_code}"
category: "{article.primary_category}"
tags: {tags_flow}
companies: {companies_flow}
sentiment: "{article.sentiment}"
relevance: {article.relevance_level}
published: {article.published_at}
source: "{article.source_url}"
---

# Riassunto

{article.summary}

# Entità Infrastrutturali

{entities_markdown}
"""
    return markdown_content
