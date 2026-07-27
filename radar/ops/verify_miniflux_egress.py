#!/usr/bin/env python3
"""Verify Miniflux egress DNS + clear sticky parsing errors via refresh.

Run inside radar-backend (has MINIFLUX_* env + radar-data network)::

    docker compose cp ops/verify_miniflux_egress.py radar-backend:/tmp/verify_miniflux_egress.py
    docker compose exec -T radar-backend python /tmp/verify_miniflux_egress.py

Env:
  MINIFLUX_API_URL / MINIFLUX_API_KEY — required
  VERIFY_SETTLE_SECONDS — pause after each batch / final wait (default 3; final=15)
  VERIFY_MAX_ERRORS — fail if error_count > N (default 0)
  VERIFY_DNS_HOST — canary host for pre-check (default example.com)
  VERIFY_MODE — ``per_feed`` (default, reliable) | ``all`` (PUT /v1/feeds/refresh)
  SKIP_REFRESH=1 — only report counts, no PUT refresh
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

MF = os.environ.get("MINIFLUX_API_URL", "http://radar-miniflux:8080").rstrip("/")
KEY = os.environ.get("MINIFLUX_API_KEY", "")
SETTLE = int(os.environ.get("VERIFY_SETTLE_SECONDS", "3"))
FINAL_SETTLE = int(os.environ.get("VERIFY_FINAL_SETTLE_SECONDS", "15"))
MAX_ERRORS = int(os.environ.get("VERIFY_MAX_ERRORS", "0"))
DNS_HOST = os.environ.get("VERIFY_DNS_HOST", "example.com").strip() or "example.com"
MODE = os.environ.get("VERIFY_MODE", "per_feed").strip().lower() or "per_feed"
SKIP_REFRESH = os.environ.get("SKIP_REFRESH", "").strip() in {"1", "true", "yes"}
API_FEEDS = os.environ.get("SMOKE_BASE", "http://localhost:8000").rstrip("/") + "/api/feeds"


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
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return int(resp.status), (json.loads(raw.decode()) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode()) if raw else {}
        except Exception:
            payload = {"detail": raw.decode("utf-8", errors="replace")[:300]}
        return int(exc.code), payload


def count_mf_errors(feeds: list) -> int:
    return sum(1 for f in feeds if int(f.get("parsing_error_count") or 0) > 0)


def main() -> int:
    if not KEY:
        print("FAIL: MINIFLUX_API_KEY missing", file=sys.stderr)
        return 2

    print(f"dns_canary={DNS_HOST} mode={MODE}")
    try:
        socket.getaddrinfo(DNS_HOST, 443)
        print(f"PASS dns resolve {DNS_HOST}")
    except OSError as exc:
        print(f"FAIL dns resolve {DNS_HOST}: {exc}", file=sys.stderr)
        return 1

    headers = {"X-Auth-Token": KEY}
    code, feeds = http_json("GET", f"{MF}/v1/feeds", headers=headers)
    if code != 200 or not isinstance(feeds, list):
        print(f"FAIL GET /v1/feeds status={code} body={feeds!r}", file=sys.stderr)
        return 1
    before = count_mf_errors(feeds)
    print(f"before_errors={before} total_feeds={len(feeds)}")

    if not SKIP_REFRESH:
        if MODE == "all":
            print("PUT /v1/feeds/refresh ...")
            rcode, _ = http_json("PUT", f"{MF}/v1/feeds/refresh", headers=headers)
            if rcode not in {200, 204}:
                print(f"FAIL refresh status={rcode}", file=sys.stderr)
                return 1
            wait = max(SETTLE, 60)
            print(f"settle {wait}s (bulk) ...")
            time.sleep(wait)
        else:
            # Per-feed refresh is reliable: bulk refresh can leave sticky ERR if
            # scheduler hasn't finished within a short settle window.
            for i, feed in enumerate(feeds, start=1):
                fid = feed.get("id")
                if fid is None:
                    continue
                rcode, _ = http_json(
                    "PUT", f"{MF}/v1/feeds/{int(fid)}/refresh", headers=headers
                )
                title = feed.get("title") or fid
                if rcode not in {200, 204}:
                    print(f"WARN refresh id={fid} title={title!r} status={rcode}")
                else:
                    print(f"refreshed {i}/{len(feeds)} id={fid} {title}")
                if SETTLE > 0:
                    time.sleep(SETTLE)
            if FINAL_SETTLE > 0:
                print(f"final settle {FINAL_SETTLE}s ...")
                time.sleep(FINAL_SETTLE)

        code, feeds = http_json("GET", f"{MF}/v1/feeds", headers=headers)
        if code != 200 or not isinstance(feeds, list):
            print(f"FAIL re-GET /v1/feeds status={code}", file=sys.stderr)
            return 1

    after = count_mf_errors(feeds)
    print(f"after_errors={after} total_feeds={len(feeds)}")

    acode, catalog = http_json("GET", API_FEEDS)
    if acode == 200 and isinstance(catalog, dict):
        print(
            "api_feeds",
            {
                "active_count": catalog.get("active_count"),
                "total_count": catalog.get("total_count"),
                "error_count": catalog.get("error_count"),
            },
        )
        api_errors = int(catalog.get("error_count") or 0)
    else:
        print(f"WARN GET /api/feeds status={acode} (using Miniflux count only)")
        api_errors = after

    still = [
        {
            "title": f.get("title"),
            "parsing_error_count": f.get("parsing_error_count"),
            "msg": (f.get("parsing_error_message") or "")[:160],
        }
        for f in feeds
        if int(f.get("parsing_error_count") or 0) > 0
    ]
    if still:
        print("remaining_errors_sample:")
        for row in still[:8]:
            print(" ", row)

    if after > MAX_ERRORS or api_errors > MAX_ERRORS:
        print(
            f"FAIL error_count after={after} api={api_errors} max_allowed={MAX_ERRORS}",
            file=sys.stderr,
        )
        return 1

    print(f"PASS error_count={after} (max={MAX_ERRORS})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
