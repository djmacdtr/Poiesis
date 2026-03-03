"""Tests for the OriginalityChecker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from poiesis.originality import OriginalityChecker, OriginalityResult


def _make_mock_model(dim: int = 384) -> MagicMock:
    """Return a mock SentenceTransformer that produces deterministic embeddings."""
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = dim

    def _encode(texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        # Produce a consistent vector from the hash of each text
        vecs = []
        for text in texts:
            rng = np.random.default_rng(abs(hash(text)) % (2**32))
            vec = rng.random(dim).astype(np.float32)
            if normalize_embeddings:
                vec = vec / (np.linalg.norm(vec) + 1e-10)
            vecs.append(vec)
        return np.array(vecs, dtype=np.float32)

    model.encode.side_effect = _encode
    return model


@pytest.fixture
def empty_vector_store(tmp_path: Path) -> VectorStore:  # noqa: F821
    """Return an empty VectorStore backed by a mock embedding model."""
    from poiesis.vector_store.store import VectorStore

    with patch("poiesis.vector_store.store.SentenceTransformer", return_value=_make_mock_model()):
        vs = VectorStore(store_path=str(tmp_path / "vs"))
    return vs


@pytest.fixture
def populated_vector_store(tmp_path: Path) -> VectorStore:  # noqa: F821
    """Return a VectorStore with one document already indexed."""
    from poiesis.vector_store.store import VectorStore

    existing_text = (
        "Aelindra descended the crumbling steps of the ruined tower, her breath "
        "misting in the cold air. The shard-iron bracelet on her wrist grew warm."
    )

    with patch("poiesis.vector_store.store.SentenceTransformer", return_value=_make_mock_model()):
        vs = VectorStore(store_path=str(tmp_path / "vs"))
        vs.add(key="chapter:1", text=existing_text, metadata={"chapter_number": 1})
    return vs


class TestOriginalityCheckerEmptyStore:
    """Tests against an empty vector store."""

    def test_original_with_empty_store(self, empty_vector_store: object) -> None:
        """Any content is original when the store is empty."""
        checker = OriginalityChecker()
        result = checker.check("Some brand new content.", empty_vector_store, threshold=0.85)  # type: ignore[arg-type]
        assert result.is_original is True
        assert result.risk_score == 0.0
        assert result.similar_chapters == []


class TestOriginalityCheckerSimilarContent:
    """Tests with a populated store."""

    def test_identical_content_flagged(self, populated_vector_store: object) -> None:
        """Identical content should have a very high similarity score."""
        checker = OriginalityChecker()
        content = (
            "Aelindra descended the crumbling steps of the ruined tower, her breath "
            "misting in the cold air. The shard-iron bracelet on her wrist grew warm."
        )
        result = checker.check(content, populated_vector_store, threshold=0.85)  # type: ignore[arg-type]
        # Identical text → same hash → same vector → similarity near 1.0
        assert result.risk_score > 0.99
        assert result.is_original is False

    def test_different_content_passes(self, populated_vector_store: object) -> None:
        """Clearly different content (different hash → different vector) should pass."""
        checker = OriginalityChecker()
        content = (
            "Deep beneath the ocean floor, where no light had ever reached, "
            "the ancient leviathan stirred for the first time in ten thousand years."
        )
        result = checker.check(content, populated_vector_store, threshold=0.85)  # type: ignore[arg-type]
        assert result.is_original is True

    def test_threshold_respected(self, populated_vector_store: object) -> None:
        """A threshold of 0.0 flags everything; a threshold of 1.0 flags nothing."""
        checker = OriginalityChecker()
        content = "Aelindra walked down some stairs."  # different hash

        result_loose = checker.check(content, populated_vector_store, threshold=0.0)  # type: ignore[arg-type]
        result_strict = checker.check(content, populated_vector_store, threshold=1.0)  # type: ignore[arg-type]

        assert result_loose.is_original is False  # everything above 0.0
        assert result_strict.is_original is True  # nothing reaches exactly 1.0


class TestOriginalityResultDataclass:
    """Tests for the OriginalityResult dataclass."""

    def test_is_original_true(self) -> None:
        result = OriginalityResult(is_original=True, risk_score=0.1)
        assert result.is_original is True
        assert result.similar_chapters == []

    def test_is_original_false(self) -> None:
        result = OriginalityResult(
            is_original=False,
            risk_score=0.95,
            similar_chapters=[{"key": "chapter:1", "score": 0.95}],
        )
        assert result.is_original is False
        assert len(result.similar_chapters) == 1
