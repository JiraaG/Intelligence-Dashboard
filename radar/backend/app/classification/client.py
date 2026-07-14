"""Gemini classification client with durable quota, deadline, and classified retry."""

from __future__ import annotations

import asyncio
import logging
import re
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any

import asyncpg
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.classification.prompts import SYSTEM_PROMPT, build_user_prompt
from app.classification.quota import QuotaLedger
from app.classification.validator import GeopoliticalArticleSchema, get_fallback_article
from app.core.config import (
    ConfigError,
    ESTIMATED_TOKENS_PER_REQUEST,
    GEMINI_MODEL,
    GEMINI_REQUEST_TIMEOUT,
    LLM_API_KEY,
    LLM_RPM,
    LLM_TPM,
)

logger = logging.getLogger("radar.classification.client")

_MAX_ATTEMPTS = 4
_RETRY_AFTER_MAX_SECONDS = 300.0


class ErrorClass(str, Enum):
    """Classification of provider / local failures for retry policy."""

    RETRYABLE = "retryable"
    FATAL = "fatal"
    VALIDATION = "validation"


def classify_provider_error(exc: BaseException) -> ErrorClass:
    """
    Retry ONLY transport / 429 / 5xx / timeout.
    Do NOT retry: auth, model-not-found, ConfigError, ValidationError (handled separately).
    """
    if isinstance(exc, ValidationError):
        return ErrorClass.VALIDATION
    if isinstance(exc, ConfigError):
        return ErrorClass.FATAL
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return ErrorClass.RETRYABLE
    if isinstance(exc, (ConnectionError, OSError, BrokenPipeError)):
        return ErrorClass.RETRYABLE

    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None)
        if code in (401, 403):
            return ErrorClass.FATAL
        if code == 404:
            return ErrorClass.FATAL
        if code == 429 or code == 408 or (isinstance(code, int) and code >= 500):
            return ErrorClass.RETRYABLE
        # Other 4xx (invalid argument, etc.) — fail fast.
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
        return ErrorClass.FATAL
    if any(
        token in message
        for token in ("timeout", "timed out", "connection reset", "temporarily unavailable")
    ):
        return ErrorClass.RETRYABLE

    # Unknown errors: treat as retryable so transient SDK wrappers still recover.
    return ErrorClass.RETRYABLE


def extract_retry_after_seconds(exc: BaseException) -> float | None:
    """Parse authoritative Retry-After from APIError response headers or details."""
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
    from datetime import datetime, timezone

    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        seconds = None
    else:
        if seconds < 0:
            return None
        return min(_RETRY_AFTER_MAX_SECONDS, seconds)

    try:
        when = parsedate_to_datetime(text)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        delta = (when - datetime.now(timezone.utc)).total_seconds()
        if delta < 0:
            return 0.0
        return min(_RETRY_AFTER_MAX_SECONDS, delta)
    except (TypeError, ValueError, OverflowError, IndexError):
        return None


def _retry_delay_from_details(details: Any) -> float | None:
    if details is None:
        return None
    if isinstance(details, dict):
        # google.rpc.RetryInfo nested under error.details[]
        error = details.get("error") if "error" in details else details
        if isinstance(error, dict):
            nested = error.get("details")
            if isinstance(nested, list):
                for item in nested:
                    if not isinstance(item, dict):
                        continue
                    retry_delay = item.get("retryDelay") or item.get("retry_delay")
                    parsed = _parse_google_duration(retry_delay)
                    if parsed is not None:
                        return parsed
            retry_delay = error.get("retryDelay") or error.get("retry_delay")
            parsed = _parse_google_duration(retry_delay)
            if parsed is not None:
                return parsed
    return None


