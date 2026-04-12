#!/usr/bin/env python3
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / 'cards' / 'sections'
OUT_DIR = ROOT / 'tree'
META_PATH = ROOT / 'cards' / 'card_metadata.v1.json'

MODEL_RE = re.compile(r'\b(?:AE|ME|GE|NE|TP|CMS|AMS|CRS|NP)\d+(?:/\d+)?(?:-[A-Z])?\b')
SENT_SPLIT = re.compile(r'(?<=[。；!?])')

PLATFORM_HINTS = ['平台', '云视频', '业务管理', '数据服务', 'API服务', '媒体交换', '信令控制', '安全', '稳定', 'AI服务模块', '系统架构', '组网设计', '专有云', '私有云', '公有云']
TERMINAL_HINTS = ['终端选型', '终端简介', '产品组成', '产品特点', '系统连接', '会议平板', '分体式终端', '一体式终端']

PLATFORM_TOPICS = {
    '安全': ['安全', '鉴权', '加密', '存储安全', '传输安全', '权限控制', '一会一密'],
    'AI': ['AI', '人工智能', '人脸识别', '同传字幕', '会议纪要', '数字人', '智能检测', '互动答题'],
    '稳定性': ['稳定', '可靠', '多活', '热备', '负载均衡', '弹性扩容', '高可用'],
    '模块架构': ['模块', '架构', '业务管理', '媒体交换', '信令控制', '数据服务', '预约服务', '智能检测服务'],
    '数据流向': ['数据服务', '调用流程', '时序', '交互', 'REST API', 'AMQ', 'Kafka', 'Processor', 'Service', 'Model', 'DMCU'],
    '开放能力': ['API', 'SDK', '开放', '第三方', 'H323', 'SIP', 'GB/T-28181', 'PSTN'],
}

TERMINAL_TOPICS = {
    '产品型号': ['AE', 'ME', 'GE', 'TP', 'CMS', 'AMS', 'NP'],
    '产品组成': ['产品组成', '配置清单', '组件', '组成'],
    '产品特点': ['产品特点', '能力', '4K30fps', 'AI智能会议'],
    '应用场景': ['应用场景', '适用于', '会议室', '培训', '指挥调度'],
    '系统连接': ['系统连接', '连接示意图', '外接', '电视机', '拼接大屏'],
}


def load_json(path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def infer_l1(card):
    text = ' '.join([card.get('title', ''), card.get('path', ''), card.get('body', '')])
    if any(k in text for k in TERMINAL_HINTS) or MODEL_RE.search(text):
        return '终端'
    if any(k in text for k in PLATFORM_HINTS):
        return '平台'
    return '平台'


def score_topic(text, topic_keywords):
    score = 0
    for kw in topic_keywords:
        if kw in text:
            score += 1
    return score


def infer_l2(card, l1):
    text = ' '.join([card.get('title', ''), card.get('path', ''), card.get('body', '')])
    topics = PLATFORM_TOPICS if l1 == '平台' else TERMINAL_TOPICS
    scored = []
    for topic, kws in topics.items():
        s = score_topic(text, kws)
        if s > 0:
            scored.append((s, topic))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1]
    return '其他'


def infer_l3_title(card, l2):
    path = card.get('path', '')
    title = card.get('title', '')
    if l2 == '产品型号':
        m = MODEL_RE.search(' '.join([title, path, card.get('body', '')]))
        if m:
            return m.group(0)
    if ' > ' in path:
        parts = [p.strip() for p in path.split(' > ') if p.strip()]
        if parts:
            return parts[-1]
    return title or '未命名标题'


def split_paragraphs(body):
    paras = [p.strip() for p in body.split('\n\n') if p.strip()]
    return paras[:12]


def paragraph_score(para, card, l1, l2, l3):
    score = 45.0
    text = para + ' ' + card.get('title', '') + ' ' + card.get('path', '')
    if l3 and l3 in text:
        score += 20
    if l2 != '其他' and l2 in text:
        score += 12
    if l1 in text:
        score += 6
    if MODEL_RE.search(text):
        score += 8
    if len(para) > 80:
        score += 5
    if any(x in para for x in ['支持', '提供', '实现', '包括', '采用']):
        score += 4
    return round(min(score, 98.0), 1)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = load_json(META_PATH) if META_PATH.exists() else {}
    cards = [load_json(p) for p in sorted(CARDS_DIR.glob('*.json'))]

    tree = {'平台': {}, '终端': {}}
    flat_titles = []
    flat_paragraphs = []
    stats = {'cards': 0, 'titles': 0, 'paragraphs': 0}

    for card in cards:
        stats['cards'] += 1
        cid = card['id']
        l1 = infer_l1(card)
        l2 = infer_l2(card, l1)
        l3 = infer_l3_title(card, l2)
        body = card.get('body', '') or ''
        card_type = meta.get(cid, {}).get('card_type', 'capability')

        tree.setdefault(l1, {})
        tree[l1].setdefault(l2, {})
        node = tree[l1][l2].setdefault(l3, {
            'title': l3,
            'cards': [],
            'paragraphs': []
        })
        node['cards'].append({
            'card_id': cid,
            'source_doc': card.get('doc_file', ''),
            'path': card.get('path', ''),
            'title': card.get('title', ''),
            'card_type': card_type,
        })
        stats['titles'] += 1
        flat_titles.append({
            'l1': l1,
            'l2': l2,
            'l3': l3,
            'card_id': cid,
            'source_doc': card.get('doc_file', ''),
            'path': card.get('path', ''),
            'title': card.get('title', ''),
            'card_type': card_type,
        })

        for idx, para in enumerate(split_paragraphs(body), start=1):
            entry = {
                'paragraph_id': f'{cid}#p{idx}',
                'card_id': cid,
                'source_doc': card.get('doc_file', ''),
                'path': card.get('path', ''),
                'title': card.get('title', ''),
                'text': para,
                'match_percent': paragraph_score(para, card, l1, l2, l3),
            }
            node['paragraphs'].append(entry)
            flat_paragraphs.append({
                'l1': l1,
                'l2': l2,
                'l3': l3,
                **entry,
            })
            stats['paragraphs'] += 1

    save_json(OUT_DIR / 'knowledge_tree.v2.json', tree)
    save_json(OUT_DIR / 'title_index.v2.json', flat_titles)
    save_json(OUT_DIR / 'paragraph_index.v2.json', flat_paragraphs)
    save_json(OUT_DIR / 'stats.v2.json', stats)

    readme = '''# Knowledge Tree V2\n\nThis folder contains a 4-layer prototype knowledge tree.\n\n## Layers\n1. L1: 大类（平台 / 终端）\n2. L2: 主题（如安全、AI、稳定性、模块架构、产品组成、系统连接）\n3. L3: 标题索引层\n4. L4: 段落索引层（每段带 match_percent）\n\n## Files\n- `knowledge_tree.v2.json`: nested tree structure\n- `title_index.v2.json`: flat title index\n- `paragraph_index.v2.json`: flat paragraph index with percentages\n- `stats.v2.json`: simple stats\n'''
    (OUT_DIR / 'README.md').write_text(readme, encoding='utf-8')
    print('Knowledge tree V2 written to', OUT_DIR)

if __name__ == '__main__':
    main()
