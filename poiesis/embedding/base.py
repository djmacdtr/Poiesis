"""Embedding 提供者抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class EmbeddingProvider(ABC):
    """Embedding 提供者抽象基类。

    所有 embedding 实现（本地哈希、远程服务等）均需继承此类。
    """

    @property
    @abstractmethod
    def dim(self) -> int:
        """返回向量维度。"""

    @abstractmethod
    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        """将文本列表编码为浮点向量矩阵。

        Args:
            texts: 待编码的文本列表。
            normalize_embeddings: 是否对向量做 L2 归一化。

        Returns:
            形状为 (len(texts), dim) 的 float32 数组。
        """
