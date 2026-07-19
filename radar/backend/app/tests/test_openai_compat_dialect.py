"""Unit tests: OpenAI-compat payload dialects + Ollama think + lane aliases."""

from __future__ import annotations

import os
from typing import Iterator

import pytest

from app.classification.deepseek import (
    DeepSeekClient,
    OpenAICompatClient,
    build_chat_completions_payload,
)
from app.classification.openai_compat_payload import uses_ollama_think_protocol
from app.classification.openai_compat_response import extract_assistant_json_text
from app.core.llm_lanes import (
    API_DIALECT_DEEPSEEK,
    API_DIALECT_OPENAI,
    api_dialect_for_provider,
    load_lane,
)


@pytest.fixture
def clean_lane_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove lane + legacy keys so load_lane sees a controlled env."""
    prefixes = (
        "LLM_SIMPLE_",
        "LLM_COMPLEX_",
        "GEMINI_",
        "GOOGLE_",
        "DEEPSEEK_",
        "OPENAI_",
        "GLM_",
        "ZHIPU_",
        "GROK_",
        "XAI_",
        "ANTHROPIC_",
        "CLAUDE_",
        "LLM_RPM",
        "LLM_TPM",
        "LLM_RPD",
    )
    for key in list(os.environ):
        if any(key.startswith(p) or key == p for p in prefixes):
            monkeypatch.delenv(key, raising=False)
    yield


def test_api_dialect_for_provider_mapping() -> None:
    assert api_dialect_for_provider("deepseek") == API_DIALECT_DEEPSEEK
    assert api_dialect_for_provider("openai") == API_DIALECT_OPENAI
    assert api_dialect_for_provider("glm") == API_DIALECT_OPENAI
    assert api_dialect_for_provider("grok") == API_DIALECT_OPENAI


def test_uses_ollama_think_protocol_prefixes() -> None:
    assert uses_ollama_think_protocol("gemma4:12b")
    assert uses_ollama_think_protocol("qwen3:14b")
    assert uses_ollama_think_protocol("qwen3.5:9b")
    assert not uses_ollama_think_protocol("gpt-4.1-mini")
    assert not uses_ollama_think_protocol("deepseek-v4-flash")


def test_deepseek_dialect_payload_includes_thinking() -> None:
    none_payload = build_chat_completions_payload(
        model="deepseek-v4-flash",
        system="sys",
        user="user",
        effort="none",
        api_dialect="deepseek",
    )
    assert none_payload["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in none_payload

    high_payload = build_chat_completions_payload(
        model="deepseek-v4-flash",
        system="sys",
        user="user",
        effort="high",
        api_dialect="deepseek",
    )
    assert high_payload["thinking"] == {"type": "enabled"}
    assert high_payload["reasoning_effort"] == "high"
    assert high_payload["max_tokens"] == 8192


def test_openai_dialect_payload_omits_thinking() -> None:
    for effort in ("none", "high"):
        payload = build_chat_completions_payload(
            model="gpt-4.1-mini",
            system="sys",
            user="user",
            effort=effort,
            api_dialect="openai",
        )
        assert "thinking" not in payload
        assert "think" not in payload
        assert "reasoning_effort" not in payload
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["max_tokens"] == (2048 if effort == "none" else 8192)


def test_openai_dialect_ollama_reasoner_enables_think_always() -> None:
    """Profilo F: reasoner locali (es. gemma4) pensano sempre."""
    for effort in ("none", "high"):
        payload = build_chat_completions_payload(
            model="gemma4:12b",
            system="sys",
            user="user",
            effort=effort,
            api_dialect="openai",
        )
        assert payload["think"] is True
        assert payload["reasoning_effort"] == "high"
        assert payload["max_tokens"] == 8192
        assert payload["messages"][0]["content"] == "sys"
        assert "response_format" not in payload
        assert payload.get("options", {}).get("num_predict") == 8192
        assert payload.get("options", {}).get("num_ctx") == 8192


def test_extract_assistant_json_prefers_content_falls_back_reasoning() -> None:
    assert (
        extract_assistant_json_text({"content": '{"a":1}', "reasoning": "noise"})
        == '{"a": 1}'
    )
    assert (
        extract_assistant_json_text(
            {"content": "", "reasoning": 'thought...\n{"title": "x"}'}
        )
        == '{"title": "x"}'
    )


def test_openai_compat_client_alias() -> None:
    assert OpenAICompatClient is DeepSeekClient


def test_client_build_payload_uses_dialect() -> None:
    openai_client = DeepSeekClient(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        effort="high",
        api_dialect="openai",
    )
    body = openai_client.build_payload(model="gpt-4.1-mini", system="s", user="u")
    assert "thinking" not in body

    ds_client = DeepSeekClient(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        effort="none",
        api_dialect="deepseek",
    )
    ds_body = ds_client.build_payload(model="deepseek-v4-flash", system="s", user="u")
    assert ds_body["thinking"] == {"type": "disabled"}


def test_load_lane_openai(clean_lane_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_SIMPLE_PROVIDER", "openai")
    monkeypatch.setenv("LLM_SIMPLE_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_SIMPLE_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_SIMPLE_RPM", "0")
    monkeypatch.setenv("LLM_SIMPLE_TPM", "0")
    monkeypatch.setenv("LLM_SIMPLE_RPD", "0")
    lane = load_lane("simple", default_provider="gemini")
    assert lane.provider == "openai"
    assert lane.api_dialect == API_DIALECT_OPENAI
    assert lane.model == "gpt-4.1-mini"
