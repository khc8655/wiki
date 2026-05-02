#!/usr/bin/env python3
"""
Hybrid retriever: BM25 + Vector semantic search with weighted fusion.
Replaces query_unified.py's search_knowledge function.
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from lib.retrieval_bm25 import get_retriever
from lib.vector_search import get_searcher


class HybridRetriever:
    """Combines BM25 keyword search with vector semantic search."""

    def __init__(self, cards_dir: Path, embeddings_dir: Path):
        self.bm25 = get_retriever(cards_dir)
        self.vector = get_searcher(embeddings_dir)
        self.bm25_weight = 0.4
        self.vector_weight = 0.6

    def search(self,
               query: str,
               top_k: int = 30,
               bm25_candidates: int = 100,
               vec_candidates: int = 80) -> List[Dict]:
        """
        Hybrid search: BM25 + vector fusion.
        
        Returns list of result dicts with: title, body, source, hit_rate
        """
        # 1. BM25 keyword search
        bm25_results = self.bm25.search(query, top_k=bm25_candidates, semantic_boost=0.3)
        bm25_scores = {cid: score for cid, score, _ in bm25_results}
        
        # 2. Vector semantic search
        try:
            query_vec = self.vector.get_embedding(query)
            vec_results = self.vector.search(query_vec, top_k=vec_candidates)
            vec_scores = {cid: score for cid, score in vec_results}
        except Exception as e:
            print(f"[Hybrid] Vector search failed: {e}, using BM25 only")
            vec_scores = {}
        
        # 3. Normalize and fuse
        all_ids = set(bm25_scores.keys()) | set(vec_scores.keys())
        
        # Normalization: min-max within each result set
        bm25_max = max(bm25_scores.values()) if bm25_scores else 1.0
        vec_max = max(vec_scores.values()) if vec_scores else 1.0
        
        # Build card lookup: card_id -> card data
        card_map = {cid: card for cid, _, card in bm25_results}
        # Also check vector results for any missing cards
        for cid in vec_scores:
            if cid not in card_map:
                # Look up card from BM25 retriever's card map
                card_map[cid] = self.bm25._card_map.get(cid, {})
        
        combined = []
        for cid in all_ids:
            bm25_norm = bm25_scores.get(cid, 0) / bm25_max
            vec_norm = vec_scores.get(cid, 0) / vec_max
            
            hit_rate = self.bm25_weight * bm25_norm + self.vector_weight * vec_norm
            
            if hit_rate > 0.05:  # Threshold
                card = card_map.get(cid, {})
                combined.append({
                    "title": card.get("title", ""),
                    "body": card.get("body", ""),
                    "source": f"{card.get('doc_file', 'unknown')} | {card.get('path', '')}",
                    "hit_rate": round(hit_rate, 3),
                    "id": cid,
                    "doc_file": card.get("doc_file", ""),
                    "_bm25": round(bm25_norm, 3),
                    "_vec": round(vec_norm, 3),
                })
        
        combined.sort(key=lambda x: -x["hit_rate"])
        return combined[:top_k]


# Singleton
_hybrid: Optional[HybridRetriever] = None


def get_hybrid(cards_dir: Path = None, embeddings_dir: Path = None) -> HybridRetriever:
    global _hybrid
    if _hybrid is None:
        root = Path(__file__).resolve().parents[1]
        cards_dir = cards_dir or (root / "cards" / "sections")
        embeddings_dir = embeddings_dir or (root / "index_store" / "embeddings")
        _hybrid = HybridRetriever(cards_dir, embeddings_dir)
    return _hybrid
