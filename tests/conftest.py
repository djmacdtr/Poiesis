"""Shared pytest fixtures for the Poiesis test suite."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from pathlib import Path
from typing import Any

import pytest

from poiesis.config import (
    Config,
    DatabaseConfig,
    GenerationConfig,
    ModelConfig,
    SimilarityConfig,
    VectorStoreConfig,
)
from poiesis.db.database import Database
from poiesis.domain.world.model import WorldModel
from poiesis.llm.base import LLMClient

# ---------------------------------------------------------------------------
# 全局 fixture：测试期间强制使用 DummyEmbeddingProvider（离线，无网络依赖）
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def force_dummy_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """在所有测试中强制使用本地 dummy embedding，确保无外网依赖。"""
    monkeypatch.setenv("POIESIS_EMBEDDING_PROVIDER", "local")


@pytest.fixture(autouse=True)
def isolate_task_registry_storage(tmp_path: Path) -> Generator[None, None, None]:
    """隔离任务注册表持久化文件，避免测试污染 data/task_registry.json。"""
    from poiesis.api.task_registry import registry

    original_storage_path = registry._storage_path
    registry._storage_path = str(tmp_path / "task_registry.json")
    with registry._lock:
        registry._tasks.clear()
    registry._persist()

    try:
        yield
    finally:
        with registry._lock:
            registry._tasks.clear()
        registry._storage_path = original_storage_path

# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class MockLLMClient(LLMClient):
    """Minimal LLM client that returns canned responses for tests."""

    def __init__(
        self,
        text_response: str = "Mock response.",
        json_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(model="mock", temperature=0.0, max_tokens=100)
        self._text_response = text_response
        self._json_response: dict[str, Any] = json_response or {}

    def _complete(self, prompt: str, system: str | None = None, **kwargs: Any) -> str:
        return self._text_response

    def _complete_json(
        self, prompt: str, system: str | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return self._json_response

    def _stream_complete(
        self, prompt: str, system: str | None = None, **kwargs: Any
    ) -> Iterator[str]:
        yield self._text_response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Return a temporary, schema-initialised Database."""
    db = Database(str(tmp_path / "test.db"))
    db.initialize_schema()
    return db


@pytest.fixture
def mock_llm() -> MockLLMClient:
    """Return a MockLLMClient with empty JSON response."""
    return MockLLMClient(
        text_response="This is a generated chapter about adventure.",
        json_response={
            "passed": True,
            "violations": [],
            "warnings": [],
            "summary": "A hero sets out.",
            "key_events": ["Hero departs the village."],
            "characters_featured": ["Aelindra Voss"],
            "new_facts_introduced": [],
            "new_characters": [],
            "new_world_rules": [],
            "timeline_events": [],
            "foreshadowing": [],
            "character_updates": [],
            "title": "The First Step",
            "character_arcs": {},
            "new_facts_budget": 2,
            "foreshadowing_hints": [],
            "tone": "hopeful",
            "opening_hook": "The road ahead was long.",
        },
    )


@pytest.fixture
def sample_world(tmp_db: Database) -> WorldModel:
    """Return a WorldModel pre-populated with sample canon data."""
    tmp_db.upsert_world_rule(
        rule_key="magic_costs_life",
        description="Using magic always costs the caster some life force.",
        is_immutable=True,
        category="magic",
    )
    tmp_db.upsert_world_rule(
        rule_key="dead_stay_dead",
        description="The dead cannot be resurrected.",
        is_immutable=True,
        category="metaphysics",
    )
    tmp_db.upsert_world_rule(
        rule_key="mutable_trade_rule",
        description="Trade caravans travel monthly between islands.",
        is_immutable=False,
        category="economy",
    )
    tmp_db.upsert_character(
        name="Aelindra Voss",
        description="A scarred mage seeking redemption.",
        core_motivation="Atone for destroying her village.",
        attributes={"age": 28, "abilities": ["fire magic", "telepathy"]},
    )

    world = WorldModel()
    world.load_from_db(tmp_db)
    return world


@pytest.fixture
def sample_config() -> Config:
    """Return a minimal Config object suitable for testing."""
    return Config(
        llm=ModelConfig(
            provider="openai", model="gpt-4o", temperature=0.8, max_tokens=100
        ),
        planner_llm=ModelConfig(
            provider="openai", model="gpt-4o", temperature=0.3, max_tokens=100
        ),
        similarity=SimilarityConfig(
            originality_threshold=0.85, fact_retrieval_k=5, chapter_similarity_k=3
        ),
        generation=GenerationConfig(
            max_chapters=5, rewrite_retries=1, new_rule_budget=3, target_word_count=500
        ),
        database=DatabaseConfig(path=":memory:"),
        vector_store=VectorStoreConfig(
            path="/tmp/test_vs", embedding_model="all-MiniLM-L6-v2"
        ),
    )
