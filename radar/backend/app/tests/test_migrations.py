"""Unit tests for ordered SQL migrations with checksum verification (no live Postgres)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.migrations import (
    MigrationError,
    discover_migrations,
    get_migrations_dir,
    run_migrations,
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.unit
def test_discover_migrations_finds_001_and_002_in_order() -> None:
    """discover_migrations returns 001, 002, 003… with non-empty SHA-256 checksums."""
    migrations = discover_migrations()
    versions = [version for version, _path, _checksum in migrations]

    assert versions[0].startswith("001_")
    assert versions[1].startswith("002_")
    assert any(v.startswith("003_") for v in versions)
    assert any(v.startswith("004_") for v in versions)
    assert any(v.startswith("005_") for v in versions)
    assert any(v.startswith("006_") for v in versions)
    assert any(v.startswith("007_") for v in versions)
    assert versions == sorted(versions)

    for version, path, checksum in migrations:
        assert path.is_file()
        assert path.suffix == ".sql"
        assert len(checksum) == 64
        assert checksum == hashlib.sha256(path.read_bytes()).hexdigest()
        assert version == path.stem

    roots = {path.parent for _v, path, _c in migrations}
    assert roots == {get_migrations_dir()}


@pytest.mark.unit
def test_discover_migrations_empty_dir_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty_migrations"
    empty.mkdir()
    with pytest.raises(MigrationError, match="Nessun file"):
        discover_migrations(empty)


@pytest.mark.unit
def test_discover_migrations_missing_dir_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    with pytest.raises(MigrationError, match="non trovata"):
        discover_migrations(missing)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_migrations_checksum_mismatch_raises(tmp_path: Path) -> None:
    """Already-applied migration with different checksum aborts with MigrationError."""
    sql_path = tmp_path / "001_initial.sql"
    sql_path.write_text("-- current content\nSELECT 1;", encoding="utf-8")
    current_checksum = _sha256_text(sql_path.read_text(encoding="utf-8"))
    stale_checksum = "0" * 64
    assert stale_checksum != current_checksum

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    # _ensure_tracking_table: table exists, version column exists
    mock_conn.fetchval = AsyncMock(side_effect=[True, True])
    mock_conn.fetch = AsyncMock(
        return_value=[{"version": "001_initial", "checksum": stale_checksum}]
    )
    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=None)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value = mock_tx

    mock_pool = MagicMock()
    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_acquire

    with pytest.raises(MigrationError, match="Checksum mismatch"):
        await run_migrations(mock_pool, migrations_dir=tmp_path)

    # Failed before applying SQL body / recording a new checksum
    assert mock_conn.transaction.call_count == 0
    insert_calls = [
        c for c in mock_conn.execute.await_args_list if "INSERT INTO schema_migrations" in str(c)
    ]
    assert insert_calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_migrations_happy_path_applies_and_records_checksum(tmp_path: Path) -> None:
    """Pending migrations are executed and recorded with their file checksum."""
    sql_a = tmp_path / "001_initial.sql"
    sql_b = tmp_path / "002_pipeline_outbox_and_quotas.sql"
    sql_a.write_text("-- 001\nCREATE TABLE IF NOT EXISTS t1 (id INT);", encoding="utf-8")
    sql_b.write_text("-- 002\nCREATE TABLE IF NOT EXISTS t2 (id INT);", encoding="utf-8")
    checksum_a = hashlib.sha256(sql_a.read_bytes()).hexdigest()
    checksum_b = hashlib.sha256(sql_b.read_bytes()).hexdigest()

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    # _ensure_tracking_table: table missing → CREATE
    mock_conn.fetchval = AsyncMock(return_value=False)
    mock_conn.fetch = AsyncMock(return_value=[])  # nothing applied yet
    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=None)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value = mock_tx

    mock_pool = MagicMock()
    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_acquire

    await run_migrations(mock_pool, migrations_dir=tmp_path)

    assert mock_conn.transaction.call_count == 2

    # schema_migrations DDL + two SQL bodies + two INSERT checksum rows
    executed_sql = [call.args[0] for call in mock_conn.execute.await_args_list]
    assert any("schema_migrations" in sql and "CREATE TABLE" in sql for sql in executed_sql)
    assert any("t1" in sql for sql in executed_sql)
    assert any("t2" in sql for sql in executed_sql)

    insert_calls = [
        call
        for call in mock_conn.execute.await_args_list
        if "INSERT INTO schema_migrations" in call.args[0]
    ]
    assert len(insert_calls) == 2
    assert insert_calls[0].args[1:] == ("001_initial", checksum_a)
    assert insert_calls[1].args[1:] == ("002_pipeline_outbox_and_quotas", checksum_b)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_incompatible_schema_aborts_before_worker_would_start() -> None:
    """
    Checksum mismatch surfaces as MigrationError from bootstrap_database,
    so lifespan would abort before starting the ingest worker.
    """
    from app.core.database import bootstrap_database

    version, _path, real_checksum = discover_migrations()[0]
    wrong_checksum = ("f" * 64) if not real_checksum.startswith("f") else ("0" * 64)

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchval = AsyncMock(side_effect=[True, True])
    mock_conn.fetch = AsyncMock(
        return_value=[{"version": version, "checksum": wrong_checksum}]
    )
    mock_tx = MagicMock()
    mock_tx.__aenter__ = AsyncMock(return_value=None)
    mock_tx.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value = mock_tx

    mock_pool = MagicMock()
    mock_acquire = MagicMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_acquire

    with pytest.raises(MigrationError, match="Checksum mismatch"):
        await bootstrap_database(mock_pool)

    assert mock_conn.transaction.call_count == 0
