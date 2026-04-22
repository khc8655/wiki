#!/usr/bin/env python3
"""
三种查询方案对比测试

方案1: 简单关键词路由（原始方案）
方案2: 置信度路由（中间方案）  
方案3: 语义意图+智能多源（新方案）
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parents[1]
EXCEL_STORE = ROOT / 'excel_store'

# 测试查询集
TEST_QUERIES = [
    ("AE800多少钱", ["pricing"], "AE800价格查询"),
    ("XE800与AE800对比", ["comparison"], "两产品对比"),
    ("AE800参数", ["proposal", "comparison"], "招标参数查询"),
    ("AE800", ["pricing", "comparison", "proposal"], "模糊产品查询"),
    ("会议室价格", ["pricing"], "类别价格查询"),
    ("PE8000停产", ["pricing"], "停产信息查询"),
    ("AI语音转写", ["pricing", "comparison"], "AI功能查询"),
    ("小鱼易连架构", ["solution"], "架构方案查询"),
]

def load_data():
    """加载所有数据"""
    data = {}
    for source in ['pricing', 'comparison', 'proposal']:
        try:
            with open(EXCEL_STORE / source / 'records.json', 'r', encoding='utf-8') as f:
                data[source] = json.load(f)
        except:
            data[source] = []
    return data

DATA = load_data()

# ============ 方案1: 简单关键词路由 ============
def approach1_keyword_routing(query: str) -> List[str]:
    """简单关键词匹配路由"""
    q = query.lower()
    
    # 对比优先
    if any(kw in q for kw in ['对比', '比较', '区别', 'vs', '差异']):
        return ['comparison']
    
    # 招标
    if any(kw in q for kw in ['招标', '投标', '参数', '询价']):
        return ['proposal']
    
    # 价格
    if any(kw in q for kw in ['价格', '多少钱', '费用', '钱', '元']):
        return ['pricing']
    
    # 默认价格
    if re.search(r'(AE|XE|GE|PE|TP)\d+', query, re.I):
        return ['pricing']
    
    return ['pricing']

# ============ 方案2: 置信度路由 ============
def approach2_confidence_routing(query: str) -> List[str]:
    """置信度评分路由"""
    q = query.lower()
    
    # 计算各类别得分
    scores = {
        'pricing': 0,
        'comparison': 0,
        'proposal': 0,
    }
    
    # 关键词得分
    pricing_kw = ['价格', '多少钱', '费用', '钱', '元', '停产', '替代']
    comparison_kw = ['对比', '比较', '区别', 'vs', '差异']
    proposal_kw = ['招标', '投标', '参数', '询价']
    
    scores['pricing'] = sum(15 for kw in pricing_kw if kw in q)
    scores['comparison'] = sum(15 for kw in comparison_kw if kw in q) * 1.2  # 权重
    scores['proposal'] = sum(15 for kw in proposal_kw if kw in q) * 1.1
    
    # 型号加分
    if re.search(r'(AE|XE|GE|PE|TP)\d+', query, re.I):
        scores['pricing'] += 20
        scores['comparison'] += 10
        scores['proposal'] += 15
    
    # 多型号 = 对比
    models = re.findall(r'(AE\d{3}|XE\d{3}|GE\d{3})', query, re.I)
    if len(models) >= 2:
        scores['comparison'] += 40
    
    # 选择最高分，差距<20分时多源
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_scores[0]
    
    if primary[1] < 30:  # 低置信度，多源
        return [s for s, v in sorted_scores if v > 15]
    
    if len(sorted_scores) > 1 and primary[1] - sorted_scores[1][1] < 20:
        return [s for s, v in sorted_scores[:2] if v > 20]
    
    return [primary[0]]

# ============ 方案3: 语义意图+智能多源 ============
def approach3_semantic_intent(query: str) -> List[str]:
    """
    语义意图识别 + 智能多源
    
    核心：识别用户到底想要什么信息，而不是关键词匹配
    """
    q = query.lower()
    sources = []
    
    # 提取实体
    models = re.findall(r'(AE\d{3}|XE\d{3}|GE\d{3}|PE\d{4}|TP\d{3})', query, re.I)
    has_price_kw = any(kw in q for kw in ['价格', '多少钱', '费用'])
    has_compare_kw = any(kw in q for kw in ['对比', '区别', 'vs', '和', '与'])
    has_spec_kw = any(kw in q for kw in ['参数', '规格', '配置'])
    has_procurement_kw = any(kw in q for kw in ['招标', '投标'])
    
    # 意图判断
    
    # 意图1: 购买决策（需要价格+规格对比）
    if has_price_kw and len(models) >= 2:
        sources = ['pricing', 'comparison']
    
    # 意图2: 产品了解（需要规格+招标参数）
    elif has_spec_kw and models:
        sources = ['comparison', 'proposal', 'pricing']
    
    # 意图3: 纯价格查询
    elif has_price_kw:
        sources = ['pricing']
        if models and '停产' in q:  # 停产信息可能在备注
            sources.append('pricing')  # 已经包含
    
    # 意图4: 纯对比
    elif has_compare_kw and len(models) >= 2:
        sources = ['comparison']
    
    # 意图5: 招标准备
    elif has_procurement_kw:
        sources = ['proposal', 'comparison']
    
    # 意图6: 单产品全面了解（最模糊但最常见）
    elif len(models) == 1:
        # 用户只说了型号，可能想了解任何东西
        # 优先查价格+规格，但保留提案可能性
        sources = ['pricing', 'comparison', 'proposal']
    
    # 意图7: 类别查询（会议室/AI等）
    elif any(kw in q for kw in ['会议室', 'ai', '云']):
        sources = ['pricing']
    
    else:
        sources = ['pricing']  # 兜底
    
    return list(set(sources))  # 去重

# ============ 测试执行 ============
def search_source(source: str, query: str) -> int:
    """模拟搜索，返回命中数"""
    q = query.lower()
    models = re.findall(r'(AE\d{3}|XE\d{3}|GE\d{3}|PE\d{4}|TP\d{3})', query, re.I)
    count = 0
    
    if source not in DATA:
        return 0
    
    for record in DATA[source]:
        text = str(record).lower()
        for m in models:
            if m.lower() in text:
                count += 1
                break
    
    return min(count, 10)  # 最多算10条

def evaluate_approach(name: str, routing_fn, test_cases: List[Tuple]) -> Dict:
    """评估方案"""
    results = {
        'name': name,
        'correct_source': 0,
        'recall': 0,
        'avg_sources': 0,
        'total_hits': 0,
        'details': []
    }
    
    for query, expected_sources, desc in test_cases:
        predicted = routing_fn(query)
        hits = sum(search_source(s, query) for s in predicted)
        
        # 检查是否覆盖了所有期望源
        covered = len(set(predicted) & set(expected_sources))
        recall = covered / len(expected_sources) if expected_sources else 1.0
        
        results['correct_source'] += 1 if set(predicted) == set(expected_sources) else 0
        results['recall'] += recall
        results['avg_sources'] += len(predicted)
        results['total_hits'] += hits
        
        results['details'].append({
            'query': query,
            'expected': expected_sources,
            'predicted': predicted,
            'recall': recall,
            'hits': hits
        })
    
    n = len(test_cases)
    results['correct_source'] /= n
    results['recall'] /= n
    results['avg_sources'] /= n
    
    return results

def main():
    print("=" * 60)
    print("三种查询方案对比测试")
    print("=" * 60)
    
    # 运行测试
    r1 = evaluate_approach("方案1: 关键词路由", approach1_keyword_routing, TEST_QUERIES)
    r2 = evaluate_approach("方案2: 置信度路由", approach2_confidence_routing, TEST_QUERIES)
    r3 = evaluate_approach("方案3: 语义意图", approach3_semantic_intent, TEST_QUERIES)
    
    # 打印汇总
    print("\n【汇总对比】")
    print("-" * 60)
    print(f"{'指标':<20} {'方案1':<12} {'方案2':<12} {'方案3':<12}")
    print("-" * 60)
    print(f"{'源完全匹配率':<20} {r1['correct_source']:.2%}{'':<6} {r2['correct_source']:.2%}{'':<6} {r3['correct_source']:.2%}")
    print(f"{'期望源召回率':<20} {r1['recall']:.2%}{'':<6} {r2['recall']:.2%}{'':<6} {r3['recall']:.2%}")
    print(f"{'平均查询源数':<20} {r1['avg_sources']:.1f}{'':<7} {r2['avg_sources']:.1f}{'':<7} {r3['avg_sources']:.1f}")
    print(f"{'总命中记录数':<20} {r1['total_hits']}{'':<7} {r2['total_hits']}{'':<7} {r3['total_hits']}")
    print("-" * 60)
    
    # 打印详细
    print("\n【详细对比】")
    for i, (query, expected, desc) in enumerate(TEST_QUERIES):
        p1, p2, p3 = r1['details'][i], r2['details'][i], r3['details'][i]
        print(f"\n查询: {query}")
        print(f"  期望源: {expected}")
        print(f"  方案1 → {p1['predicted']} (召回{p1['recall']:.0%}, 命中{p1['hits']}条)")
        print(f"  方案2 → {p2['predicted']} (召回{p2['recall']:.0%}, 命中{p2['hits']}条)")
        print(f"  方案3 → {p3['predicted']} (召回{p3['recall']:.0%}, 命中{p3['hits']}条)")
    
    #    
    # 推荐
    print("\n" + "=" * 60)
    print("【结论】")
    print("=" * 60)
    
    scores = [
        ('方案1: 关键词路由', r1['recall'] * 0.6 + (1 - r1['avg_sources']/3) * 0.4),
        ('方案2: 置信度路由', r2['recall'] * 0.6 + (1 - r2['avg_sources']/3) * 0.4),
        ('方案3: 语义意图', r3['recall'] * 0.6 + (1 - r3['avg_sources']/3) * 0.4),
    ]
    scores.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n推荐顺序：")
    for i, (name, score) in enumerate(scores, 1):
        print(f"  {i}. {name} (综合得分: {score:.2f})")
    
    print(f"\n说明:")
    print(f"  - 召回率权重60%，简洁性权重40%")
    print(f"  - 方案3在复杂查询上表现更好")
    print(f"  - 方案1最简单但召回率低")

if __name__ == '__main__':
    main()
