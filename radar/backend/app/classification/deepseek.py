"""Client chat OpenAI-compat via httpx (DeepSeek / OpenAI / GLM / Grok).

Niente package ``openai``. Dialect payload:
  - ``deepseek``: campi ``thinking`` + ``reasoning_effort``
  - ``openai``: chat/completions stock (nessun campo DeepSeek-only)

SoT:
    skill llm-json-extraction; SoT LLM §5; AGENTS.md (httpx, no openai pkg).
"""

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
from app.core.llm_lanes import API_DIALECT_DEEPSEEK, API_DIALECT_OPENAI

logger = logging.getLogger("radar.classification.deepseek")


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


def normalize_api_dialect(raw: str | None) -> str:
    """Normalizza dialect a ``deepseek``|``openai``; default ``deepseek`` se ignoto."""
    value = (raw or API_DIALECT_DEEPSEEK).strip().lower()
    if value in {API_DIALECT_DEEPSEEK, API_DIALECT_OPENAI}:
        return value
    return API_DIALECT_DEEPSEEK


def build_chat_completions_payload(
    *,
    model: str,
    system: str,
    user: str,
    effort: str,
    api_dialect: str,
) -> dict[str, Any]:
    """Costruisce il JSON POST ``/chat/completions`` per il dialect richiesto.

    ``effort=none`` → ``max_tokens`` 2048; altrimenti 8192.
    Dialect deepseek: ``thinking`` disabled oppure enabled+``reasoning_effort``
    (low mappato a high). Dialect openai: nessun campo thinking (effort ignora).

    SoT:
        SoT LLM §5 dialect; llm-json-extraction.
    """
    dialect = normalize_api_dialect(api_dialect)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 2048 if effort == "none" else 8192,
    }
    if dialect == API_DIALECT_DEEPSEEK:
        # Thinking off = path più economico / meno capace (bulk SIMPLE).
        # Thinking on: temperature/top_p non ammessi; effort high|max only (low→high).
        if effort == "none":
            payload["thinking"] = {"type": "disabled"}
        else:
            ds_effort = effort if effort in {"high", "max"} else "high"
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = ds_effort
    elif effort != "none":
        # Stock OpenAI-compat: niente ``thinking`` DeepSeek. Effort solo dimensiona
        # max_tokens sopra; vendor che rifiutano campi sconosciuti restano sicuri.
        logger.debug(
            "openai dialect ignores thinking/reasoning_effort (effort=%s model=%s)",
            effort,
            model,
        )
    return payload


class DeepSeekClient:
    """Chat completions async → stringa JSON (Pydantic a carico del chiamante)."""

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
        # none/off/disabled = non-thinking (più economico). low/medium restano per compat config.
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
    ) -> dict[str, Any]:
        """Builder pubblico per test e chiamanti che servono il body della request."""
        return build_chat_completions_payload(
            model=model,
            system=system,
            user=user,
            effort=self.effort,
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
        user_message = build_user_prompt(
            title=title,
            url=url,
            date=date,
            content=content[:4000],
        )
        # json_object richiede "json"; campi flat (SYSTEM_PROMPT parla di
        # "coordinate" e il modello tende a nestare coordinates{}).
        user_message = (
            f"{user_message}\n\n"
            "Output requirement: return a single valid JSON object (the word json is required).\n"
            "Use ONLY these top-level keys (no nested coordinates/coordinate object, no 'category'):\n"
            "title, summary, published_at, source_url, country_code, latitude, longitude,\n"
            "companies_involved, tags, primary_category, sentiment, infrastructural_entities,\n"
            "relevance_level.\n"
            "latitude and longitude MUST be separate top-level numbers (floats).\n"
            "primary_category MUST be exactly one of the 10 allowed Italian category names.\n"
            "Game/software/videogame reviews and entertainment products → Tecnologia "
            "(never Geopolitica, Sicurezza, or Infrastrutture).\n"
            "Philosophy / abstract essays / explicit no-geopolitical-content fluff → "
            "Tecnologia + relevance_level 1 + country_code XX (never Geopolitica).\n"
            "No markdown fences, no reasoning field."
        )
        if correction:
            user_message = (
                f"{user_message}\n\nCORREZIONE OBBLIGATORIA:\n{correction}\n"
                "Correggi e restituisci SOLO un JSON valido secondo lo schema "
                "(senza campo reasoning)."
            )

        payload = self.build_payload(
            model=use_model,
            system=SYSTEM_PROMPT,
            user=user_message,
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
            resp.status_code == 400
            and "credit" in resp.text.lower()
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
            # Preferisci content; ignora reasoning_content (fuori schema Radar).
            text = message.get("content") or ""
            if isinstance(text, list):
                # Alcune API restituiscono content a parti
                text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in text
                )
            text = str(text).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepSeekError(f"{label} response shape: {exc}", body=str(data)[:500]) from exc

        if not text:
            raise DeepSeekError(f"{label} empty content", status_code=502, body=str(data)[:500])

        usage = data.get("usage") or {}
        total = usage.get("total_tokens")
        try:
            tokens = int(total) if total is not None else None
        except (TypeError, ValueError):
            tokens = None

        logger.info(
            "%s ok model=%s effort=%s tokens=%s",
            label,
            use_model,
            self.effort,
            tokens,
        )
        return text, tokens
