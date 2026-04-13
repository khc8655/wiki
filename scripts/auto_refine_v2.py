#!/usr/bin/env python3
"""
V2 自动优化骨架脚本。

目标：
1. 收集高频 query 和低质量 query
2. 产出 refinement 建议
3. 为后续自动补 route / negative concept / topic hint 预留接口
"""

import json
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "updates" / "retrieval_feedback"
OUT_DIR = ROOT / "updates" / "retrieval_feedback"
REPORT = OUT_DIR / "auto_refine_report.v2.json"


def load_events():
    events = []
    if not DATA_DIR.exists():
        return events
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                events.extend(data)
            elif isinstance(data, dict):
                events.append(data)
        except Exception:
            continue
    return events


def classify(events):
    intent_counter = Counter()
    query_counter = Counter()
    low_precision = []
    missing_intent = []
    confusion_pairs = Counter()

    for e in events:
        query = e.get("query", "").strip()
        intent = e.get("intent")
        precision = e.get("precision_percent")
        top_titles = e.get("top_titles", [])
        negative_hits = e.get("negative_hits", [])

        if query:
            query_counter[query] += 1
        if intent:
            intent_counter[intent] += 1
        else:
            missing_intent.append(query)

        if isinstance(precision, (int, float)) and precision < 70:
            low_precision.append({
                "query": query,
                "intent": intent,
                "precision_percent": precision,
                "top_titles": top_titles,
            })

        for item in negative_hits:
            if isinstance(item, str):
                confusion_pairs[item] += 1

    return {
        "intent_counter": intent_counter,
        "query_counter": query_counter,
        "low_precision": low_precision,
        "missing_intent": missing_intent,
        "confusion_pairs": confusion_pairs,
    }


def build_actions(summary):
    actions = []

    for item in summary["low_precision"][:20]:
        actions.append({
            "type": "review-low-precision-query",
            "query": item["query"],
            "intent": item["intent"],
            "precision_percent": item["precision_percent"],
            "suggestion": "检查是否需要新增 high_priority_cards、negative_concepts 或更细 intent",
        })

    for query in summary["missing_intent"][:20]:
        if query:
            actions.append({
                "type": "review-missing-intent",
                "query": query,
                "suggestion": "考虑为该 query 模式新增 parseQuery 规则或 intent schema",
            })

    for pair, count in summary["confusion_pairs"].most_common(20):
        actions.append({
            "type": "review-confusion-pair",
            "pair": pair,
            "count": count,
            "suggestion": "考虑补 negative_concepts 或 confusable_with/excludes 关系",
        })

    return actions


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    events = load_events()
    summary = classify(events)

    report = {
        "event_count": len(events),
        "top_intents": summary["intent_counter"].most_common(20),
        "top_queries": summary["query_counter"].most_common(20),
        "low_precision_count": len(summary["low_precision"]),
        "missing_intent_count": len(summary["missing_intent"]),
        "top_confusion_pairs": summary["confusion_pairs"].most_common(20),
        "actions": build_actions(summary),
        "notes": [
            "该脚本当前只生成自动优化建议，不直接改写索引或 schema。",
            "后续可接入 cron 周期运行，并将 actions 交给 agent 或人工审核。"
        ]
    }

    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"auto refine report written to {REPORT}")


if __name__ == "__main__":
    main()
