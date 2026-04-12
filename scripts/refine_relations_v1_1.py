#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / 'cards' / 'sections'
REL_DIR = ROOT / 'relations'
META_PATH = ROOT / 'cards' / 'card_metadata.v1.json'

MODEL_RE = re.compile(r'\b(?:AE|ME|GE|NE|TP|CMS|AMS|CRS|NP)\d+(?:/\d+)?(?:-[A-Z])?\b')

CORE_COMPONENT_TERMS = ['终端主机', '摄像机', '麦克风', '无线传屏器', '扬声器', '编解码器', '触控屏', 'OPS电脑模块', '壁挂支架', '移动支架', '触控笔']
EXTERNAL_DEVICE_TERMS = ['电视机', '触控一体机', '话筒', '音响', '功放', '拼接大屏', '投影仪', '矩阵']
CAPABILITY_TERMS = [
    '会议纪要','同传字幕','人脸识别','电子铭牌','智能名片','虚拟背景','美颜滤镜','互动答题','签到','问卷',
    '巡检','智能检测','录制','直播','点播','监控接入','H323/SIP融合','PSTN接入','数据服务','会议预约',
    '会议控制','内容共享','无线传屏','双屏输出','4K30fps','4K图像处理','语音识别','发言者识别','网络适应',
    'AI智能会议','多媒体总线','无线投屏'
]
SCENARIO_TERMS = [
    '中型会议室','大型会议室','小型会议室','国际会议','学术交流','政务会议','培训','直播','应急指挥调度','会前保障',
    '会中互动','隐私场景','创意会议','会议室部署','系统连接','会议室','会后归档','正式会议'
]
DATAFLOW_TERMS = ['REST API','WebSocket','AMQ','Kafka','HBase','Hive','ElasticSearch','Redis','Mysql','Processor','Service','Model','Pivotor','Buffet','Charge','DMCU','RM','RS']

CARDTYPE_WEIGHTS = {
    'overview': 0.95,
    'scenario': 0.9,
    'product': 0.88,
    'spec': 0.93,
    'capability': 0.84,
    'operation': 0.8,
    'architecture': 0.78,
    'placeholder': 0.35,
}


