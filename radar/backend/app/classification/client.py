"""Multi-provider classification with durable quota, cascade, and lanes."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any

import asyncpg
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.classification.complexity import Lane, score_complexity
from app.classification.cooldown import ModelCooldownStore
from app.classification.deepseek import DeepSeekClient, DeepSeekError
from app.classification.prompts import SYSTEM_PROMPT, build_user_prompt
from app.classification.quota import QuotaBudgetExceeded, QuotaLedger
from app.classification.validator import GeopoliticalArticleSchema, get_fallback_article, parse_llm_article_json
from app.core.config import (
    ConfigError,
    ESTIMATED_TOKENS_PER_REQUEST,
    GEMINI_MODEL,
    GEMINI_REQUEST_TIMEOUT,
    LLM_API_KEY,
    LLM_COMPLEX,
    LLM_COMPLEXITY_ESCALATE_ON_VALIDATION,
    LLM_MODEL_COOLDOWN_HOURS,
    LLM_ROUTING_MODE,
    LLM_ROUTING_SHADOW,
    LLM_ROUTING_STRICT,
    LLM_SIMPLE,
)
from app.core.llm_lanes import (
    LANE_COMPLEX,
    LANE_SIMPLE,
    LlmLaneConfig,
    OPENAI_COMPAT_PROVIDERS,
)

logger = logging.getLogger("radar.classification.client")

_MAX_ATTEMPTS = 4
_RETRY_AFTER_MAX_SECONDS = 300.0
_PROVIDER_GEMINI = "gemini"
_PROVIDER_DEEPSEEK = "deepseek"
# Gemma often truncates / drifts more than Flash; prefer lower temp + more room.
# Cap below Flash-Lite extremes: 8192 + concurrency=4 was hitting the 60s deadline.
_GEMMA_MAX_OUTPUT_TOKENS = 4096
_GEMMA_TEMPERATURE = 0.1
_DEFAULT_MAX_OUTPUT_TOKENS = 2048
_DEFAULT_TEMPERATURE = 0.3


def _is_gemma_model(model: str) -> bool:
    return "gemma" in (model or "").lower()


def _extract_gemini_text(response: Any) -> str | None:
    """Best-effort text from a generate_content response (never trust .text alone)."""
    direct = getattr(response, "text", None)
    if isinstance(direct, str) and direct.strip():
        return direct
    try:
        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            chunks: list[str] = []
            for part in parts:
                t = getattr(part, "text", None)
                if isinstance(t, str) and t:
                    chunks.append(t)
            if chunks:
                joined = "".join(chunks).strip()
                if joined:
                    return joined
    except Exception:
        pass
    return None


def _exc_msg(exc: BaseException, limit: int = 200) -> str:
    """Human-readable exception text; never empty (some SDK errors have blank str())."""
    text = str(exc).strip() or repr(exc)
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        cause_text = str(cause).strip() or repr(cause)
        if cause_text and cause_text not in text:
            text = f"{text} | cause={cause_text}"
    return text[:limit]


_PROVIDER_OPENAI = "openai"
_PROVIDER_CLAUDE = "claude"

_GEMINI_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "additionalProperties",
        "additional_properties",
    }
)


def sanitize_gemini_response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied JSON Schema safe for Gemini structured outputs."""

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {
                key: _walk(value)
                for key, value in node.items()
                if key not in _GEMINI_UNSUPPORTED_SCHEMA_KEYS
            }
        if isinstance(node, list):
            return [_walk(item) for item in node]
        return node

    cleaned = _walk(schema)
    if not isinstance(cleaned, dict):
        raise TypeError("sanitize_gemini_response_schema expects a dict schema root")
    return cleaned


def build_gemini_response_schema() -> dict[str, Any]:
    """JSON Schema for GenerateContentConfig.response_schema (Gemini-safe)."""
    return sanitize_gemini_response_schema(GeopoliticalArticleSchema.model_json_schema())


class ErrorClass(str, Enum):
    RETRYABLE = "retryable"
    FATAL = "fatal"
    VALIDATION = "validation"
    HARD_COOLDOWN = "hard_cooldown"  # switch model + 24h cooldown


