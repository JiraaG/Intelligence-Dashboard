"""Lifecycle VRAM Ollama (Profilo F): unload nativo a fine ciclo idle.

Classify resta su OpenAI-compat ``/v1/chat/completions``. L'unload usa l'API
nativa ``POST /api/generate`` con ``keep_alive=0`` (``/v1`` non onora keep_alive
in modo affidabile). Gate: ``OLLAMA_AUTO_UNLOAD`` + modello SIMPLE think-protocol.

SoT: plan Fase A Ollama VRAM; llm-json-extraction; runbook § Local-Hybrid.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.classification.openai_compat_payload import uses_ollama_think_protocol
from app.core.config import (
    LLM_SIMPLE,
    OLLAMA_AUTO_UNLOAD,
    OLLAMA_KEEP_ALIVE_IDLE,
)

logger = logging.getLogger("radar.classification.ollama_lifecycle")

_UNLOAD_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


def native_base_url(openai_compat_base_url: str) -> str:
    """Deriva base nativa Ollama da ``…/v1`` (strip trailing slash e suffisso ``/v1``)."""
    base = (openai_compat_base_url or "").strip().rstrip("/")
    if base.lower().endswith("/v1"):
        base = base[:-3].rstrip("/")
    return base


def should_manage_ollama_vram(
    *,
    model: str | None = None,
    auto_unload: bool | None = None,
) -> bool:
    """True se il worker deve unloadare VRAM Ollama a fine ciclo / shutdown."""
    enabled = OLLAMA_AUTO_UNLOAD if auto_unload is None else auto_unload
    if not enabled:
        return False
    use_model = (model if model is not None else LLM_SIMPLE.model) or ""
    return uses_ollama_think_protocol(use_model)


def _parse_keep_alive(raw: str | int) -> str | int:
    """Normalizza keep_alive idle: intero se digit-only, altrimenti stringa Ollama."""
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return text


async def fetch_ollama_ps(
    *,
    openai_compat_base_url: str,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """GET ``/api/ps`` — lista modelli residenti (best-effort; [] su errore)."""
    native = native_base_url(openai_compat_base_url)
    if not native:
        return []
    url = f"{native}/api/ps"
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_UNLOAD_TIMEOUT)
    try:
        resp = await http.get(url)
        if resp.status_code >= 400:
            logger.debug("ollama_ps status=%s body=%s", resp.status_code, resp.text[:200])
            return []
        data = resp.json()
        models = data.get("models") if isinstance(data, dict) else None
        return list(models) if isinstance(models, list) else []
    except Exception as exc:
        logger.debug("ollama_ps failed: %s", exc)
        return []
    finally:
        if owns_client:
            await http.aclose()


async def unload_ollama_model(
    *,
    model: str,
    openai_compat_base_url: str,
    keep_alive: str | int | None = None,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Unload modello via ``POST /api/generate`` con ``keep_alive=0`` (pattern ufficiale).

    Idempotente: modello già scaricato → no-op / log debug. Ritorna True se la
    richiesta HTTP è andata a buon fine (2xx), False su skip/errore soft.
    """
    name = (model or "").strip()
    native = native_base_url(openai_compat_base_url)
    if not name or not native:
        logger.debug(
            "ollama_unload skip: model=%r native_base=%r",
            name,
            native,
        )
        return False

    ka = _parse_keep_alive(
        OLLAMA_KEEP_ALIVE_IDLE if keep_alive is None else keep_alive
    )
    url = f"{native}/api/generate"
    body: dict[str, Any] = {
        "model": name,
        "prompt": "",
        "stream": False,
        "keep_alive": ka,
    }
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=_UNLOAD_TIMEOUT)
    started = time.monotonic()
    try:
        logger.info(
            "ollama_unload start model=%s url=%s keep_alive=%s",
            name,
            url,
            ka,
        )
        resp = await http.post(url, json=body)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if resp.status_code >= 400:
            # Modello assente / già unloadato: spesso 404 — trattare come no-op.
            logger.debug(
                "ollama_unload soft-fail status=%s model=%s elapsed_ms=%s body=%s",
                resp.status_code,
                name,
                elapsed_ms,
                resp.text[:300],
            )
            return False
        logger.info(
            "ollama_unload ok model=%s elapsed_ms=%s",
            name,
            elapsed_ms,
        )
        try:
            resident = await fetch_ollama_ps(
                openai_compat_base_url=openai_compat_base_url,
                client=http,
            )
            names = [
                str(m.get("name") or m.get("model") or "")
                for m in resident
                if isinstance(m, dict)
            ]
            logger.info("ollama_ps after_unload models=%s", names)
        except Exception as ps_exc:
            logger.debug("ollama_ps after_unload failed: %s", ps_exc)
        return True
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "ollama_unload failed model=%s elapsed_ms=%s err=%s",
            name,
            elapsed_ms,
            exc,
        )
        return False
    finally:
        if owns_client:
            await http.aclose()


async def maybe_unload_simple_ollama(*, reason: str) -> bool:
    """Gate + unload del modello ``LLM_SIMPLE`` se Profilo F / Ollama think.

    Args:
        reason: Contesto log (``end_of_cycle``, ``shutdown``, …).
    Returns:
        True se unload HTTP ok; False se skippato o soft-fail.
    """
    if not should_manage_ollama_vram():
        logger.debug("ollama_unload skipped gate reason=%s", reason)
        return False
    model = LLM_SIMPLE.model
    base = LLM_SIMPLE.base_url or ""
    logger.info("ollama_unload gated reason=%s model=%s", reason, model)
    return await unload_ollama_model(model=model, openai_compat_base_url=base)
