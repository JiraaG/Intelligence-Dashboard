"""Routing path Markdown nel Vault Obsidian (categoria / paese / filename).

Allowlist categorie = ``PRIMARY_CATEGORIES``; country ``^[A-Z]{2}$|^XX$``.
Filename: ``{published_at}_{slug}_{sha256(url)[:16]}.md`` con tetto basename.
Containment: ``Path.resolve().relative_to(vault_root)`` — path traversal → ValueError.

SoT:
    .agents/AGENTS.md §6 (vault); docs/02 persistence.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from app.classification.validator import PRIMARY_CATEGORIES, GeopoliticalArticleSchema
from app.core.config import OBSIDIAN_VAULT_PATH

logger = logging.getLogger("radar.commit.router")

ALLOWED_CATEGORIES = frozenset(PRIMARY_CATEGORIES)
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$|^XX$")
MAX_BASENAME_CHARS = 180
URL_HASH_HEX_CHARS = 16


def initialize_vault_directories(vault_path: str | None = None) -> None:
    """Crea la root vault e le 10 sottocartelle categoria se mancanti.

    Default root: ``OBSIDIAN_VAULT_PATH`` (``/app/vault`` in container).
    Raises:
        OSError: permessi / mount vault non scrivibile.
    SoT:
        AGENTS.md §2 fallback vault ``/app/vault``.
    """
    root = Path(vault_path or OBSIDIAN_VAULT_PATH)

    logger.info("Inizializzazione delle directory del Vault su: %s", root)

    try:
        root.mkdir(parents=True, exist_ok=True)
        logger.info("Creata/verificata directory radice del Vault: %s", root)

        for category in PRIMARY_CATEGORIES:
            category_path = root / category
            category_path.mkdir(parents=True, exist_ok=True)
            logger.info("Creata/verificata sottocartella del Vault: %s", category_path)

        logger.info("Inizializzazione directory Vault completata.")
    except OSError as exc:
        logger.error("Errore durante l'inizializzazione del Vault su %s: %s", root, exc)
        raise


def slugify_title(title: str) -> str:
    """Sanitizza il titolo per filesystem Windows/macOS/Linux.

    Caratteri vietati → ``-``; spazi collassati; lowercase. Vuoto → ``senza-titolo``.
    """
    if not title:
        return "senza-titolo"

    clean = re.sub(r'[\\/:*?"<>|]', "-", title)
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"-+", "-", clean)

    return clean.strip("-").lower() or "senza-titolo"


def _validate_category(category: str) -> str:
    """Categoria in allowlist ``PRIMARY_CATEGORIES``; altrimenti ValueError."""
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(f"Categoria non valida: {category!r}")
    return category


def _validate_country_code(country_code: str) -> str:
    """ISO Alpha-2 maiuscolo o sentinel ``XX``."""
    normalized = country_code.strip().upper()
    if not COUNTRY_CODE_PATTERN.match(normalized):
        raise ValueError(f"country_code non valido: {country_code!r}")
    return normalized


def _url_hash(source_url: str) -> str:
    """Prefisso SHA-256 dell'URL: rende unico il basename a parità di titolo/data."""
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:URL_HASH_HEX_CHARS]


def _build_filename(published_at: str, slugified: str, source_url: str) -> str:
    """Costruisce basename entro ``MAX_BASENAME_CHARS``, truncando lo slug se serve."""
    url_hash = _url_hash(source_url)
    suffix = f"_{url_hash}.md"
    prefix = f"{published_at}_"
    max_slug_len = MAX_BASENAME_CHARS - len(prefix) - len(suffix)

    if max_slug_len < 1:
        raise ValueError(
            f"Impossibile costruire un nome file entro {MAX_BASENAME_CHARS} caratteri "
            f"per la data {published_at!r}"
        )

    truncated_slug = slugified[:max_slug_len].rstrip("-")
    if not truncated_slug:
        truncated_slug = "articolo"

    return f"{prefix}{truncated_slug}{suffix}"


def get_article_file_path(article: GeopoliticalArticleSchema, vault_path: str | None = None) -> str:
    """Calcola il path assoluto Markdown nel Vault con containment sul root.

    Struttura:
    ``{vault}/{primary_category}/{country_code}/{published_at}_{slug}_{sha256[:16]}.md``

    Args:
        article: Schema con categoria/paese/titolo/URL/data già validati.
        vault_path: Override root; default ``OBSIDIAN_VAULT_PATH``.
    Returns:
        Path assoluto resolved (stringa) ancora sotto il vault root.
    Raises:
        ValueError: categoria/paese invalidi, oppure path fuori dal vault (traversal).
    SoT:
        AGENTS.md §6; docs/02.
    """
    vault_root = Path(vault_path or OBSIDIAN_VAULT_PATH).resolve()
    category_folder = _validate_category(article.primary_category)
    country_folder = _validate_country_code(article.country_code)

    slugified = slugify_title(article.title)
    filename = _build_filename(article.published_at, slugified, article.source_url)

    target_dir = vault_root / category_folder / country_folder
    final_path = (target_dir / filename).resolve()

    try:
        final_path.relative_to(vault_root)
    except ValueError as exc:
        raise ValueError(
            f"Percorso di destinazione {final_path} fuoriesce dal vault root {vault_root}"
        ) from exc

    return str(final_path)
