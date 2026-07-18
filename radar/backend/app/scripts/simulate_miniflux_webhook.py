#!/usr/bin/env python3
"""Simula POST webhook Miniflux con header X-Miniflux-Signature (HMAC-SHA256).

Uso:
  set MINIFLUX_WEBHOOK_SECRET=test_secret_phase_b
  set WEBHOOK_URL=http://127.0.0.1:8000/api/webhooks/miniflux
  python -m app.scripts.simulate_miniflux_webhook
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    secret = os.environ.get("MINIFLUX_WEBHOOK_SECRET", "test_secret_phase_b")
    url = os.environ.get(
        "WEBHOOK_URL",
        "http://127.0.0.1:8000/api/webhooks/miniflux",
    )

    payload = {
        "event_type": "new_entries",
        "entries": [
            {
                "id": 900001,
                "title": "Phase B webhook simulation",
                "url": "https://example.test/phase-b-sim",
            }
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Miniflux/2.3.2-phase-b-sim",
            "X-Miniflux-Signature": signature,
            "X-Miniflux-Event-Type": "new_entries",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            print(f"HTTP {resp.status}")
            print(body)
            return 0 if resp.status in (200, 202) else 1
    except urllib.error.HTTPError as err:
        print(f"HTTP {err.code}", file=sys.stderr)
        print(err.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as err:
        print(f"URL error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
