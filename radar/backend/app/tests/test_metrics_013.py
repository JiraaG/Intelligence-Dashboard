"""Test per i tre endpoint di diagnostica e metriche FinOps (Phase 013)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_metrics_summary_invalid_date(client):
    """Data non valida deve restituire 400 Bad Request."""
    response = client.get("/api/metrics/summary?from=invalid-date")
    assert response.status_code == 400
    assert "Invalid 'from' date format" in response.json()["detail"]


def test_metrics_by_feed_invalid_date(client):
    response = client.get("/api/metrics/by-feed?to=2026-99-99")
    assert response.status_code == 400
    assert "Invalid 'to' date format" in response.json()["detail"]


def test_metrics_dedup_from_after_to(client):
    """from > to deve restituire 400."""
    response = client.get("/api/metrics/dedup?from=2026-07-20&to=2026-07-10")
    assert response.status_code == 400
    assert "'from' date cannot be after 'to' date." in response.json()["detail"]
