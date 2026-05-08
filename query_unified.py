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

# Intent classification keywords — also defines display order in disambiguation
# Lower number = higher priority (shown first)
PRICE_KWS = ['价格', '报价', '多少钱', '费用', '成本']
TENDER_KWS = ['招标', '投标', '可研']
SPEC_KWS = ['规格', '接口', '编解码', '输入', '输出', '分辨率', '像素', '参数', '介绍', '详情', '功能']
COMPARE_KWS = ['对比', '比较', '区别', '差异', 'vs']
ACCESSORY_KWS = ['配件', '附件', '可用配件']
EOL_KWS = ['停产', '替代', '退市']
CHANNEL_KWS = ['简单', '简版', '清单', '渠道']  # 渠道参数（简版）
PROPOSAL_KWS = ['方案', '可研']  # 方案参数
# 通用宽泛关键词（用于歧义检测，定义在 BROAD_KWS 统一处）

# Disambiguation category sort priority (lower = higher priority)
CATEGORY_PRIORITY = {
    '招标参数（含▲标记）': 1,
    '可研使用参数（完整）': 2,
    '简单清单参数（简版）': 3,
    '方案参数': 4,
    '渠道参数': 5,
    '报价/价格': 6,
    '产品对比参数': 7,
}
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

# Intent types for structured Excel queries
INTENT_PRICE = 'price_query'        # 价格查询
INTENT_CATEGORY = 'category_list'   # 分类列举
INTENT_COMPARE = 'compare_table'    # 对比表格
INTENT_TENDER = 'tender_params'     # 招标参数
INTENT_ACCESSORY = 'accessory'      # 配件查询（仅SQL）
INTENT_ACCESSORY_HYBRID = 'accessory_hybrid'  # 配件查询（SQL+cards）
INTENT_EOL = 'eol_info'             # 停产信息
INTENT_SOLUTION = 'solution'        # 方案描述（hybrid搜索）

def extract_models(query: str) -> List[str]:
    return sorted({m.upper() for m in MODEL_RE.findall(query)})


def classify_query(query: str) -> Tuple[str, List[str], str]:
    """Classify query intent and extract models.
    Returns: (source_type, models, intent)
    """
    models = extract_models(query)
    q = query.lower()

    # ── Intent detection (priority order) ──

    # 1. 停产信息
    if any(k in q for k in EOL_KWS):
        return 'excel', models, INTENT_EOL

    # 2. 配件查询
    if any(k in q for k in ACCESSORY_KWS):
        # 如果查询包含"包含"、"配置"、"套装"，同时查cards
        if any(k in q for k in ['包含', '配置', '套装', '清单']):
            return 'excel', models, INTENT_ACCESSORY_HYBRID
        return 'excel', models, INTENT_ACCESSORY

    # 3. 对比表格（2+模型）
    if any(k in q for k in COMPARE_KWS) and len(models) >= 2:
        return 'excel', models, INTENT_COMPARE

    # 4. 招标参数（但如果同时包含其他参数类型关键词，走spec_query）
    if any(k in q for k in TENDER_KWS):
        # 检查是否同时包含其他参数类型关键词
        has_other_param = any(k in q for k in CHANNEL_KWS + PROPOSAL_KWS)
        if has_other_param:
            # 同时提到多种参数类型，走spec_query让其内部过滤
            return 'excel', models, 'spec_query'
        return 'excel', models, INTENT_TENDER

    # 5. 分类列举（无模型，问"有哪些分类/类型"，且是表格类查询）
    if not models and any(k in q for k in ['分类', '类型', '有哪几种']):
        return 'excel', models, INTENT_CATEGORY

    # 6. 参数/规格/功能/介绍查询（有模型+SPEC关键词，优先于价格）
    if models and any(k in q for k in SPEC_KWS):
        return 'excel', models, 'spec_query'

    # 7. 价格查询（有模型+价格关键词）
    if any(k in q for k in PRICE_KWS):
        if models:
            return 'excel', models, INTENT_PRICE
        # 无模型+报价分类 → 分类列举
        if '分类' in q or '类型' in q:
            return 'excel', models, INTENT_CATEGORY

    # 8. 有模型 → 默认为方案类搜索
    if models:
        return 'knowledge', models, INTENT_SOLUTION

    # 8. 更新类
    if any(k in q for k in UPDATE_KWS):
        return 'update', models, INTENT_SOLUTION

    # 9. PPT类
    if 'ppt' in q or '幻灯片' in q:
        return 'ppt', models, INTENT_SOLUTION

    # 10. 默认：方案描述
    return 'knowledge', models, INTENT_SOLUTION


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

    # ── proposal表按型号过滤 ───────────────────────────────────────────
    # 只推荐确实有内容的分类：先查出该型号的所有proposal行，再看各phase字段是否有值
    prop_rows = db.search_proposal_by_model(model)
    has_channel = any(r.get('phase_channel', '').strip() for r in prop_rows)
    has_proposal = any(r.get('phase_proposal', '').strip() for r in prop_rows)
    has_tender = any(r.get('phase_tender', '').strip() for r in prop_rows)
    if has_channel:
        categories['简单清单参数'] = {'label': '简单清单参数（简版）', 'key': '渠道', 'source': 'excel', 'count': len(prop_rows)}
    if has_proposal:
        categories['可研使用参数'] = {'label': '可研使用参数（完整）', 'key': '可研', 'source': 'excel', 'count': len(prop_rows)}
    if has_tender:
        categories['招标参数'] = {'label': '招标参数（含▲标记）', 'key': '招标', 'source': 'excel', 'count': len(prop_rows)}

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

    # Sort by CATEGORY_PRIORITY, then by count descending
    def sort_key(c):
        p = CATEGORY_PRIORITY.get(c['label'], 99)
        return (p, -(c.get('count') or 0))

    return sorted(list(categories.values()), key=sort_key)


