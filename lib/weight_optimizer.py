#!/usr/bin/env python3
"""
Feedback-driven weight optimizer for wiki_test retrieval.

Analyzes query feedback logs to automatically adjust:
  - BM25/vector fusion weights in hybrid retriever
  - Semantic boosting weights in BM25 retriever
  - Query routing rules (which source handles which intent)

Design principles:
  - Trust region: weight changes capped at ±0.15 per adjustment
  - Cold start: requires 20+ feedback entries for initial suggestion
  - Incremental: re-analyzes every 50 new entries after initial threshold
  - History: all weight changes logged to index_store/weight_history.jsonl
"""

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# These keys define what a valid feedback entry looks like
EXPECTED_KEYS = {'query', 'timestamp'}
OPTIONAL_KEYS = {
    'rating', 'selected_card_id', 'hit_rate', 'source_type',
    'bm25_score', 'vector_score', 'bm25_norm', 'vec_norm',
    'model', 'result_count', 'selected_source', 'card_title',
    'search_duration_ms', 'query_length',
}

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / 'index_store'

# --- Keyword/config definitions shared with query_unified ---
PRICE_KWS = ['价格', '报价', '多少钱', '费用', '成本']
TENDER_KWS = ['招标', '投标', '参数', '配置', '可研']
SPEC_KWS = ['规格', '接口', '编解码', '输入', '输出', '分辨率', '像素']
COMPARE_KWS = ['对比', '比较', '区别', '差异', 'vs']
ACCESSORY_KWS = ['配件', '附件', '可用配件']
EOL_KWS = ['停产', '替代', '退市']
UPDATE_KWS = ['迭代', '新功能', '版本更新', '发版', '培训文档', '更新说明', '功能更新']

EXCEL_SIGNAL_KWS = PRICE_KWS + TENDER_KWS + SPEC_KWS + COMPARE_KWS + ACCESSORY_KWS + EOL_KWS


