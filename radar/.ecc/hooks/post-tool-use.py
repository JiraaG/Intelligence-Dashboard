#!/usr/bin/env python3
"""
Hook PostToolUse — Radar Informativo Globale
Eseguito DOPO ogni invocazione di tool da parte dell'agente.

Pattern ECC: Format check e logging post-azione.
Esegue: formatting check (ruff per Python, prettier per TS), logging strutturato.
"""

import sys
import re
import json
import subprocess
import os
from pathlib import Path


def run_python_linting(file_path: str) -> bool:
    """Esegue ruff check sul file Python modificato. Ritorna True se passa."""
    try:
        result = subprocess.run(
            ['ruff', 'check', '--quiet', file_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(f"[PostToolUse WARN] Ruff ha trovato problemi in {file_path}:", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # ruff non installato o timeout: skip silenzioso
        return True


def run_typescript_linting(file_path: str) -> bool:
    """Esegue eslint sul file TypeScript modificato. Ritorna True se passa."""
    try:
        result = subprocess.run(
            ['npx', 'eslint', '--quiet', file_path],
            capture_output=True, text=True, timeout=15,
            cwd=str(Path(file_path).parent)
        )
        if result.returncode != 0:
            print(f"[PostToolUse WARN] ESLint ha trovato problemi in {file_path}:", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True


def check_todo_comments(file_path: str) -> list[str]:
    """Controlla che il file non contenga placeholder vietati."""
    violations = []
    forbidden_patterns = [
        r'#\s*TODO', r'#\s*FIXME', r'#\s*HACK',
        r'//\s*TODO', r'//\s*FIXME',
        r'raise NotImplementedError',
        r'pass\s*#.*implement',
    ]
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                violations.append(f"Placeholder vietato trovato in {file_path}: '{matches[0]}'")
    except (FileNotFoundError, PermissionError):
        pass
    return violations


def log_tool_completion(tool_name: str, file_path: str = None):
    """Logga il completamento dell'azione."""
    import datetime
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    target = f" → {file_path}" if file_path else ""
    print(f"[{timestamp}] [PostToolUse OK] {tool_name}{target}", file=sys.stderr)


def main():
    """Entry point del hook PostToolUse."""
    try:
        tool_data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        tool_name = tool_data.get('tool_name', 'unknown')
        tool_input = tool_data.get('tool_input', {})
        file_path = tool_input.get('TargetFile') or tool_input.get('AbsolutePath', '')
    except (json.JSONDecodeError, Exception):
        tool_name = 'unknown'
        file_path = sys.argv[1] if len(sys.argv) > 1 else ''

    warnings = []

    # Solo per tool di scrittura file
    if tool_name in ('write_to_file', 'replace_file_content', 'multi_replace_file_content') and file_path:

        # Check placeholder vietati
        warnings.extend(check_todo_comments(file_path))

        # Linting per tipo di file
        if file_path.endswith('.py'):
            run_python_linting(file_path)
        elif file_path.endswith(('.ts', '.tsx')):
            run_typescript_linting(file_path)

    # Log sempre
    log_tool_completion(tool_name, file_path)

    # Mostra warnings (non bloccante)
    if warnings:
        print("[PostToolUse WARN] Problemi rilevati:", file=sys.stderr)
        for w in warnings:
            print(f"  ⚠️  {w}", file=sys.stderr)

    sys.exit(0)  # PostToolUse non blocca mai l'agente (solo avvisi)


if __name__ == '__main__':
    main()