def classify_provider_error(exc: BaseException) -> ErrorClass:
    """
    Retry ONLY transport / 429 / 5xx / timeout.
    HARD_COOLDOWN: daily quota, credits, persistent 5xx already exhausted, model 404.
    FATAL: auth — no cascade value.
    """
    if isinstance(exc, ValidationError):
        return ErrorClass.VALIDATION
    if isinstance(exc, ConfigError):
        return ErrorClass.FATAL

    if isinstance(exc, DeepSeekError):
        code = exc.status_code
        if code in (401, 403):
            return ErrorClass.FATAL
        if code == 402:
            return ErrorClass.HARD_COOLDOWN
        if code == 404:
            return ErrorClass.HARD_COOLDOWN
        if code == 429:
            return ErrorClass.RETRYABLE
        if code is not None and code >= 500:
            return ErrorClass.HARD_COOLDOWN
        if code == 408:
            return ErrorClass.RETRYABLE
        return ErrorClass.RETRYABLE

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return ErrorClass.RETRYABLE
    if isinstance(exc, (ConnectionError, OSError, BrokenPipeError)):
        return ErrorClass.RETRYABLE

    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        message = str(exc).lower()
        if code in (401, 403):
            return ErrorClass.FATAL
        if code == 404:
            return ErrorClass.HARD_COOLDOWN
        if code == 429:
            # RPD / free_tier day → cooldown 24h. RPM breve → RETRYABLE.
            if any(
                token in message
                for token in (
                    "daily",
                    "per day",
                    "rpd",
                    "requests per day",
                    "free_tier_requests",
                    "free tier",
                )
            ):
                return ErrorClass.HARD_COOLDOWN
            return ErrorClass.RETRYABLE
        if code == 408 or (isinstance(code, int) and code >= 500):
            return ErrorClass.RETRYABLE
        if isinstance(code, int) and 400 <= code < 500:
            return ErrorClass.FATAL
        return ErrorClass.RETRYABLE

    message = str(exc).lower()
    if any(
        token in message
        for token in (
            "api key",
            "invalid api key",
            "unauthenticated",
            "permission_denied",
            "permission denied",
        )
    ):
        return ErrorClass.FATAL
    if "not found" in message and "model" in message:
        return ErrorClass.HARD_COOLDOWN
    if any(
        token in message
        for token in ("timeout", "timed out", "connection reset", "temporarily unavailable")
    ):
        return ErrorClass.RETRYABLE
    if any(token in message for token in ("insufficient", "credit", "balance", "402")):
        return ErrorClass.HARD_COOLDOWN

    return ErrorClass.RETRYABLE


def extract_retry_after_seconds(exc: BaseException) -> float | None:
    """Parse authoritative Retry-After from APIError / DeepSeekError."""
    if isinstance(exc, DeepSeekError) and exc.retry_after is not None:
        return max(0.0, min(_RETRY_AFTER_MAX_SECONDS, float(exc.retry_after)))

    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers is not None:
            raw = None
            try:
                raw = headers.get("Retry-After") or headers.get("retry-after")
            except Exception:
                raw = None
            parsed = _parse_retry_after_value(raw)
            if parsed is not None:
                return parsed

    details = getattr(exc, "details", None)
    delay = _retry_delay_from_details(details)
    if delay is not None:
        return delay
    return None


def _parse_retry_after_value(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return max(0.0, min(_RETRY_AFTER_MAX_SECONDS, float(text)))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            from datetime import timezone

            dt = dt.replace(tzinfo=timezone.utc)
        from datetime import datetime, timezone

        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, min(_RETRY_AFTER_MAX_SECONDS, delta))
    except Exception:
        return None


def _retry_delay_from_details(details: Any) -> float | None:
    if details is None:
        return None
    if isinstance(details, dict):
        err = details.get("error") if isinstance(details.get("error"), dict) else details
        for item in err.get("details", []) if isinstance(err, dict) else []:
            if not isinstance(item, dict):
                continue
            delay = item.get("retryDelay") or item.get("retry_delay")
            if isinstance(delay, str) and delay.endswith("s"):
                try:
                    return max(0.0, min(_RETRY_AFTER_MAX_SECONDS, float(delay[:-1])))
                except ValueError:
                    continue
            if isinstance(delay, (int, float)):
                return max(0.0, min(_RETRY_AFTER_MAX_SECONDS, float(delay)))
    return None


def _usage_token_count(response: Any) -> int | None:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    total = getattr(meta, "total_token_count", None)
    if total is None and isinstance(meta, dict):
        total = meta.get("total_token_count")
    try:
        return max(0, int(total))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class _ModelRef:
    provider: str
    model: str
    quota_lane: str  # simple | complex — which lane limits apply
    # Distinguishes same model with different thinking (e.g. flash none vs high).
    reasoning_effort: str = "high"

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.provider, self.model, self.reasoning_effort)

