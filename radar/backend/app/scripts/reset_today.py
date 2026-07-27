#!/usr/bin/env python3
"""Ops: reset giornata corrente (RADAR_TIME_ZONE) per re-test ingest da zero.

Distruttivo (senza --dry-run):
1. Marca unread su Miniflux le entry legate agli articles creati oggi (+ entry
   pubblicate oggi ancora read, se raggiungibili)
2. Cancella markdown vault degli URL di oggi (+ prefisso data locale vault)
3. DELETE articles creati oggi (CASCADE outbox/join/embeddings)
4. DELETE llm_request_ledger creati oggi (azzera COSTI del giorno)
5. DELETE llm_model_cooldown

Eseguire dentro radar-worker::

    python -m app.scripts.reset_today --dry-run
    python -m app.scripts.reset_today
    # poi: docker compose restart radar-worker
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg
import httpx

from app.core.config import DATABASE_URL, OBSIDIAN_VAULT_PATH, RADAR_TIME_ZONE, RADAR_TIME_ZONE_NAME
from app.extraction.client import MinifluxClient

URL_HASH_HEX_CHARS = 16
_MINIFLUX_PAGE_SIZE = 50


def _url_hash(source_url: str) -> str:
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:URL_HASH_HEX_CHARS]


def _day_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Finestra [day_start, day_end) nella timezone Radar (half-open)."""
    tz = RADAR_TIME_ZONE
    current = now.astimezone(tz) if now else datetime.now(tz)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


async def _mark_unread(mf: MinifluxClient, entry_ids: list[int]) -> None:
    ids = sorted({int(i) for i in entry_ids if i is not None})
    chunk = 100
    for i in range(0, len(ids), chunk):
        await mf._request(
            "PUT",
            "/v1/entries",
            json_body={"entry_ids": ids[i : i + chunk], "status": "unread"},
            expect_json=False,
        )


async def _fetch_published_today_read(
    mf: MinifluxClient, day_start: datetime, day_end: datetime, *, limit: int = 500
) -> list[int]:
    """Entry Miniflux *read* con published_at nella giornata (best-effort, max ``limit``)."""
    collected: list[int] = []
    offset = 0
    while len(collected) < limit:
        page_limit = min(_MINIFLUX_PAGE_SIZE, limit - len(collected))
        data = await mf._request(
            "GET",
            "/v1/entries",
            params={
                "status": "read",
                "limit": page_limit,
                "offset": offset,
                "order": "published_at",
                "direction": "desc",
            },
        )
        page = (data or {}).get("entries") or []
        if not page:
            break
        stop_early = False
        for entry in page:
            published = entry.get("published_at") or entry.get("created_at")
            if not published:
                continue
            try:
                ts = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
            except ValueError:
                continue
            if day_start <= ts < day_end:
                eid = entry.get("id")
                if eid is not None:
                    collected.append(int(eid))
            elif ts < day_start:
                stop_early = True
                break
        if stop_early:
            break
        offset += len(page)
        if len(page) < page_limit:
            break
    return collected


def _delete_vault_for_urls(vault_root: Path, urls: list[str], *, dry_run: bool) -> int:
    hits = 0
    for url in urls:
        if not url:
            continue
        h = _url_hash(url)
        for path in vault_root.rglob(f"*_{h}.md"):
            hits += 1
            if dry_run:
                print(f"  would_delete_vault={path.relative_to(vault_root)}")
                continue
            try:
                path.unlink()
                lock = Path(str(path) + ".lock")
                if lock.is_file():
                    lock.unlink(missing_ok=True)
            except OSError as exc:
                print(f"vault_err {path.name}: {exc}")
    return hits