# ── Search functions ───────────────────────────────────────────────────────

def search_excel(query: str, models: List[str], intent: str = None, facet_filter: str = None) -> List[Dict]:
    """Search structured Excel data based on intent.
    
    Intent-driven SQL strategies:
    - price_query: 查pricing表，直接返回价格
    - category_list: 查pricing表，按category分组返回所有分类
    - compare_table: 查comparison表，按spec_name聚合
    - tender_params: 查proposal表，用model精确匹配
    - accessory: 查pricing表，按category字段匹配
    - eol_info: 查pricing表，检查note字段
    """
    db = get_excel_db()
    results = []
    q = query.lower()

    # ── Intent-driven SQL strategies ──

    if intent == INTENT_CATEGORY:
        # 分类列举：查pricing表，按category分组
        return _search_category_list(db, query)

    if intent == INTENT_EOL:
        # 停产信息：查pricing表，检查note字段
        return _search_eol_info(db, models)

    if intent == INTENT_ACCESSORY:
        # 配件查询：查pricing表，按category字段匹配
        return _search_accessory(db, models)

    if intent == INTENT_COMPARE:
        # 对比表格：查comparison表，按spec_name聚合
        return _search_compare_table(db, models)

    if intent == INTENT_TENDER:
        # 招标参数：查proposal表，用model精确匹配
        return _search_tender_params(db, models, facet_filter)

    if intent == INTENT_PRICE:
        # 价格查询：查pricing表，直接返回价格
        return _search_price(db, models)
    
    if intent == 'spec_query':
        # 参数/规格查询：查comparison表
        return _search_spec_query(db, models, query)

    # 默认：返回所有相关数据
    return _search_all_excel(db, models, q, facet_filter)


def _search_category_list(db, query: str) -> List[Dict]:
    """分类列举：查pricing表，按category分组返回所有分类"""
    q = query.lower()
    
    # 识别查询的分类关键词
    category_keywords = []
    if 'AI' in query or 'ai' in query:
        category_keywords = ['AI', '智能', '语音转写', '人脸识别', '大模型', '接入授权']
    elif '云会议' in query or '会议室' in query:
        category_keywords = ['会议室', '云会议']
    else:
        # 通用分类查询：返回所有有category的记录
        category_keywords = []
    
    # 查pricing表（参数化查询，避免SQL注入）
    if category_keywords:
        conditions = ' OR '.join(['category LIKE ?' for _ in category_keywords])
        params = [f'%{k}%' for k in category_keywords]
        rows = db.execute(f"SELECT DISTINCT category, product_name, price_raw, source_file, source_sheet, source_row FROM pricing WHERE {conditions} AND category != '' ORDER BY category", params)
    else:
        rows = db.execute("SELECT DISTINCT category, product_name, price_raw, source_file, source_sheet, source_row FROM pricing WHERE category != '' ORDER BY category")
    
    results = []
    seen_categories = set()
    for row in rows:
        category = row['category']
        if category not in seen_categories:
            seen_categories.add(category)
            results.append({
                'type': '表格类-分类列举',
                'hit_rate': 0.95,
                'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                'title': category,
                'body': f"分类：{category}\n产品：{row['product_name']}\n价格：{row['price_raw']}",
                'raw': dict(row),
            })
    
    return results


