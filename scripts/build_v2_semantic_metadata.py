#!/usr/bin/env python3
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "cards" / "sections"
OUT_META = ROOT / "cards" / "card_metadata.v2.json"
INDEX_DIR = ROOT / "index_store"

TOKEN_RE = re.compile(r"[A-Za-z0-9\-\+\.]+|[\u4e00-\u9fff]{2,}")
STOPWORDS = {"支持", "实现", "提供", "通过", "系统", "平台", "视频", "会议", "终端", "功能", "场景", "能力", "相关", "以及", "可以", "当前", "进行", "模块", "服务", "管理"}

RULES = [
    {
        "intent": "cross-cloud-interconnect",
        "must_any": ["跨云", "融合会管", "原MCU", "云视频MCU"],
        "concepts": ["跨云互通", "新旧系统对接", "MCU级联", "统一调度"],
        "negative": ["混合云部署", "跨网安全", "跨域安全", "多运营商接入"],
    },
    {
        "intent": "hybrid-deployment",
        "must_any": ["混合云", "本地部署", "专有云部署", "媒体数据可全部在客户内部网络中完成"],
        "concepts": ["混合云部署", "媒体本地处理", "专有云"],
        "negative": ["跨云互通", "融合会管"],
    },
    {
        "intent": "cross-network-security",
        "must_any": ["跨网", "跨域", "网闸", "光闸", "防火墙"],
        "concepts": ["跨网安全", "跨域安全", "安全互通"],
        "negative": ["跨云互通", "混合云部署"],
    },
]


def tokenize(text: str):
    out = []
    for m in TOKEN_RE.findall(text or ""):
        t = m.strip()
        if len(t) <= 1 or t in STOPWORDS:
            continue
        out.append(t)
    return out


def summarize_title(title: str, path: str):
    joined = " > ".join([p for p in [path, title] if p]).strip(" >")
    return f"本节主要讨论：{joined}" if joined else "本节主要讨论当前 section 的主题边界"


def summarize_body(body: str):
    text = (body or "").replace("\n", " ").strip()
    if not text:
        return ""
    short = text[:90]
    if len(text) > 90:
        short += "..."
    return f"本节主要描述：{short}"


def infer(card):
    joined = " ".join([card.get("title", ""), card.get("path", ""), card.get("body", "")])
    semantic_keywords = tokenize(" ".join([card.get("title", ""), card.get("path", "")]))[:12]
    intent_tags = []
    concept_tags = []
    negative_concepts = []

    for rule in RULES:
        if any(term in joined for term in rule["must_any"]):
            intent_tags.append(rule["intent"])
            concept_tags.extend(rule["concepts"])
            negative_concepts.extend(rule["negative"])

    if not intent_tags:
        if "安全" in joined:
            concept_tags.append("安全")
        if "架构" in joined:
            concept_tags.append("架构")
        if "终端" in joined:
            concept_tags.append("终端")

    related_cards = card.get("sibling_sections", [])[:5]
    quality_score = 0.9 if card.get("char_count", 0) >= 120 else 0.7

    return {
        "title_summary": summarize_title(card.get("title", ""), card.get("path", "")),
        "semantic_summary": summarize_body(card.get("body", "")),
        "semantic_keywords": sorted(set(semantic_keywords)),
        "intent_tags": sorted(set(intent_tags)),
        "concept_tags": sorted(set(concept_tags)),
        "negative_concepts": sorted(set(negative_concepts)),
        "related_cards": related_cards,
        "quality_score": quality_score,
        "version": "v2",
    }


def main():
    metadata = {}
    intent_index = defaultdict(list)
    concept_index = defaultdict(list)
    negative_index = defaultdict(list)

    for path in sorted(CARDS_DIR.glob("*.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        card_id = card["id"]
        meta = infer(card)
        metadata[card_id] = meta

        for intent in meta["intent_tags"]:
            intent_index[intent].append(card_id)
        for concept in meta["concept_tags"]:
            concept_index[concept].append(card_id)
        for concept in meta["negative_concepts"]:
            negative_index[concept].append(card_id)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    OUT_META.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "intent_index.v2.json").write_text(json.dumps(intent_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "concept_index.v2.json").write_text(json.dumps(concept_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "negative_index.v2.json").write_text(json.dumps(negative_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("V2 semantic metadata built")


if __name__ == "__main__":
    main()
