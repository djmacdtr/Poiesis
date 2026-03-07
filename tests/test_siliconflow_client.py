"""SiliconFlow client behavior tests."""

from __future__ import annotations

from poiesis.llm.siliconflow_client import SiliconFlowClient


def test_siliconflow_client_uses_env_key_when_api_key_missing(monkeypatch):
    """Should read SILICONFLOW_API_KEY when explicit api_key is omitted."""
    captured: dict[str, object] = {}

    def fake_openai_init(self, model, temperature, max_tokens, api_key=None, base_url=None):
        captured["model"] = model
        captured["temperature"] = temperature
        captured["max_tokens"] = max_tokens
        captured["api_key"] = api_key
        captured["base_url"] = base_url

    monkeypatch.setenv("SILICONFLOW_API_KEY", "sf-env-key")
    monkeypatch.setattr("poiesis.llm.siliconflow_client.OpenAIClient.__init__", fake_openai_init)

    SiliconFlowClient(model="Qwen/Qwen2.5-72B-Instruct")

    assert captured["api_key"] == "sf-env-key"


def test_siliconflow_client_prefers_explicit_api_key(monkeypatch):
    """Explicit api_key should override SILICONFLOW_API_KEY env var."""
    captured: dict[str, object] = {}

    def fake_openai_init(self, model, temperature, max_tokens, api_key=None, base_url=None):
        captured["api_key"] = api_key

    monkeypatch.setenv("SILICONFLOW_API_KEY", "sf-env-key")
    monkeypatch.setattr("poiesis.llm.siliconflow_client.OpenAIClient.__init__", fake_openai_init)

    SiliconFlowClient(model="Qwen/Qwen2.5-72B-Instruct", api_key="sf-explicit-key")

    assert captured["api_key"] == "sf-explicit-key"