def load_json(path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def extract_terms(text, terms):
    return [t for t in terms if t in text]


def confidence(card_type, strength, bonus=0.0):
    base = CARDTYPE_WEIGHTS.get(card_type, 0.7)
    score = base * strength + bonus
    score = max(0.05, min(score, 0.99))
    return round(score * 100, 1)


def typed_component_relations(card, models, card_type):
    text = ' '.join([card.get('title', ''), card.get('path', ''), card.get('body', '')])
    title = card.get('title', '')
    path = card.get('path', '')
    relations = []
    core_terms = extract_terms(text, CORE_COMPONENT_TERMS)
    external_terms = extract_terms(text, EXTERNAL_DEVICE_TERMS)

    is_spec = '产品组成' in path or '配置清单' in card.get('body', '') or card_type == 'spec'
    is_connection = '系统连接' in path or '连接示意图' in card.get('body', '')

    for model in models:
        for term in core_terms:
            rel_type = 'has_component'
            rel_conf = confidence(card_type, 1.0 if is_spec else 0.82, 0.03 if term in title else 0)
            relations.append({'type': rel_type, 'from': model, 'to': term, 'confidence': rel_conf})
        for term in external_terms:
            rel_type = 'external_device' if is_connection else 'deploys_with'
            rel_conf = confidence(card_type, 0.88 if is_connection else 0.68)
            relations.append({'type': rel_type, 'from': model, 'to': term, 'confidence': rel_conf})
    return relations


def main():
    meta = load_json(META_PATH) if META_PATH.exists() else {}
    cards = [load_json(p) for p in sorted(CARDS_DIR.glob('*.json'))]

    typed_relations = []
    product_components = defaultdict(list)
    product_external_devices = defaultdict(list)
    product_capabilities = defaultdict(list)
    capability_scenarios = defaultdict(list)
    module_dataflows = defaultdict(list)
    relation_stats = defaultdict(int)

    for card in cards:
        cid = card['id']
        body = card.get('body', '') or ''
        text = ' '.join([card.get('title', ''), card.get('path', ''), body])
        card_type = meta.get(cid, {}).get('card_type', 'capability')
        models = sorted(set(meta.get(cid, {}).get('product_models', [])) | set(MODEL_RE.findall(text)))
        capabilities = sorted(set(meta.get(cid, {}).get('capability_tags', [])) | set(extract_terms(text, CAPABILITY_TERMS)))
        scenarios = sorted(set(meta.get(cid, {}).get('scenario_tags', [])) | set(extract_terms(text, SCENARIO_TERMS)))
        dataflows = sorted(set(extract_terms(text, DATAFLOW_TERMS)))

        for rel in typed_component_relations(card, models, card_type):
            rel['card_id'] = cid
            typed_relations.append(rel)
            relation_stats[rel['type']] += 1
            if rel['type'] == 'has_component':
                product_components[rel['from']].append({'component': rel['to'], 'confidence': rel['confidence'], 'card_id': cid})
            else:
                product_external_devices[rel['from']].append({'device': rel['to'], 'confidence': rel['confidence'], 'card_id': cid})

        for model in models:
            for cap in capabilities:
                rel = {
                    'type': 'has_capability',
                    'from': model,
                    'to': cap,
                    'confidence': confidence(card_type, 0.9, 0.04 if cap in card.get('title', '') else 0),
                    'card_id': cid,
                }
                typed_relations.append(rel)
                relation_stats[rel['type']] += 1
                product_capabilities[model].append({'capability': cap, 'confidence': rel['confidence'], 'card_id': cid})
            for sc in scenarios:
                rel = {
                    'type': 'fits_scenario',
                    'from': model,
                    'to': sc,
                    'confidence': confidence(card_type, 0.82),
                    'card_id': cid,
                }
                typed_relations.append(rel)
                relation_stats[rel['type']] += 1

        for cap in capabilities:
            for sc in scenarios:
                rel = {
                    'type': 'applies_to_scenario',
                    'from': cap,
                    'to': sc,
                    'confidence': confidence(card_type, 0.86),
                    'card_id': cid,
                }
                typed_relations.append(rel)
                relation_stats[rel['type']] += 1
                capability_scenarios[cap].append({'scenario': sc, 'confidence': rel['confidence'], 'card_id': cid})

        title = card.get('title', '')
        if '模块' in title or '服务子模块' in title or '系统架构' in title:
            for flow in dataflows:
                rel = {
                    'type': 'uses_dataflow',
                    'from': title,
                    'to': flow,
                    'confidence': confidence(card_type, 0.88, 0.03 if flow in title else 0),
                    'card_id': cid,
                }
                typed_relations.append(rel)
                relation_stats[rel['type']] += 1
                module_dataflows[title].append({'term': flow, 'confidence': rel['confidence'], 'card_id': cid})

    def dedupe_entries(items, key_name):
        best = {}
        for item in items:
            k = item[key_name]
            if k not in best or item['confidence'] > best[k]['confidence']:
                best[k] = item
        return sorted(best.values(), key=lambda x: (-x['confidence'], x[key_name]))

    product_components = {k: dedupe_entries(v, 'component') for k, v in sorted(product_components.items())}
    product_external_devices = {k: dedupe_entries(v, 'device') for k, v in sorted(product_external_devices.items())}
    product_capabilities = {k: dedupe_entries(v, 'capability') for k, v in sorted(product_capabilities.items())}
    capability_scenarios = {k: dedupe_entries(v, 'scenario') for k, v in sorted(capability_scenarios.items())}
    module_dataflows = {k: dedupe_entries(v, 'term') for k, v in sorted(module_dataflows.items())}

    typed_relations = sorted(typed_relations, key=lambda x: (-x['confidence'], x['type'], x['from'], x['to']))
    relation_stats = dict(sorted(relation_stats.items()))

    save_json(REL_DIR / 'relation_graph.v1.1.json', typed_relations)
    save_json(REL_DIR / 'product_to_components.v1.1.json', product_components)
    save_json(REL_DIR / 'product_to_external_devices.v1.1.json', product_external_devices)
    save_json(REL_DIR / 'product_to_capabilities.v1.1.json', product_capabilities)
    save_json(REL_DIR / 'capability_to_scenarios.v1.1.json', capability_scenarios)
    save_json(REL_DIR / 'module_to_dataflows.v1.1.json', module_dataflows)
    save_json(REL_DIR / 'relation_stats.v1.1.json', relation_stats)

    readme = '''# Relations Layer (V1.1)\n\nThis refinement pass adds:\n- typed relations\n- per-relation confidence scores\n- cleaner separation between product components and external devices\n- cleaner module -> dataflow mapping\n\n## New files\n- `relation_graph.v1.1.json`\n- `product_to_components.v1.1.json`\n- `product_to_external_devices.v1.1.json`\n- `product_to_capabilities.v1.1.json`\n- `capability_to_scenarios.v1.1.json`\n- `module_to_dataflows.v1.1.json`\n- `relation_stats.v1.1.json`\n''' 
    (REL_DIR / 'README.v1.1.md').write_text(readme, encoding='utf-8')
    print('Refined relation artifacts written to', REL_DIR)

if __name__ == '__main__':
    main()
