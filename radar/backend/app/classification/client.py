import asyncio
import time
import logging
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.core.config import LLM_API_KEY, GEMINI_MODEL
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
        
        logger.info(f"ClassificationClient pronto. Modello target: {self.model}")

    async def _wait_for_rate_limit(self) -> None:
        """
        Garantisce che intercorrano almeno 4 secondi tra le chiamate consecutive alle API,
        proteggendo il sistema dagli errori 429 (quota di 15 RPM).
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < 4.0:
                sleep_duration = 4.0 - elapsed
                logger.debug(f"Rate Limiting attivo. Attesa obbligatoria di {sleep_duration:.2f} secondi...")
                await asyncio.sleep(sleep_duration)
            self._last_call_time = time.time()

    async def classify_article(
        self,
        title: str,
        content: str,
        url: str,
        date: str
    ) -> GeopoliticalArticleSchema:
        """
        Invia il testo dell'articolo a Gemma ed estrae dati geopolitici strutturati.
        Implementa un Correction Loop di massimo 1 tentativo prima di applicare il fallback sicuro.
        """
        # Step 1: Rispetta il Rate Limiting di 15 RPM
        await self._wait_for_rate_limit()

        user_message = (
            f"Analizza questo articolo di notizie ed estrai le informazioni geopolitiche strategiche richieste.\n\n"
            f"TITOLO: {title}\n"
            f"URL: {url}\n"
            f"DATA DI PUBBLICAZIONE: {date}\n"
            f"CONTENUTO DELL'ARTICOLO:\n{content[:4000]}"
        )

        response_text = ""
        try:
            logger.info(f"Invio articolo a LLM (Gemma) per '{title[:50]}'")
            
            # Eseguiamo la chiamata sincrona bloccante dell'SDK su un thread dedicato
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=GeopoliticalArticleSchema,
                    temperature=0.1,
                    max_output_tokens=2048
                )
            )
            response_text = response.text
            extracted = GeopoliticalArticleSchema.model_validate_json(response_text)
            return extracted

        except (ValidationError, Exception) as e:
            logger.warning(
                f"Primo tentativo di estrazione fallito per '{title[:50]}' a causa di: {e}. "
                "Attivazione Correction Loop (auto-correzione)..."
            )
            
            # Step 2: Rispetta il Rate Limiting prima di tentare la correzione
            await self._wait_for_rate_limit()

            # Prepariamo il messaggio di errore per guidare la correzione del modello
            error_details = str(e)
            correction_instruction = (
                f"L'output precedente ha generato un errore di validazione dello schema:\n"
                f"{error_details}\n\n"
                f"Correggi l'output sopra riportato restituendo unicamente un JSON valido "
                f"che soddisfi tutti i vincoli dello schema richiesto. Rileggi attentamente il ragionamento."
            )
            
            # Ricostruiamo i messaggi inserendo il contesto del tentativo fallito
            history = [
                types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
            ]
            if response_text:
                history.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))
            history.append(types.Content(role="user", parts=[types.Part.from_text(text=correction_instruction)]))

            try:
                # Eseguiamo la chiamata di correzione
                retry_response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=history,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=GeopoliticalArticleSchema,
                        temperature=0.1,
                        max_output_tokens=2048
                    )
                )
                retry_text = retry_response.text
                extracted = GeopoliticalArticleSchema.model_validate_json(retry_text)
                logger.info(f"Auto-correzione riuscita con successo per '{title[:50]}'")
                return extracted
            
            except Exception as retry_err:
                logger.error(
                    f"Tentativo di auto-correzione fallito per '{title[:50]}': {retry_err}. "
                    "Applicazione del fallback statico di sicurezza."
                )
                return get_fallback_article(title, url, date)
