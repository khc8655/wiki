#!/usr/bin/env python3
"""
全源查询 - 宁多勿少策略
同时搜索所有数据源，合并返回
"""

import json
import re
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
EXCEL_STORE = ROOT / 'excel_store'

# 产品型号正则
MODEL_PATTERN = re.compile(r'(AE\d{3}|XE\d{3}|GE\d{3}|PE\d{4}|TP\d{3}|AI|会议室)', re.I)

def extract_models(query: str) -> List[str]:
    """提取产品型号"""
    return list(set([m.upper() for m in MODEL_PATTERN.findall(query)]))

def load_json(path: Path) -> List[Dict]:
    """加载JSON文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def search_pricing(query: str, models: List[str], top_k: int = 5) -> List[Dict]:
    """搜索价格数据"""
    records = load_json(EXCEL_STORE / 'pricing' / 'records.json')
    results = []
    
    for record in records:
        score = 0
        name = record.get('product_name', '')
        category = record.get('category', '')
        
        # 型号匹配
        for model in models:
            if model in name.upper():
                score += 100
            elif model in category.upper():
                score += 50
        
        # 关键词匹配
        if any(kw in query.lower() for kw in ['价格', '多少钱', '费用', '钱']):
            if '价格' in name or '钱' in name:
                score += 30
        
        if score > 0:
            record['_score'] = score
            record['_source'] = '价格'
            results.append(record)
    
    results.sort(key=lambda x: x['_score'], reverse=True)
    return results[:top_k]

def search_comparison(query: str, models: List[str], top_k: int = 5) -> List[Dict]:
    """搜索对比数据"""
    records = load_json(EXCEL_STORE / 'comparison' / 'records.json')
    results = []
    
    for record in records:
        score = 0
        model = record.get('model', '')
        feature = record.get('feature', '')
        
        for m in models:
            if m == model.upper():
                score += 100
        
        if score > 0:
            record['_score'] = score
            record['_source'] = '规格'
            results.append(record)
    
    results.sort(key=lambda x: x['_score'], reverse=True)
    return results[:top_k]

def search_proposal(query: str, models: List[str], top_k: int = 5) -> List[Dict]:
    """搜索招标数据"""
    records = load_json(EXCEL_STORE / 'proposal' / 'records.json')
    results = []
    
    for record in records:
        score = 0
        product = record.get('product_name', '')
        model = record.get('product_model', '')
        
        for m in models:
            if m in product.upper() or m in model.upper():
                score += 100
        
        if score > 0:
            record['_score'] = score
            record['_source'] = '招标'
            results.append(record)
    
    results.sort(key=lambda x: x['_score'], reverse=True)
    return results[:top_k]

def format_result(r: Dict) -> str:
    """格式化结果"""
    source = r.get('_source', '未知')
    
    if source == '价格':
        name = r.get('product_name', 'N/A')
        price = r.get('price_raw', 'N/A')
        note = r.get('note', '')
        lines = [f"【{source}】{name}", f"  价格: {price}"]
        if note:
            lines.append(f"  备注: {note[:60]}...")
        return '\n'.join(lines)
    
    elif source == '规格':
        feature = r.get('feature', 'N/A')
        value = r.get('value', 'N/A')
        model = r.get('model', 'N/A')
        return f"【{source}】{model} - {feature}: {value[:50]}..."
    
    elif source == '招标':
        name = r.get('product_name', 'N/A')
        model = r.get('product_model', 'N/A')
        tender = r.get('phase_tender', '')
        lines = [f"【{source}】{name} ({model})"]
        if tender:
            lines.append(f"  {tender[:80]}...")
        return '\n'.join(lines)
    
    return str(r)

def query_all(query: str, top_k: int = 5) -> List[Dict]:
    """全源查询主函数"""
    models = extract_models(query)
    
    # 并行查3类Excel数据
    all_results = []
    all_results.extend(search_pricing(query, models, top_k))
    all_results.extend(search_comparison(query, models, top_k))
    all_results.extend(search_proposal(query, models, top_k))
    
    # 按分数排序
    all_results.sort(key=lambda x: x.get('_score', 0), reverse=True)
    
    return all_results

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python3 query_all_sources.py '查询内容'")
        sys.exit(1)
    
    query = sys.argv[1]
    results = query_all(query, top_k=5)
    
    print(f"=== 查询: {query} ===")
    print(f"找到 {len(results)} 条记录\n")
    
    for i, r in enumerate(results, 1):
        print(f"[{i}] {format_result(r)}\n")

if __name__ == '__main__':
    main()
