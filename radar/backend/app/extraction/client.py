"""Miniflux HTTP client with shared httpx, size limits, and retryable backoff."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

import httpx

from app.core.config import (
    MAX_MINIFLUX_RESPONSE_BYTES,
    MINIFLUX_API_KEY,
    MINIFLUX_API_URL,
    MINIFLUX_CONNECT_TIMEOUT,
    MINIFLUX_MAX_RETRIES,
    MINIFLUX_READ_TIMEOUT,
    MINIFLUX_RETRY_BASE_SECONDS,
    MINIFLUX_RETRY_MAX_SECONDS,
)
from app.extraction.entry_validation import (
    EntryValidationError,
    ValidatedMinifluxEntry,
    validate_miniflux_entry,
)

logger = logging.getLogger("radar.extraction.client")


class MinifluxResponseTooLarge(RuntimeError):
    """Raised when a Miniflux response exceeds MAX_MINIFLUX_RESPONSE_BYTES."""


def _is_retryable_http_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return _is_retryable_http_status(exc.response.status_code)
    return False


def _retry_after_seconds(response: httpx.Response | None, attempt: int) -> float:
    base = float(MINIFLUX_RETRY_BASE_SECONDS)
    capped = min(float(MINIFLUX_RETRY_MAX_SECONDS), base * (2**attempt))
    if response is None:
        return capped
    header = response.headers.get("Retry-After")
    if not header:
        return capped
    try:
        return min(float(MINIFLUX_RETRY_MAX_SECONDS), max(0.0, float(header)))
    except ValueError:
        return capped


class MinifluxClient:
    """
    Client asincrono per l'API REST Miniflux.
    Riusa un httpx.AsyncClient di proprietà del lifespan FastAPI.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        *,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.api_url = (api_url or MINIFLUX_API_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else MINIFLUX_API_KEY
        self._client = http_client

        if not self.api_url or not self.api_key:
            logger.warning("MinifluxClient inizializzato con credenziali vuote o incomplete.")

        self.headers = {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _read_limited_body(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_MINIFLUX_RESPONSE_BYTES:
                    raise MinifluxResponseTooLarge(
                        f"Content-Length {content_length} supera "
                        f"MAX_MINIFLUX_RESPONSE_BYTES={MAX_MINIFLUX_RESPONSE_BYTES}"
                    )
            except ValueError:
                pass

        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > MAX_MINIFLUX_RESPONSE_BYTES:
                raise MinifluxResponseTooLarge(
                    f"Corpo risposta Miniflux supera "
                    f"MAX_MINIFLUX_RESPONSE_BYTES={MAX_MINIFLUX_RESPONSE_BYTES}"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = f"{self.api_url}{path}"
        last_error: BaseException | None = None

        for attempt in range(MINIFLUX_MAX_RETRIES + 1):
            response: httpx.Response | None = None
            try:
                async with self._client.stream(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=self.headers,
                    timeout=httpx.Timeout(
                        connect=float(MINIFLUX_CONNECT_TIMEOUT),
                        read=float(MINIFLUX_READ_TIMEOUT),
                        write=float(MINIFLUX_READ_TIMEOUT),
                        pool=float(MINIFLUX_CONNECT_TIMEOUT),
                    ),
                ) as response:
                    if _is_retryable_http_status(response.status_code):
                        body_preview = b""
                        try:
                            body_preview = await self._read_limited_body(response)
                        except MinifluxResponseTooLarge:
                            pass
                        http_error = httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                        if attempt < MINIFLUX_MAX_RETRIES:
                            delay = _retry_after_seconds(response, attempt)
                            logger.warning(
                                "Miniflux %s %s → %s (tentativo %d/%d). Retry tra %.1fs. body=%s",
                                method,
                                path,
                                response.status_code,
                                attempt + 1,
                                MINIFLUX_MAX_RETRIES + 1,
                                delay,
                                body_preview[:200],
                            )
                            await asyncio.sleep(delay)
                            last_error = http_error
                            continue
                        raise http_error

                    response.raise_for_status()
                    raw = await self._read_limited_body(response)
                    if not expect_json:
                        return raw
                    if not raw:
                        return {}
                    return json.loads(raw.decode("utf-8"))

            except MinifluxResponseTooLarge:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < MINIFLUX_MAX_RETRIES and _is_retryable_exception(exc):
                    delay = _retry_after_seconds(
                        getattr(exc, "response", None) if isinstance(exc, httpx.HTTPStatusError) else None,
                        attempt,
                    )
                    logger.warning(
                        "Errore retryable Miniflux %s %s (tentativo %d/%d): %s. Retry tra %.1fs",
                        method,
                        path,
                        attempt + 1,
                        MINIFLUX_MAX_RETRIES + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Richiesta Miniflux fallita senza errore esplicito: {method} {path}")

    async def fetch_unread_entries(self, limit: int = 50) -> list[ValidatedMinifluxEntry]:
        """
        Recupera articoli non letti e valida ogni entry isolatamente.
        Entry malformate vengono scartate senza annullare le sorelle.
        """
        params = {
            "status": "unread",
            "limit": limit,
            "order": "published_at",
            "direction": "desc",
            "published_after": int(time.time()) - (48 * 3600),
        }

        logger.info("Recupero fino a %d articoli non letti da Miniflux...", limit)

        try:
            data = await self._request("GET", "/v1/entries", params=params)
        except Exception as e:
            logger.error("Errore durante il recupero articoli Miniflux: %s", e)
            return []

        raw_entries = data.get("entries", []) if isinstance(data, dict) else []
        if not isinstance(raw_entries, list):
            logger.error("Risposta Miniflux senza lista 'entries'")
            return []

        validated: list[ValidatedMinifluxEntry] = []
        for raw in raw_entries:
            try:
                validated.append(validate_miniflux_entry(raw))
            except EntryValidationError as exc:
                raw_id = raw.get("id") if isinstance(raw, dict) else None
                logger.warning("Entry Miniflux scartata (malformata): %s | raw_id=%r", exc, raw_id)
            except Exception as exc:
                logger.warning("Entry Miniflux scartata (errore inatteso): %s", exc, exc_info=True)

        logger.info(
            "Ricevuti %d articoli grezzi, %d validati da Miniflux.",
            len(raw_entries),
            len(validated),
        )
        return validated

    async def mark_as_read(self, entry_ids: list[int]) -> None:
        if not entry_ids:
            logger.debug("Nessun articolo da segnare come letto su Miniflux.")
            return

        payload = {"entry_ids": entry_ids, "status": "read"}
        logger.info("Marcatura di %d articoli come letti su Miniflux...", len(entry_ids))

        try:
            await self._request("PUT", "/v1/entries", json_body=payload, expect_json=False)
            logger.info("Articoli segnati come letti su Miniflux (IDs: %s).", entry_ids)
        except httpx.HTTPError as e:
            logger.warning("Errore nella marcatura articoli come letti su Miniflux: %s", e)
        except Exception as e:
            logger.error("Errore imprevisto durante mark-read Miniflux: %s", e)
            raise

    async def refresh_all_feeds(self) -> None:
        logger.info("Richiesta di refresh forzato di tutti i feed RSS su Miniflux...")
        try:
            await self._request("PUT", "/v1/feeds/refresh", expect_json=False)
            logger.info("Refresh di tutti i feed completato con successo su Miniflux.")
        except httpx.HTTPError as e:
            logger.warning("Errore durante il refresh forzato dei feed: %s", e)
        except Exception as e:
            logger.error("Errore imprevisto durante il refresh dei feed: %s", e)
