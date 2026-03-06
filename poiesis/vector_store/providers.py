"""Embedding 提供者抽象层。

通过 POIESIS_EMBEDDING_PROVIDER 环境变量选择实现：
    - local  （默认）：DummyEmbeddingProvider，确定性哈希向量，零依赖、纯离线
    - remote          ：RemoteEmbeddingProvider，通过 HTTP 调用独立 Embedding Service

注意：local 模式生成的向量无语义意义，不得用于生产相似度判断。
"""

from __future__ import annotations

import os

# 从新的 embedding 模块导入（向后兼容：re-export 旧名称）
from poiesis.embedding.base import EmbeddingProvider
from poiesis.embedding.dummy import DummyEmbeddingProvider
from poiesis.embedding.remote import RemoteEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "DummyEmbeddingProvider",
    "RemoteEmbeddingProvider",
    "get_embedding_provider",
]


def get_embedding_provider(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingProvider:
    """根据环境变量返回对应的 EmbeddingProvider。

    仅支持 POIESIS_EMBEDDING_PROVIDER=local|remote。

    Args:
        model_name: 模型名称（仅 remote 模式时传给 Embedding Service，local 模式忽略）。

    Returns:
        已配置的 EmbeddingProvider 实例。
    """
    provider_env = os.environ.get("POIESIS_EMBEDDING_PROVIDER", "").lower().strip()

    if provider_env == "remote":
        return RemoteEmbeddingProvider(model=model_name)
    if provider_env == "local":
        return DummyEmbeddingProvider()

    # 默认使用本地 dummy 模式（零依赖）
    return DummyEmbeddingProvider()
