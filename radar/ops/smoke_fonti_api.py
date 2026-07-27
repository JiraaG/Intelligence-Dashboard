#!/usr/bin/env python3
"""Smoke FONTI API inside radar-backend container (no host curl)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date

BASE = os.environ.get("SMOKE_BASE", "http://localhost:8000")
TODAY = date.today().isoformat()


def req(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    hdrs = {"Accept": "application/json"}
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    request = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read()
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            return int(resp.status), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {"detail": str(exc)}
        except Exception:
            payload = {"detail": raw.decode("utf-8", errors="replace")[:300]}
        return int(exc.code), payload


def main() -> None:
    results: list[tuple[str, bool, str]] = []

    code, live = req("GET", "/health/live")
    results.append(("health/live", code == 200, f"{code} {live}"))

    code, by_pub = req(
        "GET",
        f"/api/metrics/by-feed?from={TODAY}&to={TODAY}&date_field=published_at",
    )
    ok = code == 200 and isinstance(by_pub, dict) and "items" in by_pub
    results.append(
        (
            "by-feed published_at",
            ok,
            f"{code} items={len(by_pub.get('items', [])) if isinstance(by_pub, dict) else '?'}",
        )
    )

    code, by_def = req("GET", f"/api/metrics/by-feed?from={TODAY}&to={TODAY}")
    ok = code == 200 and isinstance(by_def, dict)
    results.append(("by-feed default created_at", ok, f"{code}"))

    code, bad = req("GET", "/api/metrics/by-feed?date_field=nope")
    results.append(("by-feed bad date_field→400", code == 400, f"{code}"))

    code, feeds = req("GET", "/api/feeds")
    ok = code == 200 and isinstance(feeds, dict) and "groups" in feeds
    results.append(
        (
            "GET /api/feeds",
            ok,
            f"{code} active={feeds.get('active_count') if isinstance(feeds, dict) else '?'} "
            f"total={feeds.get('total_count') if isinstance(feeds, dict) else '?'}",
        )
    )

    feed_id = None
    if isinstance(feeds, dict):
        for g in feeds.get("groups", []):
            for f in g.get("feeds", []):
                if f.get("id") is not None:
                    feed_id = int(f["id"])
                    break
            if feed_id is not None:
                break

    if feed_id is None:
        results.append(("PATCH toggle", False, "no live feed id"))
    else:
        code, toggled = req("PATCH", f"/api/feeds/{feed_id}/toggle", {"disabled": True})
        ok = code == 200 and isinstance(toggled, dict) and toggled.get("disabled") is True
        results.append(("PATCH disable (no token)", ok, f"{code} {toggled}"))
        code, restored = req("PATCH", f"/api/feeds/{feed_id}/toggle", {"disabled": False})
        ok = code == 200 and isinstance(restored, dict) and restored.get("disabled") is False
        results.append(("PATCH re-enable", ok, f"{code} {restored}"))

    print(json.dumps({"date": TODAY, "results": [{"name": n, "pass": p, "detail": d} for n, p, d in results]}, indent=2))
    if not all(p for _, p, _ in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
