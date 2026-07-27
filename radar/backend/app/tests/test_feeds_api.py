"""Test merge catalogo feed, token gate e date_field by-feed."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.feeds import (
    merge_feeds_catalog,
    normalize_feed_url,
    require_feed_admin_token,
    seed_enabled,
)
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_seed_enabled_default_true() -> None:
    assert seed_enabled({}) is True
    assert seed_enabled({"enabled": True}) is True
    assert seed_enabled({"enabled": False}) is False


def test_normalize_feed_url() -> None:
    assert normalize_feed_url(" https://a.com/rss/ ") == "https://a.com/rss"


def test_merge_feeds_catalog_seed_and_live() -> None:
    seed = [
        {
            "category": "BBC News",
            "title": "BBC News — World",
            "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "scraper_rules": "#main-content",
            "crawler": True,
        },
        {
            "category": "BBC News",
            "title": "BBC News — Tech",
            "feed_url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "enabled": False,
        },
    ]
    live = [
        {
            "id": 12,
            "title": "BBC News — World",
            "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "site_url": "https://www.bbc.com/news",
            "category": {"title": "BBC News"},
            "scraper_rules": "#main-content",
            "crawler": True,
            "disabled": False,
            "parsing_error_count": 0,
            "parsing_error_message": "",
            "checked_at": "2026-07-26T10:00:00Z",
            "next_check_at": "2026-07-26T11:00:00Z",
        },
        {
            "id": 99,
            "title": "Orphan Feed",
            "feed_url": "https://example.com/orphan.xml",
            "site_url": "",
            "category": {"title": "Extra"},
            "disabled": False,
            "parsing_error_count": 2,
            "parsing_error_message": "timeout",
        },
    ]
    catalog = merge_feeds_catalog(seed, live)
    assert catalog["total_count"] == 3
    assert catalog["active_count"] == 2  # world + orphan; tech seed not imported → disabled
    assert catalog["error_count"] == 1
    categories = {g["category"] for g in catalog["groups"]}
    assert "BBC News" in categories
    assert "Extra" in categories
    bbc = next(g for g in catalog["groups"] if g["category"] == "BBC News")
    world = next(f for f in bbc["feeds"] if f["title"] == "BBC News — World")
    assert world["id"] == 12
    assert world["in_seed"] is True
    assert world["disabled"] is False
    tech = next(f for f in bbc["feeds"] if f["title"] == "BBC News — Tech")
    assert tech["id"] is None
    assert tech["disabled"] is True
    assert tech["enabled_in_seed"] is False


def test_merge_guardian_url_heuristic() -> None:
    seed = [
        {
            "category": "The Guardian",
            "title": "Guardian World",
            "feed_url": "https://www.theguardian.com/world/rss",
        }
    ]
    live = [
        {
            "id": 7,
            "title": "Guardian World",
            "feed_url": "https://www.theguardian.com/uk/world/rss",
            "category": {"title": "The Guardian"},
            "disabled": False,
            "parsing_error_count": 0,
        }
    ]
    catalog = merge_feeds_catalog(seed, live)
    assert catalog["total_count"] == 1
    feed = catalog["groups"][0]["feeds"][0]
    assert feed["id"] == 7
    assert feed["in_seed"] is True


def test_require_feed_admin_token_open_when_empty() -> None:
    require_feed_admin_token("", None)
    require_feed_admin_token("   ", "anything")


def test_require_feed_admin_token_gate() -> None:
    with pytest.raises(PermissionError):
        require_feed_admin_token("secret", None)
    with pytest.raises(PermissionError):
        require_feed_admin_token("secret", "wrong")
    require_feed_admin_token("secret", "secret")


def test_metrics_by_feed_invalid_date_field(client: TestClient) -> None:
    response = client.get("/api/metrics/by-feed?date_field=updated_at")
    assert response.status_code == 400
    assert "date_field" in response.json()["detail"]


def test_toggle_feed_requires_token_when_configured(client: TestClient) -> None:
    with patch("app.main.FEED_ADMIN_TOKEN", "gate-token"):
        response = client.patch(
            "/api/feeds/1/toggle",
            json={"disabled": True},
        )
    assert response.status_code == 401


def test_toggle_feed_ok_with_token(client: TestClient) -> None:
    mock_client = MagicMock()
    mock_client.update_feed = AsyncMock(return_value={})
    mock_client.list_feeds = AsyncMock(
        return_value=[{"id": 1, "disabled": True, "feed_url": "https://x"}]
    )

    with (
        patch("app.main.FEED_ADMIN_TOKEN", "gate-token"),
        patch("app.main.MINIFLUX_API_KEY", "mock-key"),
        patch("app.main.MinifluxClient", return_value=mock_client),
        patch("app.main.httpx.AsyncClient") as mock_http_cls,
    ):
        mock_http_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        response = client.patch(
            "/api/feeds/1/toggle",
            json={"disabled": True},
            headers={"X-Feed-Admin-Token": "gate-token"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["disabled"] is True
    assert body["status"] == "ok"
    mock_client.update_feed.assert_awaited_once_with(1, disabled=True)


def test_get_feeds_merges_seed(client: TestClient, tmp_path) -> None:
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(
        '{"feeds":[{"category":"A","title":"T1","feed_url":"https://a.com/rss"}]}',
        encoding="utf-8",
    )
    live = [
        {
            "id": 5,
            "title": "T1",
            "feed_url": "https://a.com/rss",
            "category": {"title": "A"},
            "disabled": False,
            "parsing_error_count": 0,
        }
    ]
    mock_client = MagicMock()
    mock_client.list_feeds = AsyncMock(return_value=live)

    with (
        patch("app.main.MINIFLUX_API_KEY", "mock-key"),
        patch("app.api.feeds.MINIFLUX_FEEDS_SEED_PATH", str(seed_file)),
        patch("app.main.MinifluxClient", return_value=mock_client),
        patch("app.main.httpx.AsyncClient") as mock_http_cls,
    ):
        mock_http_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_http_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        response = client.get("/api/feeds")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert data["active_count"] == 1
    assert data["groups"][0]["feeds"][0]["id"] == 5
