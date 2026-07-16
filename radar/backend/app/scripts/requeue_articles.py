"""Ops: re-queue recent Miniflux read entries for another classify cycle.

Marks the last N *read* Miniflux entries as *unread*, deletes matching
PostgreSQL ``articles`` / ``article_outbox`` rows and vault markdown files
(by URL SHA-256 hex[:16]), and clears ``llm_model_cooldown``.

Run inside ``radar-worker`` (has Miniflux + DB + vault mount)::

    docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20

Default N=20. After requeue, restart the worker to force an immediate cycle
(poll interval is typically 900s)::

    docker compose restart radar-worker
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

import asyncpg
import httpx

from app.core.config import DATABASE_URL, OBSIDIAN_VAULT_PATH
from app.extraction.client import MinifluxClient

URL_HASH_HEX_CHARS = 16


def _url_hash(source_url: str) -> str:
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:URL_HASH_HEX_CHARS]


async def requeue(n: int) -> None:
    if n < 1 or n > 500:
        raise SystemExit(f"N must be 1..500, got {n}")

    async with httpx.AsyncClient(timeout=60.0) as http:
        mf = MinifluxClient(http_client=http)
        read = await mf._request(
            "GET",
            "/v1/entries",
            params={
                "status": "read",
                "limit": n,
                "order": "published_at",
                "direction": "desc",
            },
        )
        entries = (read or {}).get("entries") or []
        ids = [int(e["id"]) for e in entries if e.get("id") is not None]
        urls = [str(e.get("url") or "") for e in entries if e.get("url")]
        print(f"candidates={len(ids)}")
        if ids:
            await mf._request(
                "PUT",
                "/v1/entries",
                json_body={"entry_ids": ids, "status": "unread"},
                expect_json=False,
            )
        unread = await mf._request(
            "GET", "/v1/entries", params={"status": "unread", "limit": 1}
        )
        print(f"unread_total={(unread or {}).get('total')}")

    vault_root = Path(OBSIDIAN_VAULT_PATH)
    vault_deleted = 0
    for url in urls:
        h = _url_hash(url)
        for path in vault_root.rglob(f"*_{h}.md"):
            try:
                path.unlink()
                vault_deleted += 1
                lock = Path(str(path) + ".lock")
                if lock.is_file():
                    lock.unlink(missing_ok=True)
            except OSError as exc:
                print(f"vault_err {path.name}: {exc}")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)
    db_deleted = 0
    try:
        async with pool.acquire() as conn:
            cleared = await conn.execute("DELETE FROM llm_model_cooldown")
            print(f"cooldown_delete={cleared}")
            for url in urls:
                row = await conn.fetchrow(
                    "SELECT id FROM articles WHERE source_url = $1", url
                )
                if row is None:
                    continue
                await conn.execute(
                    "DELETE FROM article_outbox WHERE article_id = $1", row["id"]
                )
                await conn.execute("DELETE FROM articles WHERE id = $1", row["id"])
                db_deleted += 1
    finally:
        await pool.close()

    print(f"vault_deleted={vault_deleted} db_deleted={db_deleted}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Re-queue last N Miniflux read entries for classify (ops)."
    )
    parser.add_argument(
        "n",
        nargs="?",
        type=int,
        default=20,
        help="How many recent read entries to requeue (default 20, max 500)",
    )
    args = parser.parse_args(argv)
    asyncio.run(requeue(args.n))


if __name__ == "__main__":
    main(sys.argv[1:])
