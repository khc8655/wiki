#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "cards" / "sections"
INDEX_DIR = ROOT / "index_store"
QUERY_DIR = ROOT / "query_router"
TOPICS_DIR = ROOT / "topics"
META_PATH = ROOT / "cards" / "card_metadata.v1.json"

TOKEN_RE = re.compile(r"[A-Za-z0-9\-\+\.]+|[\u4e00-\u9fff]{2,}")

CARD_OVERRIDES = {
    "06-新一代视频会议系统建设方案模板-sec-089": {
        "card_type": "overview",
        "aliases": ["AI服务", "人工智能服务", "AI应用", "AI场景"],
        "keywords": ["会议纪要", "同传字幕", "人脸识别签到", "电子铭牌", "虚拟背景", "美颜滤镜"],
        "entity_tags": ["AI", "平台能力"],
        "capability_tags": ["会议纪要", "同传字幕", "人脸识别", "虚拟背景", "美颜滤镜"],
        "scenario_tags": ["智能会议", "音视频智能处理"]
    },
    "06-新一代视频会议系统建设方案模板-sec-209": {
        "card_type": "scenario",
        "aliases": ["人脸签到", "电子铭牌", "智能名片"],
        "keywords": ["人脸识别", "签到", "到会统计", "姓名显示", "职级显示"],
        "entity_tags": ["AI", "人脸识别"],
        "capability_tags": ["签到", "人员识别", "电子铭牌"],
        "scenario_tags": ["政务会议", "正式会议"]
    },
    "06-新一代视频会议系统建设方案模板-sec-214": {
        "card_type": "scenario",
        "aliases": ["实时字幕", "双语字幕", "中英互译字幕"],
        "keywords": ["同传字幕", "语音识别", "翻译", "中英文互译"],
        "entity_tags": ["AI", "语音识别"],
        "capability_tags": ["字幕", "翻译"],
        "scenario_tags": ["国际会议", "学术交流"]
    },
    "04-小鱼易连融合云视频平台技术白皮书V1.1-sec-414": {
        "card_type": "scenario",
        "aliases": ["智能会议纪要", "自动纪要", "语音转纪要"],
        "keywords": ["会议纪要", "语音识别", "文档生成"],
        "entity_tags": ["AI", "语音识别"],
        "capability_tags": ["会议纪要"],
        "scenario_tags": ["会后归档", "会议留痕"]
    },
    "04-小鱼易连融合云视频平台技术白皮书V1.1-sec-084": {
        "card_type": "capability",
        "aliases": ["智能巡检", "会前巡检", "终端智能检测"],
        "keywords": ["巡检", "网络状态", "摄像头检测", "麦克风检测", "扬声器检测"],
        "entity_tags": ["运维", "智能检测"],
        "capability_tags": ["巡检", "检测"],
        "scenario_tags": ["会前保障", "运维排障"]
    },
    "04-小鱼易连融合云视频平台技术白皮书V1.1-sec-116": {
        "card_type": "scenario",
        "aliases": ["互动答题", "会议答题", "问卷", "扫码答题"],
        "keywords": ["答题", "签到", "调查问卷", "直播互动", "培训测验"],
        "entity_tags": ["互动", "会控"],
        "capability_tags": ["答题", "问卷", "签到"],
        "scenario_tags": ["培训", "直播", "会中互动"]
    },
    "06-新一代视频会议系统建设方案模板-sec-212": {
        "card_type": "scenario",
        "aliases": ["虚拟形象", "数字人参会"],
        "keywords": ["数字人", "隐私保护", "虚拟参会"],
        "entity_tags": ["AI", "数字人"],
        "capability_tags": ["数字人"],
        "scenario_tags": ["隐私场景", "创意会议"]
    },
    "06-新一代视频会议系统建设方案模板-sec-105": {
        "card_type": "product",
        "aliases": ["AE700", "AE 700", "AE700分体式终端"],
        "keywords": ["中型会议室", "分体式终端"],
        "entity_tags": ["产品", "终端"],
        "product_models": ["AE700"],
        "scenario_tags": ["中型会议室"]
    },
    "06-新一代视频会议系统建设方案模板-sec-106": {
        "card_type": "product",
        "aliases": ["AE700", "AE700简介"],
        "keywords": ["4K30fps", "音视频接口", "拼接大屏", "触控一体机"],
        "entity_tags": ["产品", "终端"],
        "product_models": ["AE700"],
        "capability_tags": ["4K30fps", "多媒体总线"]
    },
    "06-新一代视频会议系统建设方案模板-sec-107": {
        "card_type": "capability",
        "aliases": ["AE700产品特点", "AI智能会议"],
        "keywords": ["人脸识别", "会议签到", "发言者识别", "会议纪要"],
        "entity_tags": ["产品", "AI", "终端"],
        "product_models": ["AE700"],
        "capability_tags": ["AI智能会议", "4K图像处理", "网络适应"]
    },
    "06-新一代视频会议系统建设方案模板-sec-108": {
        "card_type": "spec",
        "aliases": ["AE700组件", "AE700配置", "AE700清单", "AE700包含哪些组件"],
        "keywords": ["终端主机", "摄像机", "麦克风", "无线传屏器"],
        "entity_tags": ["产品", "终端"],
        "product_models": ["AE700"],
        "capability_tags": ["双屏输出", "无线投屏"],
        "scenario_tags": ["中型会议室"]
    },
    "06-新一代视频会议系统建设方案模板-sec-109": {
        "card_type": "operation",
        "aliases": ["AE700连接方式", "AE700连线", "AE700系统连接"],
        "keywords": ["拼接大屏", "电视机", "触控一体机", "话筒", "音响", "功放"],
        "entity_tags": ["产品", "部署"],
        "product_models": ["AE700"],
        "scenario_tags": ["会议室部署", "系统连接"]
    }
}

