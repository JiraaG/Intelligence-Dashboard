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
