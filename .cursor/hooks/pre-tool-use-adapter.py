#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path

def project_root():
    return Path(__file__).resolve().parents[2]

def main():
    raw = sys.stdin.read() if not sys.stdin.isatty() else "{}"
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if "tool_name" not in payload and "tool" in payload:
        payload = {**payload, "tool_name": payload.get("tool")}
    if "tool_input" not in payload and "arguments" in payload:
        payload = {**payload, "tool_input": payload.get("arguments") or {}}
    hook = project_root() / "radar" / ".ecc" / "hooks" / "pre-tool-use.py"
    if not hook.is_file():
        print(json.dumps({"permission": "deny", "user_message": f"missing {hook}", "agent_message": f"missing {hook}"}))
        return
    proc = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload), capture_output=True, text=True, cwd=str(project_root()), timeout=25)
    if proc.returncode == 0:
        print(json.dumps({"permission": "allow"}))
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end="")
        return
    reason = (proc.stderr or proc.stdout or "").strip() or f"blocked exit {proc.returncode}"
    print(json.dumps({"permission": "deny", "user_message": reason[:2000], "agent_message": reason[:2000]}))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"permission": "deny", "user_message": str(exc), "agent_message": str(exc)}))
