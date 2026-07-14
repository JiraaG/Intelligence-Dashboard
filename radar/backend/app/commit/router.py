# router.py — Obsidian Vault path routing

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
    """
    Scansiona la directory del Vault di Obsidian e crea le 10 sottocartelle
    delle macro-categorie geopolitiche se non sono già presenti.
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
    """
    Sanitizza il titolo per filesystem Windows/macOS/Linux.
    Sostituisce i caratteri vietati con un trattino.
    """
    if not title:
        return "senza-titolo"

    clean = re.sub(r'[\\/:*?"<>|]', "-", title)
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"-+", "-", clean)

    return clean.strip("-").lower() or "senza-titolo"


def _validate_category(category: str) -> str:
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(f"Categoria non valida: {category!r}")
    return category


def _validate_country_code(country_code: str) -> str:
    normalized = country_code.strip().upper()
    if not COUNTRY_CODE_PATTERN.match(normalized):
        raise ValueError(f"country_code non valido: {country_code!r}")
    return normalized


def _url_hash(source_url: str) -> str:
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:URL_HASH_HEX_CHARS]


def _build_filename(published_at: str, slugified: str, source_url: str) -> str:
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
    """
    Calcola il percorso semantico di salvataggio del file Markdown nel Vault.
    Struttura: {vault}/{primary_category}/{country_code}/{published_at}_{slug}_{sha256[:16]}.md
    Solleva ValueError se il percorso resolved esce dal vault root.
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
