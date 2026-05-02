#!/usr/bin/env python3
"""
Vector search: fast cosine similarity search over card embeddings.
Uses numpy for efficient matrix operations.
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from lib.embedder import load_embeddings
from lib.llm_client import embed, MODELS


class VectorSearcher:
    """Cosine-similarity based vector search over pre-computed embeddings."""

    def __init__(self, embeddings_dir: Path):
        self.embeddings_dir = Path(embeddings_dir)
        self.matrix, self.card_ids = load_embeddings(self.embeddings_dir)
        # Normalize for fast cosine (dot product of normalized vectors)
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._normalized = self.matrix / norms

    def search(self, query_vec: np.ndarray, top_k: int = 50) -> List[Tuple[str, float]]:
        """
        Search for most similar cards to query vector.
        
        Returns:
            List of (card_id, cosine_similarity) sorted descending
        """
        # Normalize query
        q_norm = query_vec / (np.linalg.norm(query_vec) or 1.0)
        # Dot product = cosine similarity for normalized vectors
        scores = self._normalized @ q_norm
        # Get top-k indices
        top_k = min(top_k, len(scores))
        if top_k == 0:
            return []
        k_for_partition = min(top_k, len(scores) - 1) if len(scores) > 1 else 1
        if len(scores) <= top_k:
            indices = np.argsort(-scores)
        else:
            indices = np.argpartition(-scores, k_for_partition)[:top_k]
            indices = indices[np.argsort(-scores[indices])]

        return [(self.card_ids[i], float(scores[i])) for i in indices if scores[i] > 0]

    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding vector for a query text."""
        vectors = embed([text], model=MODELS["embedding"], batch_size=1)
        if not vectors:
            raise RuntimeError("Failed to get embedding")
        return np.array(vectors[0], dtype=np.float32)


# Singleton
_searcher: Optional[VectorSearcher] = None


def get_searcher(embeddings_dir: Optional[Path] = None) -> VectorSearcher:
    global _searcher
    if _searcher is None:
        if embeddings_dir is None:
            embeddings_dir = Path(__file__).resolve().parents[1] / "index_store" / "embeddings"
        _searcher = VectorSearcher(embeddings_dir)
    return _searcher
