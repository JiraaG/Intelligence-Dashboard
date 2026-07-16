"""Per-lane LLM configuration (SIMPLE / COMPLEX), provider-agnostic.

Preferred env (source of truth for limits):
  LLM_SIMPLE_RPM | LLM_SIMPLE_TPM | LLM_SIMPLE_RPD   (0 = unmanaged)
  LLM_COMPLEX_RPM | LLM_COMPLEX_TPM | LLM_COMPLEX_RPD (0 = unmanaged)

Also: PROVIDER, MODEL, API_KEY, BASE_URL, BUDGET_USD_DAY, USD_PER_1M_TOKENS,
TIMEOUT, REASONING_EFFORT, FALLBACKS for each lane.

``PROVIDER`` selects the adapter: gemini | deepseek | openai | claude.
Legacy vendor keys (GEMINI_*, DEEPSEEK_*, LLM_RPM/TPM/RPD) fill gaps only when
the corresponding LLM_SIMPLE_* / LLM_COMPLEX_* key is unset — they are NOT a
shared global quota across both lanes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

LLM_PROVIDERS = frozenset({"gemini", "deepseek", "openai", "claude"})
OPENAI_COMPAT_PROVIDERS = frozenset({"deepseek", "openai"})
LANE_SIMPLE = "simple"
LANE_COMPLEX = "complex"

_PROVIDER_DEFAULT_BASE_URL: Mapping[str, str] = {
    "gemini": "",
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "claude": "https://api.anthropic.com",
}


class LlmConfigError(ValueError):
    """Invalid LLM lane / provider configuration."""


@dataclass(frozen=True, slots=True)
class LlmLaneConfig:
    """One classification lane (simple or complex).

    Rate limits are **per lane** (not shared across SIMPLE/COMPLEX):
    - rpm: requests per minute; ``0`` = unmanaged (no spacing / no RPM wait)
    - tpm: tokens per minute; ``0`` = unmanaged
    - rpd: requests per local day; ``0`` = unmanaged (no day cap / no soft-trim)
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
        return bool(self.api_key)

    @property
    def is_openai_compat(self) -> bool:
        return self.provider in OPENAI_COMPAT_PROVIDERS

    @property
    def models(self) -> tuple[str, ...]:
        out: list[str] = [self.model]
        for fb in self.fallbacks:
            if fb and fb not in out:
                out.append(fb)
        return tuple(out)


def normalize_provider(raw: str | None, *, default: str) -> str:
    value = (raw or default).strip().lower()
    if value not in LLM_PROVIDERS:
        return default
    return value


def _env_raw(name: str) -> str | None:
    if name not in os.environ:
        return None
    return os.environ.get(name)


def _env_str_or(name: str, fallback: str) -> str:
    raw = _env_raw(name)
    if raw is None:
        return fallback
    return raw.strip()


def _csv_models(raw: str | None) -> tuple[str, ...]:
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
    if provider == "gemini":
        return (
            (_env_raw("GOOGLE_API_KEY") or "").strip()
            or (_env_raw("GEMINI_API_KEY") or "").strip()
        )
    if provider == "deepseek":
        return (_env_raw("DEEPSEEK_API_KEY") or "").strip()
    if provider == "openai":
        return (_env_raw("OPENAI_API_KEY") or "").strip()
    if provider == "claude":
        return (
            (_env_raw("ANTHROPIC_API_KEY") or "").strip()
            or (_env_raw("CLAUDE_API_KEY") or "").strip()
        )
    return ""


def _legacy_model(provider: str, *, lane: str) -> str:
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
    if provider == "claude":
        return "claude-sonnet-4-5"
    return "unknown"


def load_lane(
    lane: str,
    *,
    default_provider: str,
    default_model: str | None = None,
) -> LlmLaneConfig:
    """Load one lane from ``LLM_{LANE}_*`` with legacy vendor fallbacks."""
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
    simple = load_lane(LANE_SIMPLE, default_provider="gemini")
    complex_lane = load_lane(LANE_COMPLEX, default_provider="deepseek")
    return simple, complex_lane
