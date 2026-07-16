"""Unit tests: OpenAI-compat payload dialects + lane provider aliases."""

from __future__ import annotations

import os
from typing import Iterator

import pytest

from app.classification.deepseek import (
    DeepSeekClient,
    build_chat_completions_payload,
)
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
        assert "reasoning_effort" not in payload
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["max_tokens"] == (2048 if effort == "none" else 8192)


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
    assert lane.model == "gpt-4.1-mini"
    assert lane.api_key == "sk-openai"
    assert lane.base_url == "https://api.openai.com/v1"
    assert lane.api_dialect == API_DIALECT_OPENAI
    assert lane.is_openai_compat is True


def test_load_lane_glm(clean_lane_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_COMPLEX_PROVIDER", "glm")
    monkeypatch.setenv("LLM_COMPLEX_MODEL", "glm-4-plus")
    monkeypatch.setenv("LLM_COMPLEX_API_KEY", "sk-glm")
    monkeypatch.setenv("LLM_COMPLEX_RPM", "0")
    monkeypatch.setenv("LLM_COMPLEX_TPM", "0")
    monkeypatch.setenv("LLM_COMPLEX_RPD", "0")

    lane = load_lane("complex", default_provider="deepseek")
    assert lane.provider == "glm"
    assert lane.model == "glm-4-plus"
    assert lane.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert lane.api_dialect == API_DIALECT_OPENAI


def test_load_lane_grok_legacy_key(
    clean_lane_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_SIMPLE_PROVIDER", "grok")
    monkeypatch.setenv("LLM_SIMPLE_MODEL", "grok-3-mini")
    monkeypatch.setenv("XAI_API_KEY", "sk-xai")
    monkeypatch.setenv("LLM_SIMPLE_RPM", "0")
    monkeypatch.setenv("LLM_SIMPLE_TPM", "0")
    monkeypatch.setenv("LLM_SIMPLE_RPD", "0")

    lane = load_lane("simple", default_provider="gemini")
    assert lane.provider == "grok"
    assert lane.api_key == "sk-xai"
    assert lane.base_url == "https://api.x.ai/v1"
    assert lane.api_dialect == API_DIALECT_OPENAI


def test_load_lane_custom_base_url(
    clean_lane_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_SIMPLE_PROVIDER", "openai")
    monkeypatch.setenv("LLM_SIMPLE_MODEL", "custom-model")
    monkeypatch.setenv("LLM_SIMPLE_API_KEY", "sk")
    monkeypatch.setenv("LLM_SIMPLE_BASE_URL", "https://proxy.example/v1/")
    monkeypatch.setenv("LLM_SIMPLE_RPM", "0")
    monkeypatch.setenv("LLM_SIMPLE_TPM", "0")
    monkeypatch.setenv("LLM_SIMPLE_RPD", "0")

    lane = load_lane("simple", default_provider="gemini")
    assert lane.base_url == "https://proxy.example/v1"
