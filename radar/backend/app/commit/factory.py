# factory.py — Obsidian Markdown Document Factory

from app.classification.validator import GeopoliticalArticleSchema, parse_csv_list

def generate_markdown_content(article: GeopoliticalArticleSchema) -> str:
    """
    Rappresenta l'articolo geopolitico come testo Markdown strutturato,
    completo di YAML Frontmatter leggibile e compatibile con Obsidian.
    Configura le coordinate in lista singola per il plugin Leaflet.
    """
    # Parsing delle liste da stringhe CSV
    tags_list = parse_csv_list(article.tags)
    companies_list = parse_csv_list(article.companies_involved)
    entities_list = parse_csv_list(article.infrastructural_entities)

    # Formattazione liste piatte per tags e aziende inserendo apici doppi di protezione
    tags_flow = "[" + ", ".join(f'"{t}"' for t in tags_list) + "]"
    companies_flow = "[" + ", ".join(f'"{c}"' for c in companies_list) + "]"
    
    # Formattazione delle entità infrastrutturali citate in forma di lista puntata
    entities_markdown = ""
    if entities_list:
        entities_markdown = "\n".join(f"- {entity.strip()}" for entity in entities_list if entity.strip())
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
