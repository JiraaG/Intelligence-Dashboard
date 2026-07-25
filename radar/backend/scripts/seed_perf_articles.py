#!/usr/bin/env python3
"""
Synthetic performance seed: ~10_000 articles for ONE published_at date.

Usage:
  cd radar/backend
  set DATABASE_URL=postgresql://radar:…@localhost:5432/radar   # Windows
  # export DATABASE_URL=…                                      # Unix
  python scripts/seed_perf_articles.py
  python scripts/seed_perf_articles.py --date 2026-07-15
  python scripts/seed_perf_articles.py --date 2026-07-15 --count 10000

Idempotent for a given date: deletes all articles with that published_at first
(CASCADE clears junction rows), then inserts a fresh synthetic batch.

Does NOT touch the Obsidian vault or Miniflux.
Requires DATABASE_URL (or the same defaults as the API via app.core.config).
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from datetime import date, datetime
from pathlib import Path

# Allow `python scripts/seed_perf_articles.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg

from app.core.config import DATABASE_URL

from app.classification.validator import PRIMARY_CATEGORIES

CATEGORIES = PRIMARY_CATEGORIES

SENTIMENTS = ("Positivo", "Neutrale", "Negativo")

# Real ISO-ish seeds plus synthetic AA… codes → ≥100 distinct CHAR(2).
_REAL_CODES = (
    "IT", "DE", "FR", "ES", "GB", "US", "CN", "JP", "KR", "IN",
    "BR", "AU", "CA", "MX", "RU", "TR", "SA", "AE", "EG", "ZA",
    "NG", "KE", "AR", "CL", "CO", "PE", "PL", "NL", "BE", "SE",
    "NO", "FI", "DK", "PT", "GR", "IE", "AT", "CH", "CZ", "RO",
    "HU", "UA", "IL", "IR", "IQ", "PK", "BD", "TH", "VN", "ID",
    "MY", "PH", "SG", "NZ", "XX",
)


def _synthetic_country_codes(min_count: int = 100) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for code in _REAL_CODES:
        if code not in seen:
            seen.add(code)
            codes.append(code)
    # AA, AB, … ZZ (skip already used)
    for first in range(ord("A"), ord("Z") + 1):
        for second in range(ord("A"), ord("Z") + 1):
            code = chr(first) + chr(second)
            if code in seen:
                continue
            seen.add(code)
            codes.append(code)
            if len(codes) >= min_count:
                return codes
    return codes


COUNTRY_CODES = _synthetic_country_codes(100)


def _finite_lat_lon(index: int) -> tuple[float, float]:
    """Deterministic finite coords in valid ranges (some near poles/edges)."""
    lat = -85.0 + (index % 171) * 1.0  # [-85, 85]
    lon = -175.0 + ((index * 7) % 351) * 1.0  # [-175, 175]
    # Keep strictly finite (no NaN/Inf)
    if not math.isfinite(lat) or not math.isfinite(lon):
        return 0.0, 0.0
    return lat, lon


async def seed(pub_date: date, count: int) -> None:
    if count < 1:
        raise SystemExit("--count must be >= 1")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        deleted = await conn.execute(
            "DELETE FROM articles WHERE published_at = $1",
            pub_date,
        )
        print(f"Deleted prior rows for {pub_date}: {deleted}")

        batch_size = 500
        inserted = 0
        while inserted < count:
            chunk: list[tuple] = []
            end = min(inserted + batch_size, count)
            for i in range(inserted, end):
                lat, lon = _finite_lat_lon(i)
                country = COUNTRY_CODES[i % len(COUNTRY_CODES)]
                category = CATEGORIES[i % len(CATEGORIES)]
                sentiment = SENTIMENTS[i % len(SENTIMENTS)]
                relevance = (i % 5) + 1
                is_read = (i % 4) == 0
                chunk.append(
                    (
                        f"[perf-seed] Article {i} {country} {category}",
                        f"Synthetic summary for perf seed row {i}.",
                        pub_date,
                        f"https://perf-seed.local/{pub_date.isoformat()}/{i}",
                        country,
                        lat,
                        lon,
                        category,
                        sentiment,
                        relevance,
                        is_read,
                        [],
                        "perf-seed",
                    )
                )

            await conn.executemany(
                """
                INSERT INTO articles (
                    title, summary, published_at, source_url,
                    country_code, latitude, longitude, primary_category,
                    sentiment, relevance_level, is_read,
                    infrastructural_entities, feed_title
                ) VALUES (
                    $1, $2, $3, $4,
                    $5, $6, $7, $8,
                    $9, $10, $11,
                    $12, $13
                )
                """,
                chunk,
            )
            inserted = end
            print(f"Inserted {inserted}/{count}")

        distinct_countries = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT country_code)
            FROM articles
            WHERE published_at = $1
            """,
            pub_date,
        )
        distinct_cats = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT primary_category)
            FROM articles
            WHERE published_at = $1
            """,
            pub_date,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM articles WHERE published_at = $1",
            pub_date,
        )
        print(
            f"Done: total={total}, countries={distinct_countries}, "
            f"categories={distinct_cats} (codes available={len(COUNTRY_CODES)})"
        )
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed ~10k synthetic articles for one published_at date (DB only)."
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="published_at date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10_000,
        help="Number of articles to insert (default: 10000)",
    )
    args = parser.parse_args()
    try:
        pub_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid --date {args.date!r}: use YYYY-MM-DD") from exc

    print(f"Seeding {args.count} articles for {pub_date} via DATABASE_URL")
    asyncio.run(seed(pub_date, args.count))


if __name__ == "__main__":
    main()
