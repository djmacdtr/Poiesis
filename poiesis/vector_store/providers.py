"""Embedding 提供者抽象层——支持 real（sentence-transformers）与 dummy（离线测试）两种模式。

通过环境变量 POIESIS_EMBEDDING_MODE 切换：
  - real  （默认）：使用 sentence-transformers 真实语义向量
  - dummy ：使用确定性哈希向量，纯本地，无需网络，仅用于测试

注意：dummy 模式生成的向量无语义意义，不得用于生产相似度判断。
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass

# 向量维度常量，与 all-MiniLM-L6-v2 保持一致
_DUMMY_DIM = 384


class EmbeddingProvider(ABC):
    """Embedding 提供者抽象基类。"""

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


class DummyEmbeddingProvider(EmbeddingProvider):
    """测试替身 Embedding 提供者——纯本地、确定性、零网络依赖。

    使用 SHA-256 哈希将文本映射到 384 维 float32 向量，同一输入始终
    产生相同输出。此实现不具备语义相似度能力，仅供测试与离线 CI 使用。
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


class RealEmbeddingProvider(EmbeddingProvider):
    """真实 Embedding 提供者——基于 sentence-transformers，延迟加载模型。

    只有在第一次调用 encode() 时才会加载模型，避免"导入即下载"问题。
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        # 延迟加载：_model 在首次使用前保持 None
        self._model: Any = None
        self._dim: int | None = None

    def _ensure_loaded(self) -> None:
        """懒加载 sentence-transformers 模型（仅在需要时才触发下载）。"""
        if self._model is None:
            # 仅在此处导入，避免模块级 import 触发下载
            # sentence-transformers 是可选依赖，需通过 pip install "poiesis[real-embedding]" 安装
            try:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "使用 POIESIS_EMBEDDING_MODE=real 需要安装 sentence-transformers。\n"
                    "请执行：pip install \"poiesis[real-embedding]\"\n"
                    "或在构建镜像时传入构建参数：--build-arg EMBEDDING_MODE=real"
                ) from exc

            self._model = SentenceTransformer(self._model_name)
            self._dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def dim(self) -> int:
        self._ensure_loaded()
        assert self._dim is not None
        return self._dim

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        self._ensure_loaded()
        result: Any = self._model.encode(texts, normalize_embeddings=normalize_embeddings)
        return np.array(result, dtype=np.float32)


def get_embedding_provider(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingProvider:
    """根据环境变量 POIESIS_EMBEDDING_MODE 返回对应的 EmbeddingProvider。

    - POIESIS_EMBEDDING_MODE=real  → RealEmbeddingProvider（默认）
    - POIESIS_EMBEDDING_MODE=dummy → DummyEmbeddingProvider（离线/测试用）
    """
    mode = os.environ.get("POIESIS_EMBEDDING_MODE", "real").lower().strip()
    if mode == "dummy":
        return DummyEmbeddingProvider()
    return RealEmbeddingProvider(model_name=model_name)
