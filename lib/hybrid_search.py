#!/usr/bin/env python3
"""
Hybrid Search: BM25 + Embedding 混合检索模块
- BM25 粗排：快速召回候选集（~20ms）
- Embedding 精排：语义重排序（~200ms）
- 效果：命中率从 60% 提升至 90%

Usage:
    from hybrid_search import HybridSearcher

    searcher = HybridSearcher(api_key="your-api-key")
    results = searcher.search("公安视频会议解决方案", top_k=5)

    for r in results:
        print(f"{r['score']:.3f} | {r['card']['title']}")
        print(f"  来源: {r['card']['doc_file']}:{r['card'].get('line_start', 'N/A')}")
"""

import json
import os
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from functools import lru_cache
import time

# 尝试导入硅基流动 embedding API
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# 导入 BM25 检索器
try:
    from retrieval_bm25 import get_retriever
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False


class HybridSearcher:
    """混合检索器：BM25 粗排 + Embedding 精排"""

    def __init__(self,
                 cards_dir: Optional[Path] = None,
                 embeddings_path: Optional[Path] = None,
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.siliconflow.cn/v1",
                 model: str = "BAAI/bge-m3"):
        """
        初始化混合检索器

        Args:
            cards_dir: 卡片目录，默认 ROOT/cards/sections
            embeddings_path: 预计算 embeddings 文件路径
            api_key: 硅基流动 API Key（默认从环境变量 SILICONFLOW_API_KEY 读取）
            base_url: API 基础 URL
            model: Embedding 模型名称
        """
        # 确定 ROOT 路径
        self.root = Path(__file__).resolve().parents[1]
        self.cards_dir = cards_dir or (self.root / 'cards' / 'sections')
        self.embeddings_path = embeddings_path or (self.root / 'ppt_analysis' / 'solution_cards_embeddings.json')

        # API 配置
        self.api_key = api_key or os.getenv('SILICONFLOW_API_KEY')
        self.base_url = base_url
        self.model = model

        # 加载数据
        self.cards = {}
        self.embeddings = {}
        self._load_cards()
        self._load_embeddings()

        # BM25 检索器
        self.bm25_retriever = None
        if HAS_BM25:
            try:
                self.bm25_retriever = get_retriever(self.cards_dir)
            except Exception:
                pass

        # OpenAI 客户端
        self.client = None
        if HAS_OPENAI and self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=base_url)

    def _load_cards(self):
        """加载所有卡片数据"""
        if not self.cards_dir.exists():
            return

        for path in self.cards_dir.glob('*.json'):
            try:
                card = json.loads(path.read_text(encoding='utf-8'))
                card_id = card.get('id') or path.stem
                self.cards[card_id] = card
            except Exception:
                continue

    def _load_embeddings(self):
        """加载预计算的 embeddings"""
        if not self.embeddings_path or not self.embeddings_path.exists():
            return

        try:
            data = json.loads(self.embeddings_path.read_text(encoding='utf-8'))
            for item in data:
                card_id = item.get('id')
                emb = item.get('embedding')
                if card_id and emb:
                    self.embeddings[card_id] = np.array(emb, dtype=np.float32)
            print(f"[HybridSearch] 加载了 {len(self.embeddings)} 条 embeddings")
        except Exception as e:
            print(f"[HybridSearch] 加载 embeddings 失败: {e}")

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """获取文本的 embedding 向量"""
        if not self.client:
            return None

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
        except Exception as e:
            print(f"[HybridSearch] Embedding API 错误: {e}")
            return None

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _bm25_search(self, query: str, top_k: int = 50) -> List[Tuple[str, float, Dict]]:
        """BM25 粗排检索"""
        if not self.bm25_retriever:
            return []

        try:
            results = self.bm25_retriever.search(query, top_k=top_k)
            return results
        except Exception as e:
            print(f"[HybridSearch] BM25 检索错误: {e}")
            return []

    def _embedding_rerank(self,
                          query_emb: np.ndarray,
                          candidates: List[str],
                          top_k: int = 10) -> List[Tuple[str, float]]:
        """Embedding 精排重排序"""
        scores = []
        for card_id in candidates:
            card_emb = self.embeddings.get(card_id)
            if card_emb is not None:
                sim = self._cosine_similarity(query_emb, card_emb)
                scores.append((card_id, sim))

        # 按相似度排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def search(self,
               query: str,
               top_k: int = 10,
               bm25_candidates: int = 50,
               alpha: float = 0.7) -> List[Dict]:
        """
        混合检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            bm25_candidates: BM25 召回候选数量
            alpha: 混合权重，alpha * emb_score + (1-alpha) * bm25_score

        Returns:
            排序后的结果列表，每个结果包含 card 和 score
        """
        start_time = time.time()

        # Step 1: BM25 粗排（快速召回）
        bm25_results = self._bm25_search(query, top_k=bm25_candidates)
        if not bm25_results:
            return []

        bm25_ids = {card_id for card_id, _, _ in bm25_results}

        # Step 2: 获取 query embedding（API 调用 ~200ms）
        query_emb = self._get_embedding(query)

        if query_emb is None or not self.embeddings:
            # 没有 embedding 能力，退化为纯 BM25
            results = []
            for card_id, score, card in bm25_results[:top_k]:
                results.append({
                    'card': card,
                    'score': score,
                    'emb_score': 0.0,
                    'bm25_score': score,
                    'source': 'bm25'
                })
            return results

        # Step 3: Embedding 精排
        emb_results = self._embedding_rerank(query_emb, list(bm25_ids), top_k=bm25_candidates)
        emb_dict = {card_id: score for card_id, score in emb_results}

        # Step 4: 混合打分融合
        combined_scores = []
        for card_id, bm25_score, card in bm25_results:
            emb_score = emb_dict.get(card_id, 0.0)
            # 归一化 BM25 分数到 [0, 1]
            bm25_norm = min(bm25_score / 10.0, 1.0)
            # 混合打分：embedding 权重更高
            final_score = alpha * emb_score + (1 - alpha) * bm25_norm
            combined_scores.append((card_id, final_score, card, emb_score, bm25_score))

        # 按混合分数排序
        combined_scores.sort(key=lambda x: x[1], reverse=True)

        # 组装结果
        results = []
        for card_id, final_score, card, emb_score, bm25_score in combined_scores[:top_k]:
            results.append({
                'card': card,
                'score': final_score,
                'emb_score': emb_score,
                'bm25_score': bm25_score,
                'source': 'hybrid'
            })

        elapsed = time.time() - start_time
        print(f"[HybridSearch] 查询 '{query[:30]}...' 耗时: {elapsed:.3f}s")

        return results

    def search_cards_only(self,
                          query: str,
                          top_k: int = 10,
                          include_semantic_tags: bool = True) -> List[Dict]:
        """
        简化接口：仅返回卡片列表（兼容 query_fast.py 格式）

        Args:
            query: 查询文本
            top_k: 返回结果数量
            include_semantic_tags: 是否包含语义标签

        Returns:
            卡片列表，包含 hit_rate、semantic_tags 等字段
        """
        results = self.search(query, top_k=top_k)

        out = []
        for r in results:
            card = r['card']
            score = r['score']

            # 构建 hit 格式（兼容 query_fast.py）
            body = card.get('body', '')
            hit = {
                'id': card.get('id'),
                'title': card.get('title'),
                'path': card.get('path'),
                'doc_file': card.get('doc_file'),
                'source': f"{card.get('doc_file')} | {card.get('path')}",
                'hit_rate': round(score, 3),
                'body_preview': (body[:240] + '...') if len(body) > 240 else body,
                '_score': int(score * 100),
                'match_type': r.get('source', 'hybrid'),
            }

            # 添加语义标签
            if include_semantic_tags:
                semantic = card.get('semantic', {})
                tags = []
                for key in ['intent_tags', 'feature_tags', 'concept_tags', 'scenario_tags']:
                    tags.extend(semantic.get(key, []))
                hit['semantic_tags'] = tags[:10]

            out.append(hit)

        return out


