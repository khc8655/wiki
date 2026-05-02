#!/usr/bin/env python3
"""
Card annotator: calls Qwen2.5-7B-Instruct to produce structured semantic tags
for each card (paragraph-level, not doc-level aggregation).

Processes cards one-at-a-time for reliability, but batched into parallel
groups to manage throughput. All tags kept in Chinese.
"""

import json
import time
from typing import List, Dict, Optional

from lib.llm_client import chat, MODELS

ANNOTATION_SYSTEM = """你是技术文档标注助手。为给定的文档段落生成中文语义标签。

严格按此JSON格式输出(不要markdown代码块,不要额外文字):
{"intent":["安全保障"],"concept":["国密SM4"],"scenario":["公安"],"models":["AE700"],"keywords":["端到端加密"]}

规则:
- intent: 从[安全保障,功能更新,部署运维,架构设计,集成对接,场景方案,性能参数,报价价格,利旧兼容,培训赋能,接口硬件]中选1-3个
- concept: 3-8个核心技术概念
- scenario: 适用行业场景,没有就[]
- models: 产品型号如AE700/XE800/ME200/GE600,没有就[]
- keywords: 5-12个关键检索词
- 标签用中文,不要单字条目,不要逗号条目"""


def annotate_one(title: str, path: str, body: str, model: str = None) -> Dict:
    """Annotate a single card."""
    model = model or MODELS["annotator"]
    body_short = body[:800] + ("..." if len(body) > 800 else "")
    user_msg = f"标题: {title}\n路径: {path}\n正文: {body_short}"

    messages = [
        {"role": "system", "content": ANNOTATION_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    raw = chat(messages, model=model, temperature=0.05, max_tokens=800, max_retries=2)
    if not raw:
        return _empty_annotation()

    # Extract JSON - handle various model output quirks
    text = raw.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Find the JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return _empty_annotation()

    json_str = text[start:end+1]

    # Repair common JSON issues
    import re
    json_str = re.sub(r',\s*,+', ',', json_str)          # double commas
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)    # trailing commas
    # Fix missing commas in arrays: "a""b" -> "a","b"
    json_str = re.sub(r'"\s*"(?=[^:,\]}])', '","', json_str)
    # Fix unquoted keys that look like "key:val" or "key: [" -> "key":["
    json_str = re.sub(r'(\w+):\s*\[', r'"\1":[', json_str)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return _empty_annotation()

    return {
        "intent_tags":   _list(data, "intent", "intent_tags"),
        "concept_tags":  _list(data, "concept", "concept_tags"),
        "scenario_tags": _list(data, "scenario", "scenario_tags"),
        "models":        _list(data, "models", "model"),
        "keywords":      _list(data, "keywords", "keyword"),
        "doc_hint":      data.get("doc_hint", data.get("docHint", data.get("doc_hint", "solution"))),
    }


def _list(data: dict, *keys) -> list:
    for k in keys:
        v = data.get(k, [])
        if isinstance(v, list):
            return [x for x in v if isinstance(x, str) and len(x.strip()) > 1 and x.strip() not in (',', '.', 'I', 'i')]
        if isinstance(v, str) and v.strip() and len(v.strip()) > 1 and v.strip() not in (',', '.', 'I', 'i'):
            return [v.strip()]
    return []


def _empty_annotation() -> Dict:
    return {
        "intent_tags": [], "concept_tags": [],
        "scenario_tags": [], "models": [],
        "keywords": [], "doc_hint": "solution"
    }


def annotate_all(cards: List[Dict], batch_size: int = 20, delay: float = 0.3) -> List[Dict]:
    """
    Annotate all cards. One API call per card, with progress.
    """
    all_annotations = []
    total = len(cards)

    for i, card in enumerate(cards):
        if i % batch_size == 0:
            print(f"[Annotator] {i+1}/{total} ...")
        
        ann = annotate_one(
            title=card.get("title", ""),
            path=card.get("path", ""),
            body=card.get("body", ""),
        )
        all_annotations.append(ann)
        time.sleep(delay)

    print(f"[Annotator] Done: {total} cards annotated")
    return all_annotations


if __name__ == "__main__":
    # Quick test
    test_cards = [
        {"title": "安全保障", "path": "系统设计 > 安全", "body": "系统支持SM2/SM3/SM4国密算法，端到端加密，一会一密。TLS1.3+AES256。"},
        {"title": "终端接口", "path": "硬件 > AE700", "body": "AE700: 2路HDMI输入、1路HDMI输出、1路SDI输入、2路XLR音频、1路RJ45千兆网口。"},
    ]
    for c in test_cards:
        ann = annotate_one(c["title"], c["path"], c["body"])
        print(json.dumps(ann, ensure_ascii=False, indent=2))
