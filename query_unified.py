#!/usr/bin/env python3
"""
Unified query engine for wiki_test knowledge base.
Four-source routing: 表格类 | 方案类 | 更新类 | PPT类

Architecture:
  User Query → Intent Classifier → Source Router
    ├─ 表格类: SQLite search (excel_db.py)
    ├─ 方案类: Hybrid BM25+Vector (hybrid_retriever.py)
    ├─ 更新类: BM25 coarse (retrieval_bm25.py, no vector)
    └─ PPT类:  (TBD - image-understanding cards)

Usage:
    python3 query_unified.py "AE700的接口参数"
    python3 query_unified.py "视频会议安全加密方案" --json
    python3 query_unified.py "3月迭代更新" --limit 10
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'lib'))

from excel_db import get_excel_db
from retrieval_bm25 import get_retriever
from hybrid_retriever import get_hybrid
from weight_optimizer import (
    WeightOptimizer, load_optimized_weights,
    apply_weights_to_retrievers, run_optimization,
)
from feedback import log_query, record_feedback, get_last_query_id, record_follow_up, get_stats
from query_refiner import refine_query

# Model extraction regex
MODEL_RE = re.compile(
    r'(AE\d{3}[A-Z]?|XE\d{3}[A-Z]?|GE\d{3}[A-Z]?|PE\d{4}|TP\d{3}(?:-[A-Z])?|'
    r'MX\d{2}|AC\d{2}|NC\d{2}|NP\d{2}(?:V?\d+)?|ME\d{3,4}|XM\d{4})',
    re.I
)

# Intent classification keywords
PRICE_KWS = ['价格', '报价', '多少钱', '费用', '成本']
TENDER_KWS = ['招标', '投标', '参数', '配置', '可研']
SPEC_KWS = ['规格', '接口', '编解码', '输入', '输出', '分辨率', '像素']
COMPARE_KWS = ['对比', '比较', '区别', '差异', 'vs']
ACCESSORY_KWS = ['配件', '附件', '可用配件']
EOL_KWS = ['停产', '替代', '退市']
UPDATE_KWS = ['迭代', '新功能', '版本更新', '发版', '培训文档', '更新说明', '功能更新']


def extract_models(query: str) -> List[str]:
    return sorted({m.upper() for m in MODEL_RE.findall(query)})


def classify_query(query: str) -> Tuple[str, List[str]]:
    """
    Classify query intent and extract models.
    
    Returns:
        (source_type, models)
        source_type: 'excel' | 'knowledge' | 'update' | 'ppt'
    """
    models = extract_models(query)
    q = query.lower()

    # 表格类: 有型号 + 明确的数据查询意图
    excel_keywords = PRICE_KWS + TENDER_KWS + SPEC_KWS + COMPARE_KWS + ACCESSORY_KWS + EOL_KWS
    if models:
        if any(k in q for k in excel_keywords):
            return 'excel', models
        # 只有型号,默认查表格(参数最权威)
        return 'excel', models

    # 更新类: 版本/迭代/新功能相关
    if any(k in q for k in UPDATE_KWS):
        return 'update', models

    # PPT类 (预留)
    if 'ppt' in q or '幻灯片' in q:
        return 'ppt', models

    # 方案类: 概念性/场景性问题
    return 'knowledge', models


def search_excel(query: str, models: List[str]) -> List[Dict]:
    """Search structured Excel data: pricing, specs, comparison."""
    db = get_excel_db()
    results = []
    q = query.lower()

    want_tender = '招标' in q or '投标' in q or '可研' in q
    want_channel = '渠道' in q or '通路' in q or '简单' in q
    want_spec = any(k in q for k in SPEC_KWS)
    want_price = any(k in q for k in PRICE_KWS)
    want_compare = any(k in q for k in COMPARE_KWS)
    
    # If no specific type specified, give all
    want_all = not (want_tender or want_channel or want_spec or want_price or want_compare)
    
    for model in models:
        # 1. Proposal table (multi-phase params)
        rows = db.search_proposal_by_model(model)
        for r in rows:
            product_model = r.get('product_model', '').upper().replace('小鱼易连', '').strip()
            if model == product_model:
                hit_rate = 1.0
            elif model in product_model:
                hit_rate = 0.7
            else:
                hit_rate = 0.5

            # 招标参数
            if want_tender or want_all:
                body = r.get('phase_tender', '').strip()
                if body:
                    results.append(_make_excel_hit(
                        r, '招标参数', body, hit_rate * 0.9))

            # 方案参数(最完整)
            if not want_spec and not want_price:
                body = r.get('phase_proposal', '').strip()
                if body:
                    results.append(_make_excel_hit(
                        r, '方案参数', body, hit_rate))

            # 渠道/简单参数
            if want_channel or want_all:
                body = r.get('phase_channel', '').strip()
                if body:
                    results.append(_make_excel_hit(
                        r, '渠道参数', body, hit_rate * 0.85))

        # 2. Comparison table (spec details)
        comp_rows = db.search_comparison_by_model(model)
        for r in comp_rows:
            spec_name = r.get('spec_name', '')
            spec_val = r.get('spec_value', '')
            body = f"{spec_name}: {spec_val}"
            results.append({
                'type': '表格类-产品对比',
                'hit_rate': 0.9,
                'source': f"{r.get('source_file')}:{r.get('source_sheet')}:row{r.get('source_row')}",
                'title': f"{r.get('model')} - {spec_name}",
                'body': body,
                'raw': r,
            })

        # 3. Pricing
        if want_price or want_all:
            price_rows = db.search_pricing_by_model(model)
            for r in price_rows:
                hit = 1.0 if r.get('is_pricing_record') else 0.5
                results.append({
                    'type': '表格类-价格',
                    'hit_rate': hit,
                    'source': f"{r.get('source_file')}:{r.get('source_sheet')}:row{r.get('source_row')}",
                    'title': f"{r.get('product_name')} | {r.get('product_model')}",
                    'body': f"价格: {r.get('price_raw')}\n描述: {r.get('description', '')}",
                    'raw': r,
                })

    return results


def _make_excel_hit(row: Dict, param_type: str, body: str, hit_rate: float) -> Dict:
    return {
        'type': f'表格类-{param_type}',
        'hit_rate': hit_rate,
        'source': f"{row.get('source_file')}:{row.get('source_sheet')}:row{row.get('source_row')}",
        'title': f"{row.get('product_name')} | {row.get('product_model')}",
        'body': body,
        'raw': row,
    }


def search_knowledge(query: str, models: List[str] = None) -> List[Dict]:
    """Search solution-type documents with hybrid BM25+Vector."""
    models = models or []
    try:
        hybrid = get_hybrid(ROOT / 'cards' / 'sections',
                           ROOT / 'index_store' / 'embeddings')
        raw_results = hybrid.search(query, top_k=30)

        results = []
        for r in raw_results:
            body = r.get('body', '')
            title = r.get('title', '')
            hit_rate = r['hit_rate']

            # Model filter if specified
            if models:
                body_upper = body.upper()
                title_upper = title.upper()
                if not any(m in body_upper or m in title_upper for m in models):
                    hit_rate *= 0.3  # Penalize but don't exclude
            
            if hit_rate < 0.08:
                continue

            results.append({
                'type': '方案类-段落',
                'hit_rate': round(hit_rate, 3),
                'source': r['source'],
                'title': title,
                'body': body[:2000],
                'raw': r,
            })

        return results

    except Exception as e:
        print(f"[Knowledge] Hybrid search failed: {e}, falling back to BM25", file=sys.stderr)
        # Fallback: pure BM25
        retriever = get_retriever(ROOT / 'cards' / 'sections')
        bm25_results = retriever.search(query, top_k=30)

        results = []
        for cid, score, card in bm25_results:
            if score < 0.5:
                continue
            results.append({
                'type': '方案类-段落',
                'hit_rate': round(min(score / 10.0, 1.0), 3),
                'source': f"{card.get('doc_file')} | {card.get('path')}",
                'title': card.get('title', ''),
                'body': card.get('body', '')[:2000],
                'raw': card,
            })
        return results


def search_updates(query: str) -> List[Dict]:
    """Search update/release-note documents with coarse BM25."""
    try:
        retriever = get_retriever(ROOT / 'cards' / 'sections')
        bm25_results = retriever.search(query, top_k=20)

        results = []
        for cid, score, card in bm25_results:
            tags = card.get('tags', [])
            if 'release-note' not in tags:
                continue  # Only update-type docs
            
            if score < 0.3:
                continue

            results.append({
                'type': '更新类-段落',
                'hit_rate': round(min(score / 5.0, 1.0), 3),
                'source': f"{card.get('doc_file')} | {card.get('path')}",
                'title': card.get('title', ''),
                'body': card.get('body', '')[:3000],  # Coarse: keep full paragraph
                'raw': card,
            })

        return results

    except Exception as e:
        print(f"[Update] Search failed: {e}", file=sys.stderr)
        return []


def search_ppt(query: str) -> List[Dict]:
    """Search PPT cards (future integration)."""
    # TODO: integrate PPT image understanding cards
    return []


def _compute_avg_hit_rate(results: List[Dict]) -> float:
    """Compute average hit_rate across results."""
    if not results:
        return 0.0
    rates = [r.get('hit_rate', 0) for r in results]
    return sum(rates) / len(rates)


def unified_search(query: str) -> Dict:
    """Main entry point: classify and route query."""
    source_type, models = classify_query(query)
    all_results = []

    # Route to appropriate data source(s)
    if source_type == 'excel':
        all_results = search_excel(query, models)
        # Also search knowledge base for supplementary info
        if len(all_results) < 5:
            knowledge = search_knowledge(query, models)
            all_results.extend(knowledge)

    elif source_type == 'update':
        all_results = search_updates(query)
        # Also check knowledge base
        if len(all_results) < 3:
            all_results.extend(search_knowledge(query, models))

    elif source_type == 'ppt':
        all_results = search_ppt(query)

    else:  # knowledge
        all_results = search_knowledge(query, models)

    # Deduplicate (by source + title)
    seen = set()
    unique = []
    for r in all_results:
        key = f"{r.get('source', '')}:{r.get('title', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # Sort: excel first (authoritative), then by hit_rate
    def sort_key(x):
        is_excel = '表格类' in x.get('type', '')
        return (is_excel, x['hit_rate'])

    unique.sort(key=sort_key, reverse=True)

    # Compute quality metrics
    avg_rate = _compute_avg_hit_rate(unique)

    return {
        'query': query,
        'source_type': source_type,
        'models': models,
        'result_count': len(unique),
        'results': unique,
        'avg_hit_rate': round(avg_rate, 3),
        'low_quality': (avg_rate < 0.3) or (len(unique) < 3),
    }


def format_output(hit: Dict) -> str:
    """Format a single result for display."""
    lines = []
    title = hit.get('title', '').replace('\n', ' ').strip()
    hit_rate = hit.get('hit_rate', 0)
    source = hit.get('source', 'unknown')
    body = hit.get('body', '').strip()

    lines.append(title)
    lines.append("")
    lines.append(body)
    lines.append("")
    lines.append("出处")
    lines.append(source)
    lines.append("")
    lines.append("命中率")
    lines.append("")
    lines.append(f"{hit_rate:.0%}")
    lines.append("")
    lines.append("---")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Unified wiki query engine')
    parser.add_argument('query', help='Query text')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--limit', type=int, default=5, help='Max results (default 5)')
    parser.add_argument('--all', action='store_true', help='Show all results')
    parser.add_argument('--no-vector', action='store_true', help='Disable vector search')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show feedback/logging diagnostics')
    parser.add_argument('--feedback', choices=['good', 'bad', 'skip'],
                        help='Mark quality of this query result')
    parser.add_argument('--feedback-query-id', type=str,
                        help='Query ID to attach feedback to (defaults to current query)')
    parser.add_argument('--ref-query-id', type=str,
                        help='Referenced query ID for follow-up chain')
    parser.add_argument('--optimize', action='store_true',
                        help='Analyze feedback and optimize retrieval weights')
    parser.add_argument('--optimize-apply', action='store_true',
                        help='Apply optimized weights (requires --optimize)')
    parser.add_argument('--no-optimize-weights', action='store_true',
                        help='Skip loading optimized weights (use defaults)')
    args = parser.parse_args()

    if args.all:
        args.limit = 100

    # --- Optimization mode ---
    if args.optimize:
        opt = WeightOptimizer()
        stats = opt.analyze_feedback()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        if stats.get('filterable'):
            suggestion = opt.suggest_weights(stats)
            routing = opt.optimize_routing(stats)
            print("\n=== 权重建议 ===")
            print(json.dumps(suggestion, ensure_ascii=False, indent=2))
            print("\n=== 路由建议 ===")
            print(json.dumps(routing, ensure_ascii=False, indent=2))
            if args.optimize_apply:
                suggestion = opt.apply_weights()
                if suggestion:
                    print(f"\n✅ 已应用: bm25={suggestion['bm25_weight']}, "
                          f"vector={suggestion['vector_weight']}, "
                          f"semantic_boost={suggestion['semantic_boost']}")
        else:
            print(f"\n⚠️ 仅 {stats.get('total_queries', 0)} 条反馈, 至少需要 20 条")
        return

    # --- Load optimized weights (unless disabled) ---
    if not args.no_optimize_weights:
        apply_weights_to_retrievers()

    result = unified_search(args.query)
    results = result['results'][:args.limit]

    # ── Auto-log query ─────────────────────────────────────────────────────
    last_qid = get_last_query_id()
    ref_qid = args.ref_query_id or last_qid

    log_qid = log_query(
        query=args.query,
        source_type=result['source_type'],
        models=result.get('models', []),
        total_results=result['result_count'],
        results=result['results'],
        top_n=5,
        referenced_query_id=ref_qid if ref_qid and ref_qid != get_last_query_id() else None,
    )

    # Link follow-up chain if applicable
    if last_qid and not args.ref_query_id:
        record_follow_up(last_qid, log_qid)

    # ── Feedback from CLI ───────────────────────────────────────────────────
    if args.feedback:
        target_qid = args.feedback_query_id or log_qid
        record_feedback(target_qid, args.feedback)

    # ── Refinement if low quality ──────────────────────────────────────────
    refinement = None
    if result.get('low_quality'):
        refinement = refine_query(
            query=args.query,
            results=result['results'],
            cards=[],
        )

    # ── Output ─────────────────────────────────────────────────────────────
    if args.json:
        out = {
            'query': result['query'],
            'query_id': log_qid,
            'source_type': result['source_type'],
            'models': result['models'],
            'total': result['result_count'],
            'shown': len(results),
            'avg_hit_rate': result.get('avg_hit_rate', 0),
            'low_quality': result.get('low_quality', False),
            'results': results,
        }
        if refinement:
            out['refinement'] = refinement
        if args.verbose:
            out['feedback_stats'] = get_stats()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"查询: {result['query']}")
        print(f"路由: {result['source_type']}")
        if result['models']:
            print(f"型号: {', '.join(result['models'])}")
        print(f"共召回 {result['result_count']} 条, 平均命中率 {result.get('avg_hit_rate', 0):.3f}")

        if args.verbose:
            print(f"[反馈] query_id={log_qid}")
            print(f"[反馈] low_quality={result.get('low_quality', False)}")
            stats = get_stats()
            print(f"[反馈] 累计统计: total={stats['total_queries']}, "
                  f"good={stats['good']}, bad={stats['bad']}")

        print(f"显示前 {len(results)} 条")
        print()
        for hit in results:
            print(format_output(hit))

        # Show refinement suggestions if low quality
        if refinement and refinement.get('needs_refinement'):
            print('\n' + '=' * 60)
            print('🔍 查询优化建议')
            print('=' * 60)

            sug = refinement.get('suggestions', [])
            if sug:
                print('\n💡 建议改写：')
                for s in sug:
                    print(f'   • {s}')

            terms = refinement.get('expanded_terms', [])
            if terms:
                print(f'\n📝 扩展关键词：{" / ".join(terms)}')

            topics = refinement.get('related_topics', [])
            if topics:
                print(f'\n📂 可能相关主题：{" / ".join(topics)}')

            cq = refinement.get('clarifying_question')
            if cq:
                print(f'\n❓ {cq}')

            print()


if __name__ == '__main__':
    main()
