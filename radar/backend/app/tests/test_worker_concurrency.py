"""
Tests for URL-based pg_advisory_lock concurrency and serialization (T-P1-02).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.extraction.entry_validation import ValidatedMinifluxEntry
from app.worker import WorkerState, process_single_entry
from app.classification.validator import GeopoliticalArticleSchema


class LockSimulatingConnection:
    """A mock asyncpg Connection that simulates pg_advisory_lock and is_article_duplicate."""
    
    def __init__(self, db_articles: set[str], active_locks: set[tuple[int, int]], lock_condition: asyncio.Condition) -> None:
        self.db_articles = db_articles
        self.active_locks = active_locks
        self.lock_condition = lock_condition
        
        self.execute = AsyncMock(side_effect=self._mock_execute)
        self.fetchrow = AsyncMock(side_effect=self._mock_fetchrow)
        self.fetchval = AsyncMock(side_effect=self._mock_fetchval)

    async def _mock_execute(self, query: str, *args: Any) -> None:
        query_clean = " ".join(query.split())
        if "pg_advisory_lock" in query_clean:
            ns, key = args[0], args[1]
            lock_id = (ns, key)
            async with self.lock_condition:
                while lock_id in self.active_locks:
                    await self.lock_condition.wait()
                self.active_locks.add(lock_id)
        elif "pg_advisory_unlock" in query_clean:
            ns, key = args[0], args[1]
            lock_id = (ns, key)
            async with self.lock_condition:
                if lock_id in self.active_locks:
                    self.active_locks.remove(lock_id)
                    self.lock_condition.notify_all()

    async def _mock_fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        query_clean = " ".join(query.split())
        if "SELECT o.status" in query_clean:
            url = args[0]
            if url in self.db_articles:
                return {
                    "outbox_status": "completed",
                    "primary_category": "Geopolitica",
                    "country_code": "US",
                    "published_at": "2026-07-14",
                    "title": "Mock Title",
                    "source_url": url,
                }
        return None

    async def _mock_fetchval(self, query: str, *args: Any) -> Any:
        query_clean = " ".join(query.split())
        if "EXISTS" in query_clean:
            url = args[0]
            return url in self.db_articles
        return None


def _make_entry(entry_id: int, url: str) -> ValidatedMinifluxEntry:
    return ValidatedMinifluxEntry(
        id=entry_id,
        source_url=url,
        title=f"Concurrent Title {entry_id}",
        content="<p>Body content</p>",
        published_at="2026-07-14",
        feed_title="Test Feed",
    )


@pytest.mark.asyncio
@patch("app.worker.commit_article_to_db", new_callable=AsyncMock)
async def test_concurrent_same_url_serialization(mock_commit) -> None:
    """
    Test that two concurrent workers trying to process the same URL
    are serialized by the advisory lock, and the second one bypasses LLM
    classification because the first one has already committed the article.
    """
    url = "https://example.com/concurrent-test"
    entry1 = _make_entry(101, url)
    entry2 = _make_entry(102, url)

    # Share database state between connection mocks
    db_articles: set[str] = set()
    active_locks: set[tuple[int, int]] = set()
    lock_condition = asyncio.Condition()

    def create_conn() -> LockSimulatingConnection:
        return LockSimulatingConnection(db_articles, active_locks, lock_condition)

    # Set up worker state
    state = WorkerState()
    state.db_pool = MagicMock()
    # Return a new connection instance per acquire call
    state.db_pool.acquire.side_effect = lambda: MagicMock(
        __aenter__=AsyncMock(side_effect=lambda: create_conn())
    )
    state.miniflux_client = AsyncMock()
    state.classification_client = AsyncMock()
    
    # Configure Gemini mock with a sleep to ensure overlap
    async def slow_classify(*args: Any, **kwargs: Any) -> GeopoliticalArticleSchema:
        await asyncio.sleep(0.1)
        return GeopoliticalArticleSchema(
            title="Concurrent Title",
            summary="summary",
            published_at="2026-07-14",
            source_url=url,
            country_code="US",
            latitude=0.0,
            longitude=0.0,
            companies_involved="Nessuno",
            tags="Geopolitica, concurrent",
            primary_category="Geopolitica",
            sentiment="Neutrale",
            infrastructural_entities="Nessuno",
            related_countries="Nessuno",
            relevance_level=3,
        )
    state.classification_client.classify_article.side_effect = slow_classify

    # When first worker commits, add URL to simulated DB articles
    async def mock_commit_impl(conn: Any, article: Any, *args: Any, **kwargs: Any) -> int:
        conn.db_articles.add(article.source_url)
        return 123
    mock_commit.side_effect = mock_commit_impl

    # Semaphores
    state.parse_sem = asyncio.Semaphore(2)
    state.db_sem = asyncio.Semaphore(2)
    state.gemini_sem = asyncio.Semaphore(2)

    # Execute both processes concurrently
    results = await asyncio.gather(
        process_single_entry(state, entry1),
        process_single_entry(state, entry2),
    )

    # Both must succeed (True)
    assert results == [True, True]

    # Gemini classify should only be called once because the second detects duplication after lock release
    assert state.classification_client.classify_article.call_count == 1
    assert mock_commit.call_count == 1

    # Ensure Miniflux mark_as_read was called for the duplicate entry (102)
    state.miniflux_client.mark_as_read.assert_called_once_with([102])