class ClassificationClient:
    """
    Classification with QuotaLedger reserve-before-every-attempt.

    - LLM_ROUTING_MODE=off / shadow: only SIMPLE lane chain.
    - complexity: SIMPLE → LLM_SIMPLE; BORDERLINE+COMPLEX → LLM_COMPLEX; escalate on validation.
    Provider type (gemini|deepseek|openai|claude) selects the adapter.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        *,
        quota: QuotaLedger | None = None,
        cooldown: ModelCooldownStore | None = None,
        deepseek: DeepSeekClient | None = None,
        gemini_sem: asyncio.Semaphore | None = None,
    ) -> None:
        self._simple = LLM_SIMPLE
        self._complex = LLM_COMPLEX

        needs_gemini = (
            self._simple.provider == _PROVIDER_GEMINI
            or self._complex.provider == _PROVIDER_GEMINI
        )
        gemini_key = ""
        if self._simple.provider == _PROVIDER_GEMINI:
            gemini_key = self._simple.api_key
        elif self._complex.provider == _PROVIDER_GEMINI:
            gemini_key = self._complex.api_key
        if not gemini_key:
            gemini_key = LLM_API_KEY or ""

        if needs_gemini and not gemini_key:
            raise ValueError(
                "Chiave API Gemini mancante. Imposta LLM_SIMPLE_API_KEY / "
                "LLM_COMPLEX_API_KEY oppure GEMINI_API_KEY / GOOGLE_API_KEY."
            )
        if quota is None and pool is None:
            raise ValueError("ClassificationClient richiede pool (asyncpg) o un QuotaLedger iniettato.")

        self.pool = pool
        self.quota = quota if quota is not None else QuotaLedger(pool)  # type: ignore[arg-type]
        self.client = genai.Client(api_key=gemini_key) if gemini_key else None
        self.model = (
            self._simple.model
            if self._simple.provider == _PROVIDER_GEMINI
            else (GEMINI_MODEL or "gemma-4-31b")
        )
        self._request_timeout = float(
            max(self._simple.timeout, self._complex.timeout, float(GEMINI_REQUEST_TIMEOUT))
        )
        self._estimated_tokens = int(ESTIMATED_TOKENS_PER_REQUEST)
        self.cooldown = cooldown or ModelCooldownStore(
            pool,
            default_hours=LLM_MODEL_COOLDOWN_HOURS,
        )
        self.deepseek = deepseek  # optional test inject; otherwise built per-lane
        self._compat_clients: dict[str, DeepSeekClient] = {}
        self._gemini_sem = gemini_sem

        self._routing_mode = LLM_ROUTING_MODE
        self._shadow = bool(LLM_ROUTING_SHADOW)
        self._escalate = bool(LLM_COMPLEXITY_ESCALATE_ON_VALIDATION)
        self._simple_provider = self._simple.provider
        self._simple_model = self._simple.model
        self._complex_provider = self._complex.provider
        self._complex_model = self._complex.model

        self._complex_unavailable = False
        if self._complex.provider == _PROVIDER_CLAUDE:
            msg = "LLM_COMPLEX_PROVIDER=claude non ancora supportato — COMPLEX userà SIMPLE"
            if self._routing_mode == "complexity" and LLM_ROUTING_STRICT:
                raise ValueError(msg)
            logger.warning(msg)
            self._complex_unavailable = True
        elif self._complex.provider in OPENAI_COMPAT_PROVIDERS and not self._complex.available:
            msg = (
                f"LLM_COMPLEX_PROVIDER={self._complex.provider} senza API key — "
                "COMPLEX userà la lane SIMPLE"
            )
            if self._routing_mode == "complexity" and LLM_ROUTING_STRICT:
                raise ValueError(msg)
            logger.warning(msg)
            self._complex_unavailable = True
        elif self._complex.provider == _PROVIDER_GEMINI and not self._complex.available:
            msg = "LLM_COMPLEX_PROVIDER=gemini senza API key — COMPLEX userà SIMPLE"
            if self._routing_mode == "complexity" and LLM_ROUTING_STRICT:
                raise ValueError(msg)
            logger.warning(msg)
            self._complex_unavailable = True

        if self._simple.provider == _PROVIDER_CLAUDE:
            raise ValueError("LLM_SIMPLE_PROVIDER=claude non ancora supportato.")
        if self._simple.provider in OPENAI_COMPAT_PROVIDERS and not self._simple.available:
            raise ValueError(
                f"LLM_SIMPLE_PROVIDER={self._simple.provider} richiede LLM_SIMPLE_API_KEY "
                "(o legacy DEEPSEEK_API_KEY / OPENAI_API_KEY)."
            )
        if self._simple.provider == _PROVIDER_GEMINI and not self._simple.available and not gemini_key:
            raise ValueError("LLM_SIMPLE_PROVIDER=gemini richiede una API key.")

        logger.info(
            "ClassificationClient pronto. simple=%s/%s complex=%s/%s routing=%s shadow=%s "
            "timeout=%ss limits simple(RPM=%s RPD=%s budget=%s) complex(RPM=%s RPD=%s budget=%s)",
            self._simple_provider,
            self._simple_model,
            self._complex_provider,
            self._complex_model,
            self._routing_mode,
            self._shadow,
            self._request_timeout,
            self._simple.rpm,
            self._simple.rpd,
            self._simple.budget_usd_day,
            self._complex.rpm,
            self._complex.rpd,
            self._complex.budget_usd_day,
        )

    def _lane_cfg(self, quota_lane: str) -> LlmLaneConfig:
        return self._simple if quota_lane == LANE_SIMPLE else self._complex

    def _compat_client(self, quota_lane: str) -> DeepSeekClient:
        if self.deepseek is not None and self._lane_cfg(quota_lane).provider == _PROVIDER_DEEPSEEK:
            return self.deepseek
        cached = self._compat_clients.get(quota_lane)
        if cached is not None:
            return cached
        cfg = self._lane_cfg(quota_lane)
        client = DeepSeekClient(
            api_key=cfg.api_key,
            base_url=cfg.base_url or None,
            model=cfg.model,
            effort=cfg.reasoning_effort,
            timeout=cfg.timeout,
            api_dialect=cfg.api_dialect,
        )
        self._compat_clients[quota_lane] = client
        return client

    async def _generate_content(
        self,
        *,
        contents: Any,
        model: str | None = None,
    ) -> Any:
        """Call Gemini via async SDK under application deadline (+ optional concurrency sem)."""
        use_model = model or self.model
        gemma = _is_gemma_model(use_model)
        temperature = _GEMMA_TEMPERATURE if gemma else _DEFAULT_TEMPERATURE
        max_output_tokens = _GEMMA_MAX_OUTPUT_TOKENS if gemma else _DEFAULT_MAX_OUTPUT_TOKENS

        async def _call() -> Any:
            if self.client is None:
                raise ConfigError("Gemini client non configurato")
            return await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=use_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=build_gemini_response_schema(),
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    ),
                ),
                timeout=self._request_timeout,
            )

        if self._gemini_sem is not None:
            async with self._gemini_sem:
                return await _call()
        return await _call()

    def _provider_refs(self, cfg: LlmLaneConfig) -> list[_ModelRef]:
        if cfg.provider == _PROVIDER_CLAUDE:
            return []
        if cfg.provider in OPENAI_COMPAT_PROVIDERS:
            return [
                _ModelRef(cfg.provider, m, cfg.lane, cfg.reasoning_effort)
                for m in cfg.models
            ]
        # gemini (and unknown → treat as gemini-shaped cascade)
        return [
            _ModelRef(_PROVIDER_GEMINI, m, cfg.lane, cfg.reasoning_effort)
            for m in cfg.models
        ]

    def _simple_chain(self) -> list[_ModelRef]:
        """
        Catena lane SIMPLE.

        - Primary: solo modelli di LLM_SIMPLE (niente CSV Gemini fallback).
        - Residual: lane COMPLEX se diversa (provider/model/effort) — cooldown/esaurimento.
        """
        primary = self._provider_refs(self._simple)
        simple_id = (
            self._simple.provider,
            self._simple.model,
            self._simple.reasoning_effort,
        )
        complex_id = (
            self._complex.provider,
            self._complex.model,
            self._complex.reasoning_effort,
        )
        if (
            self._routing_mode == "complexity"
            and not self._complex_unavailable
            and simple_id != complex_id
        ):
            # Cross-lane residual only — no same-provider Gemini CSV fallbacks.
            residual = self._provider_refs(self._complex)
            out: list[_ModelRef] = []
            seen: set[tuple[str, str, str]] = set()
            for ref in [*primary, *residual]:
                if ref.identity in seen:
                    continue
                seen.add(ref.identity)
                out.append(ref)
            return out
        return primary

    def _complex_chain(self) -> list[_ModelRef]:
        """
        Catena lane COMPLEX.

        - Primary: LLM_COMPLEX.
        - Residual: solo LLM_SIMPLE (viceversa su quota/cooldown COMPLEX).
        """
        primary = self._provider_refs(self._complex)
        residual = self._provider_refs(self._simple)
        out: list[_ModelRef] = []
        seen: set[tuple[str, str, str]] = set()
        for ref in [*primary, *residual]:
            if ref.identity in seen:
                continue
            seen.add(ref.identity)
            out.append(ref)
        return out

    def _chain_for(self, lane: Lane, *, force_simple: bool) -> list[_ModelRef]:
        if force_simple or self._routing_mode != "complexity":
            return self._simple_chain()
        # BORDERLINE = schema risk (geo/entity/script) → thinking-capable lane.
        if lane in (Lane.COMPLEX, Lane.BORDERLINE) and not self._complex_unavailable:
            return self._complex_chain()
        return self._simple_chain()

    async def _eligible(self, refs: list[_ModelRef]) -> list[_ModelRef]:
        out: list[_ModelRef] = []
        for ref in refs:
            if await self.cooldown.is_cooling_down(ref.provider, ref.model):
                logger.info("Skip cooldown %s/%s", ref.provider, ref.model)
                continue
            if ref.provider == _PROVIDER_CLAUDE:
                continue
            if ref.provider in OPENAI_COMPAT_PROVIDERS:
                if not self._compat_client(ref.quota_lane).available:
                    continue
            if ref.provider == _PROVIDER_GEMINI and self.client is None:
                continue
            out.append(ref)
        return out

    async def classify_article(
        self,
        title: str,
        content: str,
        url: str,
        date: str,
    ) -> GeopoliticalArticleSchema:
        """Extract structured geopolitics; cascade / escalate per routing mode."""
        truncated = content[:4000]
        complexity = score_complexity(title, content)
        lane = complexity.lane
        force_simple = (
            self._routing_mode != "complexity"
            or self._shadow
            or (
                lane in (Lane.COMPLEX, Lane.BORDERLINE)
                and self._complex_unavailable
            )
        )

        logger.info(
            "classify lane=%s families=%s score=%s shadow=%s mode=%s "
            "simple=%s/%s complex=%s/%s title=%r",
            lane.value,
            sorted(complexity.families),
            complexity.score,
            self._shadow and self._routing_mode == "complexity",
            self._routing_mode,
            self._simple_provider,
            self._simple_model,
            self._complex_provider,
            self._complex_model,
            title[:50],
        )

        chain = await self._eligible(self._chain_for(lane, force_simple=force_simple))
        if chain:
            primary = chain[0]
            logger.info(
                "route lane=%s → %s/%s effort=%s",
                lane.value,
                primary.provider,
                primary.model,
                primary.reasoning_effort,
            )
        if not chain:
            logger.error("Nessun modello eleggibile (tutti in cooldown). Fallback.")
            return get_fallback_article(title, url, date)

        escalate_ref = _ModelRef(
            self._complex_provider,
            self._complex_model,
            LANE_COMPLEX,
            self._complex.reasoning_effort,
        )
        escalated = False
        for ref in chain:
            article, outcome = await self._run_model_attempts(
                ref,
                title=title,
                content=truncated,
                url=url,
                date=date,
                lane=lane,
            )
            if article is not None:
                logger.info(
                    "OK model=%s/%s effort=%s lane=%s escalated=%s",
                    ref.provider,
                    ref.model,
                    ref.reasoning_effort,
                    lane.value,
                    escalated,
                )
                return article

            if outcome == "fatal_auth":
                return get_fallback_article(title, url, date)

            can_escalate = (
                outcome == "escalate"
                and self._escalate
                and not escalated
                and not force_simple
                and not self._complex_unavailable
                and ref.identity != escalate_ref.identity
                and not await self.cooldown.is_cooling_down(
                    escalate_ref.provider, escalate_ref.model
                )
            )
            if can_escalate and escalate_ref.provider in OPENAI_COMPAT_PROVIDERS:
                can_escalate = self._compat_client(LANE_COMPLEX).available
            if can_escalate and escalate_ref.provider == _PROVIDER_CLAUDE:
                can_escalate = False
            if can_escalate:
                escalated = True
                article, _ = await self._run_model_attempts(
                    escalate_ref,
                    title=title,
                    content=truncated,
                    url=url,
                    date=date,
                    lane=lane,
                    max_attempts=2,
                )
                if article is not None:
                    logger.info(
                        "Escalation %s/%s OK per '%s'",
                        escalate_ref.provider,
                        escalate_ref.model,
                        title[:50],
                    )
                    return article
                continue

            continue

        logger.error("Tutti i modelli esauriti per '%s'. Fallback.", title[:50])
        return get_fallback_article(title, url, date)

    async def _run_model_attempts(
        self,
        ref: _ModelRef,
        *,
        title: str,
        content: str,
        url: str,
        date: str,
        lane: Lane,
        max_attempts: int | None = None,
    ) -> tuple[GeopoliticalArticleSchema | None, str]:
        """
        Returns (article|None, outcome) where outcome is:
        ok | exhausted | escalate | fatal_auth | hard_cooldown
        """
        attempts = max_attempts if max_attempts is not None else _MAX_ATTEMPTS
        user_message = build_user_prompt(
            title=title,
            url=url,
            date=date,
            content=content,
        )
        history = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
        ]
        correction: str | None = None
        validation_fails = 0

        # Preserve legacy single-model attribute for tests / logging.
        if ref.provider == _PROVIDER_GEMINI:
            self.model = ref.model

        for attempt in range(attempts):
            try:
                reservation_id = await self.quota.reserve(
                    estimated_tokens=self._estimated_tokens,
                    model=ref.model,
                    lane=ref.quota_lane,
                    provider=ref.provider,
                )
            except QuotaBudgetExceeded as budget_err:
                logger.warning(
                    "Skip %s/%s (budget): %s",
                    ref.provider,
                    ref.model,
                    budget_err,
                )
                # Soft-cap USD: skip provider for this article — no 24h model cooldown.
                return None, "exhausted"
            response_text: str | None = None
            provider_started = False
            try:
                if attempt == 0:
                    logger.info(
                        "Invio articolo a %s/%s per '%s'",
                        ref.provider,
                        ref.model,
                        title[:50],
                    )
                else:
                    logger.warning(
                        "Tentativo %d/%d %s/%s per '%s'",
                        attempt + 1,
                        attempts,
                        ref.provider,
                        ref.model,
                        title[:50],
                    )

                provider_started = True
                if ref.provider in OPENAI_COMPAT_PROVIDERS:
                    compat = self._compat_client(ref.quota_lane)
                    response_text, tokens = await compat.classify_json(
                        title=title,
                        content=content,
                        url=url,
                        date=date,
                        correction=correction,
                        model=ref.model,
                    )
                    actual = tokens if tokens is not None else self._estimated_tokens
                    await self.quota.complete(reservation_id, actual)
                    reservation_id = -1
                    extracted = parse_llm_article_json(
                        response_text,
                        source_url=url,
                        published_at=date,
                    )
                    return extracted, "ok"

                if ref.provider == _PROVIDER_CLAUDE:
                    raise ConfigError("Provider claude non ancora supportato")

                contents = history if attempt > 0 else user_message
                response = await self._generate_content(contents=contents, model=ref.model)
                actual_tokens = _usage_token_count(response)
                await self.quota.complete(
                    reservation_id,
                    actual_tokens if actual_tokens is not None else self._estimated_tokens,
                )
                reservation_id = -1
                response_text = _extract_gemini_text(response)
                extracted = parse_llm_article_json(
                    response_text,
                    source_url=url,
                    published_at=date,
                )
                if attempt > 0:
                    logger.info(
                        "Auto-correzione riuscita al tentativo %d per '%s'",
                        attempt + 1,
                        title[:50],
                    )
                return extracted, "ok"

            except asyncio.CancelledError:
                if reservation_id >= 0:
                    try:
                        if provider_started:
                            await self.quota.fail(reservation_id)
                        else:
                            await self.quota.release(reservation_id)
                    except Exception as cleanup_err:
                        logger.warning(
                            "Cleanup reservation %s durante cancel fallito: %s",
                            reservation_id,
                            cleanup_err,
                        )
                raise

            except ValidationError as e:
                error_msg = _exc_msg(e, 400)
                validation_fails += 1
                logger.error(
                    "Validazione tentativo %d %s/%s per '%s': %s",
                    attempt + 1,
                    ref.provider,
                    ref.model,
                    title[:50],
                    error_msg[:200],
                )
                if reservation_id >= 0:
                    await self.quota.fail(reservation_id)

                # Capture Gemini raw text if validate failed after a successful generate.
                if (
                    ref.provider == _PROVIDER_GEMINI
                    and response_text is None
                    and "response" in locals()
                ):
                    response_text = _extract_gemini_text(response)

                # BORDERLINE: escalate after first failed correction (any SIMPLE provider)
                if (
                    lane == Lane.BORDERLINE
                    and self._escalate
                    and validation_fails >= 2
                ):
                    return None, "escalate"

                if (
                    ref.provider == _PROVIDER_GEMINI
                    and attempt == 0
                    and response_text
                ):
                    history.append(
                        types.Content(
                            role="model",
                            parts=[types.Part.from_text(text=response_text)],
                        )
                    )
                correction = (
                    f"L'output precedente ha fallito con errore di validazione:\n{error_msg[:300]}\n"
                    "Correggi l'output e restituisci SOLO un JSON valido secondo lo schema "
                    "(senza campo reasoning)."
                )
                if ref.provider == _PROVIDER_GEMINI:
                    history.append(
                        types.Content(
                            role="user",
                            parts=[types.Part.from_text(text=correction)],
                        )
                    )
                continue

            except ConfigError:
                if reservation_id >= 0:
                    await self.quota.release(reservation_id)
                raise

            except Exception as e:
                kind = classify_provider_error(e)
                if reservation_id >= 0:
                    await self.quota.fail(reservation_id)

                if kind == ErrorClass.FATAL:
                    logger.error(
                        "Errore FATAL %s/%s per '%s': %s",
                        ref.provider,
                        ref.model,
                        title[:50],
                        _exc_msg(e),
                    )
                    return None, "fatal_auth"

                if kind == ErrorClass.HARD_COOLDOWN:
                    await self.cooldown.set_cooldown(
                        ref.provider,
                        ref.model,
                        reason=_exc_msg(e),
                    )
                    if ref.provider == _PROVIDER_DEEPSEEK:
                        logger.warning(
                            "complex_lane deepseek cooldown model=%s",
                            ref.model,
                        )
                    return None, "hard_cooldown"

                retry_after = extract_retry_after_seconds(e)
                is_429 = (
                    (isinstance(e, genai_errors.APIError) and getattr(e, "code", None) == 429)
                    or (isinstance(e, DeepSeekError) and e.status_code == 429)
                )
                if is_429:
                    # Floor avoids Retry-After=0 thundering herd against Studio RPM.
                    delay = 5.0 if retry_after is None else max(float(retry_after), 5.0)
                    delay = min(delay, _RETRY_AFTER_MAX_SECONDS)
                    logger.warning(
                        "429 Retry-After=%.1fs %s/%s per '%s'",
                        delay,
                        ref.provider,
                        ref.model,
                        title[:50],
                    )
                    await asyncio.sleep(delay)
                elif attempt < attempts - 1:
                    backoff = float(attempt + 1) * 4.0
                    logger.warning(
                        "Retryable tentativo %d %s/%s: %s. Sleep %.1fs",
                        attempt + 1,
                        ref.provider,
                        ref.model,
                        _exc_msg(e),
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    # Exhausted retries on this model — cooldown on repeated 5xx
                    if isinstance(e, genai_errors.APIError) and getattr(e, "code", None) is not None:
                        code = getattr(e, "code", None)
                        if isinstance(code, int) and code >= 500:
                            await self.cooldown.set_cooldown(
                                ref.provider,
                                ref.model,
                                reason=f"5xx exhausted: {_exc_msg(e)}",
                            )
                            return None, "hard_cooldown"
                    logger.error(
                        "Esauriti tentativi %s/%s per '%s': %s",
                        ref.provider,
                        ref.model,
                        title[:50],
                        _exc_msg(e),
                    )

        # Validation exhausted on SIMPLE lane primary → escalate once to COMPLEX
        if (
            lane == Lane.SIMPLE
            and self._escalate
            and validation_fails > 0
            and ref.quota_lane == LANE_SIMPLE
        ):
            return None, "escalate"
        return None, "exhausted"
