import pytest
from unittest.mock import ANY, AsyncMock, patch
import httpx
from app.extraction.parser import strip_html_tags
from app.extraction.client import MinifluxClient

# ─── Tests for HTML Stripper ─────────────────────────────────────────────────

def test_strip_html_tags_basic() -> None:
    """Verifica che strip_html_tags rimuova i tag base conservando il testo."""
    html = "<p>Articolo su <strong>TSMC</strong> in Europa.</p>"
    res = strip_html_tags(html)
    assert res == "Articolo su TSMC in Europa."

def test_strip_html_tags_entities() -> None:
    """Verifica che le entità HTML comuni siano decodificate correttamente."""
    html = "Apple &amp; Nvidia &lt; TSMC &gt; Intel &quot;chips&#39;&quot;"
    res = strip_html_tags(html)
    assert res == "Apple & Nvidia < TSMC > Intel \"chips'\""

def test_strip_html_tags_whitespaces() -> None:
    """Verifica che spazi e righe vuote multipli vengano normalizzati."""
    html = "  Prima parte  \n\n\n\n Seconda   parte   \t  "
    res = strip_html_tags(html)
    assert res == "Prima parte\n\nSeconda parte"

def test_strip_html_tags_junk_tags() -> None:
    """Verifica che tag spazzatura (script, style) ed il loro contenuto siano rimossi."""
    html = (
        "Inizio."
        "<script>console.log('test'); var x = 10;</script>"
        "<style>body { background: red; }</style>"
        " Fine."
    )
    res = strip_html_tags(html)
    assert res == "Inizio. Fine."

def test_strip_html_tags_media_tags() -> None:
    """Verifica che tag multimediali (img, video, audio) siano purgati con attributi e fallback."""
    html = (
        "Testo iniziale. "
        "<img src='https://example.com/logo.png' alt='Logo' style='width:100px;'>"
        " Testo centrale. "
        "<video controls src='movie.mp4'>Your browser does not support video.</video>"
        " Testo finale."
    )
    res = strip_html_tags(html)
    assert "Logo" not in res
    assert "movie.mp4" not in res
    assert "Your browser does not support video." not in res
    assert res == "Testo iniziale. Testo centrale. Testo finale."


# ─── Tests for MinifluxClient ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_miniflux_client_fetch_unread() -> None:
    """Testa che fetch_unread_entries effettui la chiamata GET corretta e ritorni le notizie."""
    client = MinifluxClient(api_url="http://mock-miniflux", api_key="mock_key")
    
    mock_response = httpx.Response(
        status_code=200,
        json={"entries": [{"id": 123, "title": "Notizia di Test", "url": "https://test.com"}]},
        request=httpx.Request("GET", "http://mock-miniflux")
    )
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        entries = await client.fetch_unread_entries(limit=10)
        
        # Verifica URL e parametri (published_after è dinamico: now - 48h)
        mock_get.assert_called_once_with(
            "http://mock-miniflux/v1/entries",
            params={
                "status": "unread",
                "limit": 10,
                "order": "published_at",
                "direction": "desc",
                "published_after": ANY,
            },
            headers={"X-Auth-Token": "mock_key", "Content-Type": "application/json"}
        )
        assert len(entries) == 1
        assert entries[0]["id"] == 123
        assert entries[0]["title"] == "Notizia di Test"

@pytest.mark.asyncio
async def test_miniflux_client_mark_as_read() -> None:
    """Testa che mark_as_read invii la richiesta PUT corretta con gli ID degli articoli."""
    client = MinifluxClient(api_url="http://mock-miniflux", api_key="mock_key")
    
    mock_response = httpx.Response(
        status_code=200,
        request=httpx.Request("PUT", "http://mock-miniflux")
    )
    
    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        mock_put.return_value = mock_response
        
        await client.mark_as_read([123, 456])
        
        # Verifica chiamata PUT
        mock_put.assert_called_once_with(
            "http://mock-miniflux/v1/entries",
            json={"entry_ids": [123, 456], "status": "read"},
            headers={"X-Auth-Token": "mock_key", "Content-Type": "application/json"}
        )
