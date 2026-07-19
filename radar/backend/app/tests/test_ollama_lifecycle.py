"""Unit tests: Ollama VRAM lifecycle (unload native, gate, base URL)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.classification.ollama_lifecycle import (
    fetch_ollama_ps,
    maybe_unload_simple_ollama,
    native_base_url,
    should_manage_ollama_vram,
    unload_ollama_model,
)


def test_native_base_url_strips_v1() -> None:
    assert (
        native_base_url("http://host.docker.internal:11434/v1")
        == "http://host.docker.internal:11434"
    )
    assert (
        native_base_url("http://host.docker.internal:11434/v1/")
        == "http://host.docker.internal:11434"
    )
    assert native_base_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert native_base_url("") == ""


def test_should_manage_ollama_vram_gate() -> None:
    assert should_manage_ollama_vram(model="gemma4-radar", auto_unload=True) is True
    assert should_manage_ollama_vram(model="qwen3:14b", auto_unload=True) is True
    assert should_manage_ollama_vram(model="deepseek-v4-flash", auto_unload=True) is False
    assert should_manage_ollama_vram(model="gemma4-radar", auto_unload=False) is False
    assert should_manage_ollama_vram(model="", auto_unload=True) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unload_ollama_model_posts_keep_alive_zero() -> None:
    captured: dict[str, Any] = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self) -> dict[str, Any]:
            return {}

    class FakePsResp:
        status_code = 200
        text = '{"models":[]}'

        def json(self) -> dict[str, Any]:
            return {"models": []}

    client = AsyncMock()

    async def fake_post(url: str, json: dict[str, Any] | None = None) -> FakeResp:
        captured["url"] = url
        captured["json"] = json
        return FakeResp()

    async def fake_get(url: str) -> FakePsResp:
        captured["ps_url"] = url
        return FakePsResp()

    client.post = AsyncMock(side_effect=fake_post)
    client.get = AsyncMock(side_effect=fake_get)

    ok = await unload_ollama_model(
        model="gemma4-radar",
        openai_compat_base_url="http://host.docker.internal:11434/v1",
        keep_alive=0,
        client=client,
    )
    assert ok is True
    assert captured["url"] == "http://host.docker.internal:11434/api/generate"
    assert captured["json"] == {
        "model": "gemma4-radar",
        "prompt": "",
        "stream": False,
        "keep_alive": 0,
    }
    assert captured["ps_url"] == "http://host.docker.internal:11434/api/ps"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unload_ollama_model_idempotent_on_404() -> None:
    client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 404
    resp.text = "not found"
    client.post = AsyncMock(return_value=resp)

    ok = await unload_ollama_model(
        model="gemma4-radar",
        openai_compat_base_url="http://127.0.0.1:11434/v1",
        client=client,
    )
    assert ok is False
    client.post.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unload_skips_empty_model_or_base() -> None:
    assert (
        await unload_ollama_model(model="", openai_compat_base_url="http://x/v1")
        is False
    )
    assert await unload_ollama_model(model="gemma4", openai_compat_base_url="") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_ollama_ps_returns_models() -> None:
    client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.text = ""
    resp.json = MagicMock(
        return_value={"models": [{"name": "gemma4-radar", "size": 1}]}
    )
    client.get = AsyncMock(return_value=resp)
    models = await fetch_ollama_ps(
        openai_compat_base_url="http://127.0.0.1:11434/v1",
        client=client,
    )
    assert models == [{"name": "gemma4-radar", "size": 1}]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_maybe_unload_simple_respects_gate() -> None:
    with patch(
        "app.classification.ollama_lifecycle.should_manage_ollama_vram",
        return_value=False,
    ):
        assert await maybe_unload_simple_ollama(reason="test") is False

    with (
        patch(
            "app.classification.ollama_lifecycle.should_manage_ollama_vram",
            return_value=True,
        ),
        patch(
            "app.classification.ollama_lifecycle.unload_ollama_model",
            new_callable=AsyncMock,
            return_value=True,
        ) as unload,
        patch("app.classification.ollama_lifecycle.LLM_SIMPLE") as simple,
    ):
        simple.model = "gemma4-radar"
        simple.base_url = "http://host.docker.internal:11434/v1"
        assert await maybe_unload_simple_ollama(reason="test") is True
        unload.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unload_keep_alive_string_idle() -> None:
    client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "{}"
    resp.json = MagicMock(return_value={})
    client.post = AsyncMock(return_value=resp)
    client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            text="{}",
            json=MagicMock(return_value={"models": []}),
        )
    )
    await unload_ollama_model(
        model="gemma4-radar",
        openai_compat_base_url="http://127.0.0.1:11434/v1",
        keep_alive="0",
        client=client,
    )
    body = client.post.await_args.kwargs["json"]
    assert body["keep_alive"] == 0
