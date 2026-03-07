"""基于 FAISS 和可配置 EmbeddingProvider 的向量存储。

通过 POIESIS_EMBEDDING_PROVIDER 环境变量选择 embedding 实现：
    - remote：调用独立 Embedding Service，使用真实语义向量
    - local ：确定性哈希向量，离线/CI 测试专用
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from poiesis.vector_store.providers import EmbeddingProvider, get_embedding_provider


class VectorStore:
    """Persistent FAISS vector store for semantic similarity search.

    Documents are stored with their text and metadata. The FAISS index
    and metadata are persisted to disk so that state survives restarts.
    """

    _INDEX_FILE = "index.faiss"
    _META_FILE = "metadata.pkl"

    def __init__(
        self,
        store_path: str,
        embedding_model: str = "all-MiniLM-L6-v2",
        provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialise the vector store.

        Args:
            store_path: Directory where index files are persisted.
            embedding_model: Embedding 模型名称（remote 模式时传递给服务端）。
            provider: 可选的自定义 EmbeddingProvider；若为 None 则由环境变量决定。
        """
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        # 优先使用传入的 provider，否则根据 POIESIS_EMBEDDING_PROVIDER 决定
        self._provider: EmbeddingProvider = provider or get_embedding_provider(embedding_model)
        self._dim: int = self._provider.dim

        self._index_path = self.store_path / self._INDEX_FILE
        self._meta_path = self.store_path / self._META_FILE

        # metadata：与 FAISS 索引位置对齐的文档元数据列表
        self._metadata: list[dict[str, Any]] = []
        # key -> 位置的映射，支持 O(1) 复杂度的查找
        self._key_to_pos: dict[str, int] = {}

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load existing index and metadata from disk if available."""
        if self._index_path.exists() and self._meta_path.exists():
            self._index: faiss.IndexFlatIP = faiss.read_index(str(self._index_path))
            with open(self._meta_path, "rb") as fh:
                self._metadata = pickle.load(fh)
            self._key_to_pos = {m["key"]: i for i, m in enumerate(self._metadata)}
        else:
            self._index = faiss.IndexFlatIP(self._dim)

    def _save(self) -> None:
        """Persist index and metadata to disk."""
        faiss.write_index(self._index, str(self._index_path))
        with open(self._meta_path, "wb") as fh:
            pickle.dump(self._metadata, fh)

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        """Return a normalised embedding vector for *text*."""
        return self._provider.encode([text], normalize_embeddings=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, key: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add or replace a document in the store.

        Args:
            key: Unique identifier for the document.
            text: Text content to embed.
            metadata: Arbitrary metadata dict stored alongside the vector.
        """
        if key in self._key_to_pos:
            self.remove(key)

        vec = self._embed(text)
        self._index.add(vec)
        pos = len(self._metadata)
        self._metadata.append({"key": key, "text": text, "metadata": metadata or {}})
        self._key_to_pos[key] = pos
        self._save()

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return the *k* most similar documents to *query*.

        Args:
            query: Query text.
            k: Number of results to return.

        Returns:
            List of dicts with keys: ``key``, ``text``, ``metadata``,
            ``score``.
        """
        if self._index.ntotal == 0:
            return []

        vec = self._embed(query)
        k = min(k, self._index.ntotal)
        scores, indices = self._index.search(vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            entry = self._metadata[idx]
            if entry is None:
                continue
            results.append(
                {
                    "key": entry["key"],
                    "text": entry["text"],
                    "metadata": entry["metadata"],
                    "score": float(score),
                }
            )
        return results

    def remove(self, key: str) -> None:
        """Remove a document by key.

        FAISS FlatIndex does not support in-place deletion, so this
        rebuilds the index without the removed document.

        Args:
            key: Key of the document to remove.
        """
        if key not in self._key_to_pos:
            return

        pos = self._key_to_pos[key]
        # 将该槽位标记为 None 表示已删除
        self._metadata[pos] = None  # type: ignore[call-overload]

        # 从剩余条目中重建索引
        remaining = [(i, m) for i, m in enumerate(self._metadata) if m is not None]
        self._metadata = [m for _, m in remaining]
        self._key_to_pos = {m["key"]: i for i, m in enumerate(self._metadata)}

        self._index = faiss.IndexFlatIP(self._dim)
        if self._metadata:
            texts = [m["text"] for m in self._metadata]
            vecs = self._provider.encode(texts, normalize_embeddings=True)
            self._index.add(vecs)

        self._save()

    def __len__(self) -> int:
        """Return the number of documents in the store."""
        return len(self._metadata)

    def keys(self) -> list[str]:
        """Return all document keys."""
        return list(self._key_to_pos.keys())
