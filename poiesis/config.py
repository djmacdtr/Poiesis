"""Poiesis 配置管理模块，基于 Pydantic v2 实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration for an LLM model."""

    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, gt=0)
    base_url: str | None = None


class SimilarityConfig(BaseModel):
    """Configuration for similarity search thresholds."""

    originality_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    fact_retrieval_k: int = Field(default=10, gt=0)
    chapter_similarity_k: int = Field(default=5, gt=0)


class GenerationConfig(BaseModel):
    """Configuration for the generation loop."""

    max_chapters: int = Field(default=100, gt=0)
    rewrite_retries: int = Field(default=3, ge=0)
    new_rule_budget: int = Field(default=5, ge=0)
    target_word_count: int = Field(default=3000, gt=0)


class DatabaseConfig(BaseModel):
    """Configuration for the SQLite database."""

    path: str = "poiesis.db"


class VectorStoreConfig(BaseModel):
    """Configuration for the vector store."""

    path: str = "vector_store"
    embedding_model: str = "all-MiniLM-L6-v2"


class Config(BaseModel):
    """Top-level Poiesis configuration."""

    llm: ModelConfig = Field(default_factory=ModelConfig)
    planner_llm: ModelConfig = Field(
        default_factory=lambda: ModelConfig(temperature=0.3, max_tokens=2000)
    )
    similarity: SimilarityConfig = Field(default_factory=SimilarityConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    world_seed: str = "examples/world_seed.yaml"

    model_config = {"extra": "allow"}


def load_config(path: str | Path = "config.yaml") -> Config:
    """Load configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Populated Config object.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the config file contains invalid values.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    return Config(**raw)
