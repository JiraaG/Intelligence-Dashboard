"""DeepSeek V4 Flash client via httpx (OpenAI-compatible). No openai package."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.classification.prompts import SYSTEM_PROMPT, build_user_prompt
from app.core.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_REASONING_EFFORT,
    GEMINI_REQUEST_TIMEOUT,
)

logger = logging.getLogger("radar.classification.deepseek")


class DeepSeekError(Exception):
    """Provider error with optional HTTP status and Retry-After seconds."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.body = body


def _parse_retry_after(headers: httpx.Headers) -> float | None:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, min(300.0, float(raw.strip())))
    except ValueError:
        return None


class DeepSeekClient:
    """Async chat completions → JSON string (Pydantic validated by caller)."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else DEEPSEEK_API_KEY
        self.base_url = (base_url or DEEPSEEK_BASE_URL).rstrip("/")
        self.model = model or DEEPSEEK_MODEL
        effort_raw = (effort or DEEPSEEK_REASONING_EFFORT or "high").lower()
        # Never default to max (cost/verbosity).
        self.effort = effort_raw if effort_raw in {"low", "medium", "high"} else "high"
        self.timeout = float(timeout if timeout is not None else GEMINI_REQUEST_TIMEOUT)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def classify_json(
        self,
        *,
        title: str,
        content: str,
        url: str,
        date: str,
        correction: str | None = None,
        model: str | None = None,
    ) -> tuple[str, int | None]:
        """
        Return (json_text, usage_total_tokens_or_None).

        ``model`` overrides the client default (lane env LLM_*_MODEL).
        Raises DeepSeekError on HTTP/provider failures.
        """
        if not self.api_key:
            raise DeepSeekError("DEEPSEEK_API_KEY mancante", status_code=401)

        use_model = model or self.model
        user_message = build_user_prompt(
            title=title,
            url=url,
            date=date,
            content=content[:4000],
        )
        if correction:
            user_message = (
                f"{user_message}\n\nCORREZIONE OBBLIGATORIA:\n{correction}\n"
                "Restituisci SOLO un JSON valido secondo lo schema (senza campo reasoning)."
            )

        payload: dict[str, Any] = {
            "model": use_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 2048,
            "reasoning_effort": self.effort,
            "extra_body": {"thinking": {"type": "enabled"}},
        }
        # DeepSeek docs: thinking may be top-level; keep effort; strip unknown if 400.
        # Prefer flat thinking field used by API:
        payload["thinking"] = {"type": "enabled"}
        payload.pop("extra_body", None)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url_path = f"{self.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url_path, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise DeepSeekError(f"DeepSeek timeout: {exc}", status_code=408) from exc
            except httpx.TransportError as exc:
                raise DeepSeekError(f"DeepSeek transport: {exc}") from exc

        if resp.status_code == 429:
            raise DeepSeekError(
                "DeepSeek 429 rate limit",
                status_code=429,
                retry_after=_parse_retry_after(resp.headers),
                body=resp.text[:500],
            )
        if resp.status_code == 402 or (
            resp.status_code == 400
            and "credit" in resp.text.lower()
        ):
            raise DeepSeekError(
                "DeepSeek insufficient credits",
                status_code=402,
                body=resp.text[:500],
            )
        if resp.status_code in (401, 403):
            raise DeepSeekError(
                f"DeepSeek auth {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )
        if resp.status_code == 404:
            raise DeepSeekError(
                "DeepSeek model not found",
                status_code=404,
                body=resp.text[:500],
            )
        if resp.status_code >= 500:
            raise DeepSeekError(
                f"DeepSeek server {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )
        if resp.status_code >= 400:
            raise DeepSeekError(
                f"DeepSeek HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )

        data = resp.json()
        try:
            message = data["choices"][0]["message"]
            # Prefer content; ignore reasoning_content (not in Radar schema).
            text = message.get("content") or ""
            if isinstance(text, list):
                # Some APIs return content parts
                text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in text
                )
            text = str(text).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepSeekError(f"DeepSeek response shape: {exc}", body=str(data)[:500]) from exc

        if not text:
            raise DeepSeekError("DeepSeek empty content", status_code=502, body=str(data)[:500])

        usage = data.get("usage") or {}
        total = usage.get("total_tokens")
        try:
            tokens = int(total) if total is not None else None
        except (TypeError, ValueError):
            tokens = None

        logger.info(
            "DeepSeek ok model=%s effort=%s tokens=%s",
            use_model,
            self.effort,
            tokens,
        )
        return text, tokens
