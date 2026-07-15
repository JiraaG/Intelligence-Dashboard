"""
Tests for the duplicate article processing gate (T-P0-01).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.extraction.entry_validation import ValidatedMinifluxEntry
from app.worker import WorkerState, process_single_entry


def _make_entry(entry_id: int) -> ValidatedMinifluxEntry:
    return ValidatedMinifluxEntry(
        id=entry_id,
        source_url=f"https://example.com/article/{entry_id}",
        title=f"Title {entry_id}",
        content="<p>body</p>",
        published_at="2026-07-14",
        feed_title="Test Feed",
    )


def _make_state() -> WorkerState:
    state = WorkerState()
    state.db_pool = MagicMock()
    state.miniflux_client = AsyncMock()
    state.classification_client = AsyncMock()
    state.parse_sem = asyncio.Semaphore(1)
    state.db_sem = asyncio.Semaphore(1)
    state.gemini_sem = asyncio.Semaphore(1)
    return state


@pytest.mark.asyncio
@patch("app.worker.is_article_duplicate", new_callable=AsyncMock)
async def test_duplicate_gate_completed(mock_is_dup) -> None:
    """If the outbox status is 'completed', the article is marked as read."""
    mock_is_dup.return_value = True
    state = _make_state()
    entry = _make_entry(100)

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "outbox_status": "completed",
        "primary_category": "Geopolitica",
        "country_code": "US",
        "published_at": "2026-07-14",
        "title": "Title 100",
        "source_url": entry.source_url,
    }

    state.db_pool.acquire.return_value.__aenter__.return_value = mock_conn

    ok = await process_single_entry(state, entry)

    assert ok is True
    state.miniflux_client.mark_as_read.assert_awaited_once_with([100])


@pytest.mark.asyncio
@patch("app.worker.is_article_duplicate", new_callable=AsyncMock)
async def test_duplicate_gate_pending_failed_writing(mock_is_dup) -> None:
    """If outbox status is pending/failed/writing, we skip mark_as_read."""
    mock_is_dup.return_value = True

    for status in ("pending", "failed", "writing"):
        state = _make_state()
        entry = _make_entry(100)

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "outbox_status": status,
            "primary_category": "Geopolitica",
            "country_code": "US",
            "published_at": "2026-07-14",
            "title": "Title 100",
            "source_url": entry.source_url,
        }

        state.db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        ok = await process_single_entry(state, entry)

        assert ok is True
        state.miniflux_client.mark_as_read.assert_not_called()


@pytest.mark.asyncio
@patch("app.worker.is_article_duplicate", new_callable=AsyncMock)
@patch("app.worker.get_article_file_path")
async def test_duplicate_gate_null_with_file(mock_get_path, mock_is_dup) -> None:
    """If outbox status is None and vault file exists, we mark as read."""
    mock_is_dup.return_value = True
    mock_get_path.return_value = "/app/vault/Geopolitica/US/file.md"
    state = _make_state()
    entry = _make_entry(100)

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "outbox_status": None,
        "primary_category": "Geopolitica",
        "country_code": "US",
        "published_at": "2026-07-14",
        "title": "Title 100",
        "source_url": entry.source_url,
    }
    state.db_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch("pathlib.Path.is_file", return_value=True):
        ok = await process_single_entry(state, entry)

    assert ok is True
    state.miniflux_client.mark_as_read.assert_awaited_once_with([100])


@pytest.mark.asyncio
@patch("app.worker.is_article_duplicate", new_callable=AsyncMock)
@patch("app.worker.get_article_file_path")
async def test_duplicate_gate_null_without_file(mock_get_path, mock_is_dup) -> None:
    """If outbox status is None and vault file is missing, we skip mark_as_read."""
    mock_is_dup.return_value = True
    mock_get_path.return_value = "/app/vault/Geopolitica/US/file.md"
    state = _make_state()
    entry = _make_entry(100)

    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "outbox_status": None,
        "primary_category": "Geopolitica",
        "country_code": "US",
        "published_at": "2026-07-14",
        "title": "Title 100",
        "source_url": entry.source_url,
    }
    state.db_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch("pathlib.Path.is_file", return_value=False):
        ok = await process_single_entry(state, entry)

    assert ok is True
    state.miniflux_client.mark_as_read.assert_not_called()
