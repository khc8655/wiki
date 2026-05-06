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
from typing import List, Dict, Tuple, Optional

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

# ── Constants ──────────────────────────────────────────────────────────────

LOW_QUALITY_THRESHOLD = 0.5   # Below this = low quality, hidden by default
TOO_MANY_RESULTS = 15          # Trigger smart disambiguation when > this
TOO_FEW_RESULTS = 5            # Trigger search expansion hint when < this
LOW_QUALITY_AVG = 0.3          # Avg hit_rate below this = low quality signal

# Model extraction regex
MODEL_RE = re.compile(
    r'(AE\d{3}[A-Z]?|XE\d{3}[A-Z]?|GE\d{3}[A-Z]?|PE\d{4}|TP\d{3}(?:-[A-Z])?|'
    r'MX\d{2}|AC\d{2}|NC\d{2}|NP\d{2}(?:V?\d+)?|ME\d{3,4}|XM\d{4})',
    re.I
)

# Intent classification keywords
PRICE_KWS = ['价格', '报价', '多少钱', '费用', '成本']
TENDER_KWS = ['招标', '投标', '可研']
SPEC_KWS = ['规格', '接口', '编解码', '输入', '输出', '分辨率', '像素']
COMPARE_KWS = ['对比', '比较', '区别', '差异', 'vs']
ACCESSORY_KWS = ['配件', '附件', '可用配件']
EOL_KWS = ['停产', '替代', '退市']
UPDATE_KWS = ['迭代', '新功能', '版本更新', '发版', '培训文档', '更新说明', '功能更新']

# Ambiguous broad keywords — when alone with model number, query IS ambiguous
BROAD_KWS = ['参数', '配置', '规格', '信息', '详情', '介绍', '资料']
# Specific keywords that resolve ambiguity
SPECIFIC_KWS = TENDER_KWS + SPEC_KWS + PRICE_KWS + COMPARE_KWS + ACCESSORY_KWS + EOL_KWS

# Knowledge-base card tags → query keyword mapping (for semantic boost)
TAG_BOOST_MAP = {
    '招标参数': 1.5, '方案参数': 1.3, '渠道参数': 1.2,
    '安全': 1.4, '加密': 1.5, '国密': 1.5, '鉴权': 1.3, '认证': 1.3,
    '部署': 1.2, '运维': 1.2, '架构': 1.2, '集成': 1.2, '对接': 1.2,
    'release-note': 0.5,  # downgrade release notes when user wants params
}


# ── Query understanding ────────────────────────────────────────────────────

def extract_models(query: str) -> List[str]:
    return sorted({m.upper() for m in MODEL_RE.findall(query)})


def classify_query(query: str) -> Tuple[str, List[str]]:
    """Classify query intent and extract models."""
    models = extract_models(query)
    q = query.lower()

    excel_keywords = SPECIFIC_KWS
    if models:
        if any(k in q for k in excel_keywords):
            return 'excel', models
        return 'excel', models

    if any(k in q for k in UPDATE_KWS):
        return 'update', models

    if 'ppt' in q or '幻灯片' in q:
        return 'ppt', models

    return 'knowledge', models


