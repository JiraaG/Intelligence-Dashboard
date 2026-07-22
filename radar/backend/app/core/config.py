"""Configurazione applicativa con limiti bounded e fail-fast in production.

Carica `.env` all'import, costruisce le lane LLM via `load_lanes()`, poi espone
DB/Miniflux/worker/CORS. Gli alias legacy (`GEMINI_*`, `DEEPSEEK_*`, `LLM_RPM`)
sono comodità: i limiti autoritativi restano `LLM_SIMPLE` / `LLM_COMPLEX`.

SoT:
    docs/01_getting_started.md; .agents/AGENTS.md §3; SoT LLM §5–6.
"""

from __future__ import annotations

import os
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()


class ConfigError(ValueError):
    """Configurazione invalida o incompleta per l'ambiente attivo."""


def _env_str(name: str, default: str | None = None) -> str | None:
    """Legge una stringa env; chiave assente o blank → ``default``.

    Args:
        name: Nome della variabile d'ambiente.
        default: Valore se assente/blank (può essere ``None``).
    Returns:
        Stringa strip-pata, oppure ``default``.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _env_int(
    name: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
    allow_zero: bool = False,
) -> int:
    """Parse intero env con range opzionale; blank/assente → ``default``.

    Args:
        name: Nome della variabile.
        default: Valore se assente/blank.
        min_value: Minimo inclusivo (ignorato se ``allow_zero`` e valore 0).
        max_value: Massimo inclusivo.
        allow_zero: Se True, ``0`` è ammesso anche sotto ``min_value``
            (semaforo ``0`` = unmanaged sulle quote lane).
    Returns:
        Intero validato.
    Raises:
        ConfigError: valore non intero o fuori range.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = int(raw.strip())
        except ValueError as exc:
            raise ConfigError(f"{name} deve essere un intero (valore: {raw!r})") from exc

    if allow_zero and value == 0:
        return 0
    if min_value is not None and value < min_value:
        raise ConfigError(f"{name} deve essere >= {min_value} (valore: {value})")
    if max_value is not None and value > max_value:
        raise ConfigError(f"{name} deve essere <= {max_value} (valore: {value})")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse booleano env (1/true/yes/on); blank/assente → ``default``."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(
    name: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    """Parse float env con range; blank/assente → ``default``.

    Raises:
        ConfigError: valore non numerico o fuori range.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        value = default
    else:
        try:
            value = float(raw.strip())
        except ValueError as exc:
            raise ConfigError(f"{name} deve essere un numero (valore: {raw!r})") from exc
    if min_value is not None and value < min_value:
        raise ConfigError(f"{name} deve essere >= {min_value} (valore: {value})")
    if max_value is not None and value > max_value:
        raise ConfigError(f"{name} deve essere <= {max_value} (valore: {value})")
    return value


def _csv_models(raw: str | None) -> list[str]:
    """Split CSV di id modello: trim, scarta vuoti, dedup preservando l'ordine."""
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        model = part.strip()
        if not model or model in seen:
            continue
        seen.add(model)
        out.append(model)
    return out


def _resolve_time_zone(name: str):
    """Risolve timezone IANA; UTC/GMT non richiedono il pacchetto tzdata su Windows.

    Args:
        name: Identificatore IANA o ``UTC``/``GMT``.
    Returns:
        Coppia ``(tzinfo, nome_canonico)``.
    Raises:
        ConfigError: nome IANA sconosciuto.
    """
    if name.upper() in {"UTC", "GMT"}:
        return dt_timezone.utc, "UTC"
    try:
        return ZoneInfo(name), name
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"RADAR_TIME_ZONE non valida: {name!r}") from exc


RADAR_ENV = (_env_str("RADAR_ENV", "development") or "development").lower()
IS_PRODUCTION = RADAR_ENV in {"production", "prod"}

# ── LLM (per-lane: SIMPLE / COMPLEX; provider = tipo adapter) ─────────────────
from app.core.llm_lanes import (  # noqa: E402
    LANE_COMPLEX,
    LANE_SIMPLE,
    LlmLaneConfig,
    OPENAI_COMPAT_PROVIDERS,
    load_lanes,
)

LLM_SIMPLE: LlmLaneConfig
LLM_COMPLEX: LlmLaneConfig
LLM_SIMPLE, LLM_COMPLEX = load_lanes()

