"""poiesis/embedding/ 模块单元测试。

覆盖以下场景：
1. DummyEmbeddingProvider 行为（确定性、维度、归一化）
2. RemoteEmbeddingProvider 错误处理（服务不可达、HTTP 错误）
3. get_embedding_provider() 环境变量路由（local / remote / 旧变量兼容）
4. vector_store/providers.py 向后兼容性
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from poiesis.embedding.base import EmbeddingProvider
from poiesis.embedding.dummy import DummyEmbeddingProvider
from poiesis.embedding.remote import RemoteEmbeddingProvider
from poiesis.vector_store.providers import get_embedding_provider


# ─────────────────────────────────────────────────────────────────
# 测试 1：DummyEmbeddingProvider
# ─────────────────────────────────────────────────────────────────


class TestDummyEmbeddingProvider:
    """验证 DummyEmbeddingProvider 的确定性与维度正确性。"""

    def test_is_embedding_provider_subclass(self) -> None:
        """DummyEmbeddingProvider 应继承 EmbeddingProvider。"""
        assert issubclass(DummyEmbeddingProvider, EmbeddingProvider)

    def test_dim_is_384(self) -> None:
        """维度应为 384（与 all-MiniLM-L6-v2 一致）。"""
        p = DummyEmbeddingProvider()
        assert p.dim == 384

    def test_encode_shape(self) -> None:
        """encode() 应返回正确形状的数组。"""
        p = DummyEmbeddingProvider()
        texts = ["文本一", "文本二", "文本三"]
        vecs = p.encode(texts)
        assert vecs.shape == (3, 384)
        assert vecs.dtype == np.float32

    def test_encode_deterministic(self) -> None:
        """相同文本应始终产生相同向量（确定性）。"""
        p = DummyEmbeddingProvider()
        v1 = p.encode(["固定文本"])
        v2 = p.encode(["固定文本"])
        np.testing.assert_array_equal(v1, v2)

    def test_encode_normalized(self) -> None:
        """归一化后向量范数应接近 1.0。"""
        p = DummyEmbeddingProvider()
        vecs = p.encode(["test text"], normalize_embeddings=True)
        norm = float(np.linalg.norm(vecs[0]))
        assert abs(norm - 1.0) < 1e-5, f"范数应接近 1.0，实际为 {norm}"

    def test_encode_not_normalized(self) -> None:
        """不归一化时范数不一定为 1.0。"""
        p = DummyEmbeddingProvider()
        vecs = p.encode(["test text"], normalize_embeddings=False)
        norm = float(np.linalg.norm(vecs[0]))
        # 随机向量的范数通常不为 1.0（除非极小概率巧合）
        assert norm > 0.0, "范数应大于 0"

    def test_encode_empty_list_returns_empty_array(self) -> None:
        """encode([]) 应返回空数组（shape 为 (0, 384)）。"""
        p = DummyEmbeddingProvider()
        result = p.encode([])
        assert result.shape == (0, 384) or result.shape == (0,) or len(result) == 0

    def test_different_texts_produce_different_vectors(self) -> None:
        """不同文本应产生不同向量。"""
        p = DummyEmbeddingProvider()
        v1 = p.encode(["苹果"])
        v2 = p.encode(["香蕉"])
        assert not np.allclose(v1, v2), "不同文本不应产生相同向量"


# ─────────────────────────────────────────────────────────────────
# 测试 2：RemoteEmbeddingProvider 错误处理
# ─────────────────────────────────────────────────────────────────


class TestRemoteEmbeddingProvider:
    """验证 RemoteEmbeddingProvider 的初始化与错误处理。"""

    def test_default_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """默认 URL 应读取 POIESIS_EMBEDDING_URL 环境变量。"""
        monkeypatch.setenv("POIESIS_EMBEDDING_URL", "http://my-embed:9999")
        p = RemoteEmbeddingProvider()
        assert p._url == "http://my-embed:9999"

    def test_default_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """默认模型应读取 POIESIS_EMBEDDING_MODEL 环境变量。"""
        monkeypatch.setenv("POIESIS_EMBEDDING_MODEL", "my-custom-model")
        p = RemoteEmbeddingProvider()
        assert p._model == "my-custom-model"

    def test_url_trailing_slash_stripped(self) -> None:
        """URL 末尾的斜杠应被去除。"""
        p = RemoteEmbeddingProvider(url="http://embed:9000/")
        assert p._url == "http://embed:9000"

    def test_dim_default(self) -> None:
        """默认维度应为 384。"""
        p = RemoteEmbeddingProvider()
        assert p.dim == 384

    def test_encode_connect_error_raises_runtime_error(self) -> None:
        """服务不可达时应抛出 RuntimeError 并包含排障提示。"""
        import httpx

        p = RemoteEmbeddingProvider(url="http://nonexistent-embed:9000")

        with patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(RuntimeError) as exc_info:
                p.encode(["测试文本"])

        error_msg = str(exc_info.value)
        assert "无法连接到 Embedding Service" in error_msg
        assert "POIESIS_EMBEDDING_URL" in error_msg
        assert "docker compose" in error_msg

    def test_encode_http_error_raises_runtime_error(self) -> None:
        """HTTP 错误时应抛出 RuntimeError 并包含状态码。"""
        import httpx

        p = RemoteEmbeddingProvider(url="http://embed:9000")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch(
            "httpx.post",
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response
            ),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                p.encode(["测试文本"])

        assert "500" in str(exc_info.value)

    def test_encode_timeout_raises_runtime_error(self) -> None:
        """请求超时时应抛出 RuntimeError 并包含超时提示。"""
        import httpx

        p = RemoteEmbeddingProvider(url="http://embed:9000")

        with patch("httpx.post", side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(RuntimeError) as exc_info:
                p.encode(["测试文本"])

        assert "超时" in str(exc_info.value)

    def test_encode_success_returns_correct_array(self) -> None:
        """成功响应时应返回正确形状的 numpy 数组。"""
        p = RemoteEmbeddingProvider(url="http://embed:9000")

        # 模拟服务端响应：2 条文本，384 维向量
        mock_vectors = [[float(i) * 0.01] * 384 for i in range(2)]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vectors": mock_vectors,
            "dim": 384,
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response):
            result = p.encode(["文本一", "文本二"], normalize_embeddings=False)

        assert result.shape == (2, 384)
        assert result.dtype == np.float32

    def test_encode_updates_dim_from_response(self) -> None:
        """服务端响应的 dim 字段应更新本地维度记录。"""
        p = RemoteEmbeddingProvider(url="http://embed:9000")
        assert p.dim == 384  # 默认值

        mock_vectors = [[0.1] * 768]  # 768 维模型
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vectors": mock_vectors,
            "dim": 768,
            "model": "some-768-model",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response):
            p.encode(["文本"], normalize_embeddings=False)

        assert p.dim == 768


# ─────────────────────────────────────────────────────────────────
# 测试 3：get_embedding_provider() 路由逻辑
# ─────────────────────────────────────────────────────────────────


class TestGetEmbeddingProvider:
    """验证 get_embedding_provider() 根据环境变量选择正确的 Provider。"""

    def test_provider_local_returns_dummy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POIESIS_EMBEDDING_PROVIDER=local 应返回 DummyEmbeddingProvider。"""
        monkeypatch.setenv("POIESIS_EMBEDDING_PROVIDER", "local")
        provider = get_embedding_provider()
        assert isinstance(provider, DummyEmbeddingProvider)

    def test_provider_remote_returns_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POIESIS_EMBEDDING_PROVIDER=remote 应返回 RemoteEmbeddingProvider。"""
        monkeypatch.setenv("POIESIS_EMBEDDING_PROVIDER", "remote")
        provider = get_embedding_provider()
        assert isinstance(provider, RemoteEmbeddingProvider)

    def test_legacy_mode_dummy_returns_dummy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """旧配置 POIESIS_EMBEDDING_MODE=dummy 应返回 DummyEmbeddingProvider。"""
        monkeypatch.delenv("POIESIS_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.setenv("POIESIS_EMBEDDING_MODE", "dummy")
        provider = get_embedding_provider()
        assert isinstance(provider, DummyEmbeddingProvider)

    def test_legacy_mode_remote_returns_remote(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """旧配置 POIESIS_EMBEDDING_MODE=remote 应返回 RemoteEmbeddingProvider。"""
        monkeypatch.delenv("POIESIS_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.setenv("POIESIS_EMBEDDING_MODE", "remote")
        provider = get_embedding_provider()
        assert isinstance(provider, RemoteEmbeddingProvider)

    def test_default_returns_dummy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无任何配置时应默认返回 DummyEmbeddingProvider（零依赖）。"""
        monkeypatch.delenv("POIESIS_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("POIESIS_EMBEDDING_MODE", raising=False)
        provider = get_embedding_provider()
        assert isinstance(provider, DummyEmbeddingProvider)

    def test_provider_env_takes_precedence_over_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POIESIS_EMBEDDING_PROVIDER 优先级应高于 POIESIS_EMBEDDING_MODE。"""
        monkeypatch.setenv("POIESIS_EMBEDDING_PROVIDER", "local")
        monkeypatch.setenv("POIESIS_EMBEDDING_MODE", "remote")
        provider = get_embedding_provider()
        # PROVIDER=local 优先，应返回 Dummy
        assert isinstance(provider, DummyEmbeddingProvider)

    def test_legacy_real_mode_without_url_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """旧配置 POIESIS_EMBEDDING_MODE=real 且无 URL 时应抛出 RuntimeError 并提示迁移。"""
        monkeypatch.delenv("POIESIS_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.setenv("POIESIS_EMBEDDING_MODE", "real")
        monkeypatch.delenv("POIESIS_EMBEDDING_URL", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            get_embedding_provider()
        assert "remote" in str(exc_info.value)
        assert "poiesis-embed" in str(exc_info.value)

    def test_legacy_real_mode_with_url_returns_remote(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """旧配置 POIESIS_EMBEDDING_MODE=real 且设置了 URL 时应返回 RemoteEmbeddingProvider。"""
        monkeypatch.delenv("POIESIS_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.setenv("POIESIS_EMBEDDING_MODE", "real")
        monkeypatch.setenv("POIESIS_EMBEDDING_URL", "http://embed:9000")
        provider = get_embedding_provider()
        assert isinstance(provider, RemoteEmbeddingProvider)
