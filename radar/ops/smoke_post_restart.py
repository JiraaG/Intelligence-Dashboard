#!/usr/bin/env python3
"""Post-restart regression smoke: health, core APIs, FONTI, article freshness."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

BASE = os.environ.get("SMOKE_BASE", "http://localhost:8000")
TODAY = date.today().isoformat()


def req(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
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
            payload = {"detail": raw.decode("utf-8", errors="replace")[:400]}
        return int(exc.code), payload


def main() -> None:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: object) -> None:
        checks.append({"name": name, "pass": ok, "detail": detail})

    code, live = req("GET", "/health/live")
    add("health/live", code == 200, {"code": code, "body": live})

    code, ready = req("GET", "/health/ready")
    add(
        "health/ready",
        code in (200, 503),
        {"code": code, "body": ready if isinstance(ready, dict) else ready},
    )

    code, summary = req("GET", f"/api/map-summary?date={TODAY}")
    ok = code == 200 and isinstance(summary, list)
    add(
        "map-summary today",
        ok,
        {"code": code, "rows": len(summary) if isinstance(summary, list) else None},
    )

    code, rel = req("GET", f"/api/map-relations?date={TODAY}")
    add(
        "map-relations today",
        code == 200 and isinstance(rel, list),
        {"code": code, "rows": len(rel) if isinstance(rel, list) else None},
    )

    code, saved = req("GET", "/api/saved-summary")
    add(
        "saved-summary",
        code == 200 and isinstance(saved, list),
        {"code": code, "rows": len(saved) if isinstance(saved, list) else None},
    )

    code, st = req("GET", "/api/metrics/status")
    add(
        "metrics/status",
        code == 200 and isinstance(st, dict) and "level" in st,
        {
            "code": code,
            "level": st.get("level") if isinstance(st, dict) else None,
            "models": len(st.get("models", [])) if isinstance(st, dict) else None,
        },
    )

    code, cost = req("GET", f"/api/metrics/summary?from={TODAY}&to={TODAY}")
    add(
        "metrics/summary today",
        code == 200 and isinstance(cost, dict),
        {
            "code": code,
            "articles": cost.get("total_articles") if isinstance(cost, dict) else None,
            "cost": (cost.get("llm") or {}).get("total_estimated_cost_usd")
            if isinstance(cost, dict)
            else None,
        },
    )

    code, byf = req(
        "GET",
        f"/api/metrics/by-feed?from={TODAY}&to={TODAY}&date_field=published_at",
    )
    add(
        "metrics/by-feed published_at",
        code == 200 and isinstance(byf, dict) and "items" in byf,
        {
            "code": code,
            "items": len(byf.get("items", [])) if isinstance(byf, dict) else None,
        },
    )

    code, feeds = req("GET", "/api/feeds")
    add(
        "GET /api/feeds",
        code == 200 and isinstance(feeds, dict) and "groups" in feeds,
        {
            "code": code,
            "active": feeds.get("active_count") if isinstance(feeds, dict) else None,
            "total": feeds.get("total_count") if isinstance(feeds, dict) else None,
            "errors": feeds.get("error_count") if isinstance(feeds, dict) else None,
        },
    )

    # Pick a known day with articles if today map is empty
    probe_date = TODAY
    if isinstance(summary, list) and len(summary) == 0:
        probe_date = "2026-07-22"
        code, summary2 = req("GET", f"/api/map-summary?date={probe_date}")
        add(
            f"map-summary {probe_date}",
            code == 200 and isinstance(summary2, list) and len(summary2) > 0,
            {"code": code, "rows": len(summary2) if isinstance(summary2, list) else None},
        )
        if isinstance(summary2, list) and summary2:
            cc = summary2[0].get("country_code")
            code, page = req(
                "GET",
                f"/api/articles?date={probe_date}&country={cc}&limit=5",
            )
            ok = (
                code == 200
                and isinstance(page, dict)
                and isinstance(page.get("items"), list)
                and "total" in page
            )
            add(
                "articles envelope",
                ok,
                {
                    "code": code,
                    "country": cc,
                    "items": len(page.get("items", [])) if isinstance(page, dict) else None,
                    "total": page.get("total") if isinstance(page, dict) else None,
                },
            )
    elif isinstance(summary, list) and summary:
        cc = summary[0].get("country_code")
        code, page = req("GET", f"/api/articles?date={TODAY}&country={cc}&limit=5")
        ok = code == 200 and isinstance(page, dict) and "items" in page
        add(
            "articles envelope today",
            ok,
            {
                "code": code,
                "country": cc,
                "items": len(page.get("items", [])) if isinstance(page, dict) else None,
                "total": page.get("total") if isinstance(page, dict) else None,
            },
        )

    print(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(), "checks": checks}, indent=2))
    if not all(c["pass"] for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