# Alias retrocompatibili (preferire LLM_SIMPLE / LLM_COMPLEX nel codice nuovo).
GOOGLE_API_KEY = _env_str("GOOGLE_API_KEY")
GEMINI_API_KEY = _env_str("GEMINI_API_KEY")
# Chiave esposta per boot SDK Gemini: lane SIMPLE se provider=gemini, altrimenti legacy.
LLM_API_KEY = (
    LLM_SIMPLE.api_key
    if LLM_SIMPLE.provider == "gemini"
    else (GOOGLE_API_KEY or GEMINI_API_KEY or LLM_SIMPLE.api_key)
)
# Se SIMPLE non è gemini, espone comunque una chiave Gemini per l'SDK se presente.
if not LLM_API_KEY:
    LLM_API_KEY = GOOGLE_API_KEY or GEMINI_API_KEY or ""

GEMINI_MODEL = LLM_SIMPLE.model if LLM_SIMPLE.provider == "gemini" else (
    _env_str("GEMINI_MODEL", "gemma-4-31b") or "gemma-4-31b"
)
if GEMINI_MODEL in ("gemma-4-31b", "gemma-4-31b-it"):
    GEMINI_MODEL = "gemma-4-31b-it"
# Se SIMPLE è gemini, i fallback autoritativi sono già in LLM_SIMPLE.fallbacks
# (LLM_SIMPLE_FALLBACKS presente anche vuota sopprime GEMINI_MODEL_FALLBACKS — C-03).
GEMINI_MODEL_FALLBACKS = list(LLM_SIMPLE.fallbacks) if LLM_SIMPLE.provider == "gemini" else (
    _csv_models(_env_str("GEMINI_MODEL_FALLBACKS", ""))
)


def gemini_model_chain() -> list[str]:
    """Catena primary+fallback della lane SIMPLE quando il provider è gemini.

    Returns:
        Lista ordinata senza duplicati; se SIMPLE non è gemini, usa gli alias
        ``GEMINI_MODEL`` / ``GEMINI_MODEL_FALLBACKS`` legacy.
    SoT:
        plan-audit/complete/sot_llm_multi_model_fallback.md §5; C-03 su precedenza FALLBACKS.
    """
    if LLM_SIMPLE.provider == "gemini":
        return list(LLM_SIMPLE.models)
    chain = [GEMINI_MODEL]
    for model in GEMINI_MODEL_FALLBACKS:
        if model not in chain:
            chain.append(model)
    return chain


# Alias di sola comodità → valori della lane SIMPLE (NON sono limiti globali).
# Nuovo codice: usare LLM_SIMPLE.rpm / .tpm / .rpd e LLM_COMPLEX.*.
# 0 = dimensione non gestita su quella lane.
LLM_RPM = LLM_SIMPLE.rpm
LLM_TPM = LLM_SIMPLE.tpm
LLM_RPD = LLM_SIMPLE.rpd
GEMINI_REQUEST_TIMEOUT = int(max(LLM_SIMPLE.timeout, LLM_COMPLEX.timeout))
ESTIMATED_TOKENS_PER_REQUEST = _env_int(
    "ESTIMATED_TOKENS_PER_REQUEST",
    1500,
    min_value=1,
    max_value=100_000,
)

# Alias legacy COMPLEX/deepseek: riflettono LLM_COMPLEX solo se provider allineato.
DEEPSEEK_API_KEY = (
    LLM_COMPLEX.api_key
    if LLM_COMPLEX.provider == "deepseek"
    else (_env_str("DEEPSEEK_API_KEY", "") or "")
)
DEEPSEEK_MODEL = (
    LLM_COMPLEX.model
    if LLM_COMPLEX.provider == "deepseek"
    else (_env_str("DEEPSEEK_MODEL", "deepseek-v4-flash") or "deepseek-v4-flash")
)
DEEPSEEK_REASONING_EFFORT = (
    LLM_COMPLEX.reasoning_effort
    if LLM_COMPLEX.provider in OPENAI_COMPAT_PROVIDERS
    else ((_env_str("DEEPSEEK_REASONING_EFFORT", "high") or "high").lower())
)
DEEPSEEK_BASE_URL = (
    LLM_COMPLEX.base_url
    if LLM_COMPLEX.provider == "deepseek"
    else (
        _env_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com") or "https://api.deepseek.com"
    )
).rstrip("/")
DEEPSEEK_RPM = LLM_COMPLEX.rpm if LLM_COMPLEX.provider == "deepseek" else 0
DEEPSEEK_TPM = LLM_COMPLEX.tpm if LLM_COMPLEX.provider == "deepseek" else 0
DEEPSEEK_RPD = LLM_COMPLEX.rpd if LLM_COMPLEX.provider == "deepseek" else 0
DEEPSEEK_BUDGET_USD_DAY = (
    LLM_COMPLEX.budget_usd_day
    if LLM_COMPLEX.provider in OPENAI_COMPAT_PROVIDERS
    else 0.0
)
DEEPSEEK_USD_PER_1M_TOKENS = (
    LLM_COMPLEX.usd_per_1m_tokens
    if LLM_COMPLEX.provider in OPENAI_COMPAT_PROVIDERS
    else 0.28
)

