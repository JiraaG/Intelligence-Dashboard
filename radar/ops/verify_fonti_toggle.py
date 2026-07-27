#!/usr/bin/env python3
"""Verify FONTI toggle: API count + Miniflux disabled flag round-trip."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("SMOKE_BASE", "http://localhost:8000")
MF = os.environ.get("MINIFLUX_API_URL", "http://radar-miniflux:8080").rstrip("/")
KEY = os.environ.get("MINIFLUX_API_KEY", "")


def http_json(
    method: str, url: str, body: dict | None = None, headers: dict | None = None
) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    hdrs = {"Accept": "application/json"}
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return int(resp.status), (json.loads(raw.decode()) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode()) if raw else {}
        except Exception:
            payload = {"detail": raw.decode("utf-8", errors="replace")[:300]}
        return int(exc.code), payload


def main() -> None:
    code, feeds = http_json("GET", f"{BASE}/api/feeds")
    assert code == 200 and isinstance(feeds, dict), feeds
    before_active = int(feeds["active_count"])
    before_total = int(feeds["total_count"])
    target = None
    for g in feeds.get("groups", []):
        for f in g.get("feeds", []):
            if f.get("id") is not None and not f.get("disabled"):
                target = f
                break
        if target:
            break
    assert target is not None, "no active feed to toggle"
    feed_id = int(target["id"])
    title = target.get("title")

    code, toggled = http_json(
        "PATCH", f"{BASE}/api/feeds/{feed_id}/toggle", {"disabled": True}
    )
    assert code == 200 and toggled.get("disabled") is True, toggled

    code, after = http_json("GET", f"{BASE}/api/feeds")
    assert code == 200
    after_active = int(after["active_count"])

    # Direct Miniflux truth
    mf_headers = {"X-Auth-Token": KEY} if KEY else {}
    code_mf, live = http_json("GET", f"{MF}/v1/feeds/{feed_id}", headers=mf_headers)
    mf_disabled = live.get("disabled") if isinstance(live, dict) else None

    # Restore
    code_r, restored = http_json(
        "PATCH", f"{BASE}/api/feeds/{feed_id}/toggle", {"disabled": False}
    )
    code_f, final = http_json("GET", f"{BASE}/api/feeds")

    report = {
        "feed_id": feed_id,
        "title": title,
        "before": f"{before_active}/{before_total}",
        "after_disable_api": f"{after_active}/{after['total_count']}",
        "count_decremented": after_active == before_active - 1,
        "miniflux_get_status": code_mf,
        "miniflux_disabled_after_toggle": mf_disabled,
        "miniflux_confirms_disabled": mf_disabled is True,
        "restored_ok": code_r == 200 and restored.get("disabled") is False,
        "final_count": f"{final.get('active_count')}/{final.get('total_count')}"
        if isinstance(final, dict)
        else None,
        "pipeline_note": (
            "Miniflux non fa fetch di feed disabled: non crea nuovi unread per quell'URL. "
            "Il worker Radar elabora solo unread Miniflux → niente nuovi articoli da quel feed. "
            "Unread già in coda prima del disable possono ancora essere processati."
        ),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not (
        report["count_decremented"]
        and report["miniflux_confirms_disabled"]
        and report["restored_ok"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