def _parse_google_duration(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return min(_RETRY_AFTER_MAX_SECONDS, max(0.0, float(value)))
    text = str(value).strip()
    if not text:
        return None
    # e.g. "3.5s" or "3s"
    match = re.fullmatch(r"(\d+(?:\.\d+)?)s?", text)
    if match:
        return min(_RETRY_AFTER_MAX_SECONDS, float(match.group(1)))
    return None


def _usage_token_count(response: Any) -> int | None:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return None
    total = getattr(meta, "total_token_count", None)
    if total is None:
        return None
    try:
        return max(0, int(total))
    except (TypeError, ValueError):
        return None


class ClassificationClient:
    """
    Client di classificazione geopolitica asincrono (google-genai).

    - Reserve durable via QuotaLedger before EVERY provider attempt (incl. validation retries).
    - Application deadline via asyncio.wait_for around async SDK generate_content.
    - Classified retry: transport/429/5xx/timeout only; auth/model/ConfigError fail fast.
    """

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        *,
        quota: QuotaLedger | None = None,
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

        logger.info(
            "ClassificationClient pronto. Modello=%s timeout=%ss (RPM=%s TPM=%s) async SDK",
            self.model,
            self._request_timeout,
            LLM_RPM,
            LLM_TPM,
        )

    async def _generate_content(
        self,
        *,
        contents: Any,
    ) -> Any:
        """
        Call Gemini via the async SDK under an application deadline.

        Prefer client.aio.models.generate_content so wait_for can cancel the awaitable.
        If a sync fallback via asyncio.to_thread were used instead, cancellation after
        the thread starts cannot kill the underlying HTTP request.
        """
        return await asyncio.wait_for(
            self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=GeopoliticalArticleSchema,
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            ),
            timeout=self._request_timeout,
        )

    async def classify_article(
        self,
        title: str,
        content: str,
        url: str,
        date: str,
    ) -> GeopoliticalArticleSchema:
        """
        Invia il testo a Gemma ed estrae dati geopolitici strutturati.
        Correction loop multi-tentativo; nessun campo reasoning nello schema.
        """
        user_message = build_user_prompt(
            title=title,
            url=url,
            date=date,
            content=content[:4000],
        )

        history = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
        ]

        for attempt in range(_MAX_ATTEMPTS):
            reservation_id = await self.quota.reserve(
                estimated_tokens=self._estimated_tokens,
                model=self.model,
                purpose="classify_article",
            )

            response = None
            provider_started = False
            try:
                if attempt == 0:
                    logger.info("Invio articolo a LLM (Gemma) per '%s'", title[:50])
                else:
                    logger.warning(
                        "Tentativo %d/%d per '%s'",
                        attempt + 1,
                        _MAX_ATTEMPTS,
                        title[:50],
                    )

                contents = history if attempt > 0 else user_message
                provider_started = True
                response = await self._generate_content(contents=contents)

                actual_tokens = _usage_token_count(response)
                await self.quota.complete(
                    reservation_id,
                    actual_tokens if actual_tokens is not None else self._estimated_tokens,
                )
                reservation_id = -1  # already finalized

                extracted = GeopoliticalArticleSchema.model_validate_json(response.text)
                if attempt > 0:
                    logger.info(
                        "Auto-correzione riuscita al tentativo %d per '%s'",
                        attempt + 1,
                        title[:50],
                    )
                return extracted

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
                logger.error(
                    "Errore di validazione al tentativo %d per '%s': %s",
                    attempt + 1,
                    title[:50],
                    error_msg[:150],
                )
                # Usage already completed above when response arrived; if validate failed
                # before complete (should not), fail the reservation.
                if reservation_id >= 0:
                    await self.quota.fail(reservation_id)

                if attempt == 0 and response is not None and getattr(response, "text", None):
                    history.append(
                        types.Content(role="model", parts=[types.Part.from_text(text=response.text)])
                    )

                correction_instruction = (
                    f"L'output precedente ha fallito con errore di validazione:\n{error_msg[:300]}\n"
                    "Correggi l'output e restituisci SOLO un JSON valido secondo lo schema "
                    "(senza campo reasoning)."
                )
                history.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=correction_instruction)])
                )
                # Validation correction loop continues; each attempt still reserves.
                continue

            except ConfigError:
                if reservation_id >= 0:
                    await self.quota.release(reservation_id)
                raise

            except Exception as e:
                kind = classify_provider_error(e)
                if reservation_id >= 0:
                    # Provider may have started; count capacity as failed, not released.
                    await self.quota.fail(reservation_id)

                if kind == ErrorClass.FATAL:
                    logger.error(
                        "Errore non-retryable (%s) per '%s': %s. Fallback immediato.",
                        type(e).__name__,
                        title[:50],
                        str(e)[:150],
                    )
                    return get_fallback_article(title, url, date)

                retry_after = extract_retry_after_seconds(e)
                if retry_after is not None and isinstance(e, genai_errors.APIError) and getattr(e, "code", None) == 429:
                    logger.warning(
                        "429 Retry-After=%.1fs per '%s'. Attesa autoritativa poi re-check quote.",
                        retry_after,
                        title[:50],
                    )
                    await asyncio.sleep(retry_after)
                elif attempt < _MAX_ATTEMPTS - 1:
                    backoff = float(attempt + 1) * 4.0
                    logger.warning(
                        "Errore retryable al tentativo %d per '%s': %s. Retry tra %.1fs.",
                        attempt + 1,
                        title[:50],
                        str(e)[:150],
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "Errore DEFINITIVO retryable al tentativo %d per '%s': %s",
                        attempt + 1,
                        title[:50],
                        str(e)[:150],
                    )

        logger.error(
            "Tutti i %d tentativi falliti per '%s'. Applicazione fallback.",
            _MAX_ATTEMPTS,
            title[:50],
        )
        return get_fallback_article(title, url, date)
