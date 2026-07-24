import json
from unittest.mock import patch
import app.api.feed_url_resolve as resolver_module


def test_resolve_feed_url_match(tmp_path):
    seed_data = {
        "feeds": [
            {"title": "BBC News - Technology", "feed_url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
            {"title": "ANSA.it - Top News", "feed_url": "https://www.ansa.it/sito/ansait_rss.xml"},
        ]
    }
    seed_file = tmp_path / "miniflux-feeds.seed.json"
    seed_file.write_text(json.dumps(seed_data), encoding="utf-8")

    # Reset cache
    resolver_module._SEED_MAP = None

    with patch("app.api.feed_url_resolve.MINIFLUX_FEEDS_SEED_PATH", str(seed_file)):
        assert resolver_module.resolve_feed_url("BBC News - Technology") == "https://feeds.bbci.co.uk/news/technology/rss.xml"
        assert resolver_module.resolve_feed_url("Feed: ANSA.it - Top News") == "https://www.ansa.it/sito/ansait_rss.xml"
        assert resolver_module.resolve_feed_url("Unknown Feed Title") is None
        assert resolver_module.resolve_feed_url(None) is None

    # Reset cache again for clean state
    resolver_module._SEED_MAP = None
