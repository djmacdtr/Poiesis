"""LLM provider factory tests."""

from __future__ import annotations

from poiesis.config import ModelConfig
from poiesis.run_loop import _build_llm


def test_build_llm_uses_openai_branch(monkeypatch):
    """provider=openai should route to OpenAI client with expected kwargs."""
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("poiesis.run_loop.OpenAIClient", FakeOpenAI)

    cfg = ModelConfig(
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=512,
        base_url="https://example-openai-proxy/v1",
    )
    _build_llm(cfg, openai_key="oa-key")

    assert captured["model"] == "gpt-4o-mini"
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 512
    assert captured["api_key"] == "oa-key"
    assert captured["base_url"] == "https://example-openai-proxy/v1"


def test_build_llm_uses_anthropic_branch(monkeypatch):
    """provider=anthropic should route to Anthropic client with expected kwargs."""
    captured: dict[str, object] = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("poiesis.run_loop.AnthropicClient", FakeAnthropic)

    cfg = ModelConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        temperature=0.1,
        max_tokens=1024,
    )
    _build_llm(cfg, anthropic_key="anth-key")

    assert captured["model"] == "claude-3-5-sonnet-20241022"
    assert captured["temperature"] == 0.1
    assert captured["max_tokens"] == 1024
    assert captured["api_key"] == "anth-key"


def test_build_llm_uses_siliconflow_branch(monkeypatch):
    """provider=siliconflow should route to SiliconFlow client with expected kwargs."""
    captured: dict[str, object] = {}

    class FakeSiliconFlow:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("poiesis.run_loop.SiliconFlowClient", FakeSiliconFlow)

    cfg = ModelConfig(
        provider="siliconflow",
        model="Qwen/Qwen2.5-72B-Instruct",
        temperature=0.6,
        max_tokens=2048,
        base_url="https://api.siliconflow.cn/v1",
    )
    _build_llm(cfg, siliconflow_key="sf-key")

    assert captured["model"] == "Qwen/Qwen2.5-72B-Instruct"
    assert captured["temperature"] == 0.6
    assert captured["max_tokens"] == 2048
    assert captured["api_key"] == "sf-key"
    assert captured["base_url"] == "https://api.siliconflow.cn/v1"
