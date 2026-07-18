#!/usr/bin/env python3
"""Ops/dev: inserisce articoli fake US senza LLM, con NOTIFY SSE.

Uso (dentro ``radar-worker``, vault + DB montati)::

    # Smoke (1 articolo Infrastrutture)
    docker compose exec -T radar-worker \\
      python -m app.scripts.seed_sse_soft_refresh --count 1

    # 30 articoli: 10 Nucleare, 10 Infrastrutture, pausa 5s, 10 Ambiente
    docker compose exec -T radar-worker \\
      python -m app.scripts.seed_sse_soft_refresh --batches \\
      --per-category 10 --delay 2 --pause-before Ambiente --pause-seconds 5

Scrive DB + vault via commit/outbox e emette ``NOTIFY radar_article_processed``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from datetime import date

from app.classification.validator import GeopoliticalArticleSchema
from app.commit.db_commit import commit_article_to_db
from app.commit.factory import generate_markdown_content
from app.commit.outbox import process_outbox_row
from app.commit.router import get_article_file_path, initialize_vault_directories
from app.core.config import DATABASE_URL, OBSIDIAN_VAULT_PATH
from app.core.database import init_pool

# Batch sequenziale di default (--batches).
_BATCH_CATEGORIES: tuple[str, ...] = ("Nucleare", "Infrastrutture", "Ambiente")

# Centroide contiguous US (stabile per pin day-view / hub).
_US_MAINLAND_LAT = 39.8283
_US_MAINLAND_LON = -98.5795

_ENTITIES: dict[str, str] = {
    "Infrastrutture": "Rete elettrica,Trasporti",
    "Nucleare": "Impianto nucleare,Ciclo combustibile",
    "Ambiente": "Clima,Ecosistema",
    "Geopolitica": "Nessuno",
    "Spazio": "Satellite,Lancio orbitale",
}


def _build_article(
    index: int,
    *,
    run_id: str,
    today: str,
    category: str,
) -> GeopoliticalArticleSchema:
    """Articolo sintetico US con categoria esplicita."""
    lat = _US_MAINLAND_LAT + (index * 0.0001)
    lon = _US_MAINLAND_LON + (index * 0.0001)
    title = f"SSE probe US {category} #{index} ({run_id[:8]})"
    if len(title) > 120:
        title = title[:120]
    return GeopoliticalArticleSchema(
        title=title,
        summary=(
            "Articolo sintetico per prova soft-refresh SSE senza LLM. "
            f"Nazione Stati Uniti, categoria {category}."
        ),
        published_at=today,
        source_url=f"https://example.test/sse-probe/{run_id}/{index}",
        country_code="US",
        latitude=lat,
        longitude=lon,
        companies_involved="Nessuno",
        tags=f"{category},SSE-probe,Test",
        primary_category=category,  # type: ignore[arg-type]
        sentiment="Neutrale",
        relevance_level=3,
        infrastructural_entities=_ENTITIES.get(category, "Nessuno"),
    )


async def _insert_one(
    pool: object,
    article: GeopoliticalArticleSchema,
    *,
    index: int,
    total: int,
) -> int:
    md = generate_markdown_content(article)
    path = get_article_file_path(article, vault_path=OBSIDIAN_VAULT_PATH)

    async with pool.acquire() as conn:  # type: ignore[attr-defined]
        article_id = await commit_article_to_db(
            conn,
            article,
            "SSE Soft-Refresh Probe",
            outbox_target_path=path,
            outbox_payload=md,
            miniflux_entry_id=None,
        )
        notify_payload = json.dumps(
            {
                "article_id": article_id,
                "country_code": article.country_code,
                "primary_category": article.primary_category,
                "published_at": article.published_at,
            },
            separators=(",", ":"),
        )
        await conn.execute(
            "SELECT pg_notify($1, $2)",
            "radar_article_processed",
            notify_payload,
        )
        outbox_row = await conn.fetchrow(
            """
            SELECT id, article_id, target_path, payload, payload_checksum,
                   attempt_count, miniflux_entry_id, status
            FROM article_outbox
            WHERE article_id = $1
              AND status IN ('pending', 'failed')
            """,
            article_id,
        )

    vault_ok = False
    if outbox_row is not None:
        vault_ok = await process_outbox_row(pool, outbox_row, None)  # type: ignore[arg-type]

    print(
        f"[{index}/{total}] cat={article.primary_category} "
        f"article_id={article_id} vault_ok={vault_ok} title={article.title!r}"
    )
    return article_id


async def seed_articles(
    *,
    count: int,
    delay_seconds: float,
    batches: bool,
    per_category: int,
    pause_before: str | None,
    pause_seconds: float,
) -> int:
    """Inserisce articoli con delay; in modalità batches esegue N per categoria in ordine."""
    if delay_seconds < 0 or delay_seconds > 60:
        raise SystemExit(f"--delay must be 0..60, got {delay_seconds}")
    if pause_seconds < 0 or pause_seconds > 120:
        raise SystemExit(f"--pause-seconds must be 0..120, got {pause_seconds}")

    today = date.today().isoformat()
    run_id = uuid.uuid4().hex
    initialize_vault_directories(OBSIDIAN_VAULT_PATH)
    pool = await init_pool(DATABASE_URL)
    inserted = 0

    if batches:
        if per_category < 1 or per_category > 50:
            raise SystemExit(f"--per-category must be 1..50, got {per_category}")
        plan: list[tuple[str, int]] = [(c, per_category) for c in _BATCH_CATEGORIES]
        total = sum(n for _, n in plan)
    else:
        if count < 1 or count > 50:
            raise SystemExit(f"--count must be 1..50, got {count}")
        # Compat: rotazione sulle tre categorie batch.
        plan = []
        for i in range(1, count + 1):
            cat = _BATCH_CATEGORIES[(i - 1) % len(_BATCH_CATEGORIES)]
            plan.append((cat, 1))
        # Collassa in sequenza di singoli — gestito sotto come lista flat
        total = count

    try:
        print(
            f"seed_sse_soft_refresh run_id={run_id} batches={batches} "
            f"delay={delay_seconds}s pause_before={pause_before!r} "
            f"pause_seconds={pause_seconds} country=US date={today}"
        )
        if batches:
            print(f"plan={plan} total={total}")

        index = 0
        if batches:
            for category, n in plan:
                if pause_before and category == pause_before and pause_seconds > 0:
                    print(
                        f"=== pausa {pause_seconds}s prima del batch {category} "
                        f"(verifica UI) ===",
                        flush=True,
                    )
                    await asyncio.sleep(pause_seconds)
                    print(f"=== avvio batch {category} ({n} articoli) ===", flush=True)

                for _ in range(n):
                    index += 1
                    article = _build_article(
                        index, run_id=run_id, today=today, category=category
                    )
                    await _insert_one(pool, article, index=index, total=total)
                    inserted += 1
                    if index < total and delay_seconds > 0:
                        await asyncio.sleep(delay_seconds)
        else:
            for i in range(1, count + 1):
                category = _BATCH_CATEGORIES[(i - 1) % len(_BATCH_CATEGORIES)]
                article = _build_article(i, run_id=run_id, today=today, category=category)
                await _insert_one(pool, article, index=i, total=count)
                inserted += 1
                if i < count and delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
    finally:
        await pool.close()

    print(f"done inserted={inserted} run_id={run_id}")
    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed US articles + SSE NOTIFY (no LLM)."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Numero articoli (modalità rotazione; ignorato con --batches).",
    )
    parser.add_argument(
        "--batches",
        action="store_true",
        help="Batch sequenziali: Nucleare, Infrastrutture, Ambiente.",
    )
    parser.add_argument(
        "--per-category",
        type=int,
        default=10,
        help="Articoli per categoria in modalità --batches (default 10).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Secondi tra un articolo e il successivo (default 2).",
    )
    parser.add_argument(
        "--pause-before",
        type=str,
        default="",
        help="Categoria prima della quale attendere (es. Ambiente).",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=5.0,
        help="Secondi di pausa prima di --pause-before (default 5).",
    )
    args = parser.parse_args(argv)
    t0 = time.monotonic()
    expected = args.per_category * len(_BATCH_CATEGORIES) if args.batches else args.count
    inserted = asyncio.run(
        seed_articles(
            count=args.count,
            delay_seconds=args.delay,
            batches=args.batches,
            per_category=args.per_category,
            pause_before=args.pause_before.strip() or None,
            pause_seconds=args.pause_seconds,
        )
    )
    elapsed = time.monotonic() - t0
    print(f"elapsed_s={elapsed:.1f} inserted={inserted}")
    return 0 if inserted == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
