"""SiliconFlow integration smoke test for RunLoop wiring."""

from __future__ import annotations

from pathlib import Path

import yaml

from poiesis.run_loop import RunLoop


def test_run_loop_builds_siliconflow_clients_from_config_and_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """RunLoop should wire both writer/planner LLMs to SiliconFlow when configured."""
    captured: list[dict[str, object | None]] = []

    def fake_openai_init(self, model, temperature, max_tokens, api_key=None, base_url=None):
        captured.append(
            {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "api_key": api_key,
                "base_url": base_url,
            }
        )

    monkeypatch.setenv("SILICONFLOW_API_KEY", "sf-smoke-env-key")
    monkeypatch.setattr("poiesis.llm.siliconflow_client.OpenAIClient.__init__", fake_openai_init)

    config_path = tmp_path / "smoke_config.yaml"
    db_path = tmp_path / "smoke.db"
    vs_path = tmp_path / "vector_store"

    config_data = {
        "llm": {
            "provider": "siliconflow",
            "model": "Qwen/Qwen2.5-72B-Instruct",
            "temperature": 0.8,
            "max_tokens": 4000,
            "base_url": "https://api.siliconflow.cn/v1",
        },
        "planner_llm": {
            "provider": "siliconflow",
            "model": "Qwen/Qwen2.5-72B-Instruct",
            "temperature": 0.3,
            "max_tokens": 2000,
            "base_url": "https://api.siliconflow.cn/v1",
        },
        "similarity": {
            "originality_threshold": 0.85,
            "fact_retrieval_k": 10,
            "chapter_similarity_k": 5,
        },
        "generation": {
            "max_chapters": 2,
            "rewrite_retries": 1,
            "new_rule_budget": 3,
            "target_word_count": 500,
        },
        "database": {"path": str(db_path)},
        "vector_store": {
            "path": str(vs_path),
            "embedding_model": "all-MiniLM-L6-v2",
        },
        "world_seed": "examples/world_seed.yaml",
    }

    with config_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config_data, fh, sort_keys=False)

    run_loop = RunLoop(config_path=str(config_path))

    assert run_loop is not None
    assert len(captured) == 2
    assert captured[0]["api_key"] == "sf-smoke-env-key"
    assert captured[1]["api_key"] == "sf-smoke-env-key"
    assert captured[0]["base_url"] == "https://api.siliconflow.cn/v1"
    assert captured[1]["base_url"] == "https://api.siliconflow.cn/v1"