def detect_ambiguity(query: str, models: List[str], db) -> Optional[Dict]:
    """
    Smart ambiguity detection: checks if query is too broad AND results are too many,
    then uses annotated intent_tags to generate meaningful disambiguation categories.

    Thresholds:
      - Too many results (>TOO_MANY_RESULTS) + broad query → disambiguate
      - Otherwise → let results flow through with quality filtering
    """
    if not models:
        return None

    q = query.lower()
    model = models[0]

    # Check if query has specific keywords → not ambiguous
    has_specific = any(k in q for k in SPECIFIC_KWS)
    if has_specific:
        return None

    # Check if remaining words are all broad
    remaining = q
    for m in models:
        remaining = remaining.replace(m.lower(), '')
    words = [w for w in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', remaining) if len(w) >= 2]
    all_broad = all(w in BROAD_KWS for w in words) if words else True
    if not all_broad:
        return None

    # Collect all categories for this model across all sources
    categories = _collect_model_categories(model)

    # Only disambiguate if there are actually multiple categories
    if len(categories) <= 1:
        return None

    return {
        'model': model,
        'available_types': categories,
    }


def _collect_model_categories(model: str) -> List[Dict]:
    """
    Scan ALL sources for this model and return content categories.
    Returns list of {label, key, source, count} dicts sorted by relevance.
    """
    categories = {}

    # ── 1. Excel DB ────────────────────────────────────────────────────
    db = get_excel_db()
    price_rows = db.search_pricing_by_model(model)
    if price_rows:
        categories['报价/价格'] = {'label': '报价/价格', 'key': '价格', 'source': 'excel', 'count': len(price_rows)}

    comp_rows = db.search_comparison_by_model(model)
    if comp_rows:
        categories['产品对比'] = {'label': '产品对比参数', 'key': '对比', 'source': 'excel', 'count': len(comp_rows)}

    prop_rows = db.search_proposal_by_model(model)
    for r in prop_rows:
        pm = r.get('product_model', '').upper().replace('小鱼易连', '').strip()
        if model not in pm:
            continue
        if r.get('phase_channel', '').strip():
            categories['简单清单参数'] = {'label': '简单清单参数（简版）', 'key': '渠道', 'source': 'excel', 'count': 1}
        if r.get('phase_proposal', '').strip():
            categories['可研使用参数'] = {'label': '可研使用参数（完整）', 'key': '可研', 'source': 'excel', 'count': 1}
        if r.get('phase_tender', '').strip():
            categories['招标参数'] = {'label': '招标参数（含▲标记）', 'key': '招标', 'source': 'excel', 'count': 1}

    # ── 2. Knowledge base: aggregate by annotated intent_tags ───────────
    try:
        import json, os
        from collections import Counter
        cards_dir = ROOT / 'cards' / 'sections'
        intent_counts = Counter()
        title_hints = {}
        for f in os.listdir(cards_dir):
            if not f.endswith('.json'):
                continue
            card = json.loads(open(os.path.join(cards_dir, f)).read())
            title = card.get('title', '')
            body = card.get('body', '')
            tags_raw = card.get('tags', [])
            sem = card.get('semantic', {})
            intent = sem.get('intent_tags', [])

            if model.upper() not in (title + body).upper():
                continue

            # Use annotated intent_tags as primary category names
            for tag in intent:
                if tag not in ('feature_update', 'operation_maintenance', 'training_enablement', 'scenario'):
                    intent_counts[tag] += 1

            # Fallback: use document-level tags for cards without annotations
            if not intent:
                if 'release-note' in tags_raw:
                    intent_counts['功能更新'] += 1
                elif 'solution' in (tags_raw or []) or '方案' in title or '模板' in card.get('doc_file', ''):
                    if '配置' in title:
                        intent_counts['配置清单'] += 1
                    elif '简介' in title:
                        intent_counts['终端简介'] += 1

        # Add top intent categories (only if significant count)
        for intent_name, cnt in intent_counts.most_common(8):
            if cnt >= 1 and intent_name not in categories:
                # Skip English tags as category labels
                if '_' not in intent_name:
                    categories[intent_name] = {
                        'label': intent_name,
                        'key': None,
                        'source': 'knowledge',
                        'count': cnt,
                    }
    except Exception:
        pass

    return list(categories.values())


# ── Search functions ───────────────────────────────────────────────────────

def search_excel(query: str, models: List[str], facet_filter: str = None) -> List[Dict]:
    """Search structured Excel data: pricing, specs, comparison.
    facet_filter: 'tender'/'proposal'/'channel' for proposal;
                  pricing_type value for pricing;
                  comparison_type value for comparison.
    """
    db = get_excel_db()
    results = []
    q = query.lower()

    want_tender = any(k in q for k in TENDER_KWS)
    want_channel = '渠道' in q or '通路' in q or '简单' in q
    want_spec = any(k in q for k in SPEC_KWS)
    want_price = any(k in q for k in PRICE_KWS)
    want_compare = any(k in q for k in COMPARE_KWS)

    want_all = not (want_tender or want_channel or want_spec or want_price or want_compare)

    for model in models:
        # 1. Proposal table (multi-phase params)
        phase_filter = facet_filter if facet_filter in ('tender', 'proposal', 'channel') else None
        rows = db.search_proposal_by_model(model, phase_filter=phase_filter)
        for r in rows:
            product_model = r.get('product_model', '').upper().replace('小鱼易连', '').strip()
            if model == product_model:
                hit_rate = 1.0
            elif model in product_model:
                hit_rate = 0.7
            else:
                hit_rate = 0.5

            # 招标参数
            if want_tender or (want_all and not phase_filter):
                body = r.get('phase_tender', '').strip()
                if body and (not phase_filter or phase_filter == 'tender'):
                    results.append(_make_excel_hit(
                        r, '招标参数', body, round(hit_rate * 0.95, 3)))

            # 方案/可研参数 (most complete)
            if want_all and not phase_filter:
                body = r.get('phase_proposal', '').strip()
                if body:
                    results.append(_make_excel_hit(
                        r, '方案参数', body, round(hit_rate, 3)))

            # 渠道/简单参数
            if want_channel or (want_all and not phase_filter):
                body = r.get('phase_channel', '').strip()
                if body and (not phase_filter or phase_filter == 'channel'):
                    results.append(_make_excel_hit(
                        r, '渠道参数', body, round(hit_rate * 0.85, 3)))

        # 2. Comparison table (spec details)
        comp_filter = facet_filter if facet_filter and facet_filter not in ('tender', 'proposal', 'channel') else None
        if want_spec or want_all:
            comp_rows = db.search_comparison_by_model(model, comparison_type_filter=comp_filter)
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
        price_filter = facet_filter if facet_filter and facet_filter not in ('tender', 'proposal', 'channel') else None
        if want_price or want_all:
            price_rows = db.search_pricing_by_model(model, pricing_type_filter=price_filter)
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


def _compute_tag_boost(card: Dict, query: str) -> float:
    """Compute tag-based relevance boost from card annotations."""
    boost = 1.0
    q = query.lower()

    # Check card tags
    tags = card.get('tags', [])
    keywords = card.get('keywords', [])

    for tag in tags:
        tag_lower = tag.lower()
        for kw, multiplier in TAG_BOOST_MAP.items():
            if kw in tag_lower:
                boost = max(boost, multiplier)

    # Check if query words match card keywords
    for kw in keywords:
        if kw.lower() in q:
            boost = max(boost, 1.3)

    # Downgrade: if user is asking for params but result is a release-note
    if any(k in q for k in SPECIFIC_KWS) and 'release-note' in tags:
        boost = min(boost, 0.6)

    return boost


def search_knowledge(query: str, models: List[str] = None) -> List[Dict]:
    """Search solution-type documents with hybrid BM25+Vector + tag boost."""
    models = models or []
    try:
        hybrid = get_hybrid(ROOT / 'cards' / 'sections',
                           ROOT / 'index_store' / 'embeddings')
        raw_results = hybrid.search(query, top_k=40)

        results = []
        for r in raw_results:
            body = r.get('body', '')
            title = r.get('title', '')
            hit_rate = r['hit_rate']
            card = r.get('raw', r)

            # Apply tag-based relevance boost/downgrade
            tag_boost = _compute_tag_boost(card, query)
            hit_rate = round(min(hit_rate * tag_boost, 1.0), 3)

            # Model filter if specified
            if models:
                body_upper = body.upper()
                title_upper = title.upper()
                if not any(m in body_upper or m in title_upper for m in models):
                    hit_rate *= 0.3

            if hit_rate < 0.08:
                continue

            results.append({
                'type': '方案类-段落',
                'hit_rate': hit_rate,
                'source': r['source'],
                'title': title,
                'body': body[:2000],
                'raw': r,
            })

        return results

    except Exception as e:
        print(f"[Knowledge] Hybrid search failed: {e}, falling back to BM25", file=sys.stderr)
        retriever = get_retriever(ROOT / 'cards' / 'sections')
        bm25_results = retriever.search(query, top_k=40)

        results = []
        for cid, score, card in bm25_results:
            if score < 0.5:
                continue
            tag_boost = _compute_tag_boost(card, query)
            hit_rate = round(min(score / 10.0 * tag_boost, 1.0), 3)
            results.append({
                'type': '方案类-段落',
                'hit_rate': hit_rate,
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
                continue
            if score < 0.3:
                continue

            results.append({
                'type': '更新类-段落',
                'hit_rate': round(min(score / 5.0, 1.0), 3),
                'source': f"{card.get('doc_file')} | {card.get('path')}",
                'title': card.get('title', ''),
                'body': card.get('body', '')[:3000],
                'raw': card,
            })

        return results
    except Exception as e:
        print(f"[Update] Search failed: {e}", file=sys.stderr)
        return []


def search_ppt(query: str) -> List[Dict]:
    return []


# ── Core engine ────────────────────────────────────────────────────────────

def _compute_avg_hit_rate(results: List[Dict]) -> float:
    if not results:
        return 0.0
    rates = [r.get('hit_rate', 0) for r in results]
    return sum(rates) / len(rates)


def _collect_expansion_hints(results: List[Dict]) -> Optional[str]:
    """
    When results are too few, suggest broader search angles from annotated tags.
    """
    if len(results) >= TOO_FEW_RESULTS:
        return None
    all_intents = set()
    for r in results:
        raw = r.get('raw', {})
        if isinstance(raw, dict):
            sem = raw.get('semantic', {})
            for tag in sem.get('intent_tags', []):
                if '_' not in str(tag):
                    all_intents.add(str(tag))
    if all_intents:
        topics = list(all_intents)[:3]
        hint = ' / '.join(topics)
        return f'结果偏少，可尝试扩大范围查询，或指定关键词如：{hint}'
    return None


def unified_search(query: str, facet_filter: str = None) -> Dict:
    """Main entry point: classify, detect ambiguity, route, search."""
    source_type, models = classify_query(query)
    all_results = []

    # Detect if query is broad (for post-search disambiguation trigger)
    q = query.lower()
    is_broad = False
    if models:
        remaining = q
        for m in models:
            remaining = remaining.replace(m.lower(), '')
        words = [w for w in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', remaining) if len(w) >= 2]
        has_specific = any(k in q for k in SPECIFIC_KWS)
        is_broad = (all(w in BROAD_KWS for w in words) if words else True) and not has_specific

    if source_type == 'excel':
        all_results = search_excel(query, models, facet_filter=facet_filter)
        # For specific intent queries (价格/接口/招标), don't dilute with knowledge base
        query_specific = any(k in q for k in SPECIFIC_KWS)
        if len(all_results) < 5 and not query_specific:
            all_results.extend(search_knowledge(query, models))
        elif query_specific and len(all_results) == 0:
            # Only fall back to KB if Excel has literally nothing
            all_results.extend(search_knowledge(query, models))

    elif source_type == 'update':
        all_results = search_updates(query)
        if len(all_results) < 3:
            all_results.extend(search_knowledge(query, models))

    elif source_type == 'ppt':
        all_results = search_ppt(query)

    else:
        all_results = search_knowledge(query, models)

    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = f"{r.get('source', '')}:{r.get('title', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # Sort: excel first, then by hit_rate descending
    def sort_key(x):
        is_excel = '表格类' in x.get('type', '')
        return (is_excel, x['hit_rate'])

    unique.sort(key=sort_key, reverse=True)

    avg_rate = _compute_avg_hit_rate(unique)

    return {
        'query': query,
        'source_type': source_type,
        'models': models,
        'result_count': len(unique),
        'results': unique,
        'avg_hit_rate': round(avg_rate, 3),
        'low_quality': (avg_rate < 0.3) or (len(unique) < 3),
        '_query_broad': is_broad,
    }


def format_output(hit: Dict) -> str:
    title = hit.get('title', '').replace('\n', ' ').strip()
    hit_rate = hit.get('hit_rate', 0)
    source = hit.get('source', 'unknown')
    body = hit.get('body', '').strip()

    return (
        f"{title}\n\n"
        f"{body}\n\n"
        f"出处\n{source}\n\n"
        f"命中率\n\n{hit_rate:.0%}\n\n---"
    )


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Unified wiki query engine')
    parser.add_argument('query', help='Query text')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--limit', type=int, default=200, help='Max high-quality results (default 200)')
    parser.add_argument('--all', action='store_true', help='Show ALL results including low-quality')
    parser.add_argument('--all-low', action='store_true', help='Also show results below 50% hit rate')
    parser.add_argument('--no-vector', action='store_true', help='Disable vector search')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show diagnostics')
    parser.add_argument('--feedback', choices=['good', 'bad', 'skip'], help='Mark quality')
    parser.add_argument('--feedback-query-id', type=str, help='Query ID for feedback')
    parser.add_argument('--ref-query-id', type=str, help='Referenced query ID')
    parser.add_argument('--optimize', action='store_true', help='Analyze feedback and optimize')
    parser.add_argument('--optimize-apply', action='store_true', help='Apply optimized weights')
    parser.add_argument('--no-optimize-weights', action='store_true', help='Skip optimized weights')
    parser.add_argument('--facet', type=str, default=None, help='Filter by facet: tender/proposal/channel for proposal; pricing_type/comparison_type value')
    args = parser.parse_args()

    if args.all:
        args.limit = 9999

    # ── Optimization mode ──────────────────────────────────────────────────
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
                    print(f"\n✅ 已应用")
        else:
            print(f"\n⚠️ 仅 {stats.get('total_queries', 0)} 条反馈, 至少需要 20 条")
        return

    # ── Step 1: Check ambiguity BEFORE searching ───────────────────────────
    models = extract_models(args.query)
    ambiguity = None
    if models:
        db = get_excel_db()
        ambiguity = detect_ambiguity(args.query, models, db)
        if ambiguity:
            # Output disambiguation prompt in structured format
            types_list = '\n'.join(
                f"  {i+1}. {t['label']}"
                for i, t in enumerate(ambiguity['available_types'])
            )
            print(f"⚠️ 歧义检测: 查询过于宽泛\n")
            print(f"型号 {ambiguity['model']} 有以下参数类型，请指定后重新查询：\n{types_list}\n")
            print(f"示例: AE800 招标参数 | AE800 渠道参数 | AE800 方案参数\n")
            return

    # ── Step 2: Search ─────────────────────────────────────────────────────
    result = unified_search(args.query, facet_filter=args.facet)

    # ── Step 3: Facets summary (when no facet filter is active and results are many) ──
    if not args.facet and len(result['models']) == 1 and result['result_count'] > 5:
        model = result['models'][0]
        db = get_excel_db()
        pf = db.get_proposal_facets(model)
        ppf = db.get_pricing_facets(model)
        cf = db.get_comparison_facets(model)
        # Build summary line
        parts = []
        total = pf.get('tender', 0) + pf.get('proposal', 0) + pf.get('channel', 0)
        if pf.get('tender'):
            parts.append(f"招标参数(phase_tender):{pf['tender']}")
        if pf.get('proposal'):
            parts.append(f"方案参数(phase_proposal):{pf['proposal']}")
        if pf.get('channel'):
            parts.append(f"渠道参数(phase_channel):{pf['channel']}")
        if ppf:
            for k, v in ppf.items():
                parts.append(f"{k}(pricing):{v}")
        if cf:
            for k, v in cf.items():
                parts.append(f"{k}(comparison):{v}")
        if parts:
            facet_summary = " | ".join(parts)
            print(f"[分面] {model}: {facet_summary}\n")

    # ── Step 4: Smart disambiguation (post-search) ────────────────────────
    # If high-quality results are too many and query was broad → suggest categories
    high_quality = [r for r in result['results'] if r['hit_rate'] >= LOW_QUALITY_THRESHOLD]
    low_quality = [r for r in result['results'] if r['hit_rate'] < LOW_QUALITY_THRESHOLD]
    expansion_hint = _collect_expansion_hints(high_quality)

    # Detect if results are too many → suggest category narrowing
    # Only trigger when query was broad (pre-search ambiguity was detected but bypassed)
    models_found = result.get('models', [])
    query_broad = result.get('_query_broad', False)
    if len(high_quality) > TOO_MANY_RESULTS and query_broad and not args.all and not args.all_low:
        models_found = result.get('models', [])
        if models_found:
            categories = _collect_model_categories(models_found[0])
            if len(categories) > 1:
                print(f"查询: {result['query']}")
                print(f"路由: {result['source_type']}")
                print(f"共召回 {result['result_count']} 条，高相关 {len(high_quality)} 条")
                print()
                print(f"结果较多，建议缩小范围。{models_found[0]} 包含以下分类：")
                print()
                for i, cat in enumerate(categories):
                    count_str = f"({cat.get('count', '?')}条)" if cat.get('count') else ''
                    print(f"  {i+1}. {cat['label']} {count_str}")
                print()
                print(f"请指定分类重新查询，例如：{models_found[0]} {categories[0]['label']}")
                return

    if args.all:
        # Show everything
        display = result['results'][:args.limit]
    elif args.all_low:
        display = (high_quality + low_quality)[:args.limit]
    else:
        display = high_quality[:args.limit]

    # ── Logging ────────────────────────────────────────────────────────────
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

    if last_qid and not args.ref_query_id:
        record_follow_up(last_qid, log_qid)

    if args.feedback:
        target_qid = args.feedback_query_id or log_qid
        record_feedback(target_qid, args.feedback)

    # ── Output ─────────────────────────────────────────────────────────────
    if args.json:
        out = {
            'query': result['query'],
            'query_id': log_qid,
            'source_type': result['source_type'],
            'models': result['models'],
            'total': result['result_count'],
            'high_quality': len(high_quality),
            'low_quality': len(low_quality),
            'shown': len(display),
            'avg_hit_rate': result.get('avg_hit_rate', 0),
            'low_quality_flag': result.get('low_quality', False),
            'results': display,
        }
        if args.verbose:
            out['feedback_stats'] = get_stats()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"查询: {result['query']}")
        print(f"路由: {result['source_type']}")
        if result['models']:
            print(f"型号: {', '.join(result['models'])}")
        print(f"共召回 {result['result_count']} 条, 平均命中率 {result.get('avg_hit_rate', 0):.3f}")
        print(f"高相关 (≥50%): {len(high_quality)} 条  |  低相关 (<50%): {len(low_quality)} 条")

        if args.verbose:
            print(f"[反馈] query_id={log_qid}")

        if len(display) < len(result['results']) and not args.all:
            shown_label = "高相关" if not args.all_low else "全部"
            print(f"显示 {shown_label} {len(display)} 条")
        else:
            print(f"显示全部 {len(display)} 条")
        print()

        for hit in display:
            print(format_output(hit))

        # ── Follow-up prompts ────────────────────────────────────────────
        q_lower = result['query'].lower()
        # Price query: after showing price, ask if user wants full params
        if any(k in q_lower for k in PRICE_KWS):
            model_list = result.get('models', [])
            if model_list:
                m = model_list[0]
                print(f"\n需要查看 {m} 的详细参数或功能介绍吗？")
            else:
                print(f"\n需要查看详细参数或功能介绍吗？")

        # Prompt for low-quality results
        if low_quality and not args.all and not args.all_low:
            print(f"\n还有 {len(low_quality)} 条低相关结果（命中率<50%），需要显示请回复\"全部\"")

        # Low-result hint: suggest expansion
        if expansion_hint:
            print(f"\n💡 {expansion_hint}")

        # ── Query refinement: LLM-powered search optimization ─────────────────
        avg_rate = result.get('avg_hit_rate', 0)
        if (avg_rate < LOW_QUALITY_AVG and result['result_count'] > 0
                and not args.json and not args.all and not args.all_low):
            refine = refine_query(result['query'], result['results'])
            if refine.get('needs_refinement'):
                print(f"\n💡 查询优化建议（命中率偏低，LLM分析中）:")
                for s in refine.get('suggestions', []):
                    print(f"   • {s}")
                cq = refine.get('clarifying_question')
                if cq:
                    print(f"\n  {cq}")


if __name__ == '__main__':
    main()
