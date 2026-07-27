#!/usr/bin/env python3
"""Extra FONTI smoke: richest published_at day + by-feed parity."""
from __future__ import annotations

import asyncio
import json
import urllib.request

import asyncpg

from app.core.config import DATABASE_URL

BASE = "http://localhost:8000"


async def main() -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch(
        """
        SELECT published_at::date AS d, COUNT(*)::INT AS n
        FROM articles
        WHERE published_at IS NOT NULL
        GROUP BY 1
        ORDER BY n DESC
        LIMIT 5
        """
    )
    print("top_published_at", [{"d": r["d"].isoformat(), "n": r["n"]} for r in rows])
    if not rows:
        print("NO_ARTICLES")
        await conn.close()
        return
    d = rows[0]["d"].isoformat()
    await conn.close()

    for field in ("published_at", "created_at"):
        url = f"{BASE}/api/metrics/by-feed?from={d}&to={d}&date_field={field}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items") or []
        print(
            json.dumps(
                {
                    "date": d,
                    "date_field": field,
                    "items": len(items),
                    "article_sum": sum(int(i.get("article_count") or 0) for i in items),
                    "top_titles": [i.get("feed_title") for i in items[:3]],
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