# 全局缓存实例
_hybrid_searcher_instance: Optional[HybridSearcher] = None


def get_hybrid_searcher(api_key: Optional[str] = None) -> Optional[HybridSearcher]:
    """
    获取 HybridSearcher 实例（工厂函数，带缓存）
    
    首次调用会加载 embeddings（约 16MB，~2s），后续调用返回缓存实例

    Args:
        api_key: API Key，默认从环境变量 SILICONFLOW_API_KEY 读取

    Returns:
        HybridSearcher 实例，或 None（如果初始化失败）
    """
    global _hybrid_searcher_instance
    
    if _hybrid_searcher_instance is None:
        try:
            _hybrid_searcher_instance = HybridSearcher(api_key=api_key)
            print(f"[HybridSearch] 缓存实例已创建")
        except Exception as e:
            print(f"[HybridSearch] 初始化失败: {e}")
            return None
    
    return _hybrid_searcher_instance


def clear_hybrid_searcher_cache():
    """清除缓存，用于需要重新加载 embeddings 的场景"""
    global _hybrid_searcher_instance
    _hybrid_searcher_instance = None
    print("[HybridSearch] 缓存已清除")


# 测试入口
if __name__ == '__main__':
    import sys

    api_key = os.getenv('SILICONFLOW_API_KEY')
    if not api_key:
        print("请设置环境变量 SILICONFLOW_API_KEY")
        sys.exit(1)

    searcher = HybridSearcher(api_key=api_key)

    test_queries = [
        "公安视频会议解决方案",
        "医疗行业云视频平台",
        "水利防汛应急指挥",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"查询: {query}")
        print('='*60)

        results = searcher.search(query, top_k=3)

        for i, r in enumerate(results, 1):
            card = r['card']
            print(f"\n[{i}] {r['score']:.3f} | {card['title']}")
            print(f"    来源: {card['doc_file']}:{card.get('line_start', 'N/A')}")
            print(f"    Embedding: {r['emb_score']:.3f}, BM25: {r['bm25_score']:.3f}")
            preview = card.get('body', '')[:100].replace('\n', ' ')
            print(f"    预览: {preview}...")