def _search_eol_info(db, models: List[str]) -> List[Dict]:
    """停产信息：查pricing表，检查note字段"""
    results = []
    for model in models:
        rows = db.execute("SELECT * FROM pricing WHERE product_name LIKE ? OR product_model LIKE ? OR category LIKE ?", 
                         (f'%{model}%', f'%{model}%', f'%{model}%'))
        for row in rows:
            note = row['note'] or ''
            if '停产' in note or '替代' in note:
                pmodel = (row['product_model'] or '').strip()
                results.append({
                    'type': '表格类-停产信息',
                    'hit_rate': 1.0,
                    'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                    'title': f"{row['product_name']} | {pmodel}" if pmodel else row['product_name'],
                    'body': f"价格：{row['price_raw']}\n备注：{note}",
                    'raw': dict(row),
                })
    return results


def _search_accessory(db, models: List[str]) -> List[Dict]:
    """配件查询：查pricing表，按category字段匹配，同时搜索product_name/product_model
    排除主产品本身（命中率1.0），配件给0.8"""
    results = []
    seen = set()
    for model in models:
        model_upper = model.upper()
        rows = db.execute("SELECT * FROM pricing WHERE category LIKE ? OR product_name LIKE ? OR product_model LIKE ?", 
                         (f'%{model}%', f'%{model}%', f'%{model}%'))
        for row in rows:
            pname = (row['product_name'] or '').strip()
            pmodel = (row['product_model'] or '').strip()
            category = (row['category'] or '').strip()
            
            # 跳过主产品本身（category只有型号名，不是配件）
            if category.upper() == model_upper:
                continue
            
            # 去重
            key = pname
            if key in seen:
                continue
            seen.add(key)
            
            # 配件的 hit_rate 低于主产品
            hit_rate = 0.8
            
            results.append({
                'type': '表格类-配件',
                'hit_rate': hit_rate,
                'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                'title': f"{pname} | {pmodel}" if pmodel else pname,
                'body': f"价格：{row['price_raw']}\n描述：{row['description']}",
                'raw': dict(row),
            })
    return results


def _search_compare_table(db, models: List[str]) -> List[Dict]:
    """对比表格：查comparison表，按spec_name聚合，附带差异摘要"""
    from collections import defaultdict
    
    # 收集所有模型的对比数据
    model_specs = {}  # model -> {spec_name: spec_value}
    all_spec_names = []
    source_info = ""
    
    for model in models:
        rows = db.execute("SELECT * FROM comparison WHERE model = ?", (model,))
        if not rows:
            continue
        specs = {}
        for row in rows:
            spec_name = row['spec_name']
            spec_val = row['spec_value']
            if spec_name:
                specs[spec_name] = spec_val
                if spec_name not in all_spec_names:
                    all_spec_names.append(spec_name)
        model_specs[model] = specs
        if not source_info and rows:
            row = rows[0]
            source_info = f"{row['source_file']}:{row['source_sheet']}"
    
    if len(model_specs) < 2:
        return []
    
    # 构建对比表格
    table_models = [m for m in models if m in model_specs]
    header = "| 对比项 | " + " | ".join(table_models) + " |"
    separator = "| --- | " + " | ".join(["---"] * len(table_models)) + " |"
    rows_str = []
    diff_specs = []  # 有差异的参数
    same_specs = []  # 相同的参数
    
    for spec_name in all_spec_names:
        vals = []
        raw_vals = []
        for m in table_models:
            val = model_specs[m].get(spec_name, '-')
            raw_vals.append(val)
            if len(val) > 80:
                val = val[:77] + "..."
            vals.append(val)
        rows_str.append(f"| {spec_name} | " + " | ".join(vals) + " |")
        
        # 检测差异
        unique_vals = set(v.strip() for v in raw_vals if v.strip() != '-')
        if len(unique_vals) > 1:
            diff_specs.append(spec_name)
        elif len(unique_vals) == 1:
            same_specs.append(spec_name)
    
    table_body = "\n".join([header, separator] + rows_str)
    title = " vs ".join(table_models) + " 产品对比"
    
    # 生成差异摘要
    summary_parts = []
    if diff_specs:
        summary_parts.append(f"**主要差异（{len(diff_specs)}项）：**")
        for spec in diff_specs:
            diff_detail = []
            for m in table_models:
                val = model_specs[m].get(spec, '-')
                if len(val) > 50:
                    val = val[:47] + "..."
                diff_detail.append(f"{m}: {val}")
            summary_parts.append(f"- {spec} → {' | '.join(diff_detail)}")
    if same_specs:
        summary_parts.append(f"\n**相同参数：** {len(same_specs)} 项一致")
    
    summary = "\n".join(summary_parts)
    full_body = f"{table_body}\n\n---\n\n{summary}" if summary else table_body
    
    return [{
        'type': '表格类-产品对比',
        'hit_rate': 1.0,
        'source': source_info,
        'title': title,
        'body': full_body,
        'raw': {},
    }]


