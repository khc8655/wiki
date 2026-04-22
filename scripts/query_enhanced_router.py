#!/usr/bin/env python3
"""
Enhanced Query Router v2
支持五类数据源的置信度路由和多源查询
"""

import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[1]
EXCEL_STORE = ROOT / 'excel_store'

QUERY_PATTERNS = {
    'pricing': {
        'keywords': ['价格', '报价', '多少钱', '费用', '成本', '钱', '元', '贵', '便宜', '折扣', '停产', '替代'],
        'weight': 1.0
    },
    'comparison': {
        'keywords': ['对比', '比较', '区别', '差异', 'vs', 'versus', '不同', '优劣', '哪个好', '差别'],
        'weight': 1.2
    },
    'proposal': {
        'keywords': ['招标', '投标', '参数', '询价', '方案', '描述', '规格', '配置', '技术参数'],
        'weight': 1.1
    },
    'release_notes': {
        'keywords': ['迭代', '新功能', '升级', '优化', '修复', '支持', '版本', '新增', '变更', '更新', '功能'],
        'weight': 1.0
    },
    'solution': {
        'keywords': ['架构', '方案', '优势', '原理', '设计', '技术', '介绍', '什么是'],
        'weight': 0.9
    }
}

PRODUCT_MODEL_PATTERN = re.compile(
    r'([A-Z]{1,2}\d{3}[A-Z]?|AE\d{3}|XE\d{3}|GE\d{3}|PE\d{4}|TP\d{3}|AI|会议室)',
    re.IGNORECASE
)

def extract_entities(query: str) -> Dict:
    """提取查询中的实体"""
    entities = {
        'product_models': [],
        'price_terms': [],
        'compare_terms': [],
        'proposal_terms': [],
        'feature_terms': []
    }
    
    models = PRODUCT_MODEL_PATTERN.findall(query)
    entities['product_models'] = list(set([m.upper() for m in models]))
    
    q = query.lower()
    for kw in QUERY_PATTERNS['pricing']['keywords']:
        if kw in q:
            entities['price_terms'].append(kw)
    for kw in QUERY_PATTERNS['comparison']['keywords']:
        if kw in q:
            entities['compare_terms'].append(kw)
    for kw in QUERY_PATTERNS['proposal']['keywords']:
        if kw in q:
            entities['proposal_terms'].append(kw)
    for kw in QUERY_PATTERNS['release_notes']['keywords']:
        if kw in q:
            entities['feature_terms'].append(kw)
    
    return entities

def calculate_confidence(query: str, query_type: str, entities: Dict) -> float:
    """计算匹配置信度"""
    config = QUERY_PATTERNS[query_type]
    q = query.lower()
    score = 0.0
    
    keyword_hits = sum(1 for kw in config['keywords'] if kw in q)
    score += keyword_hits * 15
    
    if query_type == 'comparison':
        if len(entities['product_models']) >= 2:
            score += 40
        elif entities['compare_terms']:
            score += 20
    elif query_type == 'pricing':
        if entities['product_models'] and entities['price_terms']:
            score += 40
        elif entities['price_terms']:
            score += 25
        elif entities['product_models']:
            score += 15
    elif query_type == 'proposal':
        if entities['product_models'] and entities['proposal_terms']:
            score += 40
        elif entities['proposal_terms']:
            score += 20
    elif query_type == 'release_notes':
        if entities['product_models'] and entities['feature_terms']:
            score += 35
        elif entities['feature_terms']:
            score += 20
    
    score *= config['weight']
    return min(score, 100)

def route_query(query: str) -> Tuple[str, Dict, Dict, bool, List[str]]:
    """路由决策"""
    entities = extract_entities(query)
    
    confidences = {}
    for qtype in QUERY_PATTERNS.keys():
        confidences[qtype] = calculate_confidence(query, qtype, entities)
    
    sorted_types = sorted(confidences.items(), key=lambda x: x[1], reverse=True)
    
    primary_type = sorted_types[0][0]
    primary_conf = sorted_types[0][1]
    
    is_ambiguous = primary_conf < 30
    multi_sources = []
    
    if len(sorted_types) > 1:
        second_conf = sorted_types[1][1]
        if primary_conf - second_conf < 20:
            is_ambiguous = True
            multi_sources = [t for t, c in sorted_types[:3] if c > 20]
    
    if len(entities['product_models']) == 1 and primary_conf < 50:
        for t in ['release_notes', 'pricing', 'comparison']:
            if t not in multi_sources:
                multi_sources.append(t)
    
    return primary_type, confidences, entities, is_ambiguous, multi_sources

