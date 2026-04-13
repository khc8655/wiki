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
        "must_not": ["混合云", "跨网", "跨域", "网闸", "光闸", "多运营商"],
        "concepts": ["跨云互通", "新旧系统对接", "MCU级联", "统一调度"],
        "negative": ["混合云部署", "跨网安全", "跨域安全", "多运营商接入"],
    },
    {
        "intent": "avc-svc-dual-engine",
        "must_any": ["AVC+SVC", "SVC+AVC", "双引擎架构", "双协议引擎", "AVC和SVC双引擎", "AVC和SVC混合组网"],
        "must_not": ["跨云", "融合会管", "网闸", "光闸"],
        "concepts": ["AVC+SVC双引擎", "兼容利旧", "SVC柔性编码", "AVC兼容互通"],
        "negative": ["跨云互通", "混合云部署", "跨网安全"],
    },
    {
        "intent": "hybrid-deployment",
        "must_any": ["混合云", "本地部署", "专有云部署", "媒体数据可全部在客户内部网络中完成"],
        "must_not": ["跨云互通", "融合会管"],
        "concepts": ["混合云部署", "媒体本地处理", "专有云"],
        "negative": ["跨云互通", "融合会管", "AVC+SVC双引擎"],
    },
    {
        "intent": "cross-network-security",
        "must_any": ["跨网", "跨域", "网闸", "光闸", "防火墙"],
        "must_not": ["跨云互通", "双引擎架构"],
        "concepts": ["跨网安全", "跨域安全", "安全互通"],
        "negative": ["跨云互通", "混合云部署", "AVC+SVC双引擎"],
    },
]

MANUAL_OVERRIDES = {
    "06-新一代视频会议系统建设方案模板-sec-224": {
        "intent_tags": ["cross-cloud-interconnect"],
        "concept_tags": ["跨云互通", "新旧系统对接", "MCU级联", "统一调度", "融合会管"],
        "negative_concepts": ["混合云部署", "跨网安全", "跨域安全", "多运营商接入", "AVC+SVC双引擎"]
    },
    "06-新一代视频会议系统建设方案模板-sec-221": {
        "intent_tags": ["cross-cloud-interconnect", "avc-svc-dual-engine"],
        "concept_tags": ["跨云互通", "新旧系统对接", "MCU级联", "统一调度", "AVC+SVC双引擎", "兼容利旧", "AVC兼容互通"],
        "negative_concepts": ["混合云部署", "跨网安全", "跨域安全", "多运营商接入"]
    },
    "06-新一代视频会议系统建设方案模板-sec-055": {
        "intent_tags": ["avc-svc-dual-engine"],
        "concept_tags": ["AVC+SVC双引擎", "兼容利旧", "SVC柔性编码", "AVC兼容互通"],
        "negative_concepts": ["跨云互通", "混合云部署", "跨网安全"]
    },
    "02-小鱼易连安全稳定白皮书V1-20240829-sec-002": {
        "intent_tags": ["avc-svc-dual-engine"],
        "concept_tags": ["AVC+SVC双引擎", "开放兼容", "兼容利旧"],
        "negative_concepts": ["跨云互通", "混合云部署"]
    },
    "02-小鱼易连安全稳定白皮书V1-20240829-sec-006": {
        "intent_tags": ["avc-svc-dual-engine"],
        "concept_tags": ["AVC+SVC双引擎", "SVC柔性编码", "软件定义架构"],
        "negative_concepts": ["跨云互通", "跨网安全"]
    },
    "06-新一代视频会议系统建设方案模板-sec-201": {
        "intent_tags": ["avc-svc-dual-engine"],
        "concept_tags": ["AVC+SVC双引擎", "兼容利旧", "AVC兼容互通", "MCU级联"],
        "negative_concepts": ["混合云部署", "跨网安全"]
    }
}


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
            if any(term in joined for term in rule.get("must_not", [])):
                continue
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

    override = MANUAL_OVERRIDES.get(card["id"], {})
    intent_tags.extend(override.get("intent_tags", []))
    concept_tags.extend(override.get("concept_tags", []))
    negative_concepts.extend(override.get("negative_concepts", []))

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
