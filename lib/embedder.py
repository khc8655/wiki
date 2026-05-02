#!/usr/bin/env python3
"""
Embedding builder: calls bge-large-zh-v1.5 to vectorize cards.
Stores vectors as numpy arrays + ID mapping for fast retrieval.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from lib.llm_client import embed, MODELS


def build_card_text(card: Dict) -> str:
    """Build the text to embed from a card's content and annotations.
    Must stay under ~512 tokens for bge-large-zh-v1.5 API limit."""
    semantic = card.get("semantic", {})
    
    # Priority: title + tags (most discriminative) + body snippet
    parts = []
    
    title = card.get("title", "")
    if title:
        parts.append(title)
    
    # Semantic tags are high-signal for vector matching
    for key in ["intent_tags", "concept_tags", "keywords"]:
        tags = semantic.get(key, [])
        if tags:
            parts.append(";".join(tags[:5]))  # Top 5 per category
    
    body = card.get("body", "")
    if body:
        parts.append(body[:200])  # First 200 chars as context
    
    text = " ".join(parts)
    # Hard cap at 450 chars to stay under 512 tokens
    return text[:450]


def build_embeddings(
    cards: List[Dict],
    batch_size: int = 32,
    model: str = None,
) -> Tuple[np.ndarray, List[str]]:
    """
    Generate embeddings for all cards.
    
    Returns:
        (embedding_matrix [N x dim], card_ids [N])
    """
    model = model or MODELS["embedding"]
    card_ids = [c.get("id", str(i)) for i, c in enumerate(cards)]
    texts = [build_card_text(c) for c in cards]
    
    vectors = embed(texts, model=model, batch_size=batch_size)
    if vectors is None:
        raise RuntimeError("Embedding generation failed")
    
    matrix = np.array(vectors, dtype=np.float32)
    return matrix, card_ids


def save_embeddings(
    matrix: np.ndarray,
    card_ids: List[str],
    output_dir: Path,
):
    """Save embeddings and ID mapping to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    np.save(output_dir / "card_embeddings.npy", matrix)
    (output_dir / "card_ids.json").write_text(
        json.dumps(card_ids, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[Embedder] Saved {matrix.shape[0]} vectors (dim={matrix.shape[1]}) to {output_dir}")


def load_embeddings(path: Path) -> Tuple[np.ndarray, List[str]]:
    """Load embeddings from disk."""
    matrix = np.load(path / "card_embeddings.npy")
    card_ids = json.loads((path / "card_ids.json").read_text(encoding="utf-8"))
    return matrix, card_ids


if __name__ == "__main__":
    # Quick test
    test_cards = [
        {
            "id": "test-001",
            "title": "安全保障",
            "body": "系统支持SM2/SM3/SM4国密算法。",
            "semantic": {
                "intent_tags": ["安全保障"],
                "concept_tags": ["国密SM4", "端到端加密"],
                "keywords": ["国密算法", "TLS1.3"],
            }
        }
    ]
    matrix, ids = build_embeddings(test_cards, batch_size=1)
    print(f"Matrix shape: {matrix.shape}")
    print(f"IDs: {ids}")
    print(f"Vector[:5]: {matrix[0][:5]}")
