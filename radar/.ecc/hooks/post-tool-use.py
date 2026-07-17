#!/usr/bin/env python3
"""
Hook PostToolUse — Radar Informativo Globale (logica SoT).

Dopo un tool di scrittura: soft-warn su placeholder vietati; lint hard-fail
(ruff / prettier). Linter assente → ``LinterMissing`` → exit 1 (fail-closed).

Contratto diretto: exit nonzero = fallimento. L'adapter Cursor
(``.cursor/hooks/post-tool-use-adapter.py``) può trasformare quel fallimento in
``additional_context`` con exit 0 (C-01: docs «fail-closed» vs adapter advisory).

@see docs/04_ecc_framework.md (hooks); Phase 6 write-tool allowlist.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

# Nomi ECC + Cursor: estesi da settings.json tools.allowlist se presenti.
DEFAULT_WRITE_TOOLS = frozenset(
    {
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
        "Write",
        "StrReplace",
        "EditNotebook",
        "search_replace",
        "apply_patch",
    }
)


class LinterMissing(RuntimeError):
    """Binario lint non sul PATH — Phase 6 richiede fail-closed, non skip silenzioso."""


def resolve_radar_root() -> Path:
    """
    Root ``radar/``: da ``radar/.ecc/hooks`` → parents, oppure walk da cwd
    (anche se lanciato dalla repo-root con ``radar/.ecc`` annidato).
    """
    here = Path(__file__).resolve().parent  # radar/.ecc/hooks
    radar = here.parent.parent
    if (radar / ".ecc").is_dir() and (radar / "frontend").is_dir():
        return radar
    cur = Path.cwd().resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".ecc").is_dir() and (candidate / "frontend").is_dir():
            return candidate
        if (candidate / "radar" / ".ecc").is_dir():
            return candidate / "radar"
    return radar


def load_write_tool_names(settings_path: Path) -> frozenset[str]:
    """Unione DEFAULT_WRITE_TOOLS + allowlist settings con write/replace/edit/patch."""
    names = set(DEFAULT_WRITE_TOOLS)
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            for t in data.get("tools", {}).get("allowlist", []):
                tl = str(t).lower()
                if any(k in tl for k in ("write", "replace", "edit", "patch")):
                    names.add(str(t))
        except (OSError, json.JSONDecodeError):
            pass
    return frozenset(names)


def extract_file_path(tool_input: dict) -> str:
    """Prima chiave path non vuota tra forme ECC/Cursor/notebook."""
    for key in ("TargetFile", "AbsolutePath", "path", "file_path", "target_notebook"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def check_todo_comments(file_path: str) -> list[str]:
    """
    Soft warning: placeholder vietati dal progetto.
    Non fallisce da solo — solo ``hard_lint_failed`` / ``LinterMissing`` fanno exit 1.
    """
    violations: list[str] = []
    forbidden_patterns = [
        r"#\s*TODO",
        r"#\s*FIXME",
        r"#\s*HACK",
        r"//\s*TODO",
        r"//\s*FIXME",
        r"raise NotImplementedError",
        r"pass\s*#.*implement",
    ]
    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return violations
    for pattern in forbidden_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            violations.append(f"Placeholder vietato in {file_path}: '{matches[0]}'")
    return violations


def run_python_linting(file_path: str, cwd: Path) -> bool:
    """``ruff check``; False = problemi lint; ``LinterMissing`` se ruff assente."""
    try:
        result = subprocess.run(
            ["ruff", "check", "--quiet", file_path],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(cwd),
        )
    except FileNotFoundError as exc:
        raise LinterMissing(
            "ruff non trovato nel PATH — installare ruff (fail-closed Phase 6)"
        ) from exc
    except subprocess.TimeoutExpired:
        print(f"[PostToolUse ERROR] ruff timeout su {file_path}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(f"[PostToolUse WARN] Ruff problemi in {file_path}:", file=sys.stderr)
        print(result.stdout or result.stderr, file=sys.stderr)
        return False
    return True


def run_frontend_linting(file_path: str, frontend_root: Path) -> bool:
    """
    Linter FE di progetto = Prettier (``package.json`` lint), non ESLint.
    Path reso relativo a ``frontend/`` per ``npx prettier --check``.
    """
    try:
        rel = str(Path(file_path).resolve().relative_to(frontend_root.resolve()))
    except ValueError:
        rel = file_path
    try:
        result = subprocess.run(
            ["npx", "--no-install", "prettier", "--check", rel],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(frontend_root),
        )
    except FileNotFoundError as exc:
        raise LinterMissing(
            "npx/prettier non disponibile — fail-closed Phase 6"
        ) from exc
    except subprocess.TimeoutExpired:
        print(f"[PostToolUse ERROR] prettier timeout su {file_path}", file=sys.stderr)
        return False
    err = (result.stderr or "") + (result.stdout or "")
    if result.returncode != 0 and re.search(
        r"not found|Cannot find module|ENOENT|prettier: command not found",
        err,
        re.I,
    ):
        raise LinterMissing(f"prettier non eseguibile: {err[:200]}")
    if result.returncode != 0:
        print(f"[PostToolUse WARN] Prettier problemi in {file_path}:", file=sys.stderr)
        print(result.stdout or result.stderr, file=sys.stderr)
        return False
    return True


def log_tool_completion(tool_name: str, file_path: str = "") -> None:
    """Log su stderr (non stdout — stdout può essere consumato dall'adapter)."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target = f" → {file_path}" if file_path else ""
    print(f"[{timestamp}] [PostToolUse OK] {tool_name}{target}", file=sys.stderr)


def main() -> None:
    """
    Se write-tool + path: soft placeholder + lint per estensione.
    Exit 1: linter missing o lint fallito. Soft warning → stderr, exit 0.
    """
    radar_root = resolve_radar_root()
    settings_path = radar_root / ".ecc" / "settings.json"
    write_tools = load_write_tool_names(settings_path)

    try:
        tool_data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        tool_name = tool_data.get("tool_name") or tool_data.get("tool") or "unknown"
        tool_input = tool_data.get("tool_input") or tool_data.get("arguments") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}
        file_path = extract_file_path(tool_input)
    except (json.JSONDecodeError, OSError):
        tool_name = "unknown"
        file_path = sys.argv[1] if len(sys.argv) > 1 else ""

    soft_warnings: list[str] = []
    hard_lint_failed = False

    if tool_name in write_tools and file_path:
        soft_warnings.extend(check_todo_comments(file_path))
        try:
            if file_path.endswith(".py"):
                be = radar_root / "backend"
                cwd = be if be.is_dir() else radar_root
                if not run_python_linting(file_path, cwd):
                    hard_lint_failed = True
            elif file_path.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".html", ".scss", ".css", ".json")):
                fe = radar_root / "frontend"
                if not run_frontend_linting(file_path, fe):
                    hard_lint_failed = True
        except LinterMissing as exc:
            print(f"[PostToolUse BLOCK] {exc}", file=sys.stderr)
            sys.exit(1)

    log_tool_completion(tool_name, file_path)

    if soft_warnings:
        print("[PostToolUse WARN] Placeholder / soft issues:", file=sys.stderr)
        for w in soft_warnings:
            print(f"  ⚠️  {w}", file=sys.stderr)

    if hard_lint_failed:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
