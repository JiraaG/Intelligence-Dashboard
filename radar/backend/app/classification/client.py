import asyncio
import time
import logging
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.core.config import LLM_API_KEY, GEMINI_MODEL, LLM_RPM, LLM_TPM
from app.classification.prompts import SYSTEM_PROMPT
from app.classification.validator import GeopoliticalArticleSchema, get_fallback_article

logger = logging.getLogger("radar.classification.client")

class ClassificationClient:
    """
    Client di classificazione geopolitica asincrono basato su Google GenAI SDK.
    Gestisce internamente il throttling asincrono per non superare il limite di 15 RPM
    e implementa una pipeline di auto-correzione a 2 livelli con fallback finale.
    """
    def __init__(self) -> None:
        if not LLM_API_KEY:
            raise ValueError("Chiave API LLM mancante. Configura GOOGLE_API_KEY o GEMINI_API_KEY.")
        
        self.client = genai.Client(api_key=LLM_API_KEY)
        self.model = GEMINI_MODEL or "gemma-4-31b"
        self._lock = asyncio.Lock()
        self._last_call_time = 0.0
        self._token_window = []  # Salva tuple (timestamp, token_count)
        
        logger.info(f"ClassificationClient pronto. Modello target: {self.model} (RPM: {LLM_RPM}, TPM: {LLM_TPM})")

    async def _wait_for_rate_limit(self, estimated_tokens: int = 1500) -> None:
        """
        Applica il rate limiting su due binari:
        1. RPM: Forza la spaziatura temporale basata su LLM_RPM.
        2. TPM: Mantiene una rolling window di 60 sec per i token se LLM_TPM > 0.
        """
        if LLM_RPM <= 0:
            return

        delay_between_requests = 60.0 / LLM_RPM
        sleep_duration = 0.0

        async with self._lock:
            now = time.time()
            
            # Controllo TPM
            if LLM_TPM > 0:
                self._token_window = [(ts, tc) for ts, tc in self._token_window if now - ts < 60.0]
                current_tpm = sum(tc for ts, tc in self._token_window)
                
                if current_tpm + estimated_tokens > LLM_TPM:
                    if self._token_window:
                        oldest_ts = self._token_window[0][0]
                        sleep_for_tpm = 60.0 - (now - oldest_ts)
                        if sleep_for_tpm > 0:
                            sleep_duration = max(sleep_duration, sleep_for_tpm)

            # Controllo RPM - Calcola il tempo futuro disponibile
            next_available_time = max(now + sleep_duration, self._last_call_time + delay_between_requests)
            sleep_duration = next_available_time - now
            
            self._last_call_time = next_available_time
            if LLM_TPM > 0:
                self._token_window.append((next_available_time, estimated_tokens))

        if sleep_duration > 0:
            logger.debug(f"Rate Limiting attivo. Attesa obbligatoria di {sleep_duration:.2f} sec...")
            await asyncio.sleep(sleep_duration)

    async def _update_tpm(self, actual_tokens: int) -> None:
        """Sostituisce la stima dei token con il costo effettivo post-risposta."""
        if LLM_TPM <= 0:
            return
        async with self._lock:
            if self._token_window:
                # Sostituisce i token stimati inseriti dall'ultimo lock
                last_ts, _ = self._token_window[-1]
                self._token_window[-1] = (last_ts, actual_tokens)

    async def classify_article(
        self,
        title: str,
        content: str,
        url: str,
        date: str
    ) -> GeopoliticalArticleSchema:
        """
        Invia il testo dell'articolo a Gemma ed estrae dati geopolitici strutturati.
        Implementa un robusto Correction Loop a più tentativi per mitigare gli errori 500 istantanei
        e i rate-limit dell'API Google.
        """
        user_message = (
            f"Analizza questo articolo di notizie ed estrai le informazioni geopolitiche strategiche richieste.\n\n"
            f"TITOLO: {title}\n"
            f"URL: {url}\n"
            f"DATA DI PUBBLICAZIONE: {date}\n"
            f"CONTENUTO DELL'ARTICOLO:\n{content[:4000]}"
        )

        max_attempts = 4
        history = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
        ]

        for attempt in range(max_attempts):
            await self._wait_for_rate_limit()
            
            if attempt > 0:
                logger.warning(
                    f"Tentativo {attempt + 1}/{max_attempts} per '{title[:50]}'. "
                    f"Attesa backoff di {attempt * 4} secondi..."
                )
                await asyncio.sleep(attempt * 4.0)

            try:
                if attempt == 0:
                    logger.info(f"Invio articolo a LLM (Gemma) per '{title[:50]}'")
                    
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=history if attempt > 0 else user_message,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=GeopoliticalArticleSchema,
                        temperature=0.3,
                        max_output_tokens=2048
                    )
                )
                
                # Aggiorniamo la rolling window con il consumo reale (se disponibile e TPM attivo)
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    await self._update_tpm(response.usage_metadata.total_token_count)

                extracted = GeopoliticalArticleSchema.model_validate_json(response.text)
                if attempt > 0:
                    logger.info(f"Auto-correzione riuscita al tentativo {attempt + 1} per '{title[:50]}'")
                return extracted

            except ValidationError as e:
                error_msg = str(e)
                logger.error(f"Errore di validazione al tentativo {attempt + 1} per '{title[:50]}': {error_msg[:150]}")
                
                # Aggiungiamo l'errore alla history per istruire il modello
                if attempt == 0:
                    try:
                        history.append(types.Content(role="model", parts=[types.Part.from_text(text=response.text)]))
                    except:
                        pass
                        
                correction_instruction = (
                    f"L'output precedente ha fallito con errore di validazione:\n{error_msg[:300]}\n"
                    f"Correggi l'output e restituisci SOLO un JSON valido secondo lo schema."
                )
                history.append(types.Content(role="user", parts=[types.Part.from_text(text=correction_instruction)]))

            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"Errore temporaneo di rete/API al tentativo {attempt + 1} per '{title[:50]}': {str(e)[:150]}. Riproverà in coda.")
                else:
                    logger.error(f"Errore DEFINITIVO di rete/API al tentativo {attempt + 1} per '{title[:50]}': {str(e)[:150]}")
                # Lasciamo che il loop riprovi senza sporcare la history con istruzioni spurie

        logger.error(f"Tutti i {max_attempts} tentativi falliti per '{title[:50]}'. Applicazione fallback.")
        return get_fallback_article(title, url, date)
