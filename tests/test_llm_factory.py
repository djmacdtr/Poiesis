"""Scene 服务的 LLM 构建与模型覆盖测试。"""

from __future__ import annotations

import yaml

from poiesis.api.services.scene_run_service import _build_context, _build_llm
from poiesis.config import ModelConfig
from poiesis.db.database import Database


def test_build_llm_uses_openai_branch(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("poiesis.api.services.scene_run_service.OpenAIClient", FakeOpenAI)
    cfg = ModelConfig(
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=512,
        base_url="https://example-openai-proxy/v1",
    )
    _build_llm(cfg, openai_key="oa-key", anthropic_key=None, siliconflow_key=None)

    assert captured["model"] == "gpt-4o-mini"
    assert captured["api_key"] == "oa-key"
    assert captured["base_url"] == "https://example-openai-proxy/v1"


def test_build_llm_uses_anthropic_branch(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("poiesis.api.services.scene_run_service.AnthropicClient", FakeAnthropic)
    cfg = ModelConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        temperature=0.1,
        max_tokens=1024,
    )
    _build_llm(cfg, openai_key=None, anthropic_key="anth-key", siliconflow_key=None)

    assert captured["model"] == "claude-3-5-sonnet-20241022"
    assert captured["api_key"] == "anth-key"


def test_build_llm_uses_siliconflow_branch(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSiliconFlow:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("poiesis.api.services.scene_run_service.SiliconFlowClient", FakeSiliconFlow)
    cfg = ModelConfig(
        provider="siliconflow",
        model="Qwen/Qwen2.5-72B-Instruct",
        temperature=0.6,
        max_tokens=2048,
        base_url="https://api.siliconflow.cn/v1",
    )
    _build_llm(cfg, openai_key=None, anthropic_key=None, siliconflow_key="sf-key")

    assert captured["model"] == "Qwen/Qwen2.5-72B-Instruct"
    assert captured["api_key"] == "sf-key"
    assert captured["base_url"] == "https://api.siliconflow.cn/v1"


def test_build_context_uses_db_model_overrides(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "poiesis.db"
    vector_path = tmp_path / "vector_store"
    config_path = tmp_path / "config.yaml"

    config = {
        "llm": {"provider": "openai", "model": "gpt-4o", "temperature": 0.7, "max_tokens": 1024},
        "planner_llm": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 512},
        "database": {"path": str(db_path)},
        "vector_store": {"path": str(vector_path), "embedding_model": "all-MiniLM-L6-v2"},
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

    def fake_build_llm(cfg, openai_key=None, anthropic_key=None, siliconflow_key=None):
        captured.append((cfg.provider, cfg.model))
        return object()

    monkeypatch.setattr("poiesis.api.services.scene_run_service._build_llm", fake_build_llm)
    monkeypatch.setattr(
        "poiesis.api.services.scene_run_service.VectorStore",
        lambda path, embedding_model: object(),
    )

    context, _, _ = _build_context(str(config_path), 1)
    context.db.close()

    assert captured[0] == ("siliconflow", "Qwen/Qwen2.5-72B-Instruct")
    assert captured[1] == ("anthropic", "claude-3-7-sonnet-latest")
