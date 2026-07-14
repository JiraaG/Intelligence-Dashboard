import asyncio
import time
import logging
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.core.config import LLM_API_KEY, GEMINI_MODEL, LLM_RPM, LLM_TPM
from app.classification.prompts import SYSTEM_PROMPT, build_user_prompt
from app.classification.validator import GeopoliticalArticleSchema, get_fallback_article

logger = logging.getLogger("radar.classification.client")


class ClassificationClient:
    """
    Client di classificazione geopolitica asincrono basato su Google GenAI SDK.
    Gestisce throttling RPM/TPM e correction loop multi-tentativo con fallback finale.
    """

    def __init__(self) -> None:
        if not LLM_API_KEY:
            raise ValueError("Chiave API LLM mancante. Configura GOOGLE_API_KEY o GEMINI_API_KEY.")

        self.client = genai.Client(api_key=LLM_API_KEY)
        self.model = GEMINI_MODEL or "gemma-4-31b"
        self._lock = asyncio.Lock()
        self._last_call_time = 0.0
        self._token_window: list[tuple[float, int]] = []

        logger.info(
            "ClassificationClient pronto. Modello target: %s (RPM: %s, TPM: %s)",
            self.model,
            LLM_RPM,
            LLM_TPM,
        )

    async def _wait_for_rate_limit(self, estimated_tokens: int = 1500) -> None:
        """
        Rate limiting a due binari:
        1. RPM: spaziatura temporale (>= 4s con LLM_RPM default 10).
        2. TPM: rolling window 60s se LLM_TPM > 0.
        """
        if LLM_RPM <= 0:
            return

        delay_between_requests = 60.0 / LLM_RPM
        sleep_duration = 0.0

        async with self._lock:
            now = time.time()

            if LLM_TPM > 0:
                self._token_window = [(ts, tc) for ts, tc in self._token_window if now - ts < 60.0]
                current_tpm = sum(tc for _ts, tc in self._token_window)

                if current_tpm + estimated_tokens > LLM_TPM:
                    if self._token_window:
                        oldest_ts = self._token_window[0][0]
                        sleep_for_tpm = 60.0 - (now - oldest_ts)
                        if sleep_for_tpm > 0:
                            sleep_duration = max(sleep_duration, sleep_for_tpm)

            next_available_time = max(now + sleep_duration, self._last_call_time + delay_between_requests)
            sleep_duration = next_available_time - now

            self._last_call_time = next_available_time
            if LLM_TPM > 0:
                self._token_window.append((next_available_time, estimated_tokens))

        if sleep_duration > 0:
            logger.debug("Rate Limiting attivo. Attesa obbligatoria di %.2f sec...", sleep_duration)
            await asyncio.sleep(sleep_duration)

    async def _update_tpm(self, actual_tokens: int) -> None:
        if LLM_TPM <= 0:
            return
        async with self._lock:
            if self._token_window:
                last_ts, _ = self._token_window[-1]
                self._token_window[-1] = (last_ts, actual_tokens)

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

        max_attempts = 4
        history = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
        ]

        for attempt in range(max_attempts):
            await self._wait_for_rate_limit()

            if attempt > 0:
                logger.warning(
                    "Tentativo %d/%d per '%s'. Attesa backoff di %s secondi...",
                    attempt + 1,
                    max_attempts,
                    title[:50],
                    attempt * 4,
                )
                await asyncio.sleep(attempt * 4.0)

            response = None
            try:
                if attempt == 0:
                    logger.info("Invio articolo a LLM (Gemma) per '%s'", title[:50])

                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=history if attempt > 0 else user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=GeopoliticalArticleSchema,
                        temperature=0.3,
                        max_output_tokens=2048,
                    ),
                )

                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    await self._update_tpm(response.usage_metadata.total_token_count)

                extracted = GeopoliticalArticleSchema.model_validate_json(response.text)
                if attempt > 0:
                    logger.info(
                        "Auto-correzione riuscita al tentativo %d per '%s'",
                        attempt + 1,
                        title[:50],
                    )
                return extracted

            except ValidationError as e:
                error_msg = str(e)
                logger.error(
                    "Errore di validazione al tentativo %d per '%s': %s",
                    attempt + 1,
                    title[:50],
                    error_msg[:150],
                )

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

            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(
                        "Errore temporaneo di rete/API al tentativo %d per '%s': %s. Riproverà.",
                        attempt + 1,
                        title[:50],
                        str(e)[:150],
                    )
                else:
                    logger.error(
                        "Errore DEFINITIVO di rete/API al tentativo %d per '%s': %s",
                        attempt + 1,
                        title[:50],
                        str(e)[:150],
                    )

        logger.error("Tutti i %d tentativi falliti per '%s'. Applicazione fallback.", max_attempts, title[:50])
        return get_fallback_article(title, url, date)