# Routing: off = sola catena SIMPLE; complexity = heuristic v2.2 sulle lane.
# Default codice boot-safe: off + shadow=true (docs/01); .env.example attiva il profilo ops.
_raw_routing = (_env_str("LLM_ROUTING_MODE", "off") or "off").lower()
LLM_ROUTING_MODE = _raw_routing if _raw_routing in {"off", "complexity"} else "off"
LLM_ROUTING_SHADOW = _env_bool("LLM_ROUTING_SHADOW", True)
LLM_ROUTING_STRICT = _env_bool("LLM_ROUTING_STRICT", False)
LLM_COMPLEXITY_ESCALATE_ON_VALIDATION = _env_bool("LLM_COMPLEXITY_ESCALATE_ON_VALIDATION", True)
LLM_MODEL_COOLDOWN_HOURS = _env_int("LLM_MODEL_COOLDOWN_HOURS", 24, min_value=1, max_value=168)

# Effort reasoning dedicato per la fascia heuristic BORDERLINE sulla catena COMPLEX.
# Default codice se unset/vuoto = "high" (backward compatible, zero regressione al boot).
# Target ops post dual-run GATE = "none".
_raw_bl_effort = (_env_str("LLM_BORDERLINE_REASONING_EFFORT", "high") or "high").lower()
if _raw_bl_effort in {"none", "off", "disabled"}:
    LLM_BORDERLINE_REASONING_EFFORT = "none"
elif _raw_bl_effort in {"high", "max"}:
    LLM_BORDERLINE_REASONING_EFFORT = _raw_bl_effort
elif _raw_bl_effort in {"low", "medium"}:
    import logging
    logging.getLogger("radar.core.config").warning(
        "LLM_BORDERLINE_REASONING_EFFORT=%r rimappato a 'high' (DeepSeek dialect supporta none|high|max)",
        _raw_bl_effort,
    )
    LLM_BORDERLINE_REASONING_EFFORT = "high"
else:
    import logging
    logging.getLogger("radar.core.config").warning(
        "LLM_BORDERLINE_REASONING_EFFORT=%r non valido, default 'high'",
        _raw_bl_effort,
    )
    LLM_BORDERLINE_REASONING_EFFORT = "high"

LLM_SIMPLE_PROVIDER = LLM_SIMPLE.provider
LLM_SIMPLE_MODEL = LLM_SIMPLE.model
LLM_COMPLEX_PROVIDER = LLM_COMPLEX.provider
LLM_COMPLEX_MODEL = LLM_COMPLEX.model

# ── Database ─────────────────────────────────────────────────────────────────
_DEFAULT_PG_PASSWORD = "radar_password_secure"

pg_user = _env_str("POSTGRES_USER", "radar_user") or "radar_user"
pg_pass = _env_str("POSTGRES_PASSWORD", _DEFAULT_PG_PASSWORD) or _DEFAULT_PG_PASSWORD
pg_db = _env_str("POSTGRES_DB", "radar_db") or "radar_db"
pg_host = _env_str("POSTGRES_HOST", "localhost") or "localhost"
pg_port = _env_str("POSTGRES_PORT", "5432") or "5432"
# URL di default da pezzi Postgres; in Compose di solito arriva DATABASE_URL già pronta.
_default_db_url = (
    f"postgresql://{quote_plus(pg_user)}:{quote_plus(pg_pass)}"
    f"@{pg_host}:{pg_port}/{pg_db}"
)

DATABASE_URL = _env_str("DATABASE_URL", _default_db_url) or _default_db_url
OBSIDIAN_VAULT_PATH = _env_str("OBSIDIAN_VAULT_PATH", "/app/vault") or "/app/vault"

# ── Miniflux ─────────────────────────────────────────────────────────────────
MINIFLUX_API_URL = _env_str("MINIFLUX_API_URL", "http://localhost:8080") or "http://localhost:8080"
MINIFLUX_API_KEY = _env_str("MINIFLUX_API_KEY", "") or ""
MINIFLUX_WEBHOOK_SECRET = _env_str("MINIFLUX_WEBHOOK_SECRET", "") or ""
MINIFLUX_LIMIT = _env_int("MINIFLUX_LIMIT", 50, min_value=1, max_value=500)

