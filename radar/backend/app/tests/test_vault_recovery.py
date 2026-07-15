"""Vault recovery via outbox: no premature mark-read, retry with metadata (mocked DB)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.classification.validator import GeopoliticalArticleSchema
from app.commit.db_commit import commit_article_to_db
from app.commit.outbox import (
    payload_checksum,
    process_outbox_row,
    reconcile_outbox,
)


def _article() -> GeopoliticalArticleSchema:
    return GeopoliticalArticleSchema(
        title="Recovery Probe",
        summary="Articolo per test recovery outbox.",
        published_at="2026-07-14",
        source_url="https://example.com/recovery-probe",
        country_code="DE",
        latitude=52.5,
        longitude=13.4,
        companies_involved="Acme",
        tags="Tecnologia",
        primary_category="Tecnologia",
        sentiment="Neutrale",
        infrastructural_entities="Nessuno",
        relevance_level=2,
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
async def test_commit_enqueues_outbox_in_same_transaction() -> None:
    """DB commit inserts article relations and outbox row atomically (mocked)."""
    mock_conn = MagicMock()
    mock_conn.transaction.return_value = _async_cm(None)
    mock_conn.fetchval = AsyncMock(side_effect=[101, 201, 301])  # article, company, tag
    mock_conn.execute = AsyncMock()

    article = _article()
    payload = "---\ntitle: Recovery Probe\n---\n\nbody\n"
    target = "/vault/Tecnologia/DE/2026-07-14_recovery-probe_abcd.md"

    art_id = await commit_article_to_db(
        mock_conn,
        article,
        outbox_target_path=target,
        outbox_payload=payload,
        miniflux_entry_id=999,
    )

    assert art_id == 101
    mock_conn.transaction.assert_called_once()
    sql_blobs = [c.args[0] for c in mock_conn.execute.await_args_list]
    assert any("INSERT INTO article_outbox" in s for s in sql_blobs)
    assert any("INSERT INTO article_companies" in s for s in sql_blobs)
    # Single article insert via fetchval — no duplicate article inserts
    article_inserts = [
        c for c in mock_conn.fetchval.await_args_list if "INSERT INTO articles" in c.args[0]
    ]
    assert len(article_inserts) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vault_failure_then_reconcile_without_premature_mark_read(tmp_path: Path) -> None:
    """
    Simulated Vault write failure marks outbox failed with metadata;
    successful retry completes and only then calls mark_as_read.
    """
    target = tmp_path / "vault" / "Tecnologia" / "DE" / "article.md"
    payload = "---\ntitle: Recovery Probe\n---\n\nbody\n"
    checksum = payload_checksum(payload)
    outbox_id = 7
    article_id = 101
    entry_id = 999

    pending_row = {
        "id": outbox_id,
        "article_id": article_id,
        "target_path": str(target),
        "payload": payload,
        "payload_checksum": checksum,
        "attempt_count": 0,
        "miniflux_entry_id": entry_id,
        "status": "pending",
    }

    # ── First attempt: claim → write fails → mark failed ────────────────────
    mock_conn_fail = MagicMock()
    claimed_fail = {
        **pending_row,
        "attempt_count": 1,
        "status": "writing",
    }
    mock_conn_fail.fetchrow = AsyncMock(return_value=claimed_fail)
    mock_conn_fail.execute = AsyncMock()
    pool_fail = _make_pool(mock_conn_fail)

    miniflux = MagicMock()
    miniflux.mark_as_read = AsyncMock()

    with patch(
        "app.commit.outbox.write_file_with_lock",
        side_effect=OSError("disk full"),
    ):
        ok = await process_outbox_row(pool_fail, pending_row, miniflux)

    assert ok is False
    miniflux.mark_as_read.assert_not_awaited()

    fail_updates = [
        c for c in mock_conn_fail.execute.await_args_list if "status = 'failed'" in c.args[0]
    ]
    assert len(fail_updates) == 1
    assert "vault write failed" in fail_updates[0].args[2]
    # attempt_count was incremented on claim (returned as 1)
    assert claimed_fail["attempt_count"] == 1

    # ── Second attempt (reconcile): claim → write succeeds → mark-read ───────
    failed_row = {
        **pending_row,
        "attempt_count": 1,
        "status": "failed",
        "last_error": "vault write failed: disk full",
    }
    claimed_ok = {
        **failed_row,
        "attempt_count": 2,
        "status": "writing",
    }

    mock_conn_ok = MagicMock()
    mock_conn_ok.fetchrow = AsyncMock(return_value=claimed_ok)
    mock_conn_ok.execute = AsyncMock()
    mock_conn_ok.fetch = AsyncMock(side_effect=[[failed_row], []])
    pool_ok = _make_pool(mock_conn_ok)

    miniflux2 = MagicMock()
    miniflux2.mark_as_read = AsyncMock()

    with patch("app.commit.outbox.write_file_with_lock") as mock_write:
        mock_write.return_value = None
        # Also stub stale reset execute path used by reconcile
        mock_conn_ok.execute = AsyncMock(return_value="UPDATE 0")
        stats = await reconcile_outbox(pool_ok, miniflux2)

    assert stats["attempted"] == 1
    assert stats["succeeded"] == 1
    assert stats["failed"] == 0
    miniflux2.mark_as_read.assert_awaited_once_with([entry_id])
    mock_write.assert_called_once_with(str(target), payload)

    completed = [
        c for c in mock_conn_ok.execute.await_args_list if "status = 'completed'" in c.args[0]
    ]
    assert len(completed) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_outbox_retains_attempt_count_and_last_error() -> None:
    """_mark_failed persists last_error; claim increments attempt_count."""
    payload = "payload-body"
    checksum = payload_checksum(payload)
    row = {
        "id": 3,
        "article_id": 10,
        "target_path": "/tmp/vault/x.md",
        "payload": payload,
        "payload_checksum": checksum,
        "attempt_count": 2,
        "miniflux_entry_id": 55,
        "status": "failed",
    }
    claimed = {**row, "attempt_count": 3, "status": "writing"}

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=claimed)
    mock_conn.execute = AsyncMock()
    pool = _make_pool(mock_conn)
    miniflux = MagicMock()
    miniflux.mark_as_read = AsyncMock()

    with patch(
        "app.commit.outbox.write_file_with_lock",
        side_effect=PermissionError("locked by another process"),
    ):
        ok = await process_outbox_row(pool, row, miniflux)

    assert ok is False
    miniflux.mark_as_read.assert_not_awaited()

    # Claim SQL increments attempt_count
    claim_sql = mock_conn.fetchrow.await_args.args[0]
    assert "attempt_count = attempt_count + 1" in claim_sql

    fail_call = next(
        c for c in mock_conn.execute.await_args_list if "status = 'failed'" in c.args[0]
    )
    assert fail_call.args[1] == 3  # outbox id
    assert "locked by another process" in fail_call.args[2]
    assert claimed["attempt_count"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_successful_vault_write_marks_read_only_after_completed(tmp_path: Path) -> None:
    """mark_as_read is invoked only after outbox is marked completed."""
    target = tmp_path / "out.md"
    payload = "content"
    checksum = payload_checksum(payload)
    row = {
        "id": 1,
        "article_id": 2,
        "target_path": str(target),
        "payload": payload,
        "payload_checksum": checksum,
        "attempt_count": 0,
        "miniflux_entry_id": 42,
        "status": "pending",
    }
    claimed = {**row, "attempt_count": 1, "status": "writing"}

    call_order: list[str] = []

    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=claimed)

    async def _execute(sql, *args):
        if "status = 'completed'" in sql:
            call_order.append("completed")
        return "UPDATE 1"

    mock_conn.execute = AsyncMock(side_effect=_execute)
    pool = _make_pool(mock_conn)

    miniflux = MagicMock()

    async def _mark(ids):
        call_order.append("mark_as_read")

    miniflux.mark_as_read = AsyncMock(side_effect=_mark)

    # Real atomic write into tmp vault
    ok = await process_outbox_row(pool, row, miniflux)

    assert ok is True
    assert target.exists()
    assert (Path(str(target) + ".lock")).exists()  # permanent lock sidecar
    assert call_order == ["completed", "mark_as_read"]
    miniflux.mark_as_read.assert_awaited_once_with([42])
