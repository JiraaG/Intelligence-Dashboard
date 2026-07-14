import pytest
import time
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.classification.validator import GeopoliticalArticleSchema, get_fallback_article
from app.classification.client import ClassificationClient
from app.core.config import LLM_RPM

# ─── Tests per lo Schema Pydantic ─────────────────────────────────────────────

def test_schema_valid_article() -> None:
    """Verifica che GeopoliticalArticleSchema accetti e convalidi dati corretti."""
    data = {
        "title": "TSMC inaugura la prima fab a Dresda",
        "summary": "TSMC avvia la costruzione di un nuovo impianto da 10 miliardi in Germania. L'iniziativa punta a rafforzare l'indipendenza strategica europea.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc-germany",
        "country_code": "DE",
        "latitude": 51.0504,
        "longitude": 13.7373,
        "companies_involved": "TSMC, Infineon",
        "tags": "Tecnologia, Semiconduttori, Germania",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Fabbrica Dresda",
        "relevance_level": 4,
    }

    article = GeopoliticalArticleSchema(**data)
    assert article.country_code == "DE"
    assert article.primary_category == "Tecnologia"
    assert article.sentiment == "Positivo"
    assert article.relevance_level == 4
    assert "TSMC" in article.companies_involved


def test_schema_rejects_invalid_category() -> None:
    """Verifica che categorie non ammesse vengano rifiutate (strict, no coerce)."""
    data = {
        "title": "Titolo",
        "summary": "Riassunto.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com",
        "country_code": "IT",
        "latitude": 41.87,
        "longitude": 12.56,
        "companies_involved": "Nessuno",
        "tags": "Tag",
        "primary_category": "CATEGORIA_INVENTATA",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 1,
    }
    with pytest.raises(ValidationError):
        GeopoliticalArticleSchema(**data)


def test_schema_rejects_invalid_relevance() -> None:
    """Verifica che lo schema rifiuti relevance_level di tipo non intero."""
    data = {
        "title": "Titolo",
        "summary": "Riassunto.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com",
        "country_code": "IT",
        "latitude": 41.87,
        "longitude": 12.56,
        "companies_involved": "Nessuno",
        "tags": "Tag",
        "primary_category": "Infrastrutture",
        "sentiment": "Neutrale",
        "infrastructural_entities": "Nessuno",
        "relevance_level": "alto",
    }
    with pytest.raises(ValidationError):
        GeopoliticalArticleSchema(**data)


# ─── Tests per il Rate Limiter ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiter_spacing() -> None:
    """Verifica che il Rate Limiter calcoli correttamente e chiami sleep per chiamate ravvicinate."""
    client = ClassificationClient()
    expected_interval = 60.0 / LLM_RPM
    
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Prima chiamata: l'ultimo call time è 0, nessun intervallo richiesto
        await client._wait_for_rate_limit()
        assert mock_sleep.call_count == 0
        
        # Simuliamo che la precedente chiamata sia avvenuta proprio ora
        client._last_call_time = time.time()
        
        # Seconda chiamata immediata: deve invocare asyncio.sleep per la differenza
        await client._wait_for_rate_limit()
        assert mock_sleep.call_count == 1
        
        # Assicura che il tempo di sleep sia positivo e allineato all'intervallo RPM
        sleep_args = mock_sleep.call_args[0][0]
        assert 0.0 < sleep_args <= expected_interval + 0.1


# ─── Tests per il Client e i Flussi di Fallback/Correzione ───────────────────

@pytest.mark.asyncio
async def test_client_classify_success() -> None:
    """Verifica il successo dell'estrazione al primo tentativo con dati corretti."""
    client = ClassificationClient()
    
    # Mock della risposta dell'SDK
    mock_gen_response = MagicMock()
    mock_gen_response.text = json.dumps({
        "title": "Nuova fab TSMC",
        "summary": "TSMC apre a Dresda.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc",
        "country_code": "DE",
        "latitude": 51.0,
        "longitude": 13.0,
        "companies_involved": "TSMC",
        "tags": "Tecnologia",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 3,
    })
    
    # Mockiamo la chiamata di rete sincrona dell'SDK
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_thread.return_value = mock_gen_response
        
        article = await client.classify_article(
            title="Nuova fab TSMC",
            content="Contenuto dell'articolo",
            url="https://example.com/tsmc",
            date="2026-06-24"
        )
        
        assert article.primary_category == "Tecnologia"
        assert article.country_code == "DE"
        assert article.relevance_level == 3
        # Nessun sleep asincrono invocato in thread per correzione
        assert mock_thread.call_count == 1

@pytest.mark.asyncio
async def test_client_classify_retry_success() -> None:
    """Verifica che in caso di errore di validazione il Correction Loop effettui il tentativo di riparazione."""
    client = ClassificationClient()
    
    # Primo tentativo: restituisce JSON corrotto o incompleto (manca country_code)
    bad_response = MagicMock()
    bad_response.text = json.dumps({
        "title": "Nuova fab TSMC",
        "summary": "TSMC apre.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc",
        # country_code mancante
        "latitude": 51.0,
        "longitude": 13.0,
        "companies_involved": "Nessuno",
        "tags": "Tecnologia",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 3,
    })

    # Secondo tentativo (correzione): restituisce il JSON valido riparato
    good_response = MagicMock()
    good_response.text = json.dumps({
        "title": "Nuova fab TSMC",
        "summary": "TSMC apre.",
        "published_at": "2026-06-24",
        "source_url": "https://example.com/tsmc",
        "country_code": "DE",
        "latitude": 51.0,
        "longitude": 13.0,
        "companies_involved": "Nessuno",
        "tags": "Tecnologia",
        "primary_category": "Tecnologia",
        "sentiment": "Positivo",
        "infrastructural_entities": "Nessuno",
        "relevance_level": 3,
    })

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # Ritorna bad_response al primo colpo, e good_response al secondo
        mock_thread.side_effect = [bad_response, good_response]
        
        article = await client.classify_article(
            title="Nuova fab TSMC",
            content="Contenuto dell'articolo",
            url="https://example.com/tsmc",
            date="2026-06-24"
        )
        
        # Si accerta che le chiamate siano state 2 (originale + correzione)
        assert mock_thread.call_count == 2
        assert article.country_code == "DE"
        assert article.primary_category == "Tecnologia"

@pytest.mark.asyncio
async def test_client_classify_fallback_after_double_error() -> None:
    """Verifica che in caso di fallimenti continuati l'estrazione non crashi e ritorni il fallback."""
    client = ClassificationClient()
    
    # Tutti i tentativi restituiscono dati non validi
    bad_response = MagicMock()
    bad_response.text = "{'invalid_json': true}"

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # Client retry loop: max_attempts = 4
        mock_thread.side_effect = [bad_response] * 4
        
        article = await client.classify_article(
            title="Titolo originale",
            content="Contenuto dell'articolo",
            url="https://example.com/test",
            date="2026-06-24"
        )
        
        assert mock_thread.call_count == 4
        # Verifica l'applicazione delle proprietà del fallback statico di sicurezza
        assert article.country_code == "XX"
        assert article.primary_category == "Infrastrutture"
        assert article.latitude == 0.0
        assert article.longitude == 0.0
        assert article.relevance_level == 1
