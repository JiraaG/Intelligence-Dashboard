"""Ricerca di candidati near-duplicate tramite pgvector (cosine distance).

Filtra articoli pubblicati nella finestra di lookback (default 24h) con distanza coseno
<= (1.0 - similarity_threshold) (default distance <= 0.15 per threshold 0.85).

SoT:
    plan-audit/complete/plan_impl_fase_C_semantic_dedup.md §2 D8, §4.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import asyncpg

from app.core.config import (
    SEMANTIC_DEDUP_LOOKBACK_HOURS,
    SEMANTIC_DEDUP_SIMILARITY_THRESHOLD,
    SEMANTIC_EMBEDDING_MODEL,
)

logger = logging.getLogger("radar.extraction.semantic_dedup")


def title_token_jaccard(title1: str, title2: str) -> float:
    """Calcola la similarità Jaccard sui token dei titoli (lowercase, alfanumerici)."""
    tokens1 = set(re.findall(r"\w+", (title1 or "").lower()))
    tokens2 = set(re.findall(r"\w+", (title2 or "").lower()))
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)


def normalize_text_for_hash(title: str, body: str) -> str:
    """Normalizza titolo e testo per SHA-256 (collapse whitespace, lowercase)."""
    raw = f"{title or ''}\n{body or ''}"
    return re.sub(r"\s+", " ", raw).strip().lower()


def compute_content_sha256(title: str, body: str) -> str:
    """Calcola l'hash SHA-256 (64 char hex) del testo normalizzato."""
    norm = normalize_text_for_hash(title, body)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()



@dataclass(frozen=True, slots=True)
class CandidateArticle:
    """Candidato articolo near-duplicate recuperato dal DB."""

    id: Any  # articles.id = SERIAL (int)
    title: str
    summary: str
    published_at: str
    source_url: str
    country_code: str
    primary_category: str
    body_excerpt: str
    is_read: bool
    is_saved: bool
    distance: float


async def find_near_duplicate(
    conn: asyncpg.Connection,
    embedding: list[float],
    *,
    lookback_hours: int = SEMANTIC_DEDUP_LOOKBACK_HOURS,
    similarity_threshold: float = SEMANTIC_DEDUP_SIMILARITY_THRESHOLD,
    model_id: str = SEMANTIC_EMBEDDING_MODEL,
) -> Optional[CandidateArticle]:
    """Cerca nel DB l'articolo più vicino nello spazio vettoriale dense.

    Args:
        conn: Connessione asyncpg.
        embedding: Lista di 384 float.
        lookback_hours: Finestra temporale di ricerca in ore.
        similarity_threshold: Soglia minima di similarità (es. 0.85 → dist ≤ 0.15).
        model_id: Confronta solo embedding generati dallo stesso modello (D8).
    Returns:
        ``CandidateArticle`` se trovato un match sotto la distanza soglia, altrimenti ``None``.
    """
    if not embedding:
        return None

    max_distance = float(1.0 - similarity_threshold)
    vector_str = f"[{','.join(str(x) for x in embedding)}]"

    row = await conn.fetchrow(
        """
        SELECT a.id, a.title, a.summary, a.published_at::text, a.source_url, a.country_code,
               a.primary_category, COALESCE(a.body_excerpt, '') AS body_excerpt,
               a.is_read, a.is_saved,
               (e.embedding <=> $1::vector) AS distance
        FROM article_embeddings e
        JOIN articles a ON a.id = e.article_id
        WHERE e.created_at >= NOW() - make_interval(hours => $2::int)
          AND e.model_id = $4
          AND (e.embedding <=> $1::vector) <= $3
        ORDER BY distance ASC
        LIMIT 1
        """,
        vector_str,
        int(lookback_hours),
        max_distance,
        model_id,
    )

    if row is None:
        return None

    candidate = CandidateArticle(
        id=row["id"],
        title=row["title"],
        summary=row["summary"],
        published_at=str(row["published_at"]),
        source_url=row["source_url"],
        country_code=row["country_code"],
        primary_category=row["primary_category"],
        body_excerpt=row["body_excerpt"],
        is_read=bool(row["is_read"]),
        is_saved=bool(row["is_saved"]),
        distance=float(row["distance"]),
    )

    logger.info(
        "Trovato candidato near-dup per '%s' (distanza=%.4f, sim=%.4f) [ID=%s]",
        candidate.title[:40],
        candidate.distance,
        1.0 - candidate.distance,
        candidate.id,
    )
    return candidate


async def record_dedup_event(
    conn: asyncpg.Connection,
    *,
    incoming_url: str,
    existing_article_id: Optional[Any],
    winner: str,
    cosine_distance: Optional[float] = None,
    same_story: Optional[bool] = None,
    confidence: Optional[float] = None,
    reason: Optional[str] = None,
    dedup_kind: str = "semantic_vector",
    action_taken: Optional[str] = None,
    feed_id: Optional[int] = None,
    incoming_miniflux_entry_id: Optional[int] = None,
) -> int:
    """Inserisce un record di audit append-only nella tabella ``article_dedup_events``."""
    event_id = await conn.fetchval(
        """
        INSERT INTO article_dedup_events (
            incoming_url, existing_article_id, winner, cosine_distance,
            same_story, confidence, reason, dedup_kind, action_taken,
            feed_id, incoming_miniflux_entry_id
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING id
        """,
        incoming_url,
        existing_article_id,
        winner,
        cosine_distance,
        same_story,
        confidence,
        reason,
        dedup_kind,
        action_taken,
        feed_id,
        incoming_miniflux_entry_id,
    )
    return int(event_id) if event_id is not None else 0


async def find_article_by_content_hash(
    conn: asyncpg.Connection,
    content_sha256: str,
    *,
    lookback_hours: int = 24,
) -> Optional[CandidateArticle]:
    """Cerca un articolo esistente con lo stesso content_sha256 nelle ultime lookback_hours."""
    if not content_sha256:
        return None

    row = await conn.fetchrow(
        """
        SELECT id, title, summary, published_at::text, source_url, country_code,
               primary_category, COALESCE(body_excerpt, '') AS body_excerpt,
               is_read, is_saved, 0.0 AS distance
        FROM articles
        WHERE content_sha256 = $1
          AND created_at >= NOW() - make_interval(hours => $2::int)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        content_sha256,
        int(lookback_hours),
    )

    if row is None:
        return None

    return CandidateArticle(
        id=row["id"],
        title=row["title"],
        summary=row["summary"],
        published_at=str(row["published_at"]),
        source_url=row["source_url"],
        country_code=row["country_code"],
        primary_category=row["primary_category"],
        body_excerpt=row["body_excerpt"],
        is_read=bool(row["is_read"]),
        is_saved=bool(row["is_saved"]),
        distance=0.0,
    )

