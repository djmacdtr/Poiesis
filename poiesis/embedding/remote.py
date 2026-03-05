"""RemoteEmbeddingProvider：通过 HTTP 调用独立 Embedding Service 获取向量。

对应配置：POIESIS_EMBEDDING_PROVIDER=remote
依赖服务：poiesis-embed（默认地址 http://poiesis-embed:9000）

服务接口（POST /embed）：
  Request:  {"texts": [...], "model": "..."}
  Response: {"vectors": [[...], ...], "dim": 384, "model": "..."}

错误提示已产品化：当服务不可达时给出清晰的排障指引。
"""

from __future__ import annotations

import os

import numpy as np

from poiesis.embedding.base import EmbeddingProvider

# 默认 Embedding Service 地址
_DEFAULT_EMBEDDING_URL = "http://poiesis-embed:9000"
# 默认模型名称（与 Embedding Service 侧保持一致）
_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# 向量维度（与 all-MiniLM-L6-v2 一致；首次请求后由服务端响应确认）
_REMOTE_DIM = 384


class RemoteEmbeddingProvider(EmbeddingProvider):
    """远程 Embedding 提供者——通过 HTTP 调用独立 Embedding Service。

    首次 encode() 调用时会向服务发送请求，并从响应中确认真实维度。
    """

    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
    ) -> None:
        """初始化远程 Embedding 提供者。

        Args:
            url: Embedding Service 的 HTTP 地址，默认读取
                 POIESIS_EMBEDDING_URL 环境变量，兜底为 http://poiesis-embed:9000。
            model: 使用的模型名称，默认读取 POIESIS_EMBEDDING_MODEL 环境变量，
                   兜底为 sentence-transformers/all-MiniLM-L6-v2。
        """
        self._url = (
            url
            or os.environ.get("POIESIS_EMBEDDING_URL", _DEFAULT_EMBEDDING_URL)
        ).rstrip("/")
        self._model = model or os.environ.get("POIESIS_EMBEDDING_MODEL", _DEFAULT_MODEL)
        # 维度在首次成功请求后由服务端确认
        self._dim: int = _REMOTE_DIM

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        """调用 Embedding Service 获取向量。

        Args:
            texts: 待编码的文本列表。
            normalize_embeddings: 是否对结果向量做 L2 归一化（客户端侧处理）。

        Returns:
            形状为 (len(texts), dim) 的 float32 数组。

        Raises:
            RuntimeError: 当 Embedding Service 不可达或返回错误时，
                          包含产品化的排障提示。
        """
        try:
            import httpx  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "RemoteEmbeddingProvider 需要 httpx。\n"
                "请执行：pip install httpx"
            ) from exc

        payload = {"texts": texts, "model": self._model}
        try:
            response = httpx.post(
                f"{self._url}/embed",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"无法连接到 Embedding Service：{self._url}\n"
                "排障提示：\n"
                "  1. 检查 POIESIS_EMBEDDING_URL 是否正确（当前：{}）\n"
                "  2. 确认 poiesis-embed 容器已启动：docker compose ps\n"
                "  3. 确认端口 9000 已正确暴露：docker compose logs embed\n"
                "  4. 轻量模式（无 embed 服务）请设置"
                " POIESIS_EMBEDDING_PROVIDER=local".format(self._url)
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Embedding Service 返回错误 HTTP {exc.response.status_code}：\n"
                f"  URL：{self._url}/embed\n"
                f"  响应：{exc.response.text[:200]}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Embedding Service 请求超时（URL：{self._url}）\n"
                "排障提示：检查服务是否正常运行，或增大超时时间。"
            ) from exc

        data = response.json()
        vectors = data["vectors"]
        # 由服务端响应确认实际维度
        if "dim" in data:
            self._dim = int(data["dim"])

        arr = np.array(vectors, dtype=np.float32)

        if normalize_embeddings:
            # L2 归一化（逐行）
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            # 避免除以零
            norms = np.where(norms > 1e-10, norms, 1.0)
            arr = (arr / norms).astype(np.float32)

        return arr
