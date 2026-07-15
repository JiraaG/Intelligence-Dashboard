"""
Tests for outbox mark-read retry logic post-completed (T-P1-03).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.commit.outbox import (
    payload_checksum,
    process_outbox_row,
    reconcile_outbox,
)


def _async_cm(value):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_pool(conn: MagicMock) -> MagicMock:
    pool = MagicMock()
    pool.acquire.return_value = _async_cm(conn)
    return pool


@pytest.mark.unit
@pytest.mark.asyncio
@patch("app.commit.outbox.write_file_with_lock")
async def test_mark_read_fails_leaves_marked_at_null(mock_write, tmp_path: Path) -> None:
    """If mark_as_read fails, row becomes 'completed' but miniflux_marked_at remains NULL."""
    target = tmp_path / "article.md"
    payload = "content"
    checksum = payload_checksum(payload)
    
    row = {
        "id": 12,
        "article_id": 102,
        "target_path": str(target),
        "payload": payload,
        "payload_checksum": checksum,
        "attempt_count": 0,
        "miniflux_entry_id": 777,
        "status": "pending",
    }
    claimed = {**row, "attempt_count": 1, "status": "writing"}

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=claimed)
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    pool = _make_pool(mock_conn)

    miniflux = MagicMock()
    miniflux.mark_as_read = AsyncMock(side_effect=Exception("Miniflux connection error"))

    ok = await process_outbox_row(pool, row, miniflux)

    # process_outbox_row should still return True because Vault write succeeded
    assert ok is True
    mock_write.assert_called_once_with(str(target), payload)

    # Verify _mark_completed was called (sets status to 'completed' and miniflux_marked_at to NULL)
    completed_calls = [
        c.args for c in mock_conn.execute.call_args_list if "status = 'completed'" in c.args[0]
    ]
    assert len(completed_calls) == 1
    assert "miniflux_marked_at = NULL" in completed_calls[0][0]

    # Verify _update_miniflux_marked_at was NOT called
    marked_at_calls = [
        c.args for c in mock_conn.execute.call_args_list if "miniflux_marked_at = NOW()" in c.args[0]
    ]
    assert len(marked_at_calls) == 0


@pytest.mark.unit
@pytest.mark.asyncio
@patch("app.commit.outbox.write_file_with_lock")
async def test_reconcile_retries_failed_mark_read_and_updates_timestamp(mock_write) -> None:
    """reconcile_outbox selects completed rows with NULL marked_at and retries mark_as_read without rewriting Vault."""
    completed_row = {
        "id": 15,
        "article_id": 105,
        "miniflux_entry_id": 888,
    }

    mock_conn = MagicMock()
    # Mock reconcile query results
    # First query fetches pending/failed rows -> return empty list
    # Second query fetches completed but unmarked rows -> return our completed_row
    mock_conn.fetch = AsyncMock(side_effect=[
        [],  # pending/failed
        [completed_row],  # completed with NULL marked_at
    ])
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")
    pool = _make_pool(mock_conn)

    miniflux = MagicMock()
    miniflux.mark_as_read = AsyncMock()

    stats = await reconcile_outbox(pool, miniflux)

    # Verify stats
    assert stats["attempted"] == 1
    assert stats["succeeded"] == 1
    assert stats["failed"] == 0

    # Verify Miniflux call was made
    miniflux.mark_as_read.assert_awaited_once_with([888])

    # Verify Vault write was NOT called
    mock_write.assert_not_called()

    # Verify DB update sets miniflux_marked_at = NOW()
    marked_at_calls = [
        c.args for c in mock_conn.execute.call_args_list if "miniflux_marked_at = NOW()" in c.args[0]
    ]
    assert len(marked_at_calls) == 1
    assert marked_at_calls[0][1] == 15  # outbox_id
