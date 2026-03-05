"""Poiesis Embedding 抽象层。

通过 POIESIS_EMBEDDING_PROVIDER 环境变量选择 embedding 实现：
  - local  （默认）：使用确定性哈希向量（DummyEmbeddingProvider），零依赖、纯离线
  - remote ：通过 HTTP 调用独立 Embedding Service（RemoteEmbeddingProvider）

兼容旧变量 POIESIS_EMBEDDING_MODE（dummy/real）：
  - dummy → local
  - real  → 若已设置 POIESIS_EMBEDDING_URL 则 remote，否则抛出错误提示
"""

from poiesis.embedding.base import EmbeddingProvider
from poiesis.embedding.dummy import DummyEmbeddingProvider
from poiesis.embedding.remote import RemoteEmbeddingProvider

__all__ = ["EmbeddingProvider", "DummyEmbeddingProvider", "RemoteEmbeddingProvider"]