def _search_tender_params(db, models: List[str], facet_filter: str = None) -> List[Dict]:
    """招标参数：查proposal表，用model精确匹配"""
    results = []
    for model in models:
        rows = db.execute("SELECT * FROM proposal WHERE product_model LIKE ?", (f'%{model}%',))
        for row in rows:
            body = row['phase_tender'] or ''
            if body.strip():
                results.append({
                    'type': '表格类-招标参数',
                    'hit_rate': 1.0,
                    'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                    'title': f"{row['product_name']} {model} 招标参数",
                    'body': body,
                    'raw': dict(row),
                })
    return results


def _search_price(db, models: List[str]) -> List[Dict]:
    """价格查询：查pricing表，直接返回价格，包含停产信息
    动态评分：产品名精确匹配=1.0，产品名包含=0.9，仅category匹配=0.7
    去重：同产品名合并，保留有价格的行
    """
    results = []
    seen_products = {}  # product_name -> best result
    for model in models:
        rows = db.execute("SELECT * FROM pricing WHERE product_name LIKE ? OR product_model LIKE ? OR category LIKE ?", 
                         (f'%{model}%', f'%{model}%', f'%{model}%'))
        for row in rows:
            price = (row['price_raw'] or '').strip()
            # 跳过空价格行
            if not price:
                continue
            pname = (row['product_name'] or '').strip()
            pmodel = (row['product_model'] or '').strip()
            category = (row['category'] or '').strip()
            
            # 动态 hit_rate
            model_upper = model.upper()
            if model_upper == pmodel.upper() or model_upper == pname.upper():
                hit_rate = 1.0  # 精确匹配
            elif model_upper in pname.upper():
                hit_rate = 0.9  # 产品名包含型号
            elif model_upper in category.upper():
                hit_rate = 0.7  # 仅 category 匹配（配件等）
            else:
                hit_rate = 0.6
            
            note = row['note'] or ''
            body = f"价格：{price}\n描述：{row['description']}"
            if note and ('停产' in note or '替代' in note):
                body += f"\n备注：{note}"
            
            result = {
                'type': '表格类-价格',
                'hit_rate': hit_rate,
                'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                'title': f"{pname} | {pmodel}" if pmodel else pname,
                'body': body,
                'raw': dict(row),
            }
            
            # 去重：同产品名保留 hit_rate 最高的
            if pname not in seen_products or hit_rate > seen_products[pname]['hit_rate']:
                seen_products[pname] = result
    
    return list(seen_products.values())


def _search_all_excel(db, models: List[str], q: str, facet_filter: str = None) -> List[Dict]:
    """默认：返回所有相关数据，包含note字段"""
    results = []
    
    for model in models:
        # 查pricing表
        rows = db.execute("SELECT * FROM pricing WHERE product_name LIKE ? OR product_model LIKE ? OR category LIKE ?", 
                         (f'%{model}%', f'%{model}%', f'%{model}%'))
        for row in rows:
            note = row['note'] or ''
            body = f"价格：{row['price_raw']}\n描述：{row['description']}"
            if note:
                body += f"\n备注：{note}"
            results.append({
                'type': '表格类-价格',
                'hit_rate': 0.9,
                'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                'title': f"{row['product_name']} | {row['product_model']}",
                'body': body,
                'raw': dict(row),
            })
        
        # 查comparison表
        rows = db.execute("SELECT * FROM comparison WHERE model = ?", (model,))
        for row in rows:
            results.append({
                'type': '表格类-产品对比',
                'hit_rate': 0.9,
                'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                'title': f"{row['model']} - {row['spec_name']}",
                'body': f"{row['spec_name']}: {row['spec_value']}",
                'raw': dict(row),
            })
        
        # 查proposal表
        rows = db.execute("SELECT * FROM proposal WHERE product_model LIKE ?", (f'%{model}%',))
        for row in rows:
            for phase_name, phase_key in [('招标参数', 'phase_tender'), ('方案参数', 'phase_proposal'), ('渠道参数', 'phase_channel')]:
                body = row[phase_key] or ''
                if body.strip():
                    results.append({
                        'type': f'表格类-{phase_name}',
                        'hit_rate': 0.9,
                        'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                        'title': f"{row['product_name']} | {row['product_model']}",
                        'body': body,
                        'raw': dict(row),
                    })
    
    return results