def load_excel_data(data_type: str) -> List[Dict]:
    """加载Excel数据"""
    try:
        with open(EXCEL_STORE / data_type / 'records.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def search_pricing(entities: Dict, top_k: int = 5) -> List[Dict]:
    records = load_excel_data('pricing')
    results = []
    models = entities.get('product_models', [])
    
    for record in records:
        score = 0
        name = record.get('product_name', '')
        
        for model in models:
            if model.upper() in name.upper():
                score += 100
        
        if any(kw in name.lower() for kw in entities.get('price_terms', [])):
            score += 30
        
        if score > 0:
            record['_score'] = score
            record['_source'] = 'pricing'
            results.append(record)
    
    results.sort(key=lambda x: x['_score'], reverse=True)
    return results[:top_k]

def search_comparison(entities: Dict, top_k: int = 10) -> List[Dict]:
    records = load_excel_data('comparison')
    results = []
    models = entities.get('product_models', [])
    
    if len(models) >= 2:
        for record in records:
            if record.get('model', '').upper() in [m.upper() for m in models]:
                record['_score'] = 100
                record['_source'] = 'comparison'
                results.append(record)
    elif len(models) == 1:
        for record in records:
            if record.get('model', '').upper() == models[0].upper():
                record['_score'] = 80
                record['_source'] = 'comparison'
                results.append(record)
    
    results.sort(key=lambda x: x['_score'], reverse=True)
    return results[:top_k]

def search_proposal(entities: Dict, top_k: int = 5) -> List[Dict]:
    records = load_excel_data('proposal')
    results = []
    models = entities.get('product_models', [])
    
    for record in records:
        score = 0
        product = record.get('product_name', '')
        model = record.get('product_model', '')
        
        for m in models:
            if m.upper() in product.upper() or m.upper() in model.upper():
                score += 100
        
        if score > 0:
            record['_score'] = score
            record['_source'] = 'proposal'
            results.append(record)
    
    results.sort(key=lambda x: x['_score'], reverse=True)
    return results[:top_k]

def format_result(result: Dict, source: str) -> str:
    """格式化结果"""
    lines = [f"\n[{source.upper()}] "]
    
    if source == 'pricing':
        lines.append(f"产品: {result.get('product_name', 'N/A')}")
        lines.append(f"价格: {result.get('price_raw', 'N/A')}")
        if result.get('note'):
            lines.append(f"备注: {result['note'][:100]}...")
    elif source == 'comparison':
        lines.append(f"{result.get('feature', 'N/A')}: {result.get('value', 'N/A')[:50]}...")
    elif source == 'proposal':
        lines.append(f"产品: {result.get('product_name', 'N/A')}")
        if result.get('phase_tender'):
            lines.append(f"招标: {result['phase_tender'][:100]}...")
    
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='Enhanced Query Router')
    parser.add_argument('query', help='查询内容')
    parser.add_argument('-k', '--top-k', type=int, default=5, help='返回结果数')
    parser.add_argument('--show-confidence', action='store_true', help='显示置信度')
    args = parser.parse_args()
    
    query = args.query
    primary_type, confidences, entities, is_ambiguous, multi_sources = route_query(query)
    
    # 输出路由信息
    print(f"=== 查询分析 ===")
    print(f"查询: {query}")
    print(f"主数据源: {primary_type} (置信度: {confidences[primary_type]:.1f})")
    print(f"提取实体: {entities}")
    print(f"是否模糊: {is_ambiguous}")
    
    if args.show_confidence:
        print(f"\n各类别置信度:")
        for t, c in sorted(confidences.items(), key=lambda x: x[1], reverse=True):
            print(f"  {t}: {c:.1f}")
    
    # 执行查询
    print(f"\n=== 查询结果 ===")
    
    sources_to_query = multi_sources if is_ambiguous else [primary_type]
    
    all_results = []
    for source in sources_to_query:
        if source == 'pricing':
            results = search_pricing(entities, args.top_k)
        elif source == 'comparison':
            results = search_comparison(entities, args.top_k)
        elif source == 'proposal':
            results = search_proposal(entities, args.top_k)
        else:
            continue
        
        if results:
            print(f"\n--- {source.upper()} ({len(results)}条) ---")
            for r in results:
                print(format_result(r, source))
            all_results.extend(results)
    
    if not all_results:
        print("未找到相关结果")
        return
    
    print(f"\n总计找到 {len(all_results)} 条记录")

if __name__ == '__main__':
    main()