def _delete_vault_date_prefix(vault_root: Path, day_start: datetime, *, dry_run: bool) -> int:
    """Cancella ``YYYY-MM-DD_*.md`` nella timezone locale del filename (data giorno)."""
    # I filename vault usano tipicamente la data di publish/create in Europe o UTC;
    # cancelliamo sia la data TZ Radar sia la data Rome se diversa.
    prefixes: set[str] = {day_start.strftime("%Y-%m-%d")}
    try:
        rome = day_start.astimezone(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d")
        prefixes.add(rome)
    except Exception:
        pass
    hits = 0
    for prefix in sorted(prefixes):
        for path in vault_root.rglob(f"{prefix}_*.md"):
            hits += 1
            if dry_run:
                print(f"  would_delete_vault_date={path.relative_to(vault_root)}")
                continue
            try:
                path.unlink()
                lock = Path(str(path) + ".lock")
                if lock.is_file():
                    lock.unlink(missing_ok=True)
            except OSError as exc:
                print(f"vault_err {path.name}: {exc}")
    return hits


async def reset_today(*, dry_run: bool) -> None:
    day_start, day_end = _day_window()
    print(
        f"dry_run={dry_run} tz={RADAR_TIME_ZONE_NAME} "
        f"day=[{day_start.isoformat()}, {day_end.isoformat()})"
    )

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    a.id,
                    a.source_url,
                    o.miniflux_entry_id
                FROM articles a
                LEFT JOIN article_outbox o ON o.article_id = a.id
                WHERE a.created_at >= $1 AND a.created_at < $2
                ORDER BY a.id
                """,
                day_start,
                day_end,
            )
            ledger_count = await conn.fetchval(
                """
                SELECT COUNT(*)::INT FROM llm_request_ledger
                WHERE created_at >= $1 AND created_at < $2
                """,
                day_start,
                day_end,
            )
            dedup_count = await conn.fetchval(
                """
                SELECT COUNT(*)::INT FROM article_dedup_events
                WHERE created_at >= $1 AND created_at < $2
                """,
                day_start,
                day_end,
            )
            cooldown_count = await conn.fetchval(
                "SELECT COUNT(*)::INT FROM llm_model_cooldown"
            )

        urls = [str(r["source_url"] or "") for r in rows]
        article_ids = [int(r["id"]) for r in rows]
        entry_ids = [
            int(r["miniflux_entry_id"])
            for r in rows
            if r["miniflux_entry_id"] is not None
        ]
        print(
            f"articles_today={len(article_ids)} ledger_today={ledger_count} "
            f"dedup_today={dedup_count} cooldown_rows={cooldown_count} "
            f"miniflux_ids_from_db={len(entry_ids)}"
        )

        async with httpx.AsyncClient(timeout=60.0) as http:
            mf = MinifluxClient(http_client=http)
            extra_ids = await _fetch_published_today_read(mf, day_start, day_end)
            all_ids = sorted(set(entry_ids) | set(extra_ids))
            print(f"miniflux_unread_targets={len(all_ids)} (db+published_today_read)")

            if dry_run:
                unread = await mf._request(
                    "GET", "/v1/entries", params={"status": "unread", "limit": 1}
                )
                print(f"unread_total={(unread or {}).get('total')} (unchanged)")
            elif all_ids:
                await _mark_unread(mf, all_ids)
                unread = await mf._request(
                    "GET", "/v1/entries", params={"status": "unread", "limit": 1}
                )
                print(f"unread_total={(unread or {}).get('total')}")

        vault_root = Path(OBSIDIAN_VAULT_PATH)
        v1 = _delete_vault_for_urls(vault_root, urls, dry_run=dry_run)
        v2 = _delete_vault_date_prefix(vault_root, day_start, dry_run=dry_run)
        print(f"vault_hits_url={v1} vault_hits_date_prefix={v2}")

        async with pool.acquire() as conn:
            if dry_run:
                print(
                    f"would_delete_articles={len(article_ids)} "
                    f"would_delete_ledger={ledger_count} "
                    f"would_delete_dedup={dedup_count} "
                    f"would_clear_cooldown={cooldown_count}"
                )
            else:
                async with conn.transaction():
                    if article_ids:
                        await conn.execute(
                            "DELETE FROM articles WHERE id = ANY($1::int[])",
                            article_ids,
                        )
                    deleted_ledger = await conn.execute(
                        """
                        DELETE FROM llm_request_ledger
                        WHERE created_at >= $1 AND created_at < $2
                        """,
                        day_start,
                        day_end,
                    )
                    deleted_dedup = await conn.execute(
                        """
                        DELETE FROM article_dedup_events
                        WHERE created_at >= $1 AND created_at < $2
                        """,
                        day_start,
                        day_end,
                    )
                    cleared_cd = await conn.execute("DELETE FROM llm_model_cooldown")
                print(
                    f"deleted_articles={len(article_ids)} "
                    f"ledger_delete={deleted_ledger} "
                    f"dedup_delete={deleted_dedup} "
                    f"cooldown_delete={cleared_cd}"
                )
    finally:
        await pool.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Reset giornata Radar (articles/vault/ledger/Miniflux unread)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Anteprima; nessuna scrittura Miniflux/DB/vault",
    )
    args = parser.parse_args(argv)
    asyncio.run(reset_today(dry_run=args.dry_run))


if __name__ == "__main__":
    main(sys.argv[1:])
