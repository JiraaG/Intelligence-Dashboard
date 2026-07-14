"""Ordered SQL migrations with SHA-256 checksum verification."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger("radar.migrations")

SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class MigrationError(RuntimeError):
    """Raised when schema state is unknown or incompatible."""


def get_migrations_dir() -> Path:
    """Resolve backend/migrations relative to this module (app/core/migrations.py)."""
    return Path(__file__).resolve().parent.parent.parent / "migrations"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_migrations(migrations_dir: Path | None = None) -> list[tuple[str, Path, str]]:
    """
    Return sorted migration triples: (version, path, checksum).
    Version is the filename stem (e.g. 001_initial).
    """
    root = migrations_dir or get_migrations_dir()
    if not root.is_dir():
        raise MigrationError(f"Directory migrazioni non trovata: {root}")

    migrations: list[tuple[str, Path, str]] = []
    for path in sorted(root.glob("*.sql")):
        version = path.stem
        checksum = _sha256_file(path)
        migrations.append((version, path, checksum))

    if not migrations:
        raise MigrationError(f"Nessun file .sql trovato in {root}")

    return migrations


async def _table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = $1
            )
            """,
            table_name,
        )
    )


async def _column_exists(conn: asyncpg.Connection, table_name: str, column_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = $1
                  AND column_name = $2
            )
            """,
            table_name,
            column_name,
        )
    )


async def _ensure_tracking_table(conn: asyncpg.Connection) -> None:
    """
    Ensure schema_migrations uses (version, checksum, applied_at).
    Legacy pre-restore shape used (id, name, checksum, applied_at): drop and recreate
    so Phase 1 SQL can re-apply idempotently (CREATE/ALTER IF NOT EXISTS).
    """
    if not await _table_exists(conn, "schema_migrations"):
        await conn.execute(SCHEMA_MIGRATIONS_DDL)
        return

    if await _column_exists(conn, "schema_migrations", "version"):
        return

    if await _column_exists(conn, "schema_migrations", "name"):
        logger.warning(
            "Rilevata schema_migrations legacy (colonna name). "
            "Conversione a (version TEXT PK) con re-baseline delle migrazioni."
        )
        await conn.execute("DROP TABLE schema_migrations")
        await conn.execute(SCHEMA_MIGRATIONS_DDL)
        return

    raise MigrationError(
        "Tabella schema_migrations presente con schema sconosciuto/incompatibile. "
        "Avvio interrotto."
    )


async def run_migrations(
    pool: asyncpg.Pool,
    migrations_dir: Path | None = None,
) -> None:
    """
    Apply pending SQL migrations in order.
    Aborts startup if an already-applied migration has a checksum mismatch.
    """
    migrations = discover_migrations(migrations_dir)
    logger.info(
        "Esecuzione migrazioni da %s (%d file)",
        migrations_dir or get_migrations_dir(),
        len(migrations),
    )

    async with pool.acquire() as conn:
        await _ensure_tracking_table(conn)

        applied_rows = await conn.fetch("SELECT version, checksum FROM schema_migrations")
        applied: dict[str, str] = {row["version"]: row["checksum"] for row in applied_rows}

        for version, path, checksum in migrations:
            if version in applied:
                if applied[version] != checksum:
                    raise MigrationError(
                        f"Checksum mismatch per migrazione già applicata '{version}': "
                        f"atteso {applied[version]}, trovato {checksum}. "
                        "Schema incompatibile — avvio interrotto."
                    )
                logger.debug("Migrazione %s già applicata (checksum OK)", version)
                continue

            sql = path.read_text(encoding="utf-8")
            logger.info("Applicazione migrazione %s...", version)
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    """
                    INSERT INTO schema_migrations (version, checksum)
                    VALUES ($1, $2)
                    """,
                    version,
                    checksum,
                )
            logger.info("Migrazione %s applicata con successo", version)

    logger.info("Tutte le migrazioni sono allineate.")
