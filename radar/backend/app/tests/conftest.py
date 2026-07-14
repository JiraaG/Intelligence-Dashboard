import os
import sys

import pytest

# Aggiunge la directory backend al PYTHONPATH se necessario (pytest.ini pythonpath=backend)
_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

# Mock env per unit/integration: evita ValueError su import di app.core.config.
# I test live richiedono variabili reali e RUN_LIVE_TESTS=1.
_run_live = os.environ.get("RUN_LIVE_TESTS") == "1"

if not _run_live:
    os.environ.setdefault("DATABASE_URL", "postgresql://mock_user:mock_password@mock-host:5432/mock-db")
    os.environ.setdefault("GEMINI_API_KEY", "mock-gemini-key")
    os.environ.setdefault("GOOGLE_API_KEY", "mock-google-key")
    os.environ.setdefault("MINIFLUX_API_URL", "http://mock-miniflux")
    os.environ.setdefault("MINIFLUX_API_KEY", "mock-miniflux-key")
    os.environ.setdefault("OBSIDIAN_VAULT_PATH", "/mock/vault")


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Fail live tests unless RUN_LIVE_TESTS=1 is explicitly set."""
    if item.get_closest_marker("live") is not None:
        if os.environ.get("RUN_LIVE_TESTS") != "1":
            pytest.fail(
                "Live tests are gated: set RUN_LIVE_TESTS=1 to run "
                f"'{item.nodeid}'. Default suite uses -m 'not live'."
            )