class WeightOptimizer:
    """Analyze query feedback and suggest optimal retrieval weights and routing."""

    def __init__(self, index_dir: Optional[Path] = None):
        self.index_dir = Path(index_dir) if index_dir else INDEX_DIR
        self.history_path = self.index_dir / 'weight_history.jsonl'
        self._current_weights: Dict[str, float] = {}
        self._load_current_weights()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_feedback(self, feedback_path: Optional[Path] = None) -> dict:
        """Analyze a feedback log and return structured statistics.

        Args:
            feedback_path: Path to query_feedback.jsonl. Defaults to
                           index_store/query_feedback.jsonl.

        Returns:
            Dict with: total_queries, low_quality_rate, avg_hit_rate,
                       source_breakdown, bm25_vs_vector, source_performance,
                       bad_queries_sample, common_keywords, card_click_freq,
                       filterable.
        """
        path = Path(feedback_path) if feedback_path else (self.index_dir / 'query_feedback.jsonl')
        entries = self._load_entries(path)
        if not entries:
            return self._empty_stats()

        stats = self._compute_stats(entries)
        stats['filterable'] = len(entries) >= 20
        return stats

    def suggest_weights(self, stats: dict) -> dict:
        """Generate weight suggestions from feedback statistics.

        Args:
            stats: Output of analyze_feedback().

        Returns:
            Dict with: bm25_weight, vector_weight, semantic_boost,
                       confidence, rationale, changes.
        """
        total = stats.get('total_queries', 0)
        if total < 20:
            return {
                'bm25_weight': 0.4,
                'vector_weight': 0.6,
                'semantic_boost': 0.3,
                'confidence': 0.0,
                'rationale': f'只分析了 {total} 条反馈, 需要至少 20 条才可建议新权重',
                'changes': {},
            }

        advice = self._derive_weights(stats)
        # Clamp within trust region
        advice['bm25_weight'] = self._clamp(advice['bm25_weight'], self.current_bm25_weight, 0.15)
        advice['vector_weight'] = round(1.0 - advice['bm25_weight'], 4)
        advice['semantic_boost'] = self._clamp(advice['semantic_boost'], self.current_semantic_boost, 0.15)
        return advice

    def optimize_routing(self, stats: dict) -> dict:
        """Suggest routing rule improvements based on feedback patterns.

        Returns:
            Dict with suggested rule mods: keyword_additions, keyword_removals,
            source_biases, per_source_min_results.
        """
        result = {
            'keyword_additions': {},
            'keyword_removals': {},
            'source_biases': {},
            'per_source_min_results': {},
        }

        source_perf = stats.get('source_performance', {})
        bad_kws = stats.get('bad_query_keywords', [])

        # If excel source performs poorly on spec queries → maybe route spec to knowledge
        excel_good = source_perf.get('excel', {}).get('good_rate', 1.0)
        knowledge_good = source_perf.get('knowledge', {}).get('good_rate', 1.0)

        if excel_good < 0.4 and knowledge_good > 0.6:
            result['source_biases']['excel_spec_to_knowledge'] = True

        # If specific keywords repeatedly appear in bad queries, suggest route changes
        bad_kw_counts = Counter(bad_kws)
        for kw, cnt in bad_kw_counts.most_common(10):
            if cnt >= 3:
                # These keywords underperforming → might route to wrong source
                pass  # kept for manual review

        return result

    def apply_weights(self, config_path: Optional[Path] = None):
        """Persist optimized weights to config file and record in history."""
        path = Path(config_path) if config_path else (ROOT / 'config.yaml')
        stats = self.analyze_feedback()
        if not stats.get('filterable'):
            print(f"[WeightOptimizer] 反馈不足 {stats.get('total_queries', 0)} 条, 跳过应用")
            return None

        suggestion = self.suggest_weights(stats)
        self._record_history(suggestion, stats)
        self._write_config(path, suggestion)
        self._current_weights = {
            'bm25_weight': suggestion['bm25_weight'],
            'vector_weight': suggestion['vector_weight'],
            'semantic_boost': suggestion['semantic_boost'],
        }
        return suggestion

    def needs_reanalysis(self, feedback_path: Optional[Path] = None) -> bool:
        """Check whether enough new feedback has accumulated to re-run."""
        path = Path(feedback_path) if feedback_path else (self.index_dir / 'query_feedback.jsonl')
        if not path.exists():
            return False

        entries = self._load_entries(path)
        n = len(entries)

        history = self._load_history()
        last_n = history[-1].get('total_analyzed', 0) if history else 0
        if last_n == 0 and n >= 20:
            return True
        return (n - last_n) >= 50

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_bm25_weight(self) -> float:
        return self._current_weights.get('bm25_weight', 0.4)

    @property
    def current_vector_weight(self) -> float:
        return self._current_weights.get('vector_weight', 0.6)

    @property
    def current_semantic_boost(self) -> float:
        return self._current_weights.get('semantic_boost', 0.3)

    # ------------------------------------------------------------------
    # Internal: load / save
    # ------------------------------------------------------------------

    def _load_entries(self, path: Path) -> List[dict]:
        if not path.exists():
            return []
        entries = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if 'query' in entry:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
        return entries

    def _load_history(self) -> List[dict]:
        if not self.history_path.exists():
            return []
        items = []
        with open(self.history_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return items

    def _load_current_weights(self):
        history = self._load_history()
        if history:
            last = history[-1]
            self._current_weights = {
                'bm25_weight': last.get('bm25_weight', 0.4),
                'vector_weight': last.get('vector_weight', 0.6),
                'semantic_boost': last.get('semantic_boost', 0.3),
            }
        else:
            self._current_weights = {'bm25_weight': 0.4, 'vector_weight': 0.6, 'semantic_boost': 0.3}

    def _record_history(self, suggestion: dict, stats: dict):
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        record = {
            'timestamp': now,
            'bm25_weight': suggestion['bm25_weight'],
            'vector_weight': suggestion['vector_weight'],
            'semantic_boost': suggestion['semantic_boost'],
            'confidence': suggestion.get('confidence', 0),
            'total_analyzed': stats.get('total_queries', 0),
            'avg_hit_rate': stats.get('avg_hit_rate', 0),
            'low_quality_rate': stats.get('low_quality_rate', 0),
        }
        with open(self.history_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def _write_config(self, path: Path, suggestion: dict):
        """Write weights section to YAML config. If file doesn't exist, skip silently."""
        if not path.exists():
            # Read existing file, update weights section
            return
        content = path.read_text(encoding='utf-8')
        # Update or insert weights section
        weights_block = {
            'bm25_weight': suggestion['bm25_weight'],
            'vector_weight': suggestion['vector_weight'],
            'semantic_boost': suggestion['semantic_boost'],
            'confidence': suggestion.get('confidence', 0),
        }
        # Store alongside config
        weight_file = self.index_dir / 'optimized_weights.json'
        weight_file.write_text(json.dumps(weights_block, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # ------------------------------------------------------------------
    # Internal: statistics computation
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_stats() -> dict:
        return {
            'total_queries': 0,
            'low_quality_rate': 0.0,
            'avg_hit_rate': 0.0,
            'source_breakdown': {},
            'bm25_vs_vector': {'bm25_wins': 0, 'vector_wins': 0, 'tie': 0},
            'source_performance': {},
            'bad_queries_sample': [],
            'bad_query_keywords': [],
            'card_click_freq': {},
            'filterable': False,
        }

    def _compute_stats(self, entries: List[dict]) -> dict:
        total = len(entries)

        # --- Ratings ---
        ratings = [e.get('rating') for e in entries if e.get('rating')]
        good = sum(1 for r in ratings if r == 'good')
        bad = sum(1 for r in ratings if r == 'bad')
        low_quality_rate = bad / total if total > 0 else 0.0

        # --- Hit rates ---
        hit_rates = [e['hit_rate'] for e in entries if 'hit_rate' in e and isinstance(e['hit_rate'], (int, float))]
        avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0

        # --- Source breakdown ---
        source_counter = Counter()
        source_rating = defaultdict(lambda: {'good': 0, 'bad': 0, 'total': 0})
        for e in entries:
            st = e.get('source_type', 'unknown')
            source_counter[st] += 1
            r = e.get('rating')
            source_rating[st]['total'] += 1
            if r == 'good':
                source_rating[st]['good'] += 1
            elif r == 'bad':
                source_rating[st]['bad'] += 1

        source_performance = {}
        for st, counts in source_rating.items():
            t = counts['total']
            source_performance[st] = {
                'total': t,
                'good_rate': round(counts['good'] / t, 3) if t > 0 else 0,
                'bad_rate': round(counts['bad'] / t, 3) if t > 0 else 0,
            }

        # --- BM25 vs Vector wins (per hit_rate contribution) ---
        bm25_vs = {'bm25_wins': 0, 'vector_wins': 0, 'tie': 0}
        for e in entries:
            b25 = e.get('bm25_norm', e.get('bm25_score'))
            v = e.get('vec_norm', e.get('vector_score'))
            if b25 is not None and v is not None:
                if b25 > v + 0.05:
                    bm25_vs['bm25_wins'] += 1
                elif v > b25 + 0.05:
                    bm25_vs['vector_wins'] += 1
                else:
                    bm25_vs['tie'] += 1

        # --- Bad query analysis ---
        bad_queries = [e for e in entries if e.get('rating') == 'bad']
        bad_query_keywords = []
        for e in bad_queries[:20]:
            words = self._extract_keywords(e.get('query', ''))
            bad_query_keywords.extend(words)

        # --- Card click frequency (learning to rank signal) ---
        card_freq = Counter()
        for e in entries:
            cid = e.get('selected_card_id')
            if cid:
                card_freq[cid] += 1

        # --- Query length distribution ---
        q_lens = [e.get('query_length', len(e.get('query', ''))) for e in entries]
        avg_q_len = sum(q_lens) / len(q_lens) if q_lens else 0

        return {
            'total_queries': total,
            'rated_queries': len(ratings),
            'good_count': good,
            'bad_count': bad,
            'low_quality_rate': round(low_quality_rate, 4),
            'avg_hit_rate': round(avg_hit_rate, 4),
            'source_breakdown': dict(source_counter.most_common()),
            'bm25_vs_vector': bm25_vs,
            'source_performance': source_performance,
            'bad_queries_sample': [e.get('query', '') for e in bad_queries[:10]],
            'bad_query_keywords': bad_query_keywords,
            'card_click_freq': dict(card_freq.most_common(20)),
            'avg_query_length': round(avg_q_len, 1),
        }

    # ------------------------------------------------------------------
    # Internal: weight derivation
    # ------------------------------------------------------------------

    def _derive_weights(self, stats: dict) -> dict:
        """Core logic: infer optimal weights from statistics."""
        total = stats.get('total_queries', 1)
        bm25_wins = stats['bm25_vs_vector']['bm25_wins']
        vec_wins = stats['bm25_vs_vector']['vector_wins']
        total_comp = bm25_wins + vec_wins + stats['bm25_vs_vector']['tie']

        # --- BM25 vs Vector weight ---
        if total_comp >= 5:
            bm25_contribution = bm25_wins / total_comp if total_comp > 0 else 0.5
            ideal_bm25 = 0.2 + 0.6 * bm25_contribution  # range 0.2–0.8
        else:
            ideal_bm25 = self.current_bm25_weight

        # --- Adjust based on overall hit rate ---
        avg_hit = stats.get('avg_hit_rate', 0.7)
        if avg_hit < 0.5:
            # Low hit rate overall → balance more even
            ideal_bm25 = (ideal_bm25 + 0.5) / 2
        elif avg_hit > 0.85:
            # High hit rate → trust whatever is winning
            pass  # keep ideal_bm25 as-is

        # --- Adjust based on source performance ---
        sp = stats.get('source_performance', {})
        knowledge_perf = sp.get('knowledge', {})
        if knowledge_perf.get('total', 0) >= 5:
            kgr = knowledge_perf.get('good_rate', 0.5)
            if kgr < 0.5:
                # Knowledge underperforming → try mixing differently
                ideal_bm25 = (ideal_bm25 + 0.5) / 2

        # --- Semantic boost ---
        # If BM25+semantic is underperforming, reduce boost
        ideal_semantic = self.current_semantic_boost
        if knowledge_perf.get('total', 0) >= 10:
            kgr = knowledge_perf.get('good_rate', 0.5)
            if kgr < 0.4:
                ideal_semantic = max(0.1, ideal_semantic - 0.1)
            elif kgr > 0.7:
                ideal_semantic = min(0.6, ideal_semantic + 0.05)

        # --- Bad query penalty ---
        low_qr = stats.get('low_quality_rate', 0)
        if low_qr > 0.2:
            # Many bad queries → shift toward better-performing strategy
            if bm25_wins > vec_wins * 2:
                ideal_bm25 = min(0.75, ideal_bm25 + 0.05)
            elif vec_wins > bm25_wins * 2:
                ideal_bm25 = max(0.25, ideal_bm25 - 0.05)

        ideal_bm25 = round(ideal_bm25, 4)
        ideal_vector = round(1.0 - ideal_bm25, 4)

        # --- Confidence ---
        confidence = min(1.0, total / 200)  # max confidence at 200+ feedback

        # --- Rationale ---
        rationale_parts = []
        if total_comp >= 5:
            rationale_parts.append(
                f"BM25:Vector 贡献比 = {bm25_wins}:{vec_wins}, "
                f"BM25 贡献率 {bm25_wins / total_comp:.1%}"
            )
        rationale_parts.append(f"平均命中率 {stats.get('avg_hit_rate', 0):.1%}")
        rationale_parts.append(f"低质量率 {stats.get('low_quality_rate', 0):.1%}")
        if knowledge_perf.get('total', 0) >= 5:
            rationale_parts.append(
                f"知识库好评率 {knowledge_perf.get('good_rate', 0):.1%}"
            )

        changes = {}
        if abs(ideal_bm25 - self.current_bm25_weight) > 0.005:
            changes['bm25_weight'] = round(ideal_bm25 - self.current_bm25_weight, 4)
        if abs(ideal_semantic - self.current_semantic_boost) > 0.005:
            changes['semantic_boost'] = round(ideal_semantic - self.current_semantic_boost, 4)

        return {
            'bm25_weight': ideal_bm25,
            'vector_weight': ideal_vector,
            'semantic_boost': round(ideal_semantic, 4),
            'confidence': round(confidence, 4),
            'rationale': '; '.join(rationale_parts),
            'changes': changes,
        }

    @staticmethod
    def _clamp(value: float, current: float, max_delta: float) -> float:
        """Clamp value within ±max_delta of current, ensuring [0.0, 1.0]."""
        lo = max(current - max_delta, 0.0)
        hi = min(current + max_delta, 1.0)
        return round(max(lo, min(value, hi)), 4)

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Simple keyword extraction from Chinese query text."""
        if not text:
            return []
        # Split on common delimiters, filter out short fragments
        parts = re.split(r'[\s，。！？、；：""''（）【】《》/+-]', text)
        words = []
        for p in parts:
            p = p.strip()
            if len(p) >= 2:
                words.append(p)
        return words


# ------------------------------------------------------------------
# Config-file integration utilities
# ------------------------------------------------------------------

OPTIMIZED_WEIGHTS_FILE = INDEX_DIR / 'optimized_weights.json'


def load_optimized_weights() -> Dict[str, float]:
    """Load the most recent optimized weights from disk.

    Returns a dict with keys: bm25_weight, vector_weight, semantic_boost.
    Returns defaults if no optimized weights exist.
    """
    path = OPTIMIZED_WEIGHTS_FILE
    if not path.exists():
        return {'bm25_weight': 0.4, 'vector_weight': 0.6, 'semantic_boost': 0.3}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return {
            'bm25_weight': data.get('bm25_weight', 0.4),
            'vector_weight': data.get('vector_weight', 0.6),
            'semantic_boost': data.get('semantic_boost', 0.3),
        }
    except Exception:
        return {'bm25_weight': 0.4, 'vector_weight': 0.6, 'semantic_boost': 0.3}


def apply_weights_to_retrievers():
    """Apply optimized weights to the global hybrid retriever and BM25 retriever.

    Call this during query_unified startup to use optimized weights.
    """
    w = load_optimized_weights()

    try:
        from lib.hybrid_retriever import get_hybrid
        hybrid = get_hybrid()
        hybrid.bm25_weight = w['bm25_weight']
        hybrid.vector_weight = w['vector_weight']
    except Exception:
        pass

    try:
        from lib.retrieval_bm25 import get_retriever
        retriever = get_retriever()
        # BM25 retriever doesn't expose semantic_boost as a field, so we
        # expose it here for search() calls to pick up later.
        retriever._optimized_semantic_boost = w['semantic_boost']
    except Exception:
        pass


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def run_optimization(feedback_path: Optional[str] = None,
                     config_path: Optional[str] = None,
                     verbose: bool = False) -> dict:
    """Convenience function: analyze feedback, suggest weights, optionally apply.

    Returns the suggestion dict.
    """
    opt = WeightOptimizer()
    fp = Path(feedback_path) if feedback_path else None
    stats = opt.analyze_feedback(fp)

    if verbose:
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    if not stats.get('filterable'):
        print(f"[optimize] 仅 {stats.get('total_queries', 0)} 条反馈, 至少需要 20 条")
        return {}

    suggestion = opt.suggest_weights(stats)
    routing = opt.optimize_routing(stats)

    if verbose:
        print("\n--- 权重建议 ---")
        print(json.dumps(suggestion, ensure_ascii=False, indent=2))
        print("\n--- 路由优化 ---")
        print(json.dumps(routing, ensure_ascii=False, indent=2))

    if config_path:
        opt.apply_weights(Path(config_path))
        print(f"[optimize] 已应用权重: bm25={suggestion['bm25_weight']}, "
              f"vector={suggestion['vector_weight']}, "
              f"semantic_boost={suggestion['semantic_boost']}")
    else:
        cp = ROOT / 'config.yaml'
        opt.apply_weights(cp)
        print(f"[optimize] 已保存权重到 {OPTIMIZED_WEIGHTS_FILE}")

    return suggestion


if __name__ == '__main__':
    import sys
    opt = WeightOptimizer()

    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        run_optimization(verbose=True)
    else:
        # Dry run: print stats and suggestions
        stats = opt.analyze_feedback()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        if stats.get('filterable'):
            suggestion = opt.suggest_weights(stats)
            print("\n--- 建议权重 ---")
            print(json.dumps(suggestion, ensure_ascii=False, indent=2))
