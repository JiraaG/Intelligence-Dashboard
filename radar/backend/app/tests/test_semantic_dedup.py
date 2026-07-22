"""Tests for semantic deduplication module (extraction/semantic_dedup.py, embedder.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.extraction.embedder import generate_embedding
from app.extraction.semantic_dedup import find_near_duplicate, record_dedup_event


def test_generate_embedding_text_truncation() -> None:
    """Test embedder generates 384 dimensions or None for empty text."""
    res = generate_embedding("", "")
    assert res is None

    mock_model = MagicMock()
    mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

    with patch("app.extraction.embedder.get_embedder", return_value=mock_model):
        vector = generate_embedding("Short Title", "This is the body content")
        assert vector is not None
        assert len(vector) == 384
        mock_model.encode.assert_called_once()
        arg = mock_model.encode.call_args[0][0]
        assert len(arg) <= 400
        assert mock_model.encode.call_args.kwargs.get("normalize_embeddings") is True


@pytest.mark.asyncio
async def test_find_near_duplicate_hit() -> None:
    """Test candidate article returned when vector cosine distance is within threshold."""
    dummy_id = 101
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": dummy_id,
        "title": "Existing Title",
        "summary": "Existing Summary",
        "published_at": "2026-07-21",
        "source_url": "https://example.com/existing",
        "country_code": "US",
        "primary_category": "Geopolitica",
        "body_excerpt": "Existing Body",
        "is_read": False,
        "is_saved": True,
        "distance": 0.10,
    }

    dummy_vector = [0.1] * 384
    candidate = await find_near_duplicate(
        mock_conn, dummy_vector, lookback_hours=24, similarity_threshold=0.85
    )

    assert candidate is not None
    assert candidate.id == dummy_id
    assert candidate.distance == 0.10
    assert candidate.is_saved is True
    sql = mock_conn.fetchrow.call_args[0][0]
    assert "model_id" in sql
    assert "make_interval" in sql
    # distance threshold = 1 - 0.85 = 0.15
    assert mock_conn.fetchrow.call_args[0][3] == pytest.approx(0.15)


@pytest.mark.asyncio
async def test_find_near_duplicate_miss() -> None:
    """Test returns None when no near-duplicate candidate exists within threshold."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    dummy_vector = [0.1] * 384
    candidate = await find_near_duplicate(mock_conn, dummy_vector)

    assert candidate is None


@pytest.mark.asyncio
async def test_record_dedup_event() -> None:
    """Test recording audit event into article_dedup_events table."""
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 42

    event_id = await record_dedup_event(
        mock_conn,
        incoming_url="https://example.com/incoming",
        existing_article_id=101,
        winner="incoming",
        cosine_distance=0.08,
        same_story=True,
        confidence=0.95,
        reason="Incoming has more details",
    )

    assert event_id == 42
    mock_conn.fetchval.assert_awaited_once()


def test_title_token_jaccard() -> None:
    """M5: Test calcolo similarità Jaccard sui titoli."""
    from app.extraction.semantic_dedup import title_token_jaccard

    # Titoli quasi identici (con stop-word minori)
    t1 = "TSMC inaugura nuova fab a Dresda in Germania"
    t2 = "TSMC inaugura la nuova fab a Dresda, Germania"
    sim = title_token_jaccard(t1, t2)
    assert sim >= 0.75

    # Titoli diversi
    t3 = "L'Iran dichiara nuovi test su vettori balistici"
    assert title_token_jaccard(t1, t3) < 0.2

    # Titoli vuoti
    assert title_token_jaccard("", "") == 0.0


def test_compute_content_sha256_collapse_whitespace() -> None:
    """M6: Test normalizzazione e calcolo SHA-256 con collapse dei whitespace."""
    from app.extraction.semantic_dedup import compute_content_sha256, normalize_text_for_hash

    title = "  Titolo   con   spazi  "
    body = "Testo   del   corpo\n\n con   nuove   righe. "
    norm = normalize_text_for_hash(title, body)
    assert norm == "titolo con spazi testo del corpo con nuove righe."

    # Test che due testi con formattazioni/spaziature diverse producano lo stesso hash SHA-256
    hash1 = compute_content_sha256("Titolo con spazi", "Testo del corpo con nuove righe.")
    hash2 = compute_content_sha256("  TITOLO   CON   SPAZI  ", "\nTesto  del  corpo \n con nuove  righe.\n")
    assert hash1 == hash2


@pytest.mark.asyncio
async def test_find_article_by_content_hash_hit() -> None:
    """M6: Test ricerca per content_sha256."""
    from app.extraction.semantic_dedup import find_article_by_content_hash

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 202,
        "title": "Match Title",
        "summary": "Match Summary",
        "published_at": "2026-07-22",
        "source_url": "https://example.com/match",
        "country_code": "DE",
        "primary_category": "Tecnologia",
        "body_excerpt": "Match Body",
        "is_read": False,
        "is_saved": False,
    }

    dummy_hash = "a" * 64
    candidate = await find_article_by_content_hash(mock_conn, dummy_hash)

    assert candidate is not None
    assert candidate.id == 202
    assert candidate.distance == 0.0

