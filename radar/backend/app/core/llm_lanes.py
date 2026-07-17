"""Configurazione LLM per-lane (SIMPLE / COMPLEX), provider-agnostic.

Env preferito (fonte dei limiti):
  ``LLM_SIMPLE_RPM|TPM|RPD`` e ``LLM_COMPLEX_*`` — ``0`` = dimensione unmanaged.
Anche: ``PROVIDER``, ``MODEL``, ``API_KEY``, ``BASE_URL``, ``BUDGET_USD_DAY``,
``USD_PER_1M_TOKENS``, ``TIMEOUT``, ``REASONING_EFFORT``, ``FALLBACKS`` per lane.

``PROVIDER`` seleziona l'adapter:
  gemini | deepseek | openai | glm | grok | claude (claude = stub).
Adapter HTTP OpenAI-compat: deepseek | openai | glm | grok.
Dialect: deepseek → payload ``thinking``; openai/glm/grok → chat/completions stock.

Legacy vendor (``GEMINI_*``, ``DEEPSEEK_*``, ``LLM_RPM``/TPM/RPD) riempiono i gap
solo come default di ``load_lane`` — non sono un tetto globale condiviso.
Attenzione unset vs blank: per ``*_FALLBACKS`` chiave presente anche vuota ≠ assente
(sopprime il legacy); per RPM/TPM/RPD blank ≡ assente (usa default/legacy). Vedi C-03/C-04.

SoT:
    plan-audit/active/sot_llm_multi_model_fallback.md §5–6; skill radar-quota-ledger;
    .agents/AGENTS.md §3.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

LLM_PROVIDERS = frozenset({"gemini", "deepseek", "openai", "glm", "grok", "claude"})
OPENAI_COMPAT_PROVIDERS = frozenset({"deepseek", "openai", "glm", "grok"})
API_DIALECT_DEEPSEEK = "deepseek"
API_DIALECT_OPENAI = "openai"
LANE_SIMPLE = "simple"
LANE_COMPLEX = "complex"

_PROVIDER_DEFAULT_BASE_URL: Mapping[str, str] = {
    "gemini": "",
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "grok": "https://api.x.ai/v1",
    "claude": "https://api.anthropic.com",
}


def api_dialect_for_provider(provider: str) -> str:
    """Dialect HTTP per adapter OpenAI-compat.

    Returns:
        ``deepseek`` (campo thinking) oppure ``openai`` (stock) per ogni altro provider.
    SoT:
        skill llm-json-extraction; SoT LLM §5.
    """
    if provider == "deepseek":
        return API_DIALECT_DEEPSEEK
    return API_DIALECT_OPENAI


class LlmConfigError(ValueError):
    """Configurazione lane/provider LLM non valida."""


@dataclass(frozen=True, slots=True)
class LlmLaneConfig:
    """Una lane di classificazione (simple o complex).

    I rate limit sono **per lane** (non condivisi tra SIMPLE e COMPLEX):
    - rpm: richieste al minuto; ``0`` = unmanaged (niente spacing / attesa RPM)
    - tpm: token al minuto; ``0`` = unmanaged
    - rpd: richieste nel giorno locale; ``0`` = unmanaged (niente cap giornaliero / soft-trim)

    SoT:
        skill radar-quota-ledger; SoT LLM §6.
    """

    lane: str
    provider: str
    model: str
    api_key: str
    base_url: str
    rpm: int
    tpm: int
    rpd: int
    budget_usd_day: float
    usd_per_1m_tokens: float
    timeout: float
    reasoning_effort: str
    fallbacks: tuple[str, ...]

    @property
    def available(self) -> bool:
        """True se la lane ha una API key non vuota (pronta per chiamate provider)."""
        return bool(self.api_key)

    @property
    def is_openai_compat(self) -> bool:
        """True se il provider usa l'adapter HTTP OpenAI-compat (httpx)."""
        return self.provider in OPENAI_COMPAT_PROVIDERS

    @property
    def api_dialect(self) -> str:
        """Dialect payload derivato dal provider (thinking vs stock)."""
        return api_dialect_for_provider(self.provider)

    @property
    def models(self) -> tuple[str, ...]:
        """Catena primary + fallback senza duplicati, nell'ordine dichiarato."""
        out: list[str] = [self.model]
        for fb in self.fallbacks:
            if fb and fb not in out:
                out.append(fb)
        return tuple(out)


