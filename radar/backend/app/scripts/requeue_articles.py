"""
Ops: riaccoda entry Miniflux già lette per un altro ciclo di classificazione.

**Distruttivo** (senza ``--dry-run``):
1. Marca le ultime N entry *read* come *unread* in Miniflux (paginazione API)
2. Cancella markdown vault corrispondenti (hash URL SHA-256 hex[:16]) + sidecar ``.lock``
3. Svuota ``llm_model_cooldown`` e cancella ``articles`` / ``article_outbox`` per quegli URL

Con ``--purge-all`` (prova da zero):
- wipe di **tutti** i ``.md`` / ``.lock`` sotto il vault
- ``DELETE`` di **tutte** le righe ``articles`` (CASCADE outbox/join)

Ordine: sempre prima ``--dry-run`` (skill radar-requeue-ops), poi write, poi
    ``docker compose restart radar-worker`` (poll tipico 900s).

Eseguire **dentro** ``radar-worker`` (Miniflux + DB + mount vault)::

    docker compose exec -T radar-worker python -m app.scripts.requeue_articles 50 --dry-run
    docker compose exec -T radar-worker python -m app.scripts.requeue_articles 50 --purge-all

Default N=20 (max 500). @see radar-requeue-ops; runbook requeue.
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

# Allineato a commit/router: filename vault usa hex[:16] dell'URL.
URL_HASH_HEX_CHARS = 16
# Miniflux API tipicamente restituisce al massimo 50–100 entry per pagina.
_MINIFLUX_PAGE_SIZE = 50


def _url_hash(source_url: str) -> str:
    """Prefisso hash usato nei nomi file vault (stesso contratto del router)."""
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:URL_HASH_HEX_CHARS]


async def _fetch_read_entries(mf: MinifluxClient, n: int) -> list[dict]:
    """Raccoglie fino a ``n`` entry *read* paginando Miniflux (limit API ≤50)."""
    collected: list[dict] = []
    offset = 0
    while len(collected) < n:
        page_limit = min(_MINIFLUX_PAGE_SIZE, n - len(collected))
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
        collected.extend(page)
        offset += len(page)
        api_total = (data or {}).get("total")
        if isinstance(api_total, int) and offset >= api_total:
            break
        if len(page) < page_limit:
            break
    return collected[:n]


def _wipe_vault_markdown(vault_root: Path, *, dry_run: bool) -> int:
    """Elimina tutti i ``.md`` e sidecar ``.lock`` sotto il vault (non tocca ``.gitkeep``)."""
    hits = 0
    for path in sorted(vault_root.rglob("*.md")):
        hits += 1
        if dry_run:
            print(f"  would_wipe_vault={path.relative_to(vault_root)}")
            continue
        try:
            path.unlink()
            lock = Path(str(path) + ".lock")
            if lock.is_file():
                lock.unlink(missing_ok=True)
        except OSError as exc:
            print(f"vault_wipe_err {path.name}: {exc}")
    # Lock orfani senza .md
    for lock in sorted(vault_root.rglob("*.md.lock")):
        if dry_run:
            print(f"  would_wipe_lock={lock.relative_to(vault_root)}")
            hits += 1
            continue
        try:
            lock.unlink(missing_ok=True)
            hits += 1
        except OSError as exc:
            print(f"vault_wipe_lock_err {lock.name}: {exc}")
    return hits


async def requeue(
    n: int,
    *,
    dry_run: bool = False,
    purge_all: bool = False,
) -> None:
    """
    Esegue anteprima o requeue completo.

    Con ``dry_run=True``: lista candidati Miniflux, path vault e id DB che
    verrebbero cancellati; **nessuna** scrittura (Miniflux status, unlink, DELETE).
    Con ``dry_run=False``: applica unread → vault → cooldown → outbox/articles.
    Con ``purge_all=True``: wipe vault completo + DELETE di tutte le ``articles``.
    """
    if n < 1 or n > 500:
        raise SystemExit(f"N must be 1..500, got {n}")

    async with httpx.AsyncClient(timeout=60.0) as http:
        mf = MinifluxClient(http_client=http)
        entries = await _fetch_read_entries(mf, n)
        ids = [int(e["id"]) for e in entries if e.get("id") is not None]
        urls = [str(e.get("url") or "") for e in entries if e.get("url")]
        print(f"dry_run={dry_run} purge_all={purge_all} candidates={len(ids)}")
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
            # Miniflux PUT accetta batch; spezza se molto grandi.
            chunk = 100
            for i in range(0, len(ids), chunk):
                await mf._request(
                    "PUT",
                    "/v1/entries",
                    json_body={"entry_ids": ids[i : i + chunk], "status": "unread"},
                    expect_json=False,
                )
            unread = await mf._request(
                "GET", "/v1/entries", params={"status": "unread", "limit": 1}
            )
            print(f"unread_total={(unread or {}).get('total')}")

    vault_root = Path(OBSIDIAN_VAULT_PATH)
    vault_hits = 0
    if purge_all:
        vault_hits = _wipe_vault_markdown(vault_root, dry_run=dry_run)
    else:
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

            if purge_all:
                total_articles = await conn.fetchval("SELECT COUNT(*) FROM articles")
                db_hits = int(total_articles or 0)
                if dry_run:
                    print(f"  would_purge_all_articles={db_hits}")
                else:
                    # CASCADE: outbox, article_companies, article_tags.
                    await conn.execute("DELETE FROM articles")
                    print(f"purged_all_articles={db_hits}")
            else:
                for url in urls:
                    rows = await conn.fetch(
                        "SELECT id FROM articles WHERE source_url = $1", url
                    )
                    for row in rows:
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
    """CLI: ``N`` opzionale (default 20), ``--dry-run``, ``--purge-all``."""
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
    parser.add_argument(
        "--purge-all",
        action="store_true",
        help="Wipe all vault markdown + DELETE all articles (prova da zero)",
    )
    args = parser.parse_args(argv)
    asyncio.run(requeue(args.n, dry_run=args.dry_run, purge_all=args.purge_all))


if __name__ == "__main__":
    main(sys.argv[1:])
