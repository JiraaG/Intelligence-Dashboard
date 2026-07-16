import pytest
from unittest.mock import ANY, AsyncMock, MagicMock, patch
import httpx
from app.extraction.parser import strip_html_tags
from app.extraction.client import MinifluxClient
from app.extraction.entry_validation import validate_miniflux_entry, EntryValidationError

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
    """Verifica che tag multimediali (img, video, audio, picture, source) siano purgati con attributi e fallback."""
    html = (
        "Testo iniziale. "
        "<img src='https://example.com/logo.png' alt='Logo' style='width:100px;'>"
        " Testo centrale. "
        "<video controls src='movie.mp4'>Your browser does not support video.</video>"
        " <img>fallback interno</img>"
        " <picture><source srcset='pic.webp'>fallback picture</picture>"
        " Testo finale."
    )
    res = strip_html_tags(html)
    assert "Logo" not in res
    assert "movie.mp4" not in res
    assert "Your browser does not support video." not in res
    assert "fallback interno" not in res
    assert "fallback picture" not in res
    assert res == "Testo iniziale. Testo centrale. Testo finale."


# ─── Tests for entry validation ──────────────────────────────────────────────

def test_validate_miniflux_entry_ok() -> None:
    entry = validate_miniflux_entry({
        "id": 42,
        "url": "https://Example.com/Path/",
        "title": " Titolo ",
        "content": "<p>body</p>",
        "published_at": "2026-07-14T12:00:00Z",
        "feed": {"title": "Feed X"},
    })
    assert entry.id == 42
    assert entry.source_url == "https://example.com/Path"
    assert entry.title == "Titolo"
    assert entry.published_at == "2026-07-14"
    assert entry.feed_title == "Feed X"


def test_validate_miniflux_entry_rejects_bad_id() -> None:
    with pytest.raises(EntryValidationError):
        validate_miniflux_entry({
            "id": "nope",
            "url": "https://example.com/a",
            "title": "T",
            "content": "c",
            "published_at": "2026-07-14",
        })


# ─── Tests for MinifluxClient ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_miniflux_client_fetch_unread() -> None:
    """Testa che fetch_unread_entries effettui la chiamata GET corretta e ritorni le notizie."""
    mock_http = MagicMock(spec=httpx.AsyncClient)
    client = MinifluxClient(
        api_url="http://mock-miniflux",
        api_key="mock_key",
        http_client=mock_http,
    )

    payload = {
        "entries": [
            {
                "id": 123,
                "title": "Notizia di Test",
                "url": "https://test.com/article",
                "content": "hello",
                "published_at": "2026-07-14T10:00:00Z",
                "feed": {"title": "Feed"},
            }
        ]
    }

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = payload
        entries = await client.fetch_unread_entries(limit=10)

        mock_request.assert_awaited_once()
        assert mock_request.await_args.args[0] == "GET"
        assert mock_request.await_args.args[1] == "/v1/entries"
        assert mock_request.await_args.kwargs["params"]["limit"] == 10
        assert mock_request.await_args.kwargs["params"]["status"] == "unread"
        assert mock_request.await_args.kwargs["params"]["published_after"] == ANY
        assert len(entries) == 1
        assert entries[0].id == 123
        assert entries[0].title == "Notizia di Test"


@pytest.mark.asyncio
async def test_miniflux_client_mark_as_read() -> None:
    """Testa che mark_as_read invii la richiesta PUT corretta con gli ID degli articoli."""
    mock_http = MagicMock(spec=httpx.AsyncClient)
    client = MinifluxClient(
        api_url="http://mock-miniflux",
        api_key="mock_key",
        http_client=mock_http,
    )

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = b""
        await client.mark_as_read([123, 456])

        mock_request.assert_awaited_once_with(
            "PUT",
            "/v1/entries",
            json_body={"entry_ids": [123, 456], "status": "read"},
            expect_json=False,
        )
