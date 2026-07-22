"""Embedder locale SentenceTransformers per deduplicazione semantica.

Usa il modello ``all-MiniLM-L6-v2`` su CPU per generare vettori dense (384 dim).
In caso di errore di caricamento o inferenza, adotta un comportamento fail-open
ritornando ``None`` (il worker proseguirà senza deduplicazione semantica).

SoT:
    plan-audit/complete/plan_impl_fase_C_semantic_dedup.md §2 D6-D7.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import SEMANTIC_EMBEDDING_MODEL

logger = logging.getLogger("radar.extraction.embedder")

_embedder_model = None


def get_embedder():
    """Ritorna l'istanza singleton di SentenceTransformer; carica al primo uso."""
    global _embedder_model
    if _embedder_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Caricamento modello embedding '%s'...", SEMANTIC_EMBEDDING_MODEL)
            _embedder_model = SentenceTransformer(SEMANTIC_EMBEDDING_MODEL)
            logger.info("Modello embedding '%s' caricato con successo.", SEMANTIC_EMBEDDING_MODEL)
        except Exception as err:
            logger.error("Impossibile caricare il modello embedding '%s': %s", SEMANTIC_EMBEDDING_MODEL, err)
            return None
    return _embedder_model


def generate_embedding(title: str, content: str) -> Optional[list[float]]:
    """Genera un vettore dense (384 float) dal titolo + lead (max 400 caratteri).

    Args:
        title: Titolo dell'articolo.
        content: Testo sanitizzato dell'articolo.
    Returns:
        Lista di 384 float oppure ``None`` in caso di fail-open.
    """
    embedder = get_embedder()
    if embedder is None:
        return None

    # Prepara il testo: title + lead <= 400 char
    text_to_embed = f"{title.strip()} {content.strip()}".strip()[:400]
    if not text_to_embed:
        return None

    try:
        vector = embedder.encode(
            text_to_embed,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vector.tolist()
    except Exception as err:
        logger.warning("Generazione embedding fallita per testo '%s...': %s", title[:40], err)
        return None
