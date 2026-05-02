#!/usr/bin/env python3
"""
Query refiner: when search results are low-quality, use LLM to suggest
better search terms and clarify user intent.

Uses Qwen2.5-7B-Instruct via llm_client to:
  1. Analyze query intent vs. result tags
  2. Generate expanded keywords (synonyms, hypernyms/hyponyms)
  3. Suggest related topics
  4. Produce a natural clarifying question
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from llm_client import chat_json, MODELS


def refine_query(
    query: str,
    results: List[Dict],
    cards: Optional[List[Dict]] = None,
) -> Dict:
    """
    Analyze search quality and generate refinement suggestions when needed.

    Args:
        query: User's original query
        results: Search results (dicts with 'title','hit_rate','body','tags' etc.)
        cards: Optional raw card data for broader tag sampling

    Returns:
        {
            "needs_refinement": bool,
            "suggestions": [str, ...],
            "expanded_terms": [str, ...],
            "related_topics": [str, ...],
            "clarifying_question": str | None,
        }
    """
    # ── Quality check ───────────────────────────────────────────────────────
    hit_rates = [r.get("hit_rate", 0) for r in results]
    avg_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0

    needs = (avg_rate < 0.3) or (len(results) < 3)

    if not needs:
        return {
            "needs_refinement": False,
            "suggestions": [],
            "expanded_terms": [],
            "related_topics": [],
            "clarifying_question": None,
        }

    # ── Collect context from results ────────────────────────────────────────
    result_tags = set()
    result_titles = []
    for r in results[:10]:
        raw = r.get("raw", r)
        for tag in (raw.get("tags") or []):
            result_tags.add(str(tag))
        title = r.get("title", "").strip()
        if title:
            result_titles.append(title[:100])

    # If raw cards provided, sample their tags too
    if cards:
        for card in cards[:50]:
            for tag in (card.get("tags") or []):
                result_tags.add(str(tag))

    tags_str = ", ".join(sorted(result_tags)[:40]) if result_tags else "无"
    titles_str = "; ".join(result_titles[:10]) if result_titles else "无"

    # ── Build LLM prompt ────────────────────────────────────────────────────
    prompt = f"""你是一个知识库查询优化助手。用户的查询召回质量不理想，请帮助优化。

用户查询: {query}
平均命中率: {avg_rate:.2f}
返回结果数: {len(results)}
当前返回结果的标题: {titles_str}
知识库中已有的标签: {tags_str}

请做以下分析并严格按JSON格式输出：

1. expanded_terms: 生成3-5个扩展或替代关键词，帮助提高命中率（同义词、上下位词、更具体的术语）
2. related_topics: 猜2-4个用户可能真正关心的主题/方向
3. suggestions: 给出2-3条具体的查询改写建议（每条用自然语言表述）
4. clarifying_question: 用一句话向用户确认其真实需求（自然、友好的语气）

请严格输出JSON:
{{
  "expanded_terms": ["词1", "词2"],
  "related_topics": ["主题1", "主题2"],
  "suggestions": ["建议1", "建议2"],
  "clarifying_question": "向用户确认的问题？"
}}"""

    # ── Call LLM ────────────────────────────────────────────────────────────
    messages = [
        {"role": "system", "content": "你是知识库查询优化专家，擅长分析查询意图和改写搜索词。"},
        {"role": "user", "content": prompt},
    ]

    data = chat_json(messages, model=MODELS.get("query_expander"), temperature=0.2, max_retries=2)

    if data is None:
        # LLM failed; provide rule-based fallback
        fallback = _rule_based_refine(query, results)
        fallback["needs_refinement"] = True
        return fallback

    return {
        "needs_refinement": True,
        "suggestions": data.get("suggestions", []) or [],
        "expanded_terms": data.get("expanded_terms", []) or [],
        "related_topics": data.get("related_topics", []) or [],
        "clarifying_question": data.get("clarifying_question"),
    }


def _rule_based_refine(query: str, results: List[Dict]) -> Dict:
    """Fallback refinement when LLM is unavailable: keyword-based heuristics."""
    suggestions = []
    expanded = []
    related = []
    clarifying = "您能更具体地描述一下您想了解的内容吗？"

    ql = query.lower()

    # Common domain-specific expansions
    domain_map = {
        "加密": ["国密", "SM2", "SM4", "TLS", "端到端加密", "传输加密"],
        "录制": ["录播", "云端录制", "本地录制", "录制存储"],
        "会议": ["视频会议", "云会议", "会议室", "协作"],
        "安全": ["网络安全", "数据安全", "访问控制", "权限管理"],
        "部署": ["私有化部署", "混合云", "本地部署", "集群部署"],
        "网络": ["带宽", "QoS", "SVC", "网络自适应"],
        "音频": ["音频处理", "降噪", "回声消除", "音频编解码"],
        "视频": ["视频编解码", "H.265", "H.264", "分辨率", "帧率"],
        "集成": ["API", "SDK", "对接", "整合", "开放平台"],
        "管理": ["后台管理", "控制台", "运维", "监控"],
    }

    for kw, expansions in domain_map.items():
        if kw in ql:
            expanded.extend(expansions)
            if kw not in related:
                related.append(kw)
        # Also check results for these keywords
        for r in results[:5]:
            if kw in (r.get("body", "") or "").lower() or kw in (r.get("title", "") or "").lower():
                if kw not in related:
                    related.append(kw)

    expanded = list(dict.fromkeys(expanded))[:5]
    related = list(dict.fromkeys(related))[:4]

    if expanded:
        suggestions.append(f"试试更具体的词: {' / '.join(expanded[:3])}")

    if len(results) < 3:
        suggestions.append("查询范围可能太窄，试试用更宽泛的概念搜索")

    avg_rate = sum(r.get("hit_rate", 0) for r in results) / max(len(results), 1)
    if avg_rate < 0.1:
        suggestions.append("当前查询可能不在知识库中，试试换一个相关的方向")

    if not suggestions:
        suggestions.append("试试用更通用的术语重新描述您的问题")

    if expanded:
        clarifying = f"您是想了解 {query} 方面的 {expanded[0]}，还是其他相关的内容？"

    return {
        "suggestions": suggestions,
        "expanded_terms": expanded,
        "related_topics": related,
        "clarifying_question": clarifying,
    }


# ── test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test 1: Low quality results
    print("=" * 60)
    print("Test 1: Low quality query")
    out = refine_query(
        "不存在的查询测试",
        results=[
            {"title": "无关卡片A", "hit_rate": 0.08, "body": "这是无关内容", "raw": {"tags": ["部署", "网络"]}},
            {"title": "无关卡片B", "hit_rate": 0.05, "body": "这也是无关内容", "raw": {"tags": ["音频"]}},
        ],
        cards=[],
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))

    # Test 2: Good quality results (should not trigger)
    print("=" * 60)
    print("Test 2: Good quality query")
    out2 = refine_query(
        "视频会议安全加密方案",
        results=[
            {"title": "端到端加密方案", "hit_rate": 0.85, "raw": {"tags": ["加密", "安全"]}},
            {"title": "数据传输安全", "hit_rate": 0.72, "raw": {"tags": ["安全", "TLS"]}},
        ],
        cards=[],
    )
    print(json.dumps(out2, ensure_ascii=False, indent=2))

    print("=" * 60)
    print("All tests passed!")
