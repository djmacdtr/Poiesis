"""LLM provider factory tests."""

from __future__ import annotations

import yaml

from poiesis.config import ModelConfig
from poiesis.db.database import Database
from poiesis.run_loop import RunLoop, _build_llm


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


def test_runloop_uses_db_model_overrides(tmp_path, monkeypatch):
    """RunLoop should apply llm/planner_llm provider+model overrides from DB."""
    db_path = tmp_path / "poiesis.db"
    vector_path = tmp_path / "vector_store"
    config_path = tmp_path / "config.yaml"

    config = {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.7,
            "max_tokens": 1024,
        },
        "planner_llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.3,
            "max_tokens": 512,
        },
        "database": {"path": str(db_path)},
        "vector_store": {
            "path": str(vector_path),
            "embedding_model": "all-MiniLM-L6-v2",
        },
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    db = Database(str(db_path))
    db.initialize_schema()
    db.set_system_config("llm_provider", "anthropic")
    db.set_system_config("llm_model", "claude-3-7-sonnet-latest")
    db.set_system_config("planner_llm_provider", "siliconflow")
    db.set_system_config("planner_llm_model", "Qwen/Qwen2.5-72B-Instruct")
    db.close()

    captured: list[tuple[str, str]] = []

    def fake_build_llm(cfg, **kwargs):
        captured.append((cfg.provider, cfg.model))
        return object()

    monkeypatch.setattr("poiesis.run_loop._build_llm", fake_build_llm)

    RunLoop(config_path=str(config_path))

    assert captured[0] == ("anthropic", "claude-3-7-sonnet-latest")
    assert captured[1] == ("siliconflow", "Qwen/Qwen2.5-72B-Instruct")
