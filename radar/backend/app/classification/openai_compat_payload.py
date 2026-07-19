"""Payload builder OpenAI-compat (DeepSeek dialect + stock + Ollama think).

Niente package ``openai``. Usato da ``deepseek.DeepSeekClient`` (nome storico
del client httpx multi-provider).

SoT: SoT LLM §5 dialect; Fase A Profilo F (Ollama host).
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import OLLAMA_KEEP_ALIVE_BUSY
from app.core.llm_lanes import API_DIALECT_DEEPSEEK, API_DIALECT_OPENAI

logger = logging.getLogger("radar.classification.openai_compat_payload")

# Prefissi tag modello (Ollama / locali) che su dialect ``openai`` usano
# ``think`` + ``options.num_predict/num_ctx`` invece del shape DeepSeek.
OLLAMA_THINK_MODEL_PREFIXES: tuple[str, ...] = (
    "gemma4",
    "qwen3",
    "qwen3.5",
    "deepseek-r1",
    "qwq",
)

OLLAMA_THINK_NUM_PREDICT = 8192
# 8k ctx: realistico su RX 6750 XT 12GB con gemma4:12b; 32k veniva clampato a 4k
# sotto carico parallelo e lasciava thinking senza spazio per il JSON.
OLLAMA_THINK_NUM_CTX = 8192


def normalize_api_dialect(raw: str | None) -> str:
    """Normalizza dialect a ``deepseek``|``openai``; default ``deepseek`` se ignoto."""
    value = (raw or API_DIALECT_DEEPSEEK).strip().lower()
    if value in {API_DIALECT_DEEPSEEK, API_DIALECT_OPENAI}:
        return value
    return API_DIALECT_DEEPSEEK


def uses_ollama_think_protocol(model: str) -> bool:
    """True se il tag modello richiede protocollo think nativo Ollama su ``/v1``.

    Copre reasoner locali tipici (Gemma 4, Qwen3, …), non solo un singolo tag.
    """
    name = (model or "").strip().lower()
    if not name:
        return False
    return any(name.startswith(prefix) for prefix in OLLAMA_THINK_MODEL_PREFIXES)


def build_chat_completions_payload(
    *,
    model: str,
    system: str,
    user: str,
    effort: str,
    api_dialect: str,
    keep_alive: str | int | None = None,
) -> dict[str, Any]:
    """Costruisce il JSON POST ``/chat/completions`` per il dialect richiesto.

    - ``effort=none`` → ``max_tokens`` 2048; altrimenti 8192.
    - Dialect ``deepseek``: campi ``thinking`` + ``reasoning_effort``.
    - Dialect ``openai`` stock: nessun campo DeepSeek-only.
    - Modelli ``uses_ollama_think_protocol``: ``think=true`` sempre + budget
      ``options.num_predict/num_ctx`` (Profilo F / reasoner locali) +
      top-level ``keep_alive`` busy (best-effort su ``/v1``; unload idle via API nativa).

    SoT:
        SoT LLM §5; llm-json-extraction; plan Fase A Ollama.
    """
    dialect = normalize_api_dialect(api_dialect)
    ollama_think = uses_ollama_think_protocol(model)
    if ollama_think:
        max_tokens = OLLAMA_THINK_NUM_PREDICT
    elif effort != "none":
        max_tokens = 8192
    else:
        max_tokens = 2048
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    # response_format json_object: ok su DeepSeek/OpenAI cloud; su Ollama+think
    # spesso produce content vuoto / fence senza oggetto valido → omettere.
    if not ollama_think:
        payload["response_format"] = {"type": "json_object"}
    if dialect == API_DIALECT_DEEPSEEK:
        if effort == "none":
            payload["thinking"] = {"type": "disabled"}
        else:
            ds_effort = effort if effort in {"high", "max"} else "high"
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = ds_effort
    elif ollama_think:
        # Thinking sempre su reasoner locali; effort env scala reasoning_effort.
        payload["think"] = True
        payload["reasoning_effort"] = (
            effort if effort in {"high", "max", "medium", "low"} else "high"
        )
        if effort == "none":
            payload["reasoning_effort"] = "high"
        payload["options"] = {
            "num_predict": OLLAMA_THINK_NUM_PREDICT,
            "num_ctx": OLLAMA_THINK_NUM_CTX,
            "temperature": 0.1,
        }
        # Best-effort: alcune build Ollama ignorano keep_alive su /v1.
        # Unload idle resta su POST /api/generate keep_alive=0 (ollama_lifecycle).
        payload["keep_alive"] = (
            keep_alive if keep_alive is not None else OLLAMA_KEEP_ALIVE_BUSY
        )
    elif effort != "none":
        logger.debug(
            "openai dialect ignores thinking fields (effort=%s model=%s)",
            effort,
            model,
        )
    return payload
