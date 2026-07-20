#!/usr/bin/env python3
"""Sync Miniflux feeds from config/miniflux-feeds.seed.json (+ OPML export helper).

Run via ops/export-miniflux-feeds.sh or ops/import-miniflux-feeds.sh
(Git Bash / WSL / Linux). Uses stdlib only (urllib).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _request(
    method: str,
    base_url: str,
    path: str,
    token: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, bytes]:
    url = base_url.rstrip("/") + path
    headers = {"X-Auth-Token": token, "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return int(exc.code), body


def _json_body(status: int, body: bytes, expect: set[int]) -> Any:
    if status not in expect:
        snippet = body.decode("utf-8", errors="replace")[:500]
        _die(f"HTTP {status}: {snippet}")
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def load_seed(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("feeds"), list) or not data["feeds"]:
        _die(f"seed has no feeds: {path}")
    return data


def write_opml(seed: dict[str, Any], out: Path) -> None:
    """Write OPML 2.0 grouped by category (portable; scraper rules live in seed JSON)."""
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feed in seed["feeds"]:
        by_cat[str(feed["category"])].append(feed)

    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "Radar Miniflux feeds"
    body = ET.SubElement(opml, "body")
    for category, feeds in by_cat.items():
        cat_el = ET.SubElement(body, "outline", text=category, title=category)
        for feed in feeds:
            ET.SubElement(
                cat_el,
                "outline",
                type="rss",
                text=str(feed["title"]),
                title=str(feed["title"]),
                xmlUrl=str(feed["feed_url"]),
            )
    tree = ET.ElementTree(opml)
    ET.indent(tree, space="  ")
    out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out, encoding="utf-8", xml_declaration=True)
    print(f"Wrote OPML ({len(seed['feeds'])} feeds): {out}")


def ensure_categories(
    base_url: str, token: str, titles: set[str]
) -> dict[str, int]:
    status, body = _request("GET", base_url, "/v1/categories", token)
    cats = _json_body(status, body, {200})
    by_title = {c["title"]: int(c["id"]) for c in cats}
    for title in sorted(titles):
        if title in by_title:
            continue
        payload = json.dumps({"title": title}).encode("utf-8")
        status, body = _request(
            "POST",
            base_url,
            "/v1/categories",
            token,
            data=payload,
            content_type="application/json",
        )
        created = _json_body(status, body, {201})
        by_title[title] = int(created["id"])
        print(f"  + category {title!r} id={by_title[title]}")
    return by_title


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/")


def existing_feeds(base_url: str, token: str) -> dict[str, dict[str, Any]]:
    status, body = _request("GET", base_url, "/v1/feeds", token)
    feeds = _json_body(status, body, {200})
    return {_norm_url(str(f["feed_url"])): f for f in feeds}


def find_feed(
    current: dict[str, dict[str, Any]], seed_url: str
) -> dict[str, Any] | None:
    key = _norm_url(seed_url)
    if key in current:
        return current[key]
    # The Guardian often canonicalizes to /uk/<section>/rss.
    alt = key.replace(
        "://www.theguardian.com/", "://www.theguardian.com/uk/", 1
    )
    if alt != key and alt in current:
        return current[alt]
    for stored, feed in current.items():
        if stored == key or stored.endswith(key) or key.endswith(stored):
            return feed
    return None


def _update_feed(
    base_url: str,
    token: str,
    feed_id: int,
    *,
    title: str,
    category_id: int,
    scraper: str,
    crawler: bool,
    user_agent: str,
) -> None:
    payload = {
        "title": title,
        "category_id": category_id,
        "scraper_rules": scraper,
        "crawler": crawler,
        "user_agent": user_agent,
    }
    status, body = _request(
        "PUT",
        base_url,
        f"/v1/feeds/{feed_id}",
        token,
        data=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
    )
    _json_body(status, body, {201, 200})


def _is_duplicate_create(status: int, body: bytes) -> bool:
    if status == 409:
        return True
    if status != 500:
        return False
    text = body.decode("utf-8", errors="replace").lower()
    return "duplicate" in text or "23505" in text or "unique constraint" in text


def import_seed(base_url: str, token: str, seed: dict[str, Any]) -> None:
    default_ua = str(seed.get("user_agent") or "")
    default_crawler = bool(seed.get("crawler_default", True))
    categories = ensure_categories(
        base_url, token, {str(f["category"]) for f in seed["feeds"]}
    )
    current = existing_feeds(base_url, token)
    created = updated = skipped = 0
    for spec in seed["feeds"]:
        url = str(spec["feed_url"])
        title = str(spec["title"])
        category = str(spec["category"])
        category_id = categories[category]
        scraper = str(spec.get("scraper_rules") or "")
        crawler = bool(spec.get("crawler", default_crawler))
        user_agent = str(spec.get("user_agent") or default_ua)
        existing = find_feed(current, url)
        if existing is not None:
            _update_feed(
                base_url,
                token,
                int(existing["id"]),
                title=title,
                category_id=category_id,
                scraper=scraper,
                crawler=crawler,
                user_agent=user_agent,
            )
            updated += 1
            print(f"  ~ update {title}", flush=True)
            continue

        payload = {
            "feed_url": url,
            "category_id": category_id,
            "crawler": crawler,
            "user_agent": user_agent,
            "scraper_rules": scraper,
        }
        status, body = _request(
            "POST",
            base_url,
            "/v1/feeds",
            token,
            data=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )
        # Race / redirect: Miniflux may commit then 500 on duplicate.
        if _is_duplicate_create(status, body) or status != 201:
            current = existing_feeds(base_url, token)
            existing = find_feed(current, url)
            if existing is not None:
                _update_feed(
                    base_url,
                    token,
                    int(existing["id"]),
                    title=title,
                    category_id=category_id,
                    scraper=scraper,
                    crawler=crawler,
                    user_agent=user_agent,
                )
                updated += 1
                print(f"  ~ update after race {title}", flush=True)
                continue
            if status != 201:
                snippet = body.decode("utf-8", errors="replace")[:500]
                _die(f"create {title!r} HTTP {status}: {snippet}")
            skipped += 1
            print(f"  ! skip unresolved duplicate {title} ({url})", flush=True)
            continue

        result = json.loads(body.decode("utf-8"))
        feed_id = int(result["feed_id"])
        # Set title after create (create endpoint does not take title).
        _update_feed(
            base_url,
            token,
            feed_id,
            title=title,
            category_id=category_id,
            scraper=scraper,
            crawler=crawler,
            user_agent=user_agent,
        )
        current = existing_feeds(base_url, token)
        created += 1
        print(f"  + create {title}", flush=True)
    print(
        f"Done: created={created} updated={updated} skipped={skipped} "
        f"seed={len(seed['feeds'])}",
        flush=True,
    )


def export_live(base_url: str, token: str, opml_out: Path, json_out: Path) -> None:
    status, body = _request("GET", base_url, "/v1/export", token)
    if status != 200:
        _die(f"export OPML HTTP {status}: {body[:300]!r}")
    opml_out.parent.mkdir(parents=True, exist_ok=True)
    opml_out.write_bytes(body)
    status, body = _request("GET", base_url, "/v1/feeds", token)
    feeds = _json_body(status, body, {200})
    json_out.write_text(
        json.dumps(feeds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(feeds)} feeds → {opml_out} + {json_out}")


def live_to_seed(base_url: str, token: str) -> dict[str, Any]:
    """Build commit-ready seed dict from live Miniflux feeds (scraper/crawler/UA)."""
    status, body = _request("GET", base_url, "/v1/feeds", token)
    feeds = _json_body(status, body, {200})
    if not feeds:
        _die("no feeds on Miniflux — nothing to sync into seed")

    user_agents = [str(f.get("user_agent") or "") for f in feeds if f.get("user_agent")]
    default_ua = max(set(user_agents), key=user_agents.count) if user_agents else ""

    seed_feeds: list[dict[str, Any]] = []
    for feed in sorted(
        feeds,
        key=lambda f: (
            str((f.get("category") or {}).get("title") or ""),
            str(f.get("title") or ""),
        ),
    ):
        cat = feed.get("category") or {}
        cat_title = str(cat.get("title") or "All")
        if cat_title == "All":
            # Prefer explicit categories; skip uncategorized leftovers if any.
            continue
        entry: dict[str, Any] = {
            "category": cat_title,
            "title": str(feed.get("title") or feed.get("feed_url")),
            "feed_url": str(feed["feed_url"]),
            "scraper_rules": str(feed.get("scraper_rules") or ""),
            "crawler": bool(feed.get("crawler", False)),
        }
        ua = str(feed.get("user_agent") or "")
        if ua and ua != default_ua:
            entry["user_agent"] = ua
        seed_feeds.append(entry)

    if not seed_feeds:
        # Fallback: keep All-category feeds rather than empty seed.
        for feed in feeds:
            seed_feeds.append(
                {
                    "category": str((feed.get("category") or {}).get("title") or "All"),
                    "title": str(feed.get("title") or feed.get("feed_url")),
                    "feed_url": str(feed["feed_url"]),
                    "scraper_rules": str(feed.get("scraper_rules") or ""),
                    "crawler": bool(feed.get("crawler", False)),
                }
            )

    return {
        "source": "miniflux-live",
        "user_agent": default_ua,
        "crawler_default": True,
        "feeds": seed_feeds,
    }


def sync_seed_from_live(
    base_url: str, token: str, seed_out: Path, opml_out: Path | None
) -> None:
    seed = live_to_seed(base_url, token)
    seed_out.parent.mkdir(parents=True, exist_ok=True)
    seed_out.write_text(
        json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote seed ({len(seed['feeds'])} feeds): {seed_out}")
    if opml_out is not None:
        write_opml(seed, opml_out)


def resolve_base_url(cli_url: str | None) -> str:
    if cli_url:
        return cli_url.rstrip("/")
    env = os.environ.get("MINIFLUX_ADMIN_URL") or os.environ.get("MINIFLUX_API_URL")
    if env and "radar-miniflux" not in env:
        return env.rstrip("/")
    # Default: host LAN publish (docker-compose.lan.yml).
    return "http://localhost:8080"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gen = sub.add_parser("gen-opml", help="Write OPML from seed JSON")
    p_gen.add_argument("--seed", type=Path, required=True)
    p_gen.add_argument("--opml", type=Path, required=True)

    p_imp = sub.add_parser("import", help="Create/update feeds from seed JSON")
    p_imp.add_argument("--seed", type=Path, required=True)
    p_imp.add_argument("--url", default=None)
    p_imp.add_argument("--token", default=None)

    p_exp = sub.add_parser("export", help="Export live OPML + feeds JSON")
    p_exp.add_argument("--opml", type=Path, required=True)
    p_exp.add_argument("--json", type=Path, required=True)
    p_exp.add_argument("--url", default=None)
    p_exp.add_argument("--token", default=None)

    p_sync = sub.add_parser(
        "sync-seed",
        help="Overwrite commit-ready seed.json (+ OPML) from live Miniflux",
    )
    p_sync.add_argument("--seed", type=Path, required=True)
    p_sync.add_argument("--opml", type=Path, default=None)
    p_sync.add_argument("--url", default=None)
    p_sync.add_argument("--token", default=None)

    args = parser.parse_args()
    if args.cmd == "gen-opml":
        write_opml(load_seed(args.seed), args.opml)
        return

    token = args.token or os.environ.get("MINIFLUX_API_KEY") or ""
    if not token:
        _die("MINIFLUX_API_KEY missing (pass --token or set env)")
    base = resolve_base_url(args.url)

    if args.cmd == "import":
        print(f"Importing seed into {base} ...", flush=True)
        import_seed(base, token, load_seed(args.seed))
    elif args.cmd == "export":
        print(f"Exporting from {base} ...", flush=True)
        export_live(base, token, args.opml, args.json)
    elif args.cmd == "sync-seed":
        print(f"Syncing seed from {base} ...", flush=True)
        sync_seed_from_live(base, token, args.seed, args.opml)


if __name__ == "__main__":
    main()
