# _load_dotenv.sh — safe KEY=VALUE loader for ops scripts (Git Bash / WSL / Linux).
# Sourced by backup-postgres.sh / restore-postgres.sh. Not executable alone.
#
# Why not `source .env`? Comments or values with `()`, spaces, or Windows CRLF can
# break bash. This parser only accepts KEY=VALUE lines (optional quotes); ignores
# blanks and # comments. Does not eval / command-substitute.
#
# shellcheck shell=bash

radar_load_dotenv() {
  local env_file="${1:-}"
  [[ -n "${env_file}" && -f "${env_file}" ]] || return 0
  local line key val
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    [[ "${line}" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line//[[:space:]]/}" ]] && continue
    [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    if [[ "${val}" =~ ^\"(.*)\"$ ]]; then
      val="${BASH_REMATCH[1]}"
    elif [[ "${val}" =~ ^\'(.*)\'$ ]]; then
      val="${BASH_REMATCH[1]}"
    fi
    export "${key}=${val}"
  done < "${env_file}"
}
