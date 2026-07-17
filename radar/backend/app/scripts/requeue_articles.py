"""Ops: re-queue recent Miniflux read entries for another classify cycle.

Marks the last N *read* Miniflux entries as *unread*, deletes matching
PostgreSQL ``articles`` / ``article_outbox`` rows and vault markdown files
(by URL SHA-256 hex[:16]), and clears ``llm_model_cooldown``.

Run inside ``radar-worker`` (has Miniflux + DB + vault mount)::

    docker compose exec -T radar-worker python -m app.scripts.requeue_articles 20 --dry-run
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


async def requeue(n: int, *, dry_run: bool = False) -> None:
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
        print(f"dry_run={dry_run} candidates={len(ids)}")
        for entry in entries[:10]:
            eid = entry.get("id")
            title = (entry.get("title") or "")[:80]
            print(f"  entry_id={eid} title={title!r}")
        if len(entries) > 10:
            print(f"  ... and {len(entries) - 10} more")

        if dry_run:
            unread = await mf._request(
                "GET", "/v1/entries", params={"status": "unread", "limit": 1}
            )
            print(f"unread_total={(unread or {}).get('total')} (unchanged)")
        elif ids:
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
    vault_hits = 0
    for url in urls:
        h = _url_hash(url)
        for path in vault_root.rglob(f"*_{h}.md"):
            vault_hits += 1
            if dry_run:
                print(f"  would_delete_vault={path.name}")
            else:
                try:
                    path.unlink()
                    lock = Path(str(path) + ".lock")
                    if lock.is_file():
                        lock.unlink(missing_ok=True)
                except OSError as exc:
                    print(f"vault_err {path.name}: {exc}")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)
    db_hits = 0
    try:
        async with pool.acquire() as conn:
            cooldown_count = await conn.fetchval(
                "SELECT COUNT(*) FROM llm_model_cooldown"
            )
            if dry_run:
                print(f"would_clear_cooldown_rows={cooldown_count}")
            else:
                cleared = await conn.execute("DELETE FROM llm_model_cooldown")
                print(f"cooldown_delete={cleared}")
            for url in urls:
                row = await conn.fetchrow(
                    "SELECT id FROM articles WHERE source_url = $1", url
                )
                if row is None:
                    continue
                db_hits += 1
                if dry_run:
                    print(f"  would_delete_article_id={row['id']}")
                else:
                    await conn.execute(
                        "DELETE FROM article_outbox WHERE article_id = $1",
                        row["id"],
                    )
                    await conn.execute(
                        "DELETE FROM articles WHERE id = $1", row["id"]
                    )
    finally:
        await pool.close()

    if dry_run:
        print(f"would_delete_vault={vault_hits} would_delete_db={db_hits}")
    else:
        print(f"vault_deleted={vault_hits} db_deleted={db_hits}")


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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List candidates and would-be deletes; no Miniflux/DB/vault writes",
    )
    args = parser.parse_args(argv)
    asyncio.run(requeue(args.n, dry_run=args.dry_run))


if __name__ == "__main__":
    main(sys.argv[1:])