ROUTES_V1 = {
    "ai": {
        "intent_aliases": ["AI", "人工智能", "AI应用", "AI场景", "智能能力", "智能会议"],
        "subtopics": ["ai-overview", "ai-face-recognition", "ai-caption-minutes", "ai-inspection", "ai-interaction", "ai-digital-human"],
        "priority": 1
    },
    "ai-overview": {
        "intent_aliases": ["AI方面有哪些应用", "AI有哪些应用场景", "人工智能应用", "云视频平台AI能力"],
        "subtopics": ["ai-overview"],
        "priority": 2
    },
    "ai-face-recognition": {
        "intent_aliases": ["人脸识别", "人脸签到", "电子铭牌", "智能名片", "发言者识别"],
        "subtopics": ["ai-face-recognition"],
        "priority": 2
    },
    "ai-caption-minutes": {
        "intent_aliases": ["同传字幕", "实时字幕", "会议纪要", "语音识别", "语音转文字", "自动纪要"],
        "subtopics": ["ai-caption-minutes"],
        "priority": 2
    },
    "ai-inspection": {
        "intent_aliases": ["智能巡检", "会前巡检", "智能检测", "终端检测", "巡检"],
        "subtopics": ["ai-inspection"],
        "priority": 2
    },
    "ai-interaction": {
        "intent_aliases": ["互动答题", "扫码答题", "问卷", "培训答题", "互动签到"],
        "subtopics": ["ai-interaction"],
        "priority": 2
    },
    "ai-digital-human": {
        "intent_aliases": ["数字人", "虚拟人", "数字人参会"],
        "subtopics": ["ai-digital-human"],
        "priority": 2
    },
    "product-ae700": {
        "intent_aliases": ["AE700", "AE 700", "AE700组件", "AE700配置", "AE700包含哪些组件", "AE700连线"],
        "subtopics": ["product-ae700"],
        "priority": 2
    }
}