# Ceiling byte sullo stream HTTP e sul singolo entry prima del parse (docs/01).
MAX_MINIFLUX_RESPONSE_BYTES = _env_int(
    "MAX_MINIFLUX_RESPONSE_BYTES",
    5_000_000,
    min_value=64_000,
    max_value=50_000_000,
)
MAX_ENTRY_CONTENT_BYTES = _env_int(
    "MAX_ENTRY_CONTENT_BYTES",
    500_000,
    min_value=1_000,
    max_value=5_000_000,
)

MINIFLUX_CONNECT_TIMEOUT = _env_int("MINIFLUX_CONNECT_TIMEOUT", 10, min_value=1, max_value=120)
MINIFLUX_READ_TIMEOUT = _env_int("MINIFLUX_READ_TIMEOUT", 30, min_value=1, max_value=300)
MINIFLUX_MAX_RETRIES = _env_int("MINIFLUX_MAX_RETRIES", 3, min_value=0, max_value=10)
MINIFLUX_RETRY_BASE_SECONDS = _env_int("MINIFLUX_RETRY_BASE_SECONDS", 1, min_value=1, max_value=60)
MINIFLUX_RETRY_MAX_SECONDS = _env_int("MINIFLUX_RETRY_MAX_SECONDS", 30, min_value=1, max_value=300)

# Outbox: soglia oltre la quale uno stato `writing` stale è recuperabile.
OUTBOX_STALE_WRITING_SECONDS = _env_int(
    "OUTBOX_STALE_WRITING_SECONDS",
    300,
    min_value=30,
    max_value=86_400,
)

# ── Deduplicazione Semantica (Fase C) ─────────────────────────────────────────
SEMANTIC_DEDUP_ENABLED = _env_bool("SEMANTIC_DEDUP_ENABLED", True)
SEMANTIC_DEDUP_SIMILARITY_THRESHOLD = _env_float(
    "SEMANTIC_DEDUP_SIMILARITY_THRESHOLD",
    0.80,
    min_value=0.5,
    max_value=1.0,
)
SEMANTIC_DEDUP_LOOKBACK_HOURS = _env_int(
    "SEMANTIC_DEDUP_LOOKBACK_HOURS",
    24,
    min_value=1,
    max_value=168,
)
SEMANTIC_EMBEDDING_MODEL = (
    _env_str("SEMANTIC_EMBEDDING_MODEL", "all-MiniLM-L6-v2") or "all-MiniLM-L6-v2"
)
SEMANTIC_PREFILTER_LEN_RATIO = _env_float(
    "SEMANTIC_PREFILTER_LEN_RATIO",
    0.7,
    min_value=0.1,
    max_value=1.0,
)

# Soft hint nel prompt quality se len_incoming > len_existing * ratio (D15/§3.6).
SEMANTIC_QUALITY_REPLACE_HINT_RATIO = _env_float(
    "SEMANTIC_QUALITY_REPLACE_HINT_RATIO",
    1.25,
    min_value=1.0,
    max_value=5.0,
)

_raw_tz = _env_str("RADAR_TIME_ZONE", "UTC") or "UTC"
RADAR_TIME_ZONE, RADAR_TIME_ZONE_NAME = _resolve_time_zone(_raw_tz)

