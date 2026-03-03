"""基于向量存储相似度搜索的原创性检测器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from poiesis.vector_store.store import VectorStore


@dataclass
class OriginalityResult:
    """Result of an originality check."""

    is_original: bool
    risk_score: float
    similar_chapters: list[dict[str, Any]] = field(default_factory=list)


class OriginalityChecker:
    """Checks whether a new chapter is sufficiently different from existing chapters."""

    def check(
        self,
        content: str,
        vector_store: VectorStore,
        threshold: float = 0.85,
    ) -> OriginalityResult:
        """Check content originality against the vector store.

        Similarity scores from FAISS inner-product on normalised vectors
        are in the range [0, 1]. A score above *threshold* indicates a
        suspiciously similar existing document.

        Args:
            content: Chapter text to evaluate.
            vector_store: Populated :class:`~poiesis.vector_store.store.VectorStore`
                containing previously generated chapters.
            threshold: Cosine-similarity score above which a match is
                considered a risk.

        Returns:
            :class:`OriginalityResult` with originality verdict and
            details of any similar chapters found.
        """
        results = vector_store.search(content, k=5)

        similar: list[dict[str, Any]] = [r for r in results if r["score"] >= threshold]
        risk_score = max((r["score"] for r in results), default=0.0)

        return OriginalityResult(
            is_original=len(similar) == 0,
            risk_score=risk_score,
            similar_chapters=similar,
        )
