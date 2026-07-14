import os
import pytest
import socket
import asyncpg
import sys
import httpx

from app.extraction.client import MinifluxClient
from app.classification.client import ClassificationClient

# Aggiunge il path per caricare lo script di produzione
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.test_production_pipeline import (
    test_external_connections as run_test_external_connections,
    test_e2e_transactional_commit as run_test_e2e_transactional_commit,
    stress_test_rate_limiter as run_stress_test_rate_limiter,
)


pytestmark = pytest.mark.live


def _live_classification_client() -> ClassificationClient:
    """Live Gemini client with a no-op quota ledger (DB ledger optional for smoke)."""
    from unittest.mock import AsyncMock

    quota = AsyncMock()
    quota.reserve = AsyncMock(side_effect=list(range(1, 10_000)))
    quota.complete = AsyncMock()
    quota.release = AsyncMock()
    quota.fail = AsyncMock()
    return ClassificationClient(quota=quota)


@pytest.mark.asyncio
async def test_live_external_connections() -> None:
    """Verifica le connessioni reali ed i token delle API di Miniflux e Gemini."""
    async with httpx.AsyncClient() as http_client:
        miniflux = MinifluxClient(http_client=http_client)
        classification = _live_classification_client()
        try:
            await run_test_external_connections(miniflux, classification)
        except (socket.gaierror, ConnectionRefusedError, OSError) as e:
            pytest.skip(f"Connessione di rete non disponibile per Miniflux/Gemini: {e}")
        except Exception as e:
            err_str = str(e)
            if "genai" in str(type(e)).lower() or "500" in err_str or "429" in err_str or "limit" in err_str.lower():
                pytest.skip(f"Servizio Gemini API temporaneamente non disponibile o quota limitata: {e}")
            else:
                pytest.fail(f"Errore critico durante la verifica delle connessioni esterne: {e}")


@pytest.mark.asyncio
async def test_live_e2e_transactional_commit() -> None:
    """Verifica il ciclo di commit su DB/Vault isolati con identificatori run-unique."""
    async with httpx.AsyncClient() as http_client:
        miniflux = MinifluxClient(http_client=http_client)
        try:
            await run_test_e2e_transactional_commit(miniflux)
        except RuntimeError as e:
            pytest.skip(f"Ambiente live isolato non configurato: {e}")
        except (asyncpg.PostgresError, socket.gaierror, ConnectionRefusedError, OSError) as e:
            pytest.skip(
                f"Database PostgreSQL di test o percorso Vault isolato non disponibile: {e}"
            )


@pytest.mark.asyncio
async def test_live_rate_limiter_throttling() -> None:
    """Verifica il corretto distanziamento temporale delle chiamate asincrone concorrenti."""
    classification = _live_classification_client()
    try:
        await run_stress_test_rate_limiter(classification)
    except Exception as e:
        pytest.fail(f"Errore nel test del rate limiter throttling: {e}")