STOPWORDS = {"支持", "实现", "提供", "通过", "系统", "平台", "视频", "会议", "终端", "功能", "场景", "能力", "相关", "以及", "可以", "当前", "进行", "模块", "服务", "管理"}


def tokenize(text: str):
    tokens = []
    for m in TOKEN_RE.findall(text or ""):
        t = m.strip().lower()
        if len(t) <= 1 or t in STOPWORDS:
            continue
        tokens.append(t)
    return tokens


def merge_unique(*parts):
    seen = set()
    out = []
    for part in parts:
        for item in part or []:
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out


def infer_card_type(card):
    if card.get("body") == "":
        return "placeholder"
    path = card.get("path", "")
    title = card.get("title", "")
    if "产品组成" in path or "配置清单" in card.get("body", ""):
        return "spec"
    if "终端选型" in path or any(x in path for x in ["分体式终端", "会议平板终端"]):
        return "product"
    if any(x in path for x in ["人工智能", "应用场景", "产品特点"]):
        return "scenario"
    if any(x in path for x in ["总体架构", "架构", "模块"]):
        return "architecture"
    if any(x in title for x in ["系统连接", "调用流程"]):
        return "operation"
    return "capability"


def infer_metadata(card):
    card_id = card["id"]
    override = CARD_OVERRIDES.get(card_id, {})
    body = card.get("body", "")
    title = card.get("title", "")
    path = card.get("path", "")

    aliases = list(override.get("aliases", []))
    keywords = list(override.get("keywords", []))
    entity_tags = list(override.get("entity_tags", []))
    product_models = list(override.get("product_models", []))
    capability_tags = list(override.get("capability_tags", []))
    scenario_tags = list(override.get("scenario_tags", []))

    model_matches = re.findall(r"\b(?:AE|ME|GE|NE|TP|CMS|AMS|NP)\d+(?:-[A-Z])?\b", " ".join([title, path, body]))
    product_models = merge_unique(product_models, model_matches)

    if "AI" in title or "人工智能" in path or "人脸识别" in body or "语音识别" in body:
        entity_tags = merge_unique(entity_tags, ["AI"])
    if "终端选型" in path or "终端简介" in path:
        entity_tags = merge_unique(entity_tags, ["产品", "终端"])
    if "会议室" in body or "会议室" in path:
        scenario_tags = merge_unique(scenario_tags, ["会议室"])

    auto_keywords = []
    for src in [title, path]:
        auto_keywords.extend(tokenize(src))
    keywords = merge_unique(keywords, auto_keywords[:12])

    card_type = override.get("card_type") or infer_card_type(card)
    quality_tier = "high" if card.get("char_count", 0) >= 120 and body else "medium"
    if not body:
        quality_tier = "placeholder"

    return {
        "aliases": aliases,
        "keywords": keywords,
        "entity_tags": entity_tags,
        "product_models": product_models,
        "capability_tags": capability_tags,
        "scenario_tags": scenario_tags,
        "card_type": card_type,
        "quality_tier": quality_tier,
    }


