"""Client chat OpenAI-compat via httpx (DeepSeek / OpenAI / GLM / Grok / Ollama).

Niente package ``openai``. Il nome modulo/classe ``DeepSeek*`` è storico: il
client serve tutti i provider OpenAI-compat. Payload/response: moduli
``openai_compat_payload`` e ``openai_compat_response``.

Dialect:
  - ``deepseek``: campi ``thinking`` + ``reasoning_effort``
  - ``openai``: stock; reasoner Ollama (gemma4/qwen3/…) → ``think`` + options

SoT:
    skill llm-json-extraction; SoT LLM §5; AGENTS.md (httpx, no openai pkg).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.classification.openai_compat_payload import (
    build_chat_completions_payload,
    normalize_api_dialect,
    uses_ollama_think_protocol,
)
from app.classification.openai_compat_response import extract_assistant_json_text
from app.classification.prompts import SYSTEM_PROMPT, build_user_prompt
from app.core.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_REASONING_EFFORT,
    GEMINI_REQUEST_TIMEOUT,
)

logger = logging.getLogger("radar.classification.deepseek")

# Re-export pubblici (import path stabili per test / client).
__all__ = [
    "DeepSeekClient",
    "DeepSeekError",
    "OpenAICompatClient",
    "build_chat_completions_payload",
    "normalize_api_dialect",
    "uses_ollama_think_protocol",
    "extract_assistant_json_text",
]


class DeepSeekError(Exception):
    """Errore provider con status HTTP e ``Retry-After`` opzionali.

    Usato dal router in ``classification/client.py`` per tassonomia retry/cooldown.
    """

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
    """Parse ``Retry-After`` numerico; clamp 0–300s. Non-numerico → ``None``."""
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, min(300.0, float(raw.strip())))
    except ValueError:
        return None


class DeepSeekClient:
    """Chat completions async → stringa JSON (Pydantic a carico del chiamante).

    Alias storico; preferire ``OpenAICompatClient`` nei nuovi call-site.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        timeout: float | None = None,
        api_dialect: str | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else DEEPSEEK_API_KEY
        self.base_url = (base_url or DEEPSEEK_BASE_URL).rstrip("/")
        self.model = model or DEEPSEEK_MODEL
        effort_raw = (effort or DEEPSEEK_REASONING_EFFORT or "high").lower()
        if effort_raw in {"none", "off", "disabled"}:
            self.effort = "none"
        elif effort_raw in {"low", "medium", "high", "max"}:
            self.effort = effort_raw
        else:
            self.effort = "high"
        self.timeout = float(timeout if timeout is not None else GEMINI_REQUEST_TIMEOUT)
        self.api_dialect = normalize_api_dialect(api_dialect)

    @property
    def available(self) -> bool:
        """True se è configurata una API key non vuota."""
        return bool(self.api_key)

    def build_payload(
        self,
        *,
        model: str,
        system: str,
        user: str,
        effort: str | None = None,
    ) -> dict[str, Any]:
        """Builder pubblico per test e chiamanti che servono il body della request."""
        use_effort = self.effort if effort is None else effort
        effort_raw = (use_effort or "high").lower()
        if effort_raw in {"none", "off", "disabled"}:
            eff = "none"
        elif effort_raw in {"low", "medium", "high", "max"}:
            eff = effort_raw
        else:
            eff = "high"
        return build_chat_completions_payload(
            model=model,
            system=system,
            user=user,
            effort=eff,
            api_dialect=self.api_dialect,
        )

    async def classify_json(
        self,
        *,
        title: str,
        content: str,
        url: str,
        date: str,
        correction: str | None = None,
        model: str | None = None,
        effort: str | None = None,
    ) -> tuple[str, int | None]:
        """Chiama il provider e restituisce ``(json_text, usage_total_tokens|None)``.

        Trunca ``content`` a 4000 (invariante tutte le lane). Appende vincoli
        json_object / chiavi flat e eventuale blocco CORREZIONE. Mappa HTTP →
        ``DeepSeekError`` (429+Retry-After, 402 crediti, 401/403, 404 modello, 5xx).

        Args:
            title, content, url, date: Campi articolo per ``build_user_prompt``.
            correction: Testo di correzione schema (retry ValidationError).
            model: Override del default client (env ``LLM_*_MODEL`` della lane).
        Returns:
            Testo JSON grezzo + token usage se presente.
        Raises:
            DeepSeekError: key mancante, timeout, transport, status HTTP mappati.
        SoT:
            llm-json-extraction (``content[:4000]``, SYSTEM_PROMPT immutabile).
        """
        if not self.api_key:
            raise DeepSeekError("OpenAI-compat API key mancante", status_code=401)

        use_model = model or self.model
        user_message = self._build_user_message(
            title=title,
            content=content,
            url=url,
            date=date,
            correction=correction,
            model=use_model,
        )

        payload = self.build_payload(
            model=use_model,
            system=SYSTEM_PROMPT,
            user=user_message,
            effort=effort,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url_path = f"{self.base_url}/chat/completions"
        label = f"openai-compat/{self.api_dialect}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url_path, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise DeepSeekError(f"{label} timeout: {exc}", status_code=408) from exc
            except httpx.TransportError as exc:
                raise DeepSeekError(f"{label} transport: {exc}") from exc

        if resp.status_code == 429:
            raise DeepSeekError(
                f"{label} 429 rate limit",
                status_code=429,
                retry_after=_parse_retry_after(resp.headers),
                body=resp.text[:500],
            )
        if resp.status_code == 402 or (
            resp.status_code == 400 and "credit" in resp.text.lower()
        ):
            raise DeepSeekError(
                f"{label} insufficient credits",
                status_code=402,
                body=resp.text[:500],
            )
        if resp.status_code in (401, 403):
            raise DeepSeekError(
                f"{label} auth {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )
        if resp.status_code == 404:
            raise DeepSeekError(
                f"{label} model not found",
                status_code=404,
                body=resp.text[:500],
            )
        if resp.status_code >= 500:
            raise DeepSeekError(
                f"{label} server {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )
        if resp.status_code >= 400:
            raise DeepSeekError(
                f"{label} HTTP {resp.status_code}: {resp.text[:400]}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )

        data = resp.json()
        try:
            message = data["choices"][0]["message"]
            if not isinstance(message, dict):
                raise TypeError("message not a dict")
            text = extract_assistant_json_text(message)
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepSeekError(f"{label} response shape: {exc}", body=str(data)[:500]) from exc

        if not text or not text.lstrip().startswith("{"):
            # 422 → RETRYABLE (non HARD_COOLDOWN 5xx): correction/escalate, non ban 24h.
            content_preview = str(message.get("content") or "")[:200]
            reasoning_preview = str(
                message.get("reasoning")
                or message.get("reasoning_content")
                or message.get("thinking")
                or ""
            )[:200]
            logger.warning(
                "%s non-JSON model=%s content_len=%s reasoning_len=%s "
                "content_preview=%r reasoning_preview=%r",
                label,
                use_model,
                len(str(message.get("content") or "")),
                len(
                    str(
                        message.get("reasoning")
                        or message.get("reasoning_content")
                        or message.get("thinking")
                        or ""
                    )
                ),
                content_preview,
                reasoning_preview,
            )
            raise DeepSeekError(
                f"{label} empty or non-JSON content",
                status_code=422,
                body=(text or str(data))[:500],
            )

        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        total = usage.get("total_tokens")
        try:
            tokens = int(total) if total is not None else None
        except (TypeError, ValueError):
            tokens = None

        use_effort = self.effort if effort is None else effort
        logger.info(
            "%s ok model=%s effort=%s ollama_think=%s tokens=%s",
            label,
            use_model,
            use_effort,
            uses_ollama_think_protocol(use_model),
            tokens,
        )
        return text, usage

    def _build_user_message(
        self,
        *,
        title: str,
        content: str,
        url: str,
        date: str,
        correction: str | None = None,
        model: str | None = None,
    ) -> str:
        """Costruisce il messaggio user con micro-suffisso JSON e opzionali CORREZIONE/THINKING."""
        use_model = model or self.model
        user_msg = build_user_prompt(
            title=title,
            url=url,
            date=date,
            content=content[:4000],
        )
        user_msg = (
            f"{user_msg}\n\n"
            "Return a single valid JSON object strictly adhering to the system instructions. "
            "Do not include markdown code blocks or any reasoning text."
        )
        if correction:
            user_msg = (
                f"{user_msg}\n\nCORREZIONE OBBLIGATORIA:\n{correction}\n"
                "Correggi e restituisci SOLO un JSON valido secondo lo schema "
                "(senza campo reasoning)."
            )

        if uses_ollama_think_protocol(use_model):
            user_msg = (
                f"{user_msg}\n\n"
                "THINKING MODE: reason privately if needed, then your FINAL message "
                "must be ONLY one JSON object starting with '{' and ending with '}'. "
                "Do not echo the system prompt. Do not use markdown. Do not wrap in ```."
            )
        return user_msg



# Nome descrittivo per nuovi call-site (stesso client).
OpenAICompatClient = DeepSeekClient