def normalize_provider(raw: str | None, *, default: str) -> str:
    """Normalizza il nome provider; valore sconosciuto → ``default`` sicuro.

    Args:
        raw: Valore env grezzo (può essere ``None``).
        default: Provider di fallback (es. ``gemini`` / ``deepseek``).
    Returns:
        Token in ``LLM_PROVIDERS``, lowercase.
    """
    value = (raw or default).strip().lower()
    if value not in LLM_PROVIDERS:
        return default
    return value


def _env_raw(name: str) -> str | None:
    """Lettura grezza: ``None`` solo se la chiave è assente da ``os.environ``.

    Distingue unset (chiave mancante) da blank (chiave presente, anche stringa vuota).
    Usata per ``*_FALLBACKS`` e legacy: blank ≠ unset (C-04).
    """
    if name not in os.environ:
        return None
    return os.environ.get(name)


def _env_str_or(name: str, fallback: str) -> str:
    """Stringa env: solo chiave assente → ``fallback``; blank resta stringa strip-pata.

    Diverso da ``config._env_str`` (là blank ≡ default). Qui il blank può ancora
    essere reinterpretato dal chiamante (es. ``or model_default`` su MODEL).
    """
    raw = _env_raw(name)
    if raw is None:
        return fallback
    return raw.strip()


def _csv_models(raw: str | None) -> tuple[str, ...]:
    """CSV di id modello → tupla deduplicata; ``None``/blank → tupla vuota."""
    if not raw or not raw.strip():
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        model = part.strip()
        if not model or model in seen:
            continue
        seen.add(model)
        out.append(model)
    return tuple(out)