# ── Worker (demone ingest; non l'API) ─────────────────────────────────────────
WORKER_QUEUE_DEPTH = _env_int("WORKER_QUEUE_DEPTH", 100, min_value=1, max_value=10_000)
WORKER_ENTRY_CONCURRENCY = _env_int("WORKER_ENTRY_CONCURRENCY", 4, min_value=1, max_value=64)
WORKER_PARSE_CONCURRENCY = _env_int("WORKER_PARSE_CONCURRENCY", 8, min_value=1, max_value=64)
WORKER_DB_CONCURRENCY = _env_int("WORKER_DB_CONCURRENCY", 4, min_value=1, max_value=32)
WORKER_GEMINI_CONCURRENCY = _env_int("WORKER_GEMINI_CONCURRENCY", 2, min_value=1, max_value=16)
WORKER_SHUTDOWN_TIMEOUT = _env_int("WORKER_SHUTDOWN_TIMEOUT", 30, min_value=1, max_value=300)
WORKER_POLL_INTERVAL_SECONDS = _env_int(
    "WORKER_POLL_INTERVAL_SECONDS",
    900,
    min_value=1,
    max_value=86_400,
)
# Chiave fissa session-level per pg_try_advisory_lock (singleton worker).
WORKER_ADVISORY_LOCK_KEY = _env_int(
    "WORKER_ADVISORY_LOCK_KEY",
    742_014_722,
    min_value=1,
    max_value=2_147_483_647,
)
WORKER_ADVISORY_LOCK_BACKOFF_SECONDS = _env_int(
    "WORKER_ADVISORY_LOCK_BACKOFF_SECONDS",
    5,
    min_value=1,
    max_value=300,
)
# Intervallo UPSERT su worker_heartbeat; la readiness TTL usa STALE sotto.
WORKER_HEARTBEAT_INTERVAL_SECONDS = _env_int(
    "WORKER_HEARTBEAT_INTERVAL_SECONDS",
    30,
    min_value=5,
    max_value=300,
)
WORKER_HEARTBEAT_STALE_SECONDS = _env_int(
    "WORKER_HEARTBEAT_STALE_SECONDS",
    90,
    min_value=15,
    max_value=600,
)

# ── Ollama VRAM lifecycle (Profilo F / reasoner locali) ───────────────────────
# Attivi solo se SIMPLE usa protocollo think Ollama (gate in ollama_lifecycle).
# Unload autoritativo via API nativa /api/generate keep_alive=0 (non /v1).
OLLAMA_AUTO_UNLOAD = _env_bool("OLLAMA_AUTO_UNLOAD", True)
OLLAMA_KEEP_ALIVE_BUSY = _env_str("OLLAMA_KEEP_ALIVE_BUSY", "5m") or "5m"
# Idle unload: tipicamente 0 (libera VRAM subito). Accetta int o stringa Ollama.
OLLAMA_KEEP_ALIVE_IDLE = _env_str("OLLAMA_KEEP_ALIVE_IDLE", "0") or "0"
OLLAMA_UNLOAD_DEBOUNCE_SECONDS = _env_int(
    "OLLAMA_UNLOAD_DEBOUNCE_SECONDS",
    60,
    min_value=0,
    max_value=300,
)

# CSV allowlist per origini browser→API dirette. Vuoto = nessun middleware CORS
# (Nginx same-origin). Mai "*". SoT: AGENTS §4.11.
_raw_cors = _env_str("CORS_ALLOW_ORIGINS", "") or ""
_cors_parts = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]
if any(part == "*" for part in _cors_parts):
    raise ConfigError("CORS_ALLOW_ORIGINS non può contenere '*' — usare una allowlist esplicita.")
CORS_ALLOW_ORIGINS: list[str] = _cors_parts


def _validate_production_secrets() -> None:
    """In production, fallisce lo startup se chiavi/DB sono assenti o usano default insicuri.

    Side-effects:
        Nessuna scrittura; solleva ``ConfigError`` se ``IS_PRODUCTION`` e mancano
        chiave lane (o legacy), ``MINIFLUX_API_KEY``, oppure password/DB di default.
    SoT:
        docs/01_getting_started.md §2; AGENTS §4 password.
    """
    if not IS_PRODUCTION:
        return

    missing: list[str] = []
    if not (LLM_SIMPLE.api_key or LLM_COMPLEX.api_key or LLM_API_KEY):
        missing.append("LLM_SIMPLE_API_KEY / LLM_COMPLEX_API_KEY (o legacy GEMINI_/DEEPSEEK_)")
    if not MINIFLUX_API_KEY:
        missing.append("MINIFLUX_API_KEY")
    if not _env_str("DATABASE_URL") and not _env_str("POSTGRES_PASSWORD"):
        missing.append("DATABASE_URL o POSTGRES_PASSWORD")

    if missing:
        raise ConfigError(
            "Ambiente production: impostazioni obbligatorie mancanti: " + ", ".join(missing)
        )

    if pg_pass == _DEFAULT_PG_PASSWORD and not _env_str("DATABASE_URL"):
        raise ConfigError(
            "Ambiente production: rifiutata la password PostgreSQL di default "
            f"'{_DEFAULT_PG_PASSWORD}'. Imposta POSTGRES_PASSWORD o DATABASE_URL."
        )

    if "radar_password_secure" in DATABASE_URL and not _env_str("DATABASE_URL"):
        raise ConfigError(
            "Ambiente production: DATABASE_URL costruita con password di default non consentita."
        )


_validate_production_secrets()
