"""FAISS-backed vector store with sentence-transformers embeddings."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class VectorStore:
    """Persistent FAISS vector store for semantic similarity search.

    Documents are stored with their text and metadata. The FAISS index
    and metadata are persisted to disk so that state survives restarts.
    """

    _INDEX_FILE = "index.faiss"
    _META_FILE = "metadata.pkl"

    def __init__(self, store_path: str, embedding_model: str = "all-MiniLM-L6-v2") -> None:
        """Initialise the vector store.

        Args:
            store_path: Directory where index files are persisted.
            embedding_model: Sentence-transformers model name.
        """
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

        self._model = SentenceTransformer(embedding_model)
        self._dim: int = self._model.get_sentence_embedding_dimension()  # type: ignore[assignment]

        self._index_path = self.store_path / self._INDEX_FILE
        self._meta_path = self.store_path / self._META_FILE

        # metadata: list of {key, text, metadata} dicts, index-aligned
        self._metadata: list[dict[str, Any]] = []
        # key -> position mapping for O(1) lookups
        self._key_to_pos: dict[str, int] = {}

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load existing index and metadata from disk if available."""
        if self._index_path.exists() and self._meta_path.exists():
            self._index: faiss.IndexFlatIP = faiss.read_index(str(self._index_path))  # type: ignore[attr-defined]
            with open(self._meta_path, "rb") as fh:
                self._metadata = pickle.load(fh)
            self._key_to_pos = {m["key"]: i for i, m in enumerate(self._metadata)}
        else:
            self._index = faiss.IndexFlatIP(self._dim)  # type: ignore[attr-defined]

    def _save(self) -> None:
        """Persist index and metadata to disk."""
        faiss.write_index(self._index, str(self._index_path))  # type: ignore[attr-defined]
        with open(self._meta_path, "wb") as fh:
            pickle.dump(self._metadata, fh)

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:  # type: ignore[type-arg]
        """Return a normalised embedding vector for *text*."""
        vec = self._model.encode([text], normalize_embeddings=True)
        return vec.astype(np.float32)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, key: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add or replace a document in the store.

        Args:
            key: Unique identifier for the document.
            text: Text content to embed.
            metadata: Arbitrary metadata dict stored alongside the vector.
        """
        if key in self._key_to_pos:
            self.remove(key)

        vec = self._embed(text)
        self._index.add(vec)  # type: ignore[arg-type]
        pos = len(self._metadata)
        self._metadata.append({"key": key, "text": text, "metadata": metadata or {}})
        self._key_to_pos[key] = pos
        self._save()

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return the *k* most similar documents to *query*.

        Args:
            query: Query text.
            k: Number of results to return.

        Returns:
            List of dicts with keys: ``key``, ``text``, ``metadata``,
            ``score``.
        """
        if self._index.ntotal == 0:
            return []

        vec = self._embed(query)
        k = min(k, self._index.ntotal)
        scores, indices = self._index.search(vec, k)  # type: ignore[arg-type]

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            entry = self._metadata[idx]
            if entry is None:
                continue
            results.append(
                {
                    "key": entry["key"],
                    "text": entry["text"],
                    "metadata": entry["metadata"],
                    "score": float(score),
                }
            )
        return results

    def remove(self, key: str) -> None:
        """Remove a document by key.

        FAISS FlatIndex does not support in-place deletion, so this
        rebuilds the index without the removed document.

        Args:
            key: Key of the document to remove.
        """
        if key not in self._key_to_pos:
            return

        pos = self._key_to_pos[key]
        # Mark slot as None to indicate deletion
        self._metadata[pos] = None  # type: ignore[call-overload]

        # Rebuild index from remaining entries
        remaining = [(i, m) for i, m in enumerate(self._metadata) if m is not None]
        self._metadata = [m for _, m in remaining]
        self._key_to_pos = {m["key"]: i for i, m in enumerate(self._metadata)}

        self._index = faiss.IndexFlatIP(self._dim)  # type: ignore[attr-defined]
        if self._metadata:
            texts = [m["text"] for m in self._metadata]
            vecs = self._model.encode(texts, normalize_embeddings=True).astype(np.float32)  # type: ignore[union-attr]
            self._index.add(vecs)  # type: ignore[arg-type]

        self._save()

    def __len__(self) -> int:
        """Return the number of documents in the store."""
        return len(self._metadata)

    def keys(self) -> list[str]:
        """Return all document keys."""
        return list(self._key_to_pos.keys())
