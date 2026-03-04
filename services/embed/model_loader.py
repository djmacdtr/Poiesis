"""模型加载器：懒加载 sentence-transformers 模型。

首次请求时才触发模型下载/加载，避免启动时长时间阻塞。
支持通过挂载 volume（/app/model_cache）复用已下载的模型。
"""

from __future__ import annotations

import os
import threading
from typing import Any

# 默认模型名称
_DEFAULT_MODEL = os.environ.get(
    "POIESIS_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

# 全局模型缓存（按模型名称索引）
_model_cache: dict[str, Any] = {}
# 保护缓存的锁，防止并发首次加载时的竞争条件
_model_lock = threading.Lock()


def get_model(model_name: str = _DEFAULT_MODEL) -> Any:
    """懒加载并返回指定的 SentenceTransformer 模型。

    首次调用时下载并加载模型，后续调用直接返回缓存实例（线程安全）。

    Args:
        model_name: HuggingFace 模型 ID 或本地路径。

    Returns:
        已加载的 SentenceTransformer 实例。
    """
    # 快速路径：无锁检查（大多数调用走此路径）
    if model_name in _model_cache:
        return _model_cache[model_name]

    # 慢速路径：加锁，防止并发首次加载时的竞争条件
    with _model_lock:
        # 再次检查，防止等锁期间其他线程已完成加载
        if model_name not in _model_cache:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            # 支持通过环境变量指定模型缓存目录（Docker volume 挂载点）
            cache_dir = os.environ.get("SENTENCE_TRANSFORMERS_HOME", "/app/model_cache")
            os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", cache_dir)

            _model_cache[model_name] = SentenceTransformer(model_name)

    return _model_cache[model_name]
