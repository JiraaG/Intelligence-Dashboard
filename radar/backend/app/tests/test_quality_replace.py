"""Tests for quality comparison and replace in-place logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.classification.quality_compare import (
    compare_articles_quality,
    prepare_balanced_text,
)
from app.classification.validator import GeopoliticalArticleSchema
from app.commit.db_commit import replace_article_in_place
from app.commit.outbox import force_reopen_outbox_row


def test_prepare_balanced_text_short() -> None:
    """Short text <= 2500 chars is kept intact."""
    title = "Test Title"
    body = "Short body content " * 10
    res = prepare_balanced_text(title, body)
    assert "TITOLO: Test Title" in res
    assert "[...]" not in res


def test_prepare_balanced_text_medium_split_50_50() -> None:
    """Medium text (2500-5000 chars) is truncated with 50/50 split."""
    title = "Medium Title"
    body = "Word " * 700  # ~3500 chars
    res = prepare_balanced_text(title, body)
    assert "[...]" in res


def test_prepare_balanced_text_long_split_40_20_40() -> None:
    """Long text (>5000 chars) is truncated with 40/20/40 split."""
    title = "Long Title"
    body = "Long content paragraph " * 300  # ~6900 chars
    res = prepare_balanced_text(title, body)
    assert res.count("[...]") == 2


@pytest.mark.asyncio
async def test_compare_articles_quality_prefilter_keeps_when_incoming_shorter() -> None:
    """D15: keep existing only when incoming is clearly shorter (len_new < len_exist * 0.7)."""
    mock_pool = AsyncMock()
    existing_text = "Detailed text " * 100  # ~1400 chars
    incoming_text = "Short text"  # 10 chars

    result = await compare_articles_quality(
        mock_pool,
        existing_title="Existing",
        existing_text=existing_text,
        incoming_title="Incoming",
        incoming_text=incoming_text,
        incoming_url="https://example.com/inc",
    )

    assert result.same_story is True
    assert result.winner == "existing"
    assert result.confidence == 1.0
    assert "prefilter" in result.reason


@pytest.mark.asyncio
async def test_compare_articles_quality_prefilter_skips_when_incoming_longer() -> None:
    """Incoming much longer must NOT auto-keep existing; must go to LLM path."""
    mock_pool = AsyncMock()
    existing_text = "Short existing"
    incoming_text = "Detailed incoming article body " * 80  # clearly longer

    with patch(
        "app.classification.quality_compare.QuotaLedger"
    ) as mock_ledger_cls:
        mock_ledger = AsyncMock()
        mock_ledger.reserve = AsyncMock(side_effect=RuntimeError("force fail-safe"))
        mock_ledger_cls.return_value = mock_ledger

        result = await compare_articles_quality(
            mock_pool,
            existing_title="Existing",
            existing_text=existing_text,
            incoming_title="Incoming",
            incoming_text=incoming_text,
            incoming_url="https://example.com/inc-long",
        )

    # Fail-safe keep after attempting LLM reservation (prefilter did not short-circuit)
    assert result.winner == "existing"
    assert "prefilter" not in result.reason
    mock_ledger.reserve.assert_awaited_once()
    assert mock_ledger.reserve.await_args.kwargs["purpose"] == "quality:compare"
    assert mock_ledger.reserve.await_args.kwargs["lane"] == "complex"
    assert mock_ledger.reserve.await_args.kwargs["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_force_reopen_outbox_row() -> None:
    """force_reopen_outbox_row sets status to pending even if previously completed."""
    mock_conn = AsyncMock()
    article_id = 42

    await force_reopen_outbox_row(
        mock_conn,
        article_id=article_id,
        target_path="/app/vault/Geopolitica/US/file.md",
        payload="# Markdown Content",
        miniflux_entry_id=123,
    )

    mock_conn.execute.assert_awaited_once()
    sql = mock_conn.execute.call_args[0][0]
    assert "status = 'pending'" in sql
    assert "attempt_count = 0" in sql


@pytest.mark.asyncio
@patch("app.commit.db_commit.force_reopen_outbox_row", new_callable=AsyncMock)
async def test_replace_article_in_place(mock_force_reopen) -> None:
    """replace_article_in_place updates DB record, junctions, embedding, and reopens outbox."""
    mock_conn = MagicMock()
    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"target_path": "/app/vault/Old/Path.md"})
    mock_conn.execute = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)

    existing_id = 99
    article = GeopoliticalArticleSchema(
        title="Updated Title",
        summary="Updated Executive Summary",
        published_at="2026-07-22",
        source_url="https://example.com/updated",
        country_code="IT",
        latitude=41.87,
        longitude=12.57,
        companies_involved="Eni, Enel",
        tags="Energia, Eni",
        primary_category="Energia",
        sentiment="Positivo",
        infrastructural_entities="Oleodotto",
        related_countries="FR",
        relevance_level=4,
    )

    dummy_vector = [0.05] * 384

    res_id = await replace_article_in_place(
        mock_conn,
        existing_article_id=existing_id,
        article=article,
        feed_title="Energy Feed",
        outbox_target_path="/app/vault/Energia/IT/updated.md",
        outbox_payload="# Updated Markdown",
        miniflux_entry_id=456,
        body_excerpt="Updated body excerpt",
        embedding=dummy_vector,
    )

    assert res_id == existing_id
    mock_force_reopen.assert_awaited_once()
    # UPDATE articles must not touch is_read / is_saved
    update_sql = mock_conn.execute.call_args_list[0][0][0]
    assert "is_read" not in update_sql
    assert "is_saved" not in update_sql
    assert "body_excerpt" in update_sql
    assert "content_sha256" in update_sql

