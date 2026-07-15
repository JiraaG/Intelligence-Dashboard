#!/usr/bin/env python3
"""
Thin Cursor → Radar adapter for postToolUse / afterFileEdit.

Reshapes Cursor payloads into the Radar post-tool-use contract, then returns
Cursor-compatible JSON (additional_context on lint/soft issues).
Logic remains in radar/.ecc/hooks/post-tool-use.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


WRITE_TOOLS = frozenset(
    {
        "Write",
        "StrReplace",
        "EditNotebook",
        "search_replace",
        "apply_patch",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
    }
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def radar_post_hook() -> Path:
    return project_root() / "radar" / ".ecc" / "hooks" / "post-tool-use.py"


def to_radar_payload(cursor: dict) -> dict:
    """Map Cursor pre/post/afterFileEdit shapes → Radar {tool_name, tool_input}."""
    # afterFileEdit: { file_path, edits }
    file_path = cursor.get("file_path")
    if isinstance(file_path, str) and file_path and "tool_input" not in cursor:
        return {
            "tool_name": "Write",
            "tool_input": {"path": file_path, "file_path": file_path},
        }

    tool_name = cursor.get("tool_name") or cursor.get("tool") or "unknown"
    tool_input = cursor.get("tool_input") or cursor.get("arguments") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    return {"tool_name": tool_name, "tool_input": tool_input}


def main() -> None:
    raw = sys.stdin.read() if not sys.stdin.isatty() else "{}"
    try:
        cursor = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        cursor = {}

    radar_payload = to_radar_payload(cursor)
    hook = radar_post_hook()
    if not hook.is_file():
        print(
            json.dumps(
                {
                    "additional_context": (
                        f"[PostToolUse] Radar post-hook missing: {hook}"
                    )
                }
            )
        )
        sys.exit(0)

    # Skip expensive lint when not a write-like tool and no file path
    tool_name = str(radar_payload.get("tool_name") or "")
    tool_input = radar_payload.get("tool_input") or {}
    has_path = any(
        isinstance(tool_input.get(k), str) and tool_input.get(k)
        for k in ("path", "file_path", "TargetFile", "AbsolutePath", "target_notebook")
    )
    if tool_name not in WRITE_TOOLS and not has_path:
        print(json.dumps({}))
        sys.exit(0)

    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(radar_payload),
        capture_output=True,
        text=True,
        cwd=str(project_root()),
        timeout=55,
    )

    stderr = (proc.stderr or "").strip()
    if proc.returncode == 0:
        out: dict = {}
        if stderr and ("WARN" in stderr or "Placeholder" in stderr):
            out["additional_context"] = f"[Radar post-tool-use]\n{stderr[:3000]}"
        print(json.dumps(out))
        sys.exit(0)

    # Lint hard-fail or linter missing: surface to agent; exit 0 (post cannot block)
    msg = stderr or (proc.stdout or "").strip() or f"post-tool-use exit {proc.returncode}"
    print(
        json.dumps(
            {
                "additional_context": (
                    "[Radar post-tool-use FAILED]\n"
                    f"{msg[:3000]}\n"
                    "Fix lint/placeholder issues before considering the edit done."
                )
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired:
        print(
            json.dumps(
                {
                    "additional_context": "[Radar post-tool-use] timed out"
                }
            )
        )
        sys.exit(0)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "additional_context": f"[Radar post-tool-use adapter error] {exc}"
                }
            )
        )
        sys.exit(0)
