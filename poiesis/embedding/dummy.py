"""DummyEmbeddingProvider：基于 SHA-256 哈希的确定性 embedding 提供者。

零依赖、纯离线，适用于本地模式（POIESIS_EMBEDDING_PROVIDER=local）和测试环境。
生成的向量无语义意义，不得用于生产相似度判断。
"""

from __future__ import annotations

import hashlib

import numpy as np

from poiesis.embedding.base import EmbeddingProvider

# 向量维度常量，与 all-MiniLM-L6-v2 保持一致
_DUMMY_DIM = 384


class DummyEmbeddingProvider(EmbeddingProvider):
    """测试替身 Embedding 提供者——纯本地、确定性、零网络依赖。

    使用 SHA-256 哈希将文本映射到 384 维 float32 向量，同一输入始终
    产生相同输出。此实现不具备语义相似度能力，仅供测试与离线/本地使用。
    """

    @property
    def dim(self) -> int:
        return _DUMMY_DIM

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        """用确定性哈希生成固定维度向量（384 维）。

        注意：此为测试替身，不具备真实语义相似度，不用于生产环境。
        """
        vecs = []
        for text in texts:
            # 用 SHA-256 生成稳定的种子，避免 Python hash() 因 PYTHONHASHSEED 而随机化
            seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()
            seed = int.from_bytes(seed_bytes[:4], "big")
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(_DUMMY_DIM).astype(np.float32)
            if normalize_embeddings:
                norm = np.linalg.norm(vec)
                if norm > 1e-10:
                    vec = vec / norm
            vecs.append(vec)
        return np.array(vecs, dtype=np.float32)