def _search_spec_query(db, models: List[str], query: str = '') -> List[Dict]:
    """参数/规格查询：查comparison表 + proposal表，返回结构化表格
    单模型时输出竖排表格，多模型时输出对比表格
    根据查询关键词过滤参数类型：简单/渠道→渠道参数，招标→招标参数，方案→方案参数"""
    from collections import defaultdict
    
    results = []
    q = query.lower() if query else ''
    
    # 检测用户想要的参数类型
    want_tender = any(k in q for k in TENDER_KWS)
    want_channel = any(k in q for k in CHANNEL_KWS)
    want_proposal = any(k in q for k in PROPOSAL_KWS)
    # 如果没有指定具体类型，则返回所有
    want_all = not (want_tender or want_channel or want_proposal)
    
    # 1. 查 comparison 表
    model_specs = {}  # model -> {spec_name: spec_value}
    all_spec_names = []
    source_info = ""
    
    for model in models:
        rows = db.execute("SELECT * FROM comparison WHERE model = ?", (model,))
        if not rows:
            continue
        specs = {}
        for row in rows:
            spec_name = row['spec_name']
            spec_val = row['spec_value']
            if spec_name and spec_val:
                specs[spec_name] = spec_val
                if spec_name not in all_spec_names:
                    all_spec_names.append(spec_name)
        model_specs[model] = specs
        if not source_info and rows:
            row = rows[0]
            source_info = f"{row['source_file']}:{row['source_sheet']}"
    
    if model_specs:
        if len(model_specs) >= 2:
            # 多模型对比表格
            table_models = [m for m in models if m in model_specs]
            header = "| 对比项 | " + " | ".join(table_models) + " |"
            separator = "| --- | " + " | ".join(["---"] * len(table_models)) + " |"
            rows_str = []
            for spec_name in all_spec_names:
                vals = []
                for m in table_models:
                    val = model_specs[m].get(spec_name, '-')
                    if len(val) > 80:
                        val = val[:77] + "..."
                    vals.append(val)
                rows_str.append(f"| {spec_name} | " + " | ".join(vals) + " |")
            table_body = "\n".join([header, separator] + rows_str)
            title = " vs ".join(table_models) + " 产品对比"
            
            # 生成差异摘要
            diff_specs = []
            same_specs = []
            for spec_name in all_spec_names:
                unique_vals = set(model_specs[m].get(spec_name, '-').strip() for m in table_models if model_specs[m].get(spec_name, '-').strip() != '-')
                if len(unique_vals) > 1:
                    diff_specs.append(spec_name)
                elif len(unique_vals) == 1:
                    same_specs.append(spec_name)
            
            summary_parts = []
            if diff_specs:
                summary_parts.append(f"**主要差异（{len(diff_specs)}项）：**")
                for spec in diff_specs:
                    diff_detail = []
                    for m in table_models:
                        val = model_specs[m].get(spec, '-')
                        if len(val) > 50:
                            val = val[:47] + "..."
                        diff_detail.append(f"{m}: {val}")
                    summary_parts.append(f"- {spec} → {' | '.join(diff_detail)}")
            if same_specs:
                summary_parts.append(f"\n**相同参数：** {len(same_specs)} 项一致")
            
            summary = "\n".join(summary_parts)
            full_body = f"{table_body}\n\n---\n\n{summary}" if summary else table_body
            
            results.append({
                'type': '表格类-产品对比',
                'hit_rate': 1.0,
                'source': source_info,
                'title': title,
                'body': full_body,
                'raw': {},
            })
        else:
            # 单模型参数表格
            model = models[0]
            specs = model_specs.get(model, {})
            if specs:
                header = "| 参数项 | 参数值 |"
                separator = "| --- | --- |"
                rows_str = []
                for spec_name, spec_val in specs.items():
                    if len(spec_val) > 100:
                        spec_val = spec_val[:97] + "..."
                    rows_str.append(f"| {spec_name} | {spec_val} |")
                table_body = "\n".join([header, separator] + rows_str)
                results.append({
                    'type': '表格类-参数',
                    'hit_rate': 1.0,
                    'source': source_info,
                    'title': f"{model} 产品参数",
                    'body': table_body,
                    'raw': {'model': model},
                })
    
    # 2. 查 proposal 表（招标/方案/渠道参数）
    # 根据查询关键词过滤参数类型
    phase_filters = []
    if want_all:
        phase_filters = [('招标参数', 'phase_tender'), ('方案参数', 'phase_proposal'), ('渠道参数', 'phase_channel')]
    else:
        if want_tender:
            phase_filters.append(('招标参数', 'phase_tender'))
        if want_proposal:
            phase_filters.append(('方案参数', 'phase_proposal'))
        if want_channel:
            phase_filters.append(('渠道参数', 'phase_channel'))
    
    for model in models:
        rows = db.execute("SELECT * FROM proposal WHERE product_model LIKE ?", (f'%{model}%',))
        for row in rows:
            for phase_name, phase_key in phase_filters:
                body = row[phase_key] or ''
                if body.strip():
                    results.append({
                        'type': f'表格类-{phase_name}',
                        'hit_rate': 0.95,
                        'source': f"{row['source_file']}:{row['source_sheet']}:row{row['source_row']}",
                        'title': f"{row['product_name']} {phase_name}",
                        'body': body,
                        'raw': dict(row),
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


def _build_comparison_table(db, models: List[str]) -> Optional[Dict]:
    """Build a unified comparison table for 2+ models.
    Returns a single aggregated result with all specs in a table format."""
    from collections import defaultdict

    # Collect all comparison rows for all models
    model_specs = {}  # model -> {spec_name: spec_value}
    all_spec_names = []
    source_info = ""

    for model in models:
        rows = db.search_comparison_by_model(model)
        if not rows:
            continue
        specs = {}
        for r in rows:
            spec_name = r.get('spec_name', '')
            spec_val = r.get('spec_value', '')
            if spec_name:
                specs[spec_name] = spec_val
                if spec_name not in all_spec_names:
                    all_spec_names.append(spec_name)
        model_specs[model] = specs
        if not source_info and rows:
            r = rows[0]
            source_info = f"{r.get('source_file', '')}:{r.get('source_sheet', '')}"

    if len(model_specs) < 2:
        return None

    # Build table
    table_models = [m for m in models if m in model_specs]
    header = "| 对比项 | " + " | ".join(table_models) + " |"
    separator = "| --- | " + " | ".join(["---"] * len(table_models)) + " |"
    rows_str = []
    for spec_name in all_spec_names:
        vals = []
        for m in table_models:
            val = model_specs[m].get(spec_name, '-')
            # Truncate long values for readability
            if len(val) > 80:
                val = val[:77] + "..."
            vals.append(val)
        rows_str.append(f"| {spec_name} | " + " | ".join(vals) + " |")

    table_body = "\n".join([header, separator] + rows_str)
    title = " vs ".join(table_models) + " 产品对比"

    return {
        'type': '表格类-产品对比',
        'hit_rate': 1.0,
        'source': source_info,
        'title': title,
        'body': table_body,
        'raw': {},
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
            # For proposal-type excel cards (tender/proposal/channel), the model name
            # lives in semantic.models which is stripped by hybrid.search.
            # Since these cards have high relevance to model-specific queries,
            # ONLY apply the ×0.3 penalty when the card has NO relevance signal at all
            # (no model in body/title AND no model in semantic AND no proposal-type structure).
            if models:
                body_upper = body.upper()
                title_upper = title.upper()
                semantic_models = []
                is_proposal_type = ('proposal' in r.get('id', '') or
                                    'proposal' in r.get('raw', {}).get('id', '') or
                                    'tender' in r.get('id', '') or
                                    'channel' in r.get('id', ''))
                if isinstance(card, dict):
                    semantic_models = card.get('semantic', {}).get('models', []) or []
                has_model_match = any(m in body_upper or m in title_upper or m in semantic_models for m in models)
                if not has_model_match and not is_proposal_type:
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
        if not bm25_results:
            return results
        
        # Min-max normalization for BM25 scores
        scores = [score for _, score, _ in bm25_results]
        score_min = min(scores)
        score_max = max(scores)
        score_range = score_max - score_min if score_max > score_min else 1.0
        
        for cid, score, card in bm25_results:
            if score < 0.5:
                continue
            tag_boost = _compute_tag_boost(card, query)
            # Proper min-max normalization
            norm_score = (score - score_min) / score_range
            hit_rate = round(min(norm_score * tag_boost, 1.0), 3)
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


def _intent_rerank(results: List[Dict], query: str) -> List[Dict]:
    """Intent-based reranking: boost result types that match explicit query intent.

    When a user explicitly asks for 招标参数/可研参数/渠道参数,
    the matching proposal-phase cards should outrank generic comparison specs
    even if their raw hit_rate is lower.
    """
    q = query.lower()

    # Detect explicit intent
    want_tender = any(k in q for k in TENDER_KWS)
    want_proposal = any(k in q for k in ['可研', '方案参数'])
    want_channel = any(k in q for k in ['渠道', '通路', '简单清单'])
    want_compare = any(k in q for k in COMPARE_KWS)
    want_spec = any(k in q for k in SPEC_KWS)
    want_accessory = any(k in q for k in ACCESSORY_KWS)

    if not (want_tender or want_proposal or want_channel or
            want_compare or want_accessory):
        # No explicit type intent → keep hit_rate ordering
        results.sort(key=lambda x: x['hit_rate'], reverse=True)
        return results

    # Compute boost for each result based on type match
    INTENTS = {
        '招标参数': want_tender,
        '可研参数': want_proposal,
        '方案参数': want_proposal,
        '渠道参数': want_channel,
        '产品对比': want_compare,
        '性能参数': want_spec,
    }

    def rerank_key(r: Dict) -> tuple:
        raw_rate = r.get('hit_rate', 0)
        rtype = r.get('type', '') or ''

        # Determine source type from raw data (more reliable than rtype alone,
        # since all cards are typed as '方案类-段落' at the result-building layer)
        raw = r.get('raw', {})
        raw_src = raw.get('source', '') or raw.get('doc_file', '') or ''
        raw_id = raw.get('id', '') or ''
        is_excel = 'excel_proposal' in raw_id or 'excel_pricing' in raw_id or 'excel_comparison' in raw_id

        # Build a rich type identifier from the card's id/path/doc_file
        extra_types = []
        if is_excel:
            # e.g. excel_proposal_tender_proposal_000010 → extract 'proposal' + 'tender'
            parts = raw_id.replace('excel_proposal_', '').split('_')
            extra_types.extend([p for p in parts if p and p not in ('excel', 'proposal')])
        # Also check path for KB cards
        path = raw.get('path', '') or ''
        if '招标参数' in path:
            extra_types.append('招标参数')
        if '可研参数' in path or '方案参数' in path:
            extra_types.append('方案参数')
        if '渠道参数' in path:
            extra_types.append('渠道参数')

        # Determine type match score
        type_boost = 0.0
        matched = False
        for intent_name, active in INTENTS.items():
            if active and (intent_name in rtype or intent_name in extra_types or intent_name in path):
                type_boost = 0.15
                matched = True
                break
            elif not active and intent_name in rtype:
                type_boost = -0.10  # Demote non-requested types slightly

        # doc_hint from excel cards (check id as fallback for hybrid's stripped raw)
        doc_hint = raw.get('doc_hint', '')
        if not doc_hint and 'proposal' in raw_id:
            doc_hint = 'proposal'

        if want_tender and doc_hint == 'proposal' and ('招标' in path or 'tender' in raw_id):
            type_boost = 0.20
            matched = True
        elif want_proposal and doc_hint == 'proposal' and '可研' in path:
            type_boost = 0.20
            matched = True
        elif want_channel and doc_hint == 'proposal' and '渠道' in path:
            type_boost = 0.20
            matched = True

        # Prefer comparison specs when comparing
        if want_compare and 'comparison' in rtype:
            type_boost = 0.20
            matched = True

        # For accessory queries: boost pricing cards (which list bundled items)
        # and demote comparison spec cards (which list interface specs)
        if want_accessory:
            if 'pricing' in raw_id or 'pricing' in rtype.lower():
                type_boost = 0.20
                matched = True
            elif 'comparison' in raw_id or 'comparison' in rtype.lower():
                type_boost = -0.15  # Demote spec cards for accessory queries

        # title check: if query mentions a specific model, title match matters
        title_lower = r.get('title', '').lower()
        models_in_q = extract_models(query)
        title_model_match = any(m.lower() in title_lower for m in models_in_q)

        # Adjusted score
        adjusted = raw_rate + type_boost
        # Tie-breaker: title model match > hit_rate
        return (adjusted, title_model_match, raw_rate)

    results.sort(key=rerank_key, reverse=True)
    return results


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
    """Main entry point: ALL queries go through unified hybrid search.

    The excel SQLite path is only used when a facet filter is explicitly
    specified (--facet tender/proposal/channel/pricing_type/etc).
    Without a facet filter, every query competes in the same hybrid pool
    (BM25 + Vector over all cards including excel_*.json cards).
    """
    source_type, models, intent = classify_query(query)
    q = query.lower()

    # Broad query detection (for disambiguation UI)
    is_broad = False
    if models:
        remaining = q
        for m in models:
            remaining = remaining.replace(m.lower(), '')
        words = [w for w in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', remaining) if len(w) >= 2]
        has_specific = any(k in q for k in SPECIFIC_KWS)
        is_broad = (all(w in BROAD_KWS for w in words) if words else True) and not has_specific

    all_results = []

    # ── Intent-driven routing ──
    
    # 结构化查询意图：直接走SQL，不走hybrid搜索
    if intent in [INTENT_PRICE, INTENT_CATEGORY, INTENT_EOL, INTENT_ACCESSORY, INTENT_TENDER, 'spec_query']:
        all_results = search_excel(query, models, intent=intent, facet_filter=facet_filter)
    
    # 配件查询（SQL+cards）
    elif intent == INTENT_ACCESSORY_HYBRID:
        all_results = search_excel(query, models, intent=INTENT_ACCESSORY, facet_filter=facet_filter)
        all_results.extend(search_knowledge(query, models))
    
    # 对比表格：走SQL聚合
    elif intent == INTENT_COMPARE:
        all_results = search_excel(query, models, intent=intent, facet_filter=facet_filter)
    
    # 方案描述：走hybrid搜索
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

    # Sort by hit_rate descending (no more "excel first" bias)
    # Apply intent-based reranking: if query specifies 招标/可研/渠道,
    # boost matching proposal card types above general comparison specs
    unique = _intent_rerank(unique, q)

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
        f"出处: {source}\n"
        f"命中率: {hit_rate:.0%}\n\n---"
    )


def format_summary_table(hits: List[Dict]) -> str:
    """当结果超过5条时，输出紧凑的汇总表格"""
    if not hits:
        return ""
    
    # 判断结果类型
    first_type = hits[0].get('type', '')
    
    # 价格类汇总
    if '价格' in first_type or '分类' in first_type:
        lines = ["| 序号 | 产品/分类 | 价格 | 命中率 |", "| --- | --- | --- | --- |"]
        for i, h in enumerate(hits, 1):
            title = h.get('title', '').replace('\n', ' ').strip()
            if len(title) > 30:
                title = title[:27] + "..."
            body = h.get('body', '')
            # 提取价格
            price = '-'
            for line in body.split('\n'):
                if line.startswith('价格：') or line.startswith('价格:'):
                    price = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                    if len(price) > 20:
                        price = price[:17] + "..."
                    break
            hit_rate = h.get('hit_rate', 0)
            lines.append(f"| {i} | {title} | {price} | {hit_rate:.0%} |")
        return "\n".join(lines)
    
    # 配件类汇总
    if '配件' in first_type:
        lines = ["| 序号 | 配件名称 | 价格 | 命中率 |", "| --- | --- | --- | --- |"]
        for i, h in enumerate(hits, 1):
            title = h.get('title', '').replace('\n', ' ').strip()
            if len(title) > 30:
                title = title[:27] + "..."
            body = h.get('body', '')
            price = '-'
            for line in body.split('\n'):
                if line.startswith('价格：') or line.startswith('价格:'):
                    price = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                    if len(price) > 15:
                        price = price[:12] + "..."
                    break
            hit_rate = h.get('hit_rate', 0)
            lines.append(f"| {i} | {title} | {price} | {hit_rate:.0%} |")
        return "\n".join(lines)
    
    # 通用汇总（方案类等）
    lines = ["| 序号 | 标题 | 命中率 |", "| --- | --- | --- |"]
    for i, h in enumerate(hits, 1):
        title = h.get('title', '').replace('\n', ' ').strip()
        if len(title) > 40:
            title = title[:37] + "..."
        hit_rate = h.get('hit_rate', 0)
        lines.append(f"| {i} | {title} | {hit_rate:.0%} |")
    return "\n".join(lines)


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

        # 超过5条结果时，先输出汇总表格，再输出详情
        if len(display) > 5 and not args.all:
            print(format_summary_table(display))
            print(f"\n以上为汇总，共 {len(display)} 条。详细信息如下：\n")
        
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
