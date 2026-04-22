#!/usr/bin/env python3
"""
Query Excel Knowledge Base
Supports three data types:
- pricing: 价格查询
- proposal: 阶段描述查询
- comparison: 产品对比查询
"""

import json
import re
import argparse
from pathlib import Path
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[1]
EXCEL_STORE = ROOT / 'excel_store'

def load_data(data_type):
    """Load records and indexes for a data type"""
    data_dir = EXCEL_STORE / data_type
    
    with open(data_dir / 'records.json', 'r', encoding='utf-8') as f:
        records = json.load(f)
    
    with open(data_dir / 'indexes.json', 'r', encoding='utf-8') as f:
        indexes = json.load(f)
    
    return records, indexes

def similarity(a, b):
    """Calculate string similarity"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def search_pricing(query, top_k=5):
    """Search pricing records"""
    records, indexes = load_data('pricing')
    
    results = []
    query_lower = query.lower()
    
    for record in records:
        score = 0
        reasons = []
        
        name = record.get('product_name', '')
        if name:
            if query_lower == name.lower():
                score += 100
                reasons.append('exact_name')
            elif query_lower in name.lower():
                score += 50
                reasons.append('name_contains')
            elif similarity(query, name) > 0.7:
                score += 30
                reasons.append('name_similar')
        
        category = record.get('category', '')
        if category and query_lower in category.lower():
            score += 20
            reasons.append('category')
        
        code = record.get('product_code', '')
        if code and query_lower in code.lower():
            score += 40
            reasons.append('code')
        
        note = record.get('note', '')
        if note and query_lower in note.lower():
            score += 15
            reasons.append('note')
        
        desc = record.get('description', '')
        if desc and query_lower in desc.lower():
            score += 10
            reasons.append('desc')
        
        if score > 0:
            results.append({'record': record, 'score': score, 'reasons': reasons})
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]

def search_proposal(query, top_k=5):
    """Search proposal records"""
    records, indexes = load_data('proposal')
    
    results = []
    query_lower = query.lower()
    
    for record in records:
        score = 0
        reasons = []
        
        product = record.get('product_name', '')
        model = record.get('product_model', '')
        
        if product:
            if query_lower == product.lower():
                score += 100
                reasons.append('exact_product')
            elif query_lower in product.lower():
                score += 50
                reasons.append('product_contains')
        
        if model:
            if query_lower == model.lower():
                score += 90
                reasons.append('exact_model')
            elif query_lower in model.lower():
                score += 45
                reasons.append('model_contains')
        
        if score > 0:
            results.append({'record': record, 'score': score, 'reasons': reasons})
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]

def search_comparison(query, top_k=10):
    """Search comparison records"""
    records, indexes = load_data('comparison')
    
    results = []
    query_lower = query.lower()
    
    for record in records:
        score = 0
        reasons = []
        
        model = record.get('model', '')
        if model:
            if query_lower == model.lower():
                score += 100
                reasons.append('exact_model')
            elif query_lower in model.lower():
                score += 50
                reasons.append('model_contains')
        
        feature = record.get('feature', '')
        if query_lower in feature.lower():
            score += 20
            reasons.append('feature')
        
        value = record.get('value', '')
        if query_lower in value.lower():
            score += 10
            reasons.append('value')
        
        if score > 0:
            results.append({'record': record, 'score': score, 'reasons': reasons})
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]

def get_model_features(model):
    """Get all features for a model"""
    records, indexes = load_data('comparison')
    return [r for r in records if r['model'] == model]

def compare_models(models):
    """Compare multiple models"""
    records, indexes = load_data('comparison')
    
    if not models:
        return []
    
    model_records = {m: [] for m in models}
    for record in records:
        model = record.get('model', '')
        if model in models:
            model_records[model].append(record)
    
    all_features = set()
    for m in models:
        for r in model_records[m]:
            all_features.add(r['feature'])
    
    comparison = []
    for feature in sorted(all_features):
        row = {'feature': feature}
        for model in models:
            values = [r['value'] for r in model_records[model] if r['feature'] == feature]
            row[model] = values[0] if values else 'N/A'
        comparison.append(row)
    
    return comparison

def format_pricing_result(result, idx):
    """Format pricing result"""
    r = result['record']
    lines = [
        f"\n[{idx}] {r.get('product_name', 'N/A')}",
        f"    类别: {r.get('category', 'N/A')}",
        f"    型号: {r.get('product_model', 'N/A')}",
        f"    编码: {r.get('product_code', 'N/A')}",
        f"    价格: {r.get('price_raw', 'N/A')}",
        f"    单位: {r.get('unit', 'N/A')}",
    ]
    
    if r.get('note'):
        lines.append(f"    备注: {r['note']}")
    
    lines.append(f"    来源: {r.get('source_sheet', 'N/A')} 第{r.get('source_row', 'N/A')}行")
    
    return '\n'.join(lines)

def format_proposal_result(result, idx, phase=None):
    """Format proposal result"""
    r = result['record']
    lines = [
        f"\n[{idx}] {r.get('product_name', 'N/A')} ({r.get('product_model', 'N/A')})",
    ]
    
    if phase == 'channel' or phase is None:
        if r.get('phase_channel'):
            lines.append(f"    【渠道询价阶段】\n{r['phase_channel'][:300]}...")
    
    if phase == 'proposal' or phase is None:
        if r.get('phase_proposal'):
            lines.append(f"    【方案设计阶段】\n{r['phase_proposal'][:300]}...")
    
    if phase == 'tender' or phase is None:
        if r.get('phase_tender'):
            lines.append(f"    【招投标阶段】\n{r['phase_tender'][:300]}...")
    
    if r.get('note'):
        lines.append(f"    备注: {r['note'][:200]}")
    
    return '\n'.join(lines)

def format_comparison_result(results, query):
    """Format comparison results"""
    if not results:
        return "未找到相关结果"
    
    # Group by model
    models = {}
    for result in results:
        model = result['record']['model']
        if model not in models:
            models[model] = []
        models[model].append(result['record'])
    
    lines = [f"\n找到 {len(models)} 个相关型号:"]
    
    for model, records in sorted(models.items()):
        lines.append(f"\n【{model}】")
        for r in records[:8]:  # Show top 8 features
            lines.append(f"  - {r['feature']}: {r['value'][:100]}")
    
    return '\n'.join(lines)

def format_comparison_table(comparison, models):
    """Format comparison as table"""
    if not comparison:
        return "无可对比数据"
    
    lines = ["\n【产品对比表】"]
    lines.append("=" * 80)
    
    header = f"{'能力项':<20}"
    for model in models:
        header += f"{model:<20}"
    lines.append(header)
    lines.append("-" * 80)
    
    for row in comparison[:15]:  # Show top 15 features
        line = f"{row['feature']:<20}"
        for model in models:
            val = str(row.get(model, 'N/A'))[:18]
            line += f"{val:<20}"
        lines.append(line)
    
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='Query Excel Knowledge Base')
    parser.add_argument('query', help='Search query')
    parser.add_argument('-t', '--type', choices=['pricing', 'proposal', 'comparison'], 
                        default='pricing', help='Data type to search')
    parser.add_argument('-k', '--top-k', type=int, default=5, help='Number of results')
    parser.add_argument('--brief', action='store_true', help='Brief output')
    parser.add_argument('--compare', nargs='+', help='Models to compare')
    parser.add_argument('--phase', choices=['channel', 'proposal', 'tender'], 
                        help='Proposal phase to show')
    
    args = parser.parse_args()
    
    if args.type == 'pricing':
        results = search_pricing(args.query, args.top_k)
        if not results:
            print(f"未找到与 '{args.query}' 相关的价格信息")
            return
        
        print(f"\n=== 价格查询: {args.query} ===")
        print(f"找到 {len(results)} 条记录\n")
        
        for i, result in enumerate(results, 1):
            print(format_pricing_result(result, i))
    
    elif args.type == 'proposal':
        results = search_proposal(args.query, args.top_k)
        if not results:
            print(f"未找到与 '{args.query}' 相关的方案描述")
            return
        
        print(f"\n=== 方案描述查询: {args.query} ===")
        print(f"找到 {len(results)} 条记录\n")
        
        for i, result in enumerate(results, 1):
            print(format_proposal_result(result, i, args.phase))
    
    elif args.type == 'comparison':
        if args.compare and len(args.compare) >= 2:
            # Compare specific models
            comparison = compare_models(args.compare)
            print(f"\n=== 产品对比: {' vs '.join(args.compare)} ===")
            print(format_comparison_table(comparison, args.compare))
        else:
            # Search by query
            results = search_comparison(args.query, args.top_k * 3)
            if not results:
                print(f"未找到与 '{args.query}' 相关的产品对比信息")
                return
            
            print(f"\n=== 产品对比查询: {args.query} ===")
            print(format_comparison_result(results, args.query))

if __name__ == '__main__':
    main()