def main():
    cards = []
    for path in sorted(CARDS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            cards.append(json.load(f))

    metadata = {}
    keyword_index = defaultdict(list)
    alias_index = defaultdict(list)
    product_index = defaultdict(list)
    topic_index = defaultdict(list)
    scenario_index = defaultdict(list)
    card_type_index = defaultdict(list)

    for card in cards:
        meta = infer_metadata(card)
        metadata[card["id"]] = meta

        for key in merge_unique(card.get("tags", []), meta["entity_tags"], meta["capability_tags"], meta["keywords"]):
            keyword_index[key.lower()].append(card["id"])
        for alias in meta["aliases"]:
            alias_index[alias.lower()].append(card["id"])
        for model in meta["product_models"]:
            product_index[model.upper()].append(card["id"])
        for topic in merge_unique(card.get("tags", []), meta["entity_tags"]):
            topic_index[topic.lower()].append(card["id"])
        for scenario in meta["scenario_tags"]:
            scenario_index[scenario.lower()].append(card["id"])
        card_type_index[meta["card_type"]].append(card["id"])

    def normalize_index(src):
        return {k: sorted(set(v)) for k, v in sorted(src.items())}

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "keyword_index.v1.json").write_text(json.dumps(normalize_index(keyword_index), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "alias_index.v1.json").write_text(json.dumps(normalize_index(alias_index), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "product_index.v1.json").write_text(json.dumps(normalize_index(product_index), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "topic_index.v1.json").write_text(json.dumps(normalize_index(topic_index), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "scenario_index.v1.json").write_text(json.dumps(normalize_index(scenario_index), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (INDEX_DIR / "card_type_index.v1.json").write_text(json.dumps(normalize_index(card_type_index), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    routes_path = QUERY_DIR / "routes.v1.json"
    routes_path.write_text(json.dumps(ROUTES_V1, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ai_topic = """# AI Retrieval Topic (V1)\n\n## Coverage\n- AI 服务总览\n- 人脸识别 / 电子铭牌 / 人脸签到\n- 同传字幕 / 会议纪要 / 语音识别\n- 智能巡检 / 终端智能检测\n- 互动答题 / 问卷 / 签到\n- 数字人 / 虚拟参会\n\n## High-priority cards\n- 06-新一代视频会议系统建设方案模板-sec-089\n- 06-新一代视频会议系统建设方案模板-sec-209\n- 06-新一代视频会议系统建设方案模板-sec-214\n- 04-小鱼易连融合云视频平台技术白皮书V1.1-sec-414\n- 04-小鱼易连融合云视频平台技术白皮书V1.1-sec-084\n- 04-小鱼易连融合云视频平台技术白皮书V1.1-sec-116\n- 06-新一代视频会议系统建设方案模板-sec-212\n\n## Retrieval advice\n1. 先命中 `routes.v1.json` 中的 ai / ai-* 路由。\n2. 再优先读取 `alias_index.v1.json`、`keyword_index.v1.json`。\n3. 候选卡以 overview / scenario / capability 优先，architecture 次之。\n"""
    (TOPICS_DIR / "ai-retrieval-v1.md").write_text(ai_topic, encoding="utf-8")

    ae700_topic = """# AE700 Retrieval Topic (V1)\n\n## Coverage\n- AE700 产品简介\n- AE700 产品特点\n- AE700 产品组成\n- AE700 系统连接\n\n## High-priority cards\n- 06-新一代视频会议系统建设方案模板-sec-105\n- 06-新一代视频会议系统建设方案模板-sec-106\n- 06-新一代视频会议系统建设方案模板-sec-107\n- 06-新一代视频会议系统建设方案模板-sec-108\n- 06-新一代视频会议系统建设方案模板-sec-109\n\n## Retrieval advice\n1. 对型号类问题优先查 `product_index.v1.json`。\n2. “包含哪些组件/配置清单/组件”优先命中 sec-108。\n3. “怎么连接/连线方式”优先命中 sec-109。\n"""
    (TOPICS_DIR / "product-ae700-v1.md").write_text(ae700_topic, encoding="utf-8")

    print("V1 indexes built:")
    for name in [
        META_PATH,
        INDEX_DIR / "keyword_index.v1.json",
        INDEX_DIR / "alias_index.v1.json",
        INDEX_DIR / "product_index.v1.json",
        INDEX_DIR / "topic_index.v1.json",
        INDEX_DIR / "scenario_index.v1.json",
        INDEX_DIR / "card_type_index.v1.json",
        routes_path,
        TOPICS_DIR / "ai-retrieval-v1.md",
        TOPICS_DIR / "product-ae700-v1.md",
    ]:
        print(name.relative_to(ROOT))


if __name__ == "__main__":
    main()
