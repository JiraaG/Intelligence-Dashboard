#!/usr/bin/env python3
"""
Hook PreToolUse — Radar Informativo Globale
Eseguito PRIMA di qualsiasi invocazione di tool da parte dell'agente.

Pattern ECC: Security scanning e validazione input prima dell'azione.
Rileva: path traversal, secret leak, accesso a file system vietati, comandi pericolosi.
Phase 6: domain match == o endswith('.'+allowed) — no suffix spoof.
"""

from __future__ import annotations

import json
import re
import sys


FORBIDDEN_PATHS = [
    r"\.ssh[/\\]",
    r"\.env$",
    r"\.gnupg[/\\]",
    r"C:\\Windows\\",
    r"/etc/passwd",
    r"/etc/shadow",
    r"/proc/",
    r"AppData\\Roaming",
]

SECRET_PATTERNS = [
    r"AIza[0-9A-Za-z_-]{35}",
    r"sk-[A-Za-z0-9]{32,}",
    r"ghp_[A-Za-z0-9]{36}",
    r"postgres://[^\s]+:[^\s]+@",
    r"MINIFLUX_API_KEY\s*=\s*\S+",
    r"GEMINI_API_KEY\s*=\s*\S+",
    r"GOOGLE_API_KEY\s*=\s*\S+",
    r"POSTGRES_PASSWORD\s*=\s*\S+",
]

DANGEROUS_COMMANDS = [
    r"\brm\s+-rf\s+/",
    r"\bdrop\s+table\b",
    r"\btruncate\s+table\b",
    r"\bformat\s+[a-z]:\b",
    r"\bdel\s+/[sf]\b",
    r"curl\s+.*\|\s*(bash|sh|python)",
]

ALLOWED_DOMAINS = [
    "github.com",
    "raw.githubusercontent.com",
    "generativelanguage.googleapis.com",
    "api.miniflux.app",
    "pypi.org",
    "npmjs.com",
    "registry.npmjs.org",
    "registry.hub.docker.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "opendatacommons.org",
]


def check_forbidden_paths(tool_input: str) -> list[str]:
    violations = []
    for pattern in FORBIDDEN_PATHS:
        if re.search(pattern, tool_input, re.IGNORECASE):
            violations.append(f"FORBIDDEN PATH: pattern '{pattern}' rilevato")
    return violations


def check_secret_patterns(tool_input: str) -> list[str]:
    violations = []
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, tool_input):
            violations.append(f"SECRET DETECTED: pattern '{pattern}' trovato — oscurato")
    return violations


def check_dangerous_commands(tool_input: str) -> list[str]:
    violations = []
    for pattern in DANGEROUS_COMMANDS:
        if re.search(pattern, tool_input, re.IGNORECASE):
            violations.append(f"DANGEROUS COMMAND: '{pattern}' rilevato")
    return violations


def _normalize_host(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("[") and "]" in host:
        host = host[1 : host.index("]")]
    else:
        host = host.split("%", 1)[0]
        if host.count(":") == 1:
            host = host.rsplit(":", 1)[0]
    if host.endswith("."):
        host = host[:-1]
    return host


def domain_allowed(domain: str, allowed_domains: list[str]) -> bool:
    """Accept only exact match or a proper subdomain of an allowlisted apex."""
    domain = _normalize_host(domain)
    if not domain or domain.startswith("."):
        return False
    for allowed in allowed_domains:
        allowed_n = _normalize_host(allowed)
        if not allowed_n:
            continue
        if domain == allowed_n or domain.endswith("." + allowed_n):
            return True
    return False


def check_network_domains(tool_input: str) -> list[str]:
    violations = []
    urls = re.findall(r"https?://([^/\s\"']+)", tool_input)
    for url_domain in urls:
        domain = _normalize_host(url_domain)
        if not domain_allowed(domain, ALLOWED_DOMAINS):
            violations.append(f"UNAUTHORIZED DOMAIN: '{domain}' non è in whitelist")
    return violations


def main() -> None:
    try:
        tool_data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        tool_name = tool_data.get("tool_name", "unknown")
        tool_input_str = json.dumps(tool_data.get("tool_input", {}))
    except (json.JSONDecodeError, OSError):
        tool_input_str = sys.argv[1] if len(sys.argv) > 1 else ""
        tool_name = "unknown"

    all_violations: list[str] = []
    all_violations.extend(check_forbidden_paths(tool_input_str))
    all_violations.extend(check_secret_patterns(tool_input_str))
    all_violations.extend(check_dangerous_commands(tool_input_str))

    if tool_name in ("run_command", "execute_bash", "Shell", "read_url_content", "WebFetch"):
        all_violations.extend(check_network_domains(tool_input_str))

    if all_violations:
        print(
            f"[PreToolUse BLOCK] Hook ha bloccato l'esecuzione del tool '{tool_name}':",
            file=sys.stderr,
        )
        for v in all_violations:
            print(f"  ⛔ {v}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
