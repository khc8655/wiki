#!/usr/bin/env python3
"""
BM25-based retrieval engine for wiki knowledge base.
Replaces simple scoring (score += 15/25) with proper TF-IDF + length normalization.
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from functools import lru_cache


class BM25Retriever:
    """BM25 retrieval for knowledge base cards."""
    
    def __init__(self, cards_dir: Path, k1: float = 1.5, b: float = 0.75):
        self.cards_dir = Path(cards_dir)
        self.k1 = k1  # BM25 parameter: term frequency saturation
        self.b = b    # BM25 parameter: length normalization
        self._corpus = None
        self._doc_freqs = None
        self._avg_dl = None
        self._doc_lengths = None
        self._card_map = None
        self._build_index()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize Chinese text using character-based + bigram approach."""
        if not text:
            return []
        # 保护特殊术语: H.264, H.265, H.323 等
        # 先替换点为占位符
        text = re.sub(r'([A-Za-z])\.(\d)', r'\1DOT\2', text)
        # Clean text: 先在中英文/数字交界处插入空格
        text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff])', r'\1 \2', text)
        text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z0-9])', r'\1 \2', text)
        # 然后清理其他特殊字符（保留DOT占位符）
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9DOT]', ' ', text)
        # 恢复点
        text = text.replace('DOT', '.')
        
        # Stopwords
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        
        tokens = []
        words = text.split()
        
        for word in words:
            word = word.strip()
            if len(word) == 0:
                continue
            elif len(word) == 1:
                if word not in stopwords:
                    tokens.append(word.lower())
            elif len(word) == 2:
                tokens.append(word.lower())
            else:
                # Chinese: extract bigrams for better recall
                # English/alphanumeric: keep as whole
                if all('\u4e00' <= c <= '\u9fff' for c in word):
                    # Chinese word: extract bigrams
                    for i in range(len(word) - 1):
                        bigram = word[i:i+2]
                        if not all(c in stopwords for c in bigram):
                            tokens.append(bigram.lower())
                    # Also add the full word if length reasonable
                    if len(word) <= 6:
                        tokens.append(word.lower())
                else:
                    # Alphanumeric (型号如 AE650, XE800): 保留完整词 + 拆分
                    # 先保留完整型号
                    tokens.append(word.lower())
                    # 再尝试拆分驼峰（如 VideoCodec -> video, codec）
                    parts = re.split(r'(?=[A-Z])|[_\-]', word)
                    for part in parts:
                        part = part.strip()
                        if len(part) >= 2 and part.lower() != word.lower():
                            tokens.append(part.lower())
        
        return [t for t in tokens if t and t not in stopwords and len(t) >= 2]
    
    def _build_index(self):
        """Build BM25 index from all cards."""
        self._corpus = []
        self._card_map = {}
        total_length = 0
        doc_count = 0
        
        for card_file in self.cards_dir.glob('*.json'):
            try:
                card = json.loads(card_file.read_text(encoding='utf-8'))
                card_id = card.get('id', card_file.stem)
                
                # Combine all text fields including semantic tags for better recall
                semantic = card.get('semantic', {})
                tag_text = ' '.join(
                    semantic.get('intent_tags', []) +
                    semantic.get('concept_tags', []) +
                    semantic.get('keywords', []) +
                    semantic.get('models', [])
                )
                text = f"{card.get('title', '')} {card.get('body', '')} {tag_text} {card.get('path', '')}"
                tokens = self._tokenize(text)
                
                self._corpus.append((card_id, tokens, card))
                self._card_map[card_id] = card
                total_length += len(tokens)
                doc_count += 1
                
            except Exception as e:
                continue
        
        if doc_count == 0:
            self._avg_dl = 1.0
            self._doc_freqs = {}
            return
        
        self._avg_dl = total_length / doc_count
        
        # Calculate document frequencies
        self._doc_freqs = {}
        for _, tokens, _ in self._corpus:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1
        
        self._doc_lengths = {cid: len(tokens) for cid, tokens, _ in self._corpus}
    
    def _calc_idf(self, term: str, n_docs: int) -> float:
        """Calculate IDF with smoothing."""
        df = self._doc_freqs.get(term, 0)
        if df == 0:
            return 0
        # BM25 IDF with smoothing
        return math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
    
    def _bm25_score(self, doc_tokens: List[str], query_tokens: List[str], doc_length: float) -> float:
        """Calculate BM25 score for a document."""
        if not query_tokens:
            return 0
        
        score = 0
        n_docs = len(self._corpus)
        
        for query_term in query_tokens:
            idf = self._calc_idf(query_term, n_docs)
            tf = doc_tokens.count(query_term)
            
            if tf == 0:
                continue
            
            # BM25 term weighting
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_length / self._avg_dl)
            score += idf * numerator / denominator
        
        return score
    
    def search(self, query: str, top_k: int = 20, semantic_boost: float = 0.3) -> List[Tuple[str, float, Dict]]:
        """
        Search cards using BM25 + semantic tag boosting.
        
        Args:
            query: Search query
            top_k: Number of results to return
            semantic_boost: Weight for semantic tag matching (0-1)
        
        Returns:
            List of (card_id, score, card_data) tuples
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        results = []
        
        for card_id, doc_tokens, card in self._corpus:
            # BM25 score
            doc_length = len(doc_tokens)
            bm25_score = self._bm25_score(doc_tokens, query_tokens, doc_length)
            
            # Semantic tag boost - uses new annotation fields (all Chinese)
            semantic_score = 0
            if semantic_boost > 0:
                semantic = card.get('semantic', {})
                all_tags = []
                for key in ['intent_tags', 'concept_tags', 'keywords', 'scenario_tags', 'models']:
                    all_tags.extend(semantic.get(key, []))
                
                for tag in all_tags:
                    tag_tokens = self._tokenize(tag)
                    for qt in query_tokens:
                        if any(qt in tt or tt in qt for tt in tag_tokens):
                            semantic_score += 1.0
            
            total_score = bm25_score + semantic_boost * semantic_score
            
            if total_score > 0:
                results.append((card_id, total_score, card))
        
        # Sort by score descending
        results.sort(key=lambda x: -x[1])
        return results[:top_k]
    
    def search_with_semantic(self, query: str, intent_tags: List[str] = None, 
                            concept_tags: List[str] = None, top_k: int = 20) -> List[Tuple[str, float, Dict, str]]:
        """
        Search with structured semantic filtering.
        
        Returns:
            List of (card_id, score, card_data, match_type) tuples
            match_type: 'bm25' | 'semantic' | 'both'
        """
        query_tokens = self._tokenize(query)
        results = []
        
        for card_id, doc_tokens, card in self._corpus:
            doc_length = len(doc_tokens)
            bm25_score = self._bm25_score(doc_tokens, query_tokens, doc_length)
            
            semantic = card.get('semantic', {})
            card_intents = set(semantic.get('intent_tags', []))
            card_concepts = set(semantic.get('concept_tags', []))
            
            match_type = []
            
            # Check semantic matches
            if intent_tags and any(it in card_intents for it in intent_tags):
                bm25_score *= 1.5  # Boost for intent match
                match_type.append('intent')
            
            if concept_tags and any(ct in card_concepts for ct in concept_tags):
                bm25_score *= 1.3  # Boost for concept match
                match_type.append('concept')
            
            match_str = '+'.join(match_type) if match_type else 'bm25'
            
            if bm25_score > 0:
                results.append((card_id, bm25_score, card, match_str))
        
        results.sort(key=lambda x: -x[1])
        return results[:top_k]


# Singleton pattern
_retriever_instance = None

def get_retriever(cards_dir: Optional[Path] = None) -> BM25Retriever:
    """Get or create BM25 retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        if cards_dir is None:
            cards_dir = Path(__file__).resolve().parents[1] / 'cards' / 'sections'
        _retriever_instance = BM25Retriever(cards_dir)
    return _retriever_instance


# Export main class and functions
__all__ = ['BM25Retriever', 'get_retriever']