"""Gemini (+ optional DeepSeek) classification with durable quota, cascade, and lanes."""

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
from app.classification.quota import QuotaLedger
from app.classification.validator import GeopoliticalArticleSchema, get_fallback_article
from app.core.config import (
    ConfigError,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    ESTIMATED_TOKENS_PER_REQUEST,
    GEMINI_MODEL,
    GEMINI_REQUEST_TIMEOUT,
    LLM_API_KEY,
    LLM_COMPLEXITY_ESCALATE_ON_VALIDATION,
    LLM_MODEL_COOLDOWN_HOURS,
    LLM_ROUTING_MODE,
    LLM_ROUTING_SHADOW,
    LLM_ROUTING_STRICT,
    LLM_RPM,
    LLM_TPM,
    gemini_model_chain,
)

logger = logging.getLogger("radar.classification.client")

_MAX_ATTEMPTS = 4
_RETRY_AFTER_MAX_SECONDS = 300.0
_PROVIDER_GEMINI = "gemini"
_PROVIDER_DEEPSEEK = "deepseek"

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
            # Daily / resource exhausted → cooldown; short Retry-After stays retryable.
            if any(
                token in message
                for token in ("daily", "resource exhausted", "quota exceeded", "per day", "rpd")
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


@dataclass
class _ModelRef:
    provider: str
    model: str


class ClassificationClient:
    """
    Classification with QuotaLedger reserve-before-every-attempt.

    - LLM_ROUTING_MODE=off: Gemini cascade (primary + fallbacks), no DeepSeek lane.
    - complexity + shadow: log lane, still Gemini-only.
    - complexity + !shadow: COMPLEX → DeepSeek first; escalate rules per lane.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        *,
        quota: QuotaLedger | None = None,
        cooldown: ModelCooldownStore | None = None,
        deepseek: DeepSeekClient | None = None,
    ) -> None:
        if not LLM_API_KEY:
            raise ValueError("Chiave API LLM mancante. Configura GOOGLE_API_KEY o GEMINI_API_KEY.")
        if quota is None and pool is None:
            raise ValueError("ClassificationClient richiede pool (asyncpg) o un QuotaLedger iniettato.")

        self.pool = pool
        self.quota = quota if quota is not None else QuotaLedger(pool)  # type: ignore[arg-type]
        self.client = genai.Client(api_key=LLM_API_KEY)
        self.model = GEMINI_MODEL or "gemma-4-31b"
        self._request_timeout = float(GEMINI_REQUEST_TIMEOUT)
        self._estimated_tokens = int(ESTIMATED_TOKENS_PER_REQUEST)
        self.cooldown = cooldown or ModelCooldownStore(
            pool,
            default_hours=LLM_MODEL_COOLDOWN_HOURS,
        )
        self.deepseek = deepseek if deepseek is not None else DeepSeekClient()

        self._routing_mode = LLM_ROUTING_MODE
        self._shadow = bool(LLM_ROUTING_SHADOW)
        self._escalate = bool(LLM_COMPLEXITY_ESCALATE_ON_VALIDATION)

        if self._routing_mode == "complexity" and not self.deepseek.available:
            msg = (
                "LLM_ROUTING_MODE=complexity ma DEEPSEEK_API_KEY assente — "
                "fallback a Gemini-only (mode effettivo off per paid lane)"
            )
            if LLM_ROUTING_STRICT:
                raise ValueError(msg)
            logger.warning(msg)
            self._paid_unavailable = True
        else:
            self._paid_unavailable = not self.deepseek.available

        logger.info(
            "ClassificationClient pronto. Modello=%s chain=%s routing=%s shadow=%s "
            "timeout=%ss (RPM=%s TPM=%s) deepseek=%s",
            self.model,
            gemini_model_chain(),
            self._routing_mode,
            self._shadow,
            self._request_timeout,
            LLM_RPM,
            LLM_TPM,
            bool(self.deepseek.available),
        )

    async def _generate_content(
        self,
        *,
        contents: Any,
        model: str | None = None,
    ) -> Any:
        """Call Gemini via async SDK under application deadline."""
        use_model = model or self.model
        return await asyncio.wait_for(
            self.client.aio.models.generate_content(
                model=use_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=build_gemini_response_schema(),
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            ),
            timeout=self._request_timeout,
        )

    def _gemini_chain_refs(self) -> list[_ModelRef]:
        return [_ModelRef(_PROVIDER_GEMINI, m) for m in gemini_model_chain()]

    def _chain_for(self, lane: Lane, *, force_gemini: bool) -> list[_ModelRef]:
        gemini = self._gemini_chain_refs()
        if force_gemini or self._routing_mode != "complexity" or self._paid_unavailable:
            return gemini
        if lane == Lane.COMPLEX:
            return [_ModelRef(_PROVIDER_DEEPSEEK, DEEPSEEK_MODEL), *gemini]
        return gemini

    async def _eligible(self, refs: list[_ModelRef]) -> list[_ModelRef]:
        out: list[_ModelRef] = []
        for ref in refs:
            if await self.cooldown.is_cooling_down(ref.provider, ref.model):
                logger.info("Skip cooldown %s/%s", ref.provider, ref.model)
                continue
            if ref.provider == _PROVIDER_DEEPSEEK and not self.deepseek.available:
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
        force_gemini = (
            self._routing_mode != "complexity"
            or self._shadow
            or self._paid_unavailable
        )

        logger.info(
            "classify lane=%s families=%s score=%s shadow=%s mode=%s title=%r",
            lane.value,
            sorted(complexity.families),
            complexity.score,
            self._shadow and self._routing_mode == "complexity",
            self._routing_mode,
            title[:50],
        )

        chain = await self._eligible(self._chain_for(lane, force_gemini=force_gemini))
        if not chain:
            logger.error("Nessun modello eleggibile (tutti in cooldown). Fallback.")
            return get_fallback_article(title, url, date)

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
                    "OK model=%s/%s lane=%s escalated=%s",
                    ref.provider,
                    ref.model,
                    lane.value,
                    escalated,
                )
                return article

            if outcome == "fatal_auth":
                return get_fallback_article(title, url, date)

            if (
                outcome == "escalate"
                and self._escalate
                and not escalated
                and not force_gemini
                and self.deepseek.available
                and not await self.cooldown.is_cooling_down(_PROVIDER_DEEPSEEK, DEEPSEEK_MODEL)
            ):
                escalated = True
                ds_ref = _ModelRef(_PROVIDER_DEEPSEEK, DEEPSEEK_MODEL)
                article, _ = await self._run_model_attempts(
                    ds_ref,
                    title=title,
                    content=truncated,
                    url=url,
                    date=date,
                    lane=lane,
                    max_attempts=2,
                )
                if article is not None:
                    logger.info("Escalation DeepSeek OK per '%s'", title[:50])
                    return article
                continue

            # hard_cooldown / exhausted → next model in chain
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
            reservation_id = await self.quota.reserve(
                estimated_tokens=self._estimated_tokens,
                model=ref.model,
                purpose="classify_article",
            )
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
                if ref.provider == _PROVIDER_DEEPSEEK:
                    response_text, tokens = await self.deepseek.classify_json(
                        title=title,
                        content=content,
                        url=url,
                        date=date,
                        correction=correction,
                    )
                    actual = tokens if tokens is not None else self._estimated_tokens
                    await self.quota.complete(reservation_id, actual)
                    reservation_id = -1
                    extracted = GeopoliticalArticleSchema.model_validate_json(response_text)
                    return extracted, "ok"

                contents = history if attempt > 0 else user_message
                response = await self._generate_content(contents=contents, model=ref.model)
                actual_tokens = _usage_token_count(response)
                await self.quota.complete(
                    reservation_id,
                    actual_tokens if actual_tokens is not None else self._estimated_tokens,
                )
                reservation_id = -1
                response_text = response.text
                extracted = GeopoliticalArticleSchema.model_validate_json(response_text)
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
                error_msg = str(e)
                validation_fails += 1
                logger.error(
                    "Validazione tentativo %d %s/%s per '%s': %s",
                    attempt + 1,
                    ref.provider,
                    ref.model,
                    title[:50],
                    error_msg[:150],
                )
                if reservation_id >= 0:
                    await self.quota.fail(reservation_id)

                # Capture Gemini raw text if validate failed after a successful generate.
                if (
                    ref.provider == _PROVIDER_GEMINI
                    and response_text is None
                    and "response" in locals()
                    and getattr(response, "text", None)
                ):
                    response_text = response.text

                # BORDERLINE: escalate after first failed correction
                if (
                    lane == Lane.BORDERLINE
                    and self._escalate
                    and validation_fails >= 2
                    and ref.provider == _PROVIDER_GEMINI
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
                        str(e)[:150],
                    )
                    return None, "fatal_auth"

                if kind == ErrorClass.HARD_COOLDOWN:
                    await self.cooldown.set_cooldown(
                        ref.provider,
                        ref.model,
                        reason=str(e)[:200],
                    )
                    if ref.provider == _PROVIDER_DEEPSEEK:
                        logger.warning("paid_unavailable=1 (DeepSeek cooldown)")
                    return None, "hard_cooldown"

                retry_after = extract_retry_after_seconds(e)
                is_429 = (
                    (isinstance(e, genai_errors.APIError) and getattr(e, "code", None) == 429)
                    or (isinstance(e, DeepSeekError) and e.status_code == 429)
                )
                if retry_after is not None and is_429:
                    logger.warning(
                        "429 Retry-After=%.1fs %s/%s per '%s'",
                        retry_after,
                        ref.provider,
                        ref.model,
                        title[:50],
                    )
                    await asyncio.sleep(retry_after)
                elif attempt < attempts - 1:
                    backoff = float(attempt + 1) * 4.0
                    logger.warning(
                        "Retryable tentativo %d %s/%s: %s. Sleep %.1fs",
                        attempt + 1,
                        ref.provider,
                        ref.model,
                        str(e)[:150],
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
                                reason=f"5xx exhausted: {e}"[:200],
                            )
                            return None, "hard_cooldown"
                    logger.error(
                        "Esauriti tentativi %s/%s per '%s': %s",
                        ref.provider,
                        ref.model,
                        title[:50],
                        str(e)[:150],
                    )

        # Validation exhausted on SIMPLE → escalate once
        if (
            lane == Lane.SIMPLE
            and self._escalate
            and validation_fails > 0
            and ref.provider == _PROVIDER_GEMINI
        ):
            return None, "escalate"
        return None, "exhausted"