def _parse_int(
    name: str,
    *,
    default: int,
    min_value: int,
    max_value: int,
    allow_zero: bool = False,
) -> int:
    """Parse intero lane: chiave assente **o** blank → ``default`` (fill-gap legacy).

    Nota C-04: a differenza di ``*_FALLBACKS``, qui blank ≡ unset.
    ``0`` con ``allow_zero`` significa dimensione unmanaged, non errore di range.
    """
    raw = _env_raw(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise LlmConfigError(f"{name} must be int, got {raw!r}") from exc
    if value == 0 and allow_zero:
        return 0
    if value < min_value or value > max_value:
        raise LlmConfigError(
            f"{name}={value} out of range [{min_value}, {max_value}]"
            + (" (0 allowed)" if allow_zero else "")
        )
    return value


def _parse_float(
    name: str,
    *,
    default: float,
    min_value: float,
    max_value: float,
) -> float:
    """Parse float lane: assente o blank → ``default`` (stessa semantica di ``_parse_int``)."""
    raw = _env_raw(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise LlmConfigError(f"{name} must be float, got {raw!r}") from exc
    if value < min_value or value > max_value:
        raise LlmConfigError(
            f"{name}={value} out of range [{min_value}, {max_value}]"
        )
    return value


def _legacy_api_key(provider: str) -> str:
    """Chiave vendor legacy per ``provider`` se ``LLM_{LANE}_API_KEY`` è vuota.

    Non è Gemini-only: mappa provider → env storica (GOOGLE/GEMINI, DEEPSEEK,
    OPENAI, GLM/ZHIPU, GROK/XAI, ANTHROPIC/CLAUDE).
    """
    if provider == "gemini":
        return (
            (_env_raw("GOOGLE_API_KEY") or "").strip()
            or (_env_raw("GEMINI_API_KEY") or "").strip()
        )
    if provider == "deepseek":
        return (_env_raw("DEEPSEEK_API_KEY") or "").strip()
    if provider == "openai":
        return (_env_raw("OPENAI_API_KEY") or "").strip()
    if provider == "glm":
        return (
            (_env_raw("GLM_API_KEY") or "").strip()
            or (_env_raw("ZHIPU_API_KEY") or "").strip()
        )
    if provider == "grok":
        return (
            (_env_raw("GROK_API_KEY") or "").strip()
            or (_env_raw("XAI_API_KEY") or "").strip()
        )
    if provider == "claude":
        return (
            (_env_raw("ANTHROPIC_API_KEY") or "").strip()
            or (_env_raw("CLAUDE_API_KEY") or "").strip()
        )
    return ""


def _legacy_model(provider: str, *, lane: str) -> str:
    """Default modello vendor quando ``LLM_{LANE}_MODEL`` è unset/blank dopo strip.

    ``lane`` è riservato per estensioni future; oggi i default dipendono dal provider.
    """
    if provider == "gemini":
        raw = (_env_raw("GEMINI_MODEL") or "gemma-4-31b").strip() or "gemma-4-31b"
        return "gemma-4-31b-it" if raw in ("gemma-4-31b", "gemma-4-31b-it") else raw
    if provider == "deepseek":
        return (
            (_env_raw("DEEPSEEK_MODEL") or "deepseek-v4-flash").strip()
            or "deepseek-v4-flash"
        )
    if provider == "openai":
        return "gpt-4.1-mini"
    if provider == "glm":
        return "glm-4-flash"
    if provider == "grok":
        return "grok-3-mini"
    if provider == "claude":
        return "claude-sonnet-4-5"
    return "unknown"


def load_lane(
    lane: str,
    *,
    default_provider: str,
    default_model: str | None = None,
) -> LlmLaneConfig:
    """Carica una lane da ``LLM_{LANE}_*`` con default legacy vendor.

    Ordine tipico per campo:
    1. env lane esplicita (``LLM_SIMPLE_RPM``, …);
    2. se assente (o blank su int/float), default da legacy (``LLM_RPM``,
       ``GEMINI_MODEL_FALLBACKS``, ``DEEPSEEK_*``, …) o costante codice.

    Precedenza ``*_FALLBACKS`` (C-03): se la chiave lane è **presente** — anche
    stringa vuota — vince e non si usa ``GEMINI_MODEL_FALLBACKS``. Solo chiave
    **assente** abilita il fill-gap legacy (SIMPLE) o la tupla vuota (COMPLEX).

    Args:
        lane: ``simple`` o ``complex``.
        default_provider: Provider se ``*_PROVIDER`` assente/invalido.
        default_model: Override del default modello; altrimenti ``_legacy_model``.
    Returns:
        ``LlmLaneConfig`` immutabile con limiti per-lane (``0`` = unmanaged).
    Raises:
        LlmConfigError: lane sconosciuta o valore fuori range.
    SoT:
        SoT LLM §5–6; skill radar-quota-ledger; runbook §LLM (C-03/C-04).
    """
    if lane not in {LANE_SIMPLE, LANE_COMPLEX}:
        raise LlmConfigError(f"unknown lane {lane!r}")

    prefix = f"LLM_{lane.upper()}"
    provider = normalize_provider(
        _env_raw(f"{prefix}_PROVIDER"),
        default=default_provider,
    )

    model_default = default_model or _legacy_model(provider, lane=lane) or "unknown"
    model = _env_str_or(f"{prefix}_MODEL", model_default).strip() or model_default

    api_key = _env_str_or(f"{prefix}_API_KEY", "").strip()
    if not api_key:
        api_key = _legacy_api_key(provider)

    base_default = _PROVIDER_DEFAULT_BASE_URL.get(provider, "")
    if provider == "deepseek":
        base_default = (
            (_env_raw("DEEPSEEK_BASE_URL") or base_default).strip() or base_default
        ).rstrip("/")
    base_url = _env_str_or(f"{prefix}_BASE_URL", base_default).rstrip("/")

    # Default numerici: legacy fill-gap (SIMPLE←LLM_RPM/…; COMPLEX←DEEPSEEK_*).
    if lane == LANE_SIMPLE:
        rpm_default = _parse_int(
            "LLM_RPM", default=10, min_value=0, max_value=10_000, allow_zero=True
        )
        tpm_default = _parse_int(
            "LLM_TPM", default=0, min_value=0, max_value=2_000_000, allow_zero=True
        )
        rpd_default = _parse_int(
            "LLM_RPD", default=1400, min_value=0, max_value=1_000_000, allow_zero=True
        )
        budget_default = 0.0
        usd_default = 0.0
        timeout_default = float(
            _parse_int("GEMINI_REQUEST_TIMEOUT", default=60, min_value=1, max_value=600)
        )
        effort_default = "high"
        fallbacks_default = _csv_models(_env_raw("GEMINI_MODEL_FALLBACKS"))
    else:
        rpm_default = _parse_int(
            "DEEPSEEK_RPM", default=0, min_value=0, max_value=10_000, allow_zero=True
        )
        tpm_default = _parse_int(
            "DEEPSEEK_TPM", default=0, min_value=0, max_value=2_000_000, allow_zero=True
        )
        rpd_default = _parse_int(
            "DEEPSEEK_RPD", default=0, min_value=0, max_value=1_000_000, allow_zero=True
        )
        budget_default = _parse_float(
            "DEEPSEEK_BUDGET_USD_DAY", default=0.0, min_value=0.0, max_value=10_000.0
        )
        usd_default = _parse_float(
            "DEEPSEEK_USD_PER_1M_TOKENS", default=0.28, min_value=0.0, max_value=100.0
        )
        timeout_default = float(
            _parse_int("GEMINI_REQUEST_TIMEOUT", default=60, min_value=1, max_value=600)
        )
        effort_default = (
            (_env_raw("DEEPSEEK_REASONING_EFFORT") or "high").strip().lower() or "high"
        )
        fallbacks_default = ()

    rpm = _parse_int(
        f"{prefix}_RPM",
        default=rpm_default,
        min_value=0,
        max_value=10_000,
        allow_zero=True,
    )
    tpm = _parse_int(
        f"{prefix}_TPM",
        default=tpm_default,
        min_value=0,
        max_value=2_000_000,
        allow_zero=True,
    )
    rpd = _parse_int(
        f"{prefix}_RPD",
        default=rpd_default,
        min_value=0,
        max_value=1_000_000,
        allow_zero=True,
    )
    budget = _parse_float(
        f"{prefix}_BUDGET_USD_DAY",
        default=budget_default,
        min_value=0.0,
        max_value=10_000.0,
    )
    usd = _parse_float(
        f"{prefix}_USD_PER_1M_TOKENS",
        default=usd_default,
        min_value=0.0,
        max_value=100.0,
    )
    timeout = float(
        _parse_int(
            f"{prefix}_TIMEOUT",
            default=int(timeout_default),
            min_value=1,
            max_value=600,
        )
    )
    effort_raw = _env_str_or(f"{prefix}_REASONING_EFFORT", effort_default).lower()
    if effort_raw in {"none", "off", "disabled"}:
        effort = "none"
    elif effort_raw in {"low", "medium", "high", "max"}:
        effort = effort_raw
    else:
        effort = "high"

    # C-03: chiave lane presente (anche "") → CSV lane; solo unset → legacy/default.
    fallbacks_raw = _env_raw(f"{prefix}_FALLBACKS")
    fallbacks = (
        _csv_models(fallbacks_raw) if fallbacks_raw is not None else fallbacks_default
    )

    return LlmLaneConfig(
        lane=lane,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        rpm=rpm,
        tpm=tpm,
        rpd=rpd,
        budget_usd_day=budget,
        usd_per_1m_tokens=usd,
        timeout=timeout,
        reasoning_effort=effort,
        fallbacks=fallbacks,
    )


def load_lanes() -> tuple[LlmLaneConfig, LlmLaneConfig]:
    """Costruisce le due lane di boot: SIMPLE (default gemini) e COMPLEX (default deepseek).

    Returns:
        Coppia ``(LLM_SIMPLE, LLM_COMPLEX)`` usata da ``core.config`` all'import.
    SoT:
        docs/01_getting_started.md (profili A–E); SoT LLM §5.
    """
    simple = load_lane(LANE_SIMPLE, default_provider="gemini")
    complex_lane = load_lane(LANE_COMPLEX, default_provider="deepseek")
    return simple, complex_lane
