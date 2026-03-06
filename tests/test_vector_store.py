"""Local Embedding Provider 下的 VectorStore 与 OriginalityChecker 离线测试。

测试目标（均在 POIESIS_EMBEDDING_PROVIDER=local 下运行，无外网依赖）：
1. VectorStore 初始化不触网（不加载 sentence-transformers 模型）
2. VectorStore.add / search 行为结构正确
3. OriginalityChecker 在 dummy 模式下可执行并返回合法分数
"""

from __future__ import annotations

from pathlib import Path

from poiesis.originality import OriginalityChecker
from poiesis.vector_store.providers import DummyEmbeddingProvider
from poiesis.vector_store.store import VectorStore

# ---------------------------------------------------------------------------
# 测试 1：VectorStore 初始化不触网
# ---------------------------------------------------------------------------


class TestVectorStoreOfflineInit:
    """验证 local provider 下 VectorStore 初始化无需访问网络。"""

    def test_init_uses_dummy_provider(self, tmp_path: Path) -> None:
        """VectorStore 在 local provider 下应使用 DummyEmbeddingProvider，不加载远程模型。"""
        # force_dummy_embedding fixture (conftest autouse) 已设置 POIESIS_EMBEDDING_PROVIDER=local
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        # 确认内部 provider 是 DummyEmbeddingProvider（不是 RealEmbeddingProvider）
        assert isinstance(vs._provider, DummyEmbeddingProvider), (
            "local provider 下应使用 DummyEmbeddingProvider，而非远程服务"
        )

    def test_init_creates_store_directory(self, tmp_path: Path) -> None:
        """VectorStore 初始化后应自动创建存储目录。"""
        store_path = tmp_path / "vs_subdir"
        assert not store_path.exists()
        VectorStore(store_path=str(store_path))
        assert store_path.is_dir()

    def test_dim_correct(self, tmp_path: Path) -> None:
        """local provider 下向量维度应为 384。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        assert vs._dim == 384


# ---------------------------------------------------------------------------
# 测试 2：VectorStore.add / search 结构正确
# ---------------------------------------------------------------------------


class TestVectorStoreAddSearch:
    """验证 local provider 下 add / search 行为的结构正确性。"""

    def test_add_increases_length(self, tmp_path: Path) -> None:
        """add() 后 VectorStore 长度应增加。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        assert len(vs) == 0
        vs.add("doc:1", "第一章正文内容。")
        assert len(vs) == 1
        vs.add("doc:2", "第二章不同内容。")
        assert len(vs) == 2

    def test_search_returns_correct_structure(self, tmp_path: Path) -> None:
        """search() 结果应包含 key/text/metadata/score 字段。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        vs.add("doc:1", "英雄踏上旅程，告别故乡。", metadata={"chapter": 1})
        results = vs.search("英雄的旅程", k=1)
        assert len(results) == 1
        result = results[0]
        assert "key" in result
        assert "text" in result
        assert "metadata" in result
        assert "score" in result
        assert result["key"] == "doc:1"
        assert isinstance(result["score"], float)

    def test_search_identical_text_returns_highest_score(self, tmp_path: Path) -> None:
        """对完全相同文本的搜索应返回相似度接近 1.0 的结果。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        text = "月光洒在古老的石板路上，银色的光芒如梦如幻。"
        vs.add("doc:1", text)
        results = vs.search(text, k=1)
        assert len(results) == 1
        # dummy provider 对相同输入产生相同向量，归一化后内积应为 1.0
        assert results[0]["score"] > 0.99, f"相同文本相似度应接近 1.0，实际为 {results[0]['score']}"

    def test_search_empty_store_returns_empty(self, tmp_path: Path) -> None:
        """空 VectorStore 搜索应返回空列表。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        assert vs.search("任何查询", k=5) == []

    def test_remove_decreases_length(self, tmp_path: Path) -> None:
        """remove() 后 VectorStore 长度应减少。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        vs.add("doc:1", "内容一")
        vs.add("doc:2", "内容二")
        vs.remove("doc:1")
        assert len(vs) == 1
        assert "doc:1" not in vs.keys()
        assert "doc:2" in vs.keys()


# ---------------------------------------------------------------------------
# 测试 3：OriginalityChecker 在 dummy 模式下可执行并返回合法分数
# ---------------------------------------------------------------------------


class TestOriginalityCheckerDummyMode:
    """验证 dummy 模式下 OriginalityChecker 可正常运行并返回合法分数。"""

    def test_returns_originality_result(self, tmp_path: Path) -> None:
        """OriginalityChecker.check() 应返回 OriginalityResult 对象。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        vs.add("c:1", "勇士在烈日下骑马穿越沙漠。")
        checker = OriginalityChecker()
        result = checker.check("一场突如其来的暴风雨席卷了海岸。", vs, threshold=0.85)
        assert hasattr(result, "is_original")
        assert hasattr(result, "risk_score")
        assert hasattr(result, "similar_chapters")
        assert isinstance(result.risk_score, float)
        # FAISS 内积分数范围通常在 [-1, 1]，对非相同向量可能略小于 0
        assert -1.0 <= result.risk_score <= 1.0

    def test_identical_content_flagged(self, tmp_path: Path) -> None:
        """相同内容应被标记为非原创（相似度 > 0.99）。"""
        content = "法师在古塔的顶层凝望星空，默默计算着命运的轨迹。"
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        vs.add("c:1", content)
        checker = OriginalityChecker()
        result = checker.check(content, vs, threshold=0.85)
        assert result.is_original is False
        assert result.risk_score > 0.99

    def test_empty_store_always_original(self, tmp_path: Path) -> None:
        """空 VectorStore 下任何内容应被视为原创。"""
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        checker = OriginalityChecker()
        result = checker.check("完全新颖的叙事内容。", vs, threshold=0.85)
        assert result.is_original is True
        assert result.risk_score == 0.0
        assert result.similar_chapters == []
