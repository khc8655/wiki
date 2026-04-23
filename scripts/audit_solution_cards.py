#!/usr/bin/env python3
"""
方案类卡片质量巡检脚本

目标：
- 只检查 solution / 方案类文档
- 找出过粗、过空、弱标题、疑似可继续拆分的卡片
- 输出一份可读 JSON 报告，便于入库后快速检查
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / 'cards' / 'sections'
REPORT_PATH = ROOT / 'index_store' / 'solution_card_audit.json'

WEAK_TITLES = {
    '说明', '功能说明', '功能背景', '概述', '介绍', '配置', '参数', '能力',
    '部署方案', '实施方案', '设计方案', '相关要求', '其他', '附录'
}

SPLIT_HINT_PATTERNS = [
    re.compile(r'^\s*[-*•]\s+', re.M),
    re.compile(r'^\s*\d+[\.、\)]\s+', re.M),
    re.compile(r'\n\s*\n'),
]


def is_solution_doc(doc_file: str) -> bool:
    return ('方案' in doc_file) or ('建设' in doc_file) or ('对比' in doc_file) or ('口袋书' in doc_file)


def load_cards():
    for path in sorted(CARDS_DIR.glob('*.json')):
        try:
            card = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        if is_solution_doc(card.get('doc_file', '')):
            yield card


def classify(card: dict):
    title = (card.get('title') or '').strip()
    body = card.get('body') or ''
    char_count = card.get('char_count') or len(body)
    issues = []
    score = 0

    if char_count == 0:
        issues.append('empty_body')
        score += 100
    elif char_count < 40:
        issues.append('too_short')
        score += 35

    if char_count > 1800:
        issues.append('too_long')
        score += 90
    elif char_count > 1200:
        issues.append('long')
        score += 50

    if title in WEAK_TITLES or len(title) <= 2:
        issues.append('weak_title')
        score += 30

    split_hints = 0
    for pat in SPLIT_HINT_PATTERNS:
        split_hints += len(pat.findall(body))
    if char_count > 800 and split_hints >= 6:
        issues.append('split_candidate')
        score += 45
    elif char_count > 500 and split_hints >= 10:
        issues.append('split_candidate')
        score += 35

    if body.count('![](data:image') >= 3 and char_count < 120:
        issues.append('image_heavy_low_text')
        score += 25

    return {
        'id': card.get('id'),
        'doc_file': card.get('doc_file'),
        'title': title,
        'path': card.get('path'),
        'char_count': char_count,
        'issues': issues,
        'priority_score': score,
        'body_preview': body[:240],
    }


def main():
    parser = argparse.ArgumentParser(description='Audit solution cards quality')
    parser.add_argument('--json', action='store_true', help='print full json to stdout')
    parser.add_argument('--top', type=int, default=30, help='top suspicious cards to show')
    args = parser.parse_args()

    cards = list(load_cards())
    findings = [classify(c) for c in cards]
    suspicious = [f for f in findings if f['issues']]
    suspicious.sort(key=lambda x: (-x['priority_score'], -x['char_count'], x['doc_file'], x['id']))

    by_doc = defaultdict(list)
    issue_counter = Counter()
    for item in suspicious:
        by_doc[item['doc_file']].append(item)
        issue_counter.update(item['issues'])

    summary_docs = []
    for doc, items in by_doc.items():
        summary_docs.append({
            'doc_file': doc,
            'flagged_cards': len(items),
            'top_issue_counts': dict(Counter(i for it in items for i in it['issues']).most_common(5)),
            'max_char_count': max(i['char_count'] for i in items),
        })
    summary_docs.sort(key=lambda x: (-x['flagged_cards'], -x['max_char_count'], x['doc_file']))

    report = {
        'summary': {
            'solution_card_count': len(cards),
            'flagged_card_count': len(suspicious),
            'issue_counts': dict(issue_counter.most_common()),
        },
        'top_docs': summary_docs[:20],
        'top_suspicious_cards': suspicious[:args.top],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"solution cards: {len(cards)}")
    print(f"flagged cards: {len(suspicious)}")
    print(f"report: {REPORT_PATH}")
    print("\nissue counts:")
    for k, v in issue_counter.most_common():
        print(f"- {k}: {v}")
    print("\ntop docs:")
    for item in summary_docs[:10]:
        print(f"- {item['doc_file']}: flagged={item['flagged_cards']}, max={item['max_char_count']}, issues={item['top_issue_counts']}")


if __name__ == '__main__':
    main()
