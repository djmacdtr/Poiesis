"""Poiesis Embedding Service — FastAPI 应用。

提供以下端点：
  POST /embed   — 将文本列表编码为向量
  GET  /health  — 健康检查

端口：9000（通过 uvicorn 启动）

环境变量：
  POIESIS_EMBEDDING_MODEL  — 使用的模型，默认 sentence-transformers/all-MiniLM-L6-v2
  SENTENCE_TRANSFORMERS_HOME — 模型缓存目录，默认 /app/model_cache
"""

from __future__ import annotations

import os

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.embed.model_loader import get_model

# 默认模型名称（可通过环境变量覆盖）
_DEFAULT_MODEL = os.environ.get(
    "POIESIS_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

app = FastAPI(
    title="Poiesis Embedding Service",
    description="为 poiesis-api 提供真实语义向量（sentence-transformers）",
    version="1.0.0",
)


# ── 请求/响应 Schema ──────────────────────────────────────────────


class EmbedRequest(BaseModel):
    """POST /embed 请求体。"""

    texts: list[str]
    model: str | None = None  # 可选，默认使用环境变量中配置的模型


class EmbedResponse(BaseModel):
    """POST /embed 响应体。"""

    vectors: list[list[float]]
    dim: int
    model: str


# ── 路由 ──────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点，返回 200 OK。"""
    return {"status": "ok"}


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    """将文本列表编码为语义向量。

    Args:
        request: 包含 texts（文本列表）和可选 model 的请求体。

    Returns:
        包含向量矩阵、维度和模型名称的响应体。
    """
    model_name = request.model or _DEFAULT_MODEL

    if not request.texts:
        raise HTTPException(status_code=400, detail="texts 列表不能为空")

    try:
        model = get_model(model_name)
        # 编码并归一化（与 DummyEmbeddingProvider 行为保持一致）
        raw: np.ndarray = model.encode(
            request.texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        vectors_array = np.array(raw, dtype=np.float32)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"模型推理失败：{exc}",
        ) from exc

    if vectors_array.ndim != 2 or vectors_array.shape[0] == 0:
        raise HTTPException(status_code=500, detail="模型返回了空的向量矩阵")

    dim = vectors_array.shape[1]
    vectors = vectors_array.tolist()

    return EmbedResponse(vectors=vectors, dim=dim, model=model_name)
