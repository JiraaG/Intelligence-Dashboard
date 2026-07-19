"""Estrazione testo/JSON da risposte chat OpenAI-compat (Ollama reasoner incluso).

I modelli con thinking spesso riempiono ``reasoning`` e lasciano ``content``
vuoto, oppure mischiano prose+JSON. Qui si recupera solo il dict Radar utile,
senza esporre CoT nello schema Pydantic.
"""

from __future__ import annotations

import json
from typing import Any

# Chiavi tipiche del contratto GeopoliticalArticleSchema usate come segnale
# che il dict estratto è l'output di classificazione e non un frammento spurio.
_RADAR_JSON_SIGNAL_KEYS = frozenset(
    {"title", "primary_category", "country_code", "summary"}
)


def strip_think_channel_wrappers(text: str) -> str:
    """Rimuove wrapper thought (channel Gemma / fence markdown)."""
    cleaned = text.strip()
    for marker in ("<channel|>", "<|channel|>"):
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[-1].strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def extract_radar_json_object(text: str) -> str | None:
    """Ritorna un oggetto JSON parseabile; preferisce il dict più completo Radar."""
    cleaned = text.strip()
    best: str | None = None
    best_score = -1
    for i in range(len(cleaned) - 1, -1, -1):
        if cleaned[i] != "{":
            continue
        try:
            obj, _end = json.JSONDecoder().raw_decode(cleaned[i:])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        dumped = json.dumps(obj, ensure_ascii=False)
        score = sum(1 for k in _RADAR_JSON_SIGNAL_KEYS if k in obj and obj.get(k) not in (None, ""))
        # Preferisci oggetti con almeno title+un altro segnale (evita frammenti
        # tipo solo related_countries/published_at dal canale thinking).
        if score >= 2 and score > best_score:
            best_score = score
            best = dumped
            if score >= 3:
                return dumped
        elif score > best_score or best is None:
            best_score = score
            best = dumped
    return best


def extract_assistant_json_text(message: dict[str, Any]) -> str:
    """Estrae il JSON di classificazione da ``choices[].message``.

    Ordine: ``content`` → ``reasoning`` / ``reasoning_content`` / ``thinking``
    → concatenazione content+reasoning (Gemma a volte spezza l'oggetto).
    Da ogni candidato tenta ``extract_radar_json_object``.
    """
    candidates: list[str] = []
    raw = message.get("content") or ""
    if isinstance(raw, list):
        raw = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw
        )
    content = strip_think_channel_wrappers(str(raw).strip())
    if content:
        candidates.append(content)
    reasoning_parts: list[str] = []
    for key in ("reasoning", "reasoning_content", "thinking"):
        alt = message.get(key)
        if alt:
            cleaned = strip_think_channel_wrappers(str(alt).strip())
            if cleaned:
                candidates.append(cleaned)
                reasoning_parts.append(cleaned)
    if content and reasoning_parts:
        candidates.append(strip_think_channel_wrappers(content + "\n" + "\n".join(reasoning_parts)))
    for candidate in candidates:
        extracted = extract_radar_json_object(candidate)
        if extracted:
            return extracted
    return candidates[0] if candidates else ""
