#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / 'cards' / 'sections'
OUT_DIR = ROOT / 'relations'
INDEX_DIR = ROOT / 'index_store'
META_PATH = ROOT / 'cards' / 'card_metadata.v1.json'

MODEL_RE = re.compile(r'\b(?:AE|ME|GE|NE|TP|CMS|AMS|CRS|NP)\d+(?:/\d+)?(?:-[A-Z])?\b')
LAYER_PATTERNS = [
    ('设备接入层', ['设备接入层']),
    ('网络接入层', ['网络接入层']),
    ('平台服务层', ['平台服务层']),
    ('业务应用层', ['业务应用层']),
]
CAPABILITY_TERMS = [
    '会议纪要','同传字幕','人脸识别','电子铭牌','智能名片','虚拟背景','美颜滤镜','互动答题','签到','问卷',
    '巡检','智能检测','录制','直播','点播','监控接入','H323/SIP融合','PSTN接入','数据服务','会议预约',
    '会议控制','内容共享','无线传屏','双屏输出','4K30fps','语音识别','发言者识别'
]
SCENARIO_TERMS = [
    '中型会议室','大型会议室','小型会议室','国际会议','学术交流','政务会议','培训','直播','应急指挥调度','会前保障',
    '会中互动','隐私场景','创意会议','会议室部署','系统连接'
]
COMPONENT_TERMS = ['终端主机','摄像机','麦克风','无线传屏器','话筒','音响','功放','电视机','触控一体机']
DATAFLOW_TERMS = ['REST API','WebSocket','AMQ','Kafka','HBase','Hive','ElasticSearch','Redis','Mysql','Processor','Service','Model','Pivotor','Buffet','Charge','DMCU']


def load_json(path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def extract_terms(text, terms):
    found = []
    for term in terms:
        if term in text:
            found.append(term)
    return found


def first_sentence(text, limit=120):
    text = re.sub(r'!\[[^\]]*\]\([^\)]*\)', '', text).strip()
    text = re.sub(r'\s+', ' ', text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_json(META_PATH) if META_PATH.exists() else {}

    entities = {}
    relations = []
    concept_index = defaultdict(list)
    card_summaries = []

    product_to_components = defaultdict(set)
    product_to_capabilities = defaultdict(set)
    capability_to_scenarios = defaultdict(set)
    module_to_dataflows = defaultdict(set)
    layer_to_modules = defaultdict(set)

    for card_path in sorted(CARDS_DIR.glob('*.json')):
        card = load_json(card_path)
        cid = card['id']
        body = card.get('body', '') or ''
        title = card.get('title', '') or ''
        path = card.get('path', '') or ''
        full = ' '.join([title, path, body])
        meta = metadata.get(cid, {})

        models = set(meta.get('product_models', [])) | set(MODEL_RE.findall(full))
        capabilities = set(meta.get('capability_tags', [])) | set(extract_terms(full, CAPABILITY_TERMS))
        scenarios = set(meta.get('scenario_tags', [])) | set(extract_terms(full, SCENARIO_TERMS))
        components = set(extract_terms(full, COMPONENT_TERMS))
        dataflows = set(extract_terms(full, DATAFLOW_TERMS))
        layers = [name for name, pats in LAYER_PATTERNS if any(p in full for p in pats)]

        card_summaries.append({
            'card_id': cid,
            'title': title,
            'path': path,
            'summary': first_sentence(body or title),
            'product_models': sorted(models),
            'capabilities': sorted(capabilities),
            'scenarios': sorted(scenarios),
            'components': sorted(components),
            'dataflow_terms': sorted(dataflows),
            'layers': layers,
        })

        for model in models:
            entities.setdefault(model, {'entity_type': 'product_model', 'cards': []})
            entities[model]['cards'].append(cid)
            concept_index[model].append(cid)
            for comp in components:
                product_to_components[model].add(comp)
                relations.append({'type': 'has_component', 'from': model, 'to': comp, 'card_id': cid})
            for cap in capabilities:
                product_to_capabilities[model].add(cap)
                relations.append({'type': 'has_capability', 'from': model, 'to': cap, 'card_id': cid})
            for sc in scenarios:
                relations.append({'type': 'fits_scenario', 'from': model, 'to': sc, 'card_id': cid})

        for cap in capabilities:
            entities.setdefault(cap, {'entity_type': 'capability', 'cards': []})
            entities[cap]['cards'].append(cid)
            concept_index[cap].append(cid)
            for sc in scenarios:
                capability_to_scenarios[cap].add(sc)
                relations.append({'type': 'applies_to_scenario', 'from': cap, 'to': sc, 'card_id': cid})

        module_name = None
        if '模块' in title or '服务子模块' in title or '系统架构' in title:
            module_name = title
            entities.setdefault(module_name, {'entity_type': 'module', 'cards': []})
            entities[module_name]['cards'].append(cid)
            for d in dataflows:
                module_to_dataflows[module_name].add(d)
                relations.append({'type': 'uses_dataflow', 'from': module_name, 'to': d, 'card_id': cid})
            for layer in layers:
                layer_to_modules[layer].add(module_name)
                relations.append({'type': 'belongs_to_layer', 'from': module_name, 'to': layer, 'card_id': cid})

    for name, info in entities.items():
        info['cards'] = sorted(set(info['cards']))

    outputs = {
        'entity_index.v1.json': entities,
        'relation_graph.v1.json': relations,
        'product_to_components.v1.json': {k: sorted(v) for k, v in sorted(product_to_components.items())},
        'product_to_capabilities.v1.json': {k: sorted(v) for k, v in sorted(product_to_capabilities.items())},
        'capability_to_scenarios.v1.json': {k: sorted(v) for k, v in sorted(capability_to_scenarios.items())},
        'module_to_dataflows.v1.json': {k: sorted(v) for k, v in sorted(module_to_dataflows.items())},
        'layer_to_modules.v1.json': {k: sorted(v) for k, v in sorted(layer_to_modules.items())},
        'card_summaries.v1.json': card_summaries,
        'concept_index.v1.json': {k: sorted(set(v)) for k, v in sorted(concept_index.items())},
    }

    for name, data in outputs.items():
        (OUT_DIR / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    readme = '''# Relations Layer (V1)\n\nThis folder stores one-off enriched knowledge artifacts generated from the current corpus.\n\n## Files\n- `entity_index.v1.json`: extracted entities such as product models, capabilities, and modules\n- `relation_graph.v1.json`: flat relation edges with source card ids\n- `product_to_components.v1.json`: product model -> component list\n- `product_to_capabilities.v1.json`: product model -> capability list\n- `capability_to_scenarios.v1.json`: capability -> scenario list\n- `module_to_dataflows.v1.json`: module -> dataflow / interface terms\n- `layer_to_modules.v1.json`: architecture layer -> module list\n- `card_summaries.v1.json`: short per-card semantic summary for quick browse\n- `concept_index.v1.json`: concept -> related cards\n\n## Intended use\nUse these files as the first association layer before deep reading full card bodies.\n'''
    (OUT_DIR / 'README.md').write_text(readme, encoding='utf-8')
    print('Generated relation artifacts in', OUT_DIR)

if __name__ == '__main__':
    main()
