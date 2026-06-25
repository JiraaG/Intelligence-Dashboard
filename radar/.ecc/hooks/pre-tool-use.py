#!/usr/bin/env python3
"""
Hook PreToolUse — Radar Informativo Globale
Eseguito PRIMA di qualsiasi invocazione di tool da parte dell'agente.

Pattern ECC: Security scanning e validazione input prima dell'azione.
Rileva: path traversal, secret leak, accesso a file system vietati, comandi pericolosi.
"""

import sys
import re
import json
import os


# ── Percorsi assolutamente vietati ──────────────────────────────────────────
FORBIDDEN_PATHS = [
    r'\.ssh[/\\]',
    r'\.env$',
    r'\.gnupg[/\\]',
    r'C:\\Windows\\',
    r'/etc/passwd',
    r'/etc/shadow',
    r'/proc/',
    r'AppData\\Roaming',
]

# ── Pattern di segreti da intercettare ──────────────────────────────────────
SECRET_PATTERNS = [
    r'AIza[0-9A-Za-z_-]{35}',          # Google API Key
    r'sk-[A-Za-z0-9]{32,}',             # OpenAI API Key
    r'ghp_[A-Za-z0-9]{36}',             # GitHub PAT
    r'postgres://[^\s]+:[^\s]+@',        # PostgreSQL URL con credenziali
    r'MINIFLUX_API_KEY\s*=\s*\S+',       # Miniflux key nel codice
]

# ── Comandi di sistema pericolosi ───────────────────────────────────────────
DANGEROUS_COMMANDS = [
    r'\brm\s+-rf\s+/',
    r'\bdrop\s+table\b',
    r'\btruncate\s+table\b',
    r'\bformat\s+[a-z]:\b',
    r'\bdel\s+/[sf]\b',
    r'curl\s+.*\|\s*(bash|sh|python)',  # Pipe curl to shell
]

# ── Domini di rete consentiti ────────────────────────────────────────────────
ALLOWED_DOMAINS = [
    'github.com',
    'generativelanguage.googleapis.com',
    'api.miniflux.app',
    'pypi.org',
    'npmjs.com',
    'registry.hub.docker.com',
    'fonts.googleapis.com',
    'fonts.gstatic.com',
]


def check_forbidden_paths(tool_input: str) -> list[str]:
    """Rileva tentativi di accesso a percorsi vietati."""
    violations = []
    for pattern in FORBIDDEN_PATHS:
        if re.search(pattern, tool_input, re.IGNORECASE):
            violations.append(f"FORBIDDEN PATH: pattern '{pattern}' rilevato")
    return violations


def check_secret_patterns(tool_input: str) -> list[str]:
    """Rileva segreti nel contenuto da scrivere."""
    violations = []
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, tool_input):
            violations.append(f"SECRET DETECTED: pattern '{pattern}' trovato — oscurato")
    return violations


def check_dangerous_commands(tool_input: str) -> list[str]:
    """Rileva comandi potenzialmente distruttivi."""
    violations = []
    for pattern in DANGEROUS_COMMANDS:
        if re.search(pattern, tool_input, re.IGNORECASE):
            violations.append(f"DANGEROUS COMMAND: '{pattern}' rilevato")
    return violations


def check_network_domains(tool_input: str) -> list[str]:
    """Rileva chiamate a domini non in whitelist."""
    violations = []
    urls = re.findall(r'https?://([^/\s"\']+)', tool_input)
    for url_domain in urls:
        domain = url_domain.split(':')[0]  # Rimuovi porta
        if not any(domain.endswith(allowed) for allowed in ALLOWED_DOMAINS):
            violations.append(f"UNAUTHORIZED DOMAIN: '{domain}' non è in whitelist")
    return violations


def main():
    """Entry point del hook PreToolUse."""
    try:
        # Leggi l'input del tool da stdin (formato ECC: JSON)
        tool_data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        tool_name = tool_data.get('tool_name', 'unknown')
        tool_input_str = json.dumps(tool_data.get('tool_input', {}))

    except (json.JSONDecodeError, Exception):
        # Se non c'è input strutturato, leggi come testo grezzo
        tool_input_str = sys.argv[1] if len(sys.argv) > 1 else ''
        tool_name = 'unknown'

    all_violations = []

    # Esegui tutti i controlli
    all_violations.extend(check_forbidden_paths(tool_input_str))
    all_violations.extend(check_secret_patterns(tool_input_str))
    all_violations.extend(check_dangerous_commands(tool_input_str))

    # Controllo domini solo per tool di rete
    if tool_name in ('run_command', 'execute_bash', 'read_url_content'):
        all_violations.extend(check_network_domains(tool_input_str))

    if all_violations:
        print(f"[PreToolUse BLOCK] Hook ha bloccato l'esecuzione del tool '{tool_name}':", file=sys.stderr)
        for v in all_violations:
            print(f"  ⛔ {v}", file=sys.stderr)
        sys.exit(1)  # Exit code 1 = blocca l'esecuzione del tool

    # Tutto ok, lascia proseguire
    sys.exit(0)


if __name__ == '__main__':
    main()
