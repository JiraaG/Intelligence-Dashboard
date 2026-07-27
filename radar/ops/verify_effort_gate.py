#!/usr/bin/env python3
"""Gate post-deploy: env effort + health + metrics status (in-container)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

BASE = os.environ.get("SMOKE_BASE", "http://radar-backend:8000")
TODAY = date.today().isoformat()


def req(method: str, path: str) -> tuple[int, object]:
    request = urllib.request.Request(
        BASE + path,
        headers={"Accept": "application/json"},
        method=method,
    )
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


def main() -> int:
    expected_bl = os.environ.get("EXPECT_BL_EFFORT", "high")
    expected_cplx = os.environ.get("EXPECT_COMPLEX_EFFORT", "max")
    failed = 0

    for name, path in (
        ("live", "/health/live"),
        ("ready", "/health/ready"),
        ("map-summary", f"/api/map-summary?date={TODAY}"),
        ("metrics-status", "/api/metrics/status"),
        ("metrics-summary", f"/api/metrics/summary?from={TODAY}&to={TODAY}"),
    ):
        status, payload = req("GET", path)
        ok = 200 <= status < 300
        print(f"{name}: status={status} ok={ok}")
        if not ok:
            failed += 1
            print("  detail=", payload)
            continue
        if name == "metrics-status" and isinstance(payload, dict):
            bl = (payload.get("borderline") or {}).get("reasoning_effort")
            models = [
                (m.get("role"), m.get("reasoning_effort"))
                for m in (payload.get("models") or [])
            ]
            print(f"  borderline_effort={bl}")
            print(f"  models={models}")
            if str(bl).lower() != expected_bl:
                print(f"  FAIL borderline expected {expected_bl}")
                failed += 1
            cplx = next(
                (m.get("reasoning_effort") for m in (payload.get("models") or []) if m.get("role") == "complex"),
                None,
            )
            if str(cplx).lower() != expected_cplx:
                print(f"  FAIL complex expected {expected_cplx} got {cplx}")
                failed += 1
        if name == "metrics-summary" and isinstance(payload, dict):
            brk = ((payload.get("llm") or {}).get("models_breakdown")) or []
            efforts = sorted({str(x.get("reasoning_effort")) for x in brk})
            print(f"  breakdown_efforts={efforts}")

    print("RESULT", "PASS" if failed == 0 else f"FAIL count={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
