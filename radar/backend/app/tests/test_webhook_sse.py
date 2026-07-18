"""Unit tests for Miniflux HMAC webhook and SSE broadcast manager (Fase B)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import pytest
from unittest.mock import patch

from app.main import verify_miniflux_signature, SSEBroadcastManager


def test_verify_miniflux_signature_accepts_valid_hmac() -> None:
    secret = "my_secret_token"
    raw_body = b'{"event_type":"new_entries","entries":[]}'
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    with patch("app.main.MINIFLUX_WEBHOOK_SECRET", secret):
        assert verify_miniflux_signature(raw_body, signature) is True


def test_verify_miniflux_signature_rejects_mismatch() -> None:
    secret = "my_secret_token"
    raw_body = b'{"event_type":"new_entries","entries":[]}'
    signature = "wrong_signature_value"

    with patch("app.main.MINIFLUX_WEBHOOK_SECRET", secret):
        assert verify_miniflux_signature(raw_body, signature) is False


def test_verify_miniflux_signature_returns_false_when_secret_empty() -> None:
    raw_body = b'{"event_type":"new_entries","entries":[]}'
    signature = "some_signature"

    with patch("app.main.MINIFLUX_WEBHOOK_SECRET", ""):
        assert verify_miniflux_signature(raw_body, signature) is False


async def test_sse_broadcast_manager_fanout() -> None:
    manager = SSEBroadcastManager(queue_maxsize=5)
    q1 = manager.subscribe()
    q2 = manager.subscribe()

    manager.publish("event_1")
    manager.publish("event_2")

    assert await q1.get() == "event_1"
    assert await q1.get() == "event_2"
    assert await q2.get() == "event_1"
    assert await q2.get() == "event_2"

    manager.close_all()
    assert await q1.get() is None
    assert await q2.get() is None
