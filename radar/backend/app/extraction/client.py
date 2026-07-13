import logging
import httpx
import time
from app.core.config import MINIFLUX_API_URL, MINIFLUX_API_KEY

logger = logging.getLogger("radar.extraction.client")

class MinifluxClient:
    """
    Client asincrono per l'interazione con l'API REST di Miniflux.
    Consente il recupero dei feed e l'aggiornamento dello stato di lettura degli articoli.
    """
    def __init__(self, api_url: str = None, api_key: str = None) -> None:
        self.api_url = (api_url or MINIFLUX_API_URL).rstrip("/")
        self.api_key = api_key or MINIFLUX_API_KEY
        
        if not self.api_url or not self.api_key:
            logger.warning("MinifluxClient inizializzato con credenziali vuote o incomplete.")

        # Inizializziamo gli header di autorizzazione predefiniti
        self.headers = {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json"
        }

    async def fetch_unread_entries(self, limit: int = 50) -> list[dict]:
        """
        Recupera gli articoli non letti presenti nell'aggregatore Miniflux.
        Ritorna una lista di dizionari rappresentanti gli articoli.
        """
        url = f"{self.api_url}/v1/entries"
        params = {
            "status": "unread",
            "limit": limit,
            "order": "published_at",
            "direction": "desc",
            "published_after": int(time.time()) - (48 * 3600)
        }
        
        logger.info(f"Recupero fino a {limit} articoli non letti da Miniflux...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                entries = data.get("entries", [])
                logger.info(f"Ricevuti con successo {len(entries)} articoli da Miniflux.")
                return entries
            except httpx.HTTPError as e:
                logger.error(f"Errore durante la richiesta HTTP a Miniflux API: {e}")
                return []
            except Exception as e:
                logger.error(f"Errore imprevisto nel recupero articoli Miniflux: {e}")
                return []

    async def mark_as_read(self, entry_ids: list[int]) -> None:
        """
        Invia una richiesta PUT a Miniflux per segnare gli ID degli articoli forniti come letti.
        """
        if not entry_ids:
            logger.debug("Nessun articolo da segnare come letto su Miniflux.")
            return

        url = f"{self.api_url}/v1/entries"
        payload = {
            "entry_ids": entry_ids,
            "status": "read"
        }

        logger.info(f"Marcatura di {len(entry_ids)} articoli come letti su Miniflux...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.put(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(f"Articoli segnati come letti con successo su Miniflux (IDs: {entry_ids}).")
            except httpx.HTTPError as e:
                logger.warning(f"Errore nella marcatura articoli come letti su Miniflux: {e}")
            except Exception as e:
                logger.error(f"Errore imprevisto durante l'aggiornamento lettura articoli Miniflux: {e}")
                raise

    async def refresh_all_feeds(self) -> None:
        """
        Invia una richiesta PUT a Miniflux per forzare l'aggiornamento (refresh) 
        immediato di tutti i feed RSS.
        """
        url = f"{self.api_url}/v1/feeds/refresh"
        logger.info("Richiesta di refresh forzato di tutti i feed RSS su Miniflux...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.put(url, headers=self.headers)
                response.raise_for_status()
                logger.info("Refresh di tutti i feed completato con successo su Miniflux.")
            except httpx.HTTPError as e:
                logger.warning(f"Errore durante il refresh forzato dei feed: {e}")
            except Exception as e:
                logger.error(f"Errore imprevisto durante il refresh dei feed: {e}")
