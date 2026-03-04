"""Embedding 提供者抽象层——支持 local（离线哈希）、remote（HTTP 服务）与 real（本地模型）三种模式。

通过环境变量选择 embedding 实现（优先级：POIESIS_EMBEDDING_PROVIDER > POIESIS_EMBEDDING_MODE）：

  POIESIS_EMBEDDING_PROVIDER（推荐，新配置）：
    - local  （默认）：DummyEmbeddingProvider，确定性哈希向量，零依赖、纯离线
    - remote          ：RemoteEmbeddingProvider，通过 HTTP 调用独立 Embedding Service

  POIESIS_EMBEDDING_MODE（旧配置，向后兼容）：
    - dummy           → local
    - real            → remote（若设置了 POIESIS_EMBEDDING_URL）或报错

注意：local/dummy 模式生成的向量无语义意义，不得用于生产相似度判断。
      real 模式已弃用，请使用 remote 模式配合独立 poiesis-embed 服务。
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

    优先读取 POIESIS_EMBEDDING_PROVIDER（推荐），再回退到旧的 POIESIS_EMBEDDING_MODE。

    Args:
        model_name: 模型名称（仅 remote 模式时传给 Embedding Service，local 模式忽略）。

    Returns:
        已配置的 EmbeddingProvider 实例。
    """
    # 优先读取新配置变量
    provider_env = os.environ.get("POIESIS_EMBEDDING_PROVIDER", "").lower().strip()

    if provider_env == "remote":
        return RemoteEmbeddingProvider(model=model_name)
    if provider_env == "local":
        return DummyEmbeddingProvider()

    # 兼容旧配置变量 POIESIS_EMBEDDING_MODE
    mode = os.environ.get("POIESIS_EMBEDDING_MODE", "local").lower().strip()
    if mode == "dummy" or mode == "local":
        return DummyEmbeddingProvider()
    if mode == "remote":
        return RemoteEmbeddingProvider(model=model_name)
    if mode == "real":
        # real 模式已弃用：若配置了远程 URL 则使用 remote，否则提示迁移
        if os.environ.get("POIESIS_EMBEDDING_URL"):
            return RemoteEmbeddingProvider(model=model_name)
        raise RuntimeError(
            "POIESIS_EMBEDDING_MODE=real 已弃用。\n"
            "请改用独立 Embedding Service（推荐）：\n"
            "  1. 启动 poiesis-embed 容器：docker compose --profile full up -d\n"
            "  2. 设置环境变量：POIESIS_EMBEDDING_PROVIDER=remote\n"
            "  3. 设置服务地址：POIESIS_EMBEDDING_URL=http://poiesis-embed:9000\n"
            "轻量本地模式（无语义搜索）：POIESIS_EMBEDDING_PROVIDER=local"
        )

    # 默认使用本地 dummy 模式（零依赖）
    return DummyEmbeddingProvider()
