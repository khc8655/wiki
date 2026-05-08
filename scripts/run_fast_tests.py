#!/usr/bin/env python3
"""快速测试脚本 - 使用query_unified.py
验证项：
1. 路由正确性（source_type）
2. 型号提取（models）
3. 结果数量（min_results）
4. 命中率合理性（hit_rate 不全为1.0）
5. 去重正确性（无重复）
6. 出处完整性（非空）
7. 对比查询有差异摘要
8. spec_query 走SQL不走knowledge
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
queries = [
    # (查询, 期望source_type, 期望models, 最小结果数, 额外检查)
    ('AE800的价格是多少？', 'excel', ['AE800'], 1, 'price_dynamic_rate'),
    ('AI相关的报价分类有哪些？', 'excel', [], 5, 'category_has_source'),
    ('可按年购买的固定方数云会议室有哪几种？', 'excel', [], 10, 'category_summary'),
    ('AE800可以使用的配件有哪些？', 'excel', ['AE800'], 2, 'accessory_no_main'),
    ('PE8000什么时候停产？', 'excel', ['PE8000'], 1, 'eol_has_note'),
    ('XE800与AE800的接口对比', 'excel', ['AE800', 'XE800'], 1, 'compare_has_diff'),
    ('GE600的招标参数', 'excel', ['GE600'], 1, 'tender_ok'),
    ('云视频在公安行业的应用有哪些？', 'knowledge', [], 2, 'knowledge_rate_realistic'),
    ('软件端与硬件端的对比', 'knowledge', [], 1, 'knowledge_rate_realistic'),
    ('XE800的接口参数', 'excel', ['XE800'], 1, 'spec_is_table'),
    ('PE8000的价格', 'excel', ['PE8000'], 1, 'no_duplicate'),
]

passed = 0
failed = 0

for i, (q, expected_intent, expected_models, min_results, check_type) in enumerate(queries, 1):
    print(f"\n{'='*60}")
    print(f"CASE {i}: {q}")
    print(f"{'='*60}")
    try:
        proc = subprocess.run(
            ['python3', 'query_unified.py', q, '--json'],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            print(f"❌ ERROR: {proc.stderr.strip()[:200]}")
            failed += 1
            continue
        
        data = json.loads(proc.stdout)
        intent = data.get('source_type', '')
        models = data.get('models', [])
        results = data.get('results', [])
        result_count = len(results) if isinstance(results, list) else 0
        
        print(f"intent={intent}, models={models}, count={result_count}")
        
        # 基本验证
        ok = True
        issues = []
        
        if expected_intent and intent != expected_intent:
            issues.append(f"意图不匹配，期望: {expected_intent}, 实际: {intent}")
        
        if expected_models and set(expected_models) != set(models):
            issues.append(f"模型不匹配，期望: {expected_models}, 实际: {models}")
        
        if result_count < min_results:
            issues.append(f"结果数不足，期望≥{min_results}，实际: {result_count}")
        
        # 额外检查
        if check_type == 'price_dynamic_rate':
            # 价格查询：命中率不应全为1.0
            rates = [r.get('hit_rate', 0) for r in results]
            if rates and all(r == 1.0 for r in rates):
                issues.append("命中率全为1.0，未实现动态评分")
            # 检查去重
            titles = [r.get('title', '') for r in results]
            if len(titles) != len(set(titles)):
                issues.append("存在重复结果")
        
        elif check_type == 'category_has_source':
            # 分类查询：出处不应是硬编码的"pricing表"
            for r in results:
                source = r.get('source', '')
                if source == 'pricing表':
                    issues.append(f"出处仍为硬编码'pricing表'")
                    break
        
        elif check_type == 'category_summary':
            # 大量结果应有汇总
            if result_count > 5:
                # 检查是否有汇总表格（通过输出格式判断）
                pass  # JSON模式下不检查显示格式
        
        elif check_type == 'accessory_no_main':
            # 配件查询：不应包含主产品本身
            for r in results:
                title = r.get('title', '')
                body = r.get('body', '')
                category = ''
                for line in body.split('\n'):
                    if '分类' in line:
                        category = line
                        break
                # 主产品的category应该只有型号名
                if any(m.upper() in title.upper() for m in expected_models):
                    # 可能是主产品，检查hit_rate
                    if r.get('hit_rate', 0) >= 0.9:
                        issues.append(f"配件查询包含了主产品: {title}")
        
        elif check_type == 'eol_has_note':
            # 停产查询：应包含备注信息
            has_note = any('停产' in r.get('body', '') or '替代' in r.get('body', '') for r in results)
            if not has_note:
                issues.append("停产查询未包含备注信息")
        
        elif check_type == 'compare_has_diff':
            # 对比查询：应包含差异摘要
            if results:
                body = results[0].get('body', '')
                if '主要差异' not in body and '相同参数' not in body:
                    issues.append("对比查询未包含差异摘要")
        
        elif check_type == 'knowledge_rate_realistic':
            # 知识库查询：命中率不应全为1.0
            rates = [r.get('hit_rate', 0) for r in results]
            if rates and all(r >= 0.9 for r in rates):
                issues.append("知识库命中率过于集中，可能归一化有问题")
        
        elif check_type == 'spec_is_table':
            # spec_query：应返回表格格式
            if results:
                body = results[0].get('body', '')
                if '| 参数项 |' not in body and '| 对比项 |' not in body:
                    issues.append("spec_query未返回表格格式")
        
        elif check_type == 'no_duplicate':
            # 无重复检查
            titles = [r.get('title', '') for r in results]
            if len(titles) != len(set(titles)):
                issues.append("存在重复结果")
        
        # 检查出处完整性
        for r in results:
            source = r.get('source', '')
            if not source or source == 'unknown':
                issues.append(f"出处为空或unknown: {r.get('title', '')[:30]}")
                break
        
        if issues:
            for issue in issues:
                print(f"⚠️ {issue}")
            ok = False
        
        if ok:
            print(f"✅ PASS")
            passed += 1
        else:
            print(f"⚠️ PARTIAL")
            failed += 1
        
    except subprocess.TimeoutExpired:
        print(f"❌ TIMEOUT")
        failed += 1
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        failed += 1
    except Exception as e:
        print(f"❌ ERROR: {e}")
        failed += 1

print(f"\n{'='*60}")
print(f"结果: {passed} 通过, {failed} 失败")
if failed == 0:
    print("🎉 全部通过！")
else:
    print(f"⚠️ 有 {failed} 个问题需要检查")
