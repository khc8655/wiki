#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE_DIR = ROOT / 'tree'
OUT_DIR = TREE_DIR

NOISE_TITLE_PATTERNS = [
    re.compile(r'^!\['),
    re.compile(r'^图\s*$'),
    re.compile(r'^未命名标题$'),
]

TOPIC_RULES_PLATFORM = {
    '安全': ['安全', '鉴权', '加密', '黑名单', '密码', '证书', 'SSL', 'TLS', '存储安全', '传输安全'],
    'AI': ['AI', '人工智能', '人脸识别', '字幕', '纪要', '数字人', '美颜', '虚拟背景', '智能检测', '答题'],
    '数据流向': ['数据服务', '调用流程', '时序', 'REST', 'AMQ', 'Kafka', 'Processor', 'Service', 'Model', 'DMCU', '交互原理', 'WebSocket'],
    '开放能力': ['开放', 'API', 'SDK', '第三方', 'H323', 'SIP', 'PSTN', '28181'],
    '稳定性': ['稳定', '可靠', '多活', '热备', '高可用', '容灾', '负载均衡', '弹性'],
    '模块架构': ['架构', '模块', '微服务', '平台服务层', '业务管理', '媒体交换', '信令控制', '系统架构'],
}

TOPIC_RULES_TERMINAL = {
    '产品组成': ['产品组成', '配置清单', '组成'],
    '系统连接': ['系统连接', '连接示意图', '连接'],
    '应用场景': ['应用场景', '适用于', '部署在', '场景使用', '指挥调度'],
    '产品特点': ['产品特点', '4K', 'AI智能会议', '网络适应', '双屏', '多媒体总线'],
    '产品型号': ['终端简介', '终端选型'],
}


def load_json(path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def is_noise_title(title):
    t = (title or '').strip()
    if not t:
        return True
    return any(p.search(t) for p in NOISE_TITLE_PATTERNS)


def decide_topic(l1, title, path, text):
    rules = TOPIC_RULES_PLATFORM if l1 == '平台' else TOPIC_RULES_TERMINAL
    best_topic = '其他'
    best_score = -1
    joined = ' '.join([title, path, text])
    for topic, kws in rules.items():
        score = sum(1 for kw in kws if kw in joined)
        if score > best_score:
            best_score = score
            best_topic = topic
    return best_topic if best_score > 0 else ('产品型号' if l1 == '终端' else '其他')


def adjust_percent(entry, l2):
    score = float(entry.get('match_percent', 50.0))
    text = entry.get('text', '')
    if l2 == '数据流向' and any(k in text for k in ['REST', 'AMQ', 'Kafka', 'Processor', 'Service', 'Model', 'DMCU']):
        score += 10
    if l2 == '安全' and any(k in text for k in ['加密', '密码', '证书', '鉴权', '黑名单']):
        score += 8
    if l2 == '产品组成' and any(k in text for k in ['终端主机', '摄像机', '麦克风', '无线传屏器']):
        score += 10
    if len(text) < 25:
        score -= 10
    return round(max(5.0, min(score, 99.0)), 1)


def main():
    tree = load_json(TREE_DIR / 'knowledge_tree.v2.json')
    paragraph_index = load_json(TREE_DIR / 'paragraph_index.v2.json')
    title_index = load_json(TREE_DIR / 'title_index.v2.json')

    new_tree = {'平台': {}, '终端': {}}
    new_titles = []
    new_paragraphs = []
    stats = {'titles_before': len(title_index), 'paragraphs_before': len(paragraph_index), 'noise_titles_removed': 0}

    title_lookup = {}
    for item in title_index:
        key = item['card_id']
        title_lookup[key] = item

    for item in title_index:
        title = item.get('title', '')
        if is_noise_title(title):
            stats['noise_titles_removed'] += 1
            continue
        l1 = item['l1']
        l2 = decide_topic(l1, item.get('title', ''), item.get('path', ''), '')
        l3 = item.get('l3') or item.get('title')
        new_tree.setdefault(l1, {})
        new_tree[l1].setdefault(l2, {})
        node = new_tree[l1][l2].setdefault(l3, {'title': l3, 'cards': [], 'paragraphs': []})
        node['cards'].append(item)
        new_item = dict(item)
        new_item['l2'] = l2
        new_titles.append(new_item)

    for para in paragraph_index:
        title_item = title_lookup.get(para['card_id'])
        if not title_item or is_noise_title(title_item.get('title', '')):
            continue
        l1 = para['l1']
        l2 = decide_topic(l1, para.get('title', ''), para.get('path', ''), para.get('text', ''))
        l3 = title_item.get('l3') or para.get('title')
        para2 = dict(para)
        para2['l2'] = l2
        para2['l3'] = l3
        para2['match_percent'] = adjust_percent(para2, l2)
        new_tree.setdefault(l1, {})
        new_tree[l1].setdefault(l2, {})
        new_tree[l1][l2].setdefault(l3, {'title': l3, 'cards': [], 'paragraphs': []})
        new_tree[l1][l2][l3]['paragraphs'].append(para2)
        new_paragraphs.append(para2)

    stats['titles_after'] = len(new_titles)
    stats['paragraphs_after'] = len(new_paragraphs)

    save_json(OUT_DIR / 'knowledge_tree.v2.1.json', new_tree)
    save_json(OUT_DIR / 'title_index.v2.1.json', new_titles)
    save_json(OUT_DIR / 'paragraph_index.v2.1.json', new_paragraphs)
    save_json(OUT_DIR / 'stats.v2.1.json', stats)

    readme = '''# Knowledge Tree V2.1\n\nThis refinement pass improves the V2 tree by:\n- removing noisy/image-like titles\n- reclassifying L2 topics with stronger rules\n- adjusting paragraph percentages based on topic-specific cues\n\n## Files\n- `knowledge_tree.v2.1.json`\n- `title_index.v2.1.json`\n- `paragraph_index.v2.1.json`\n- `stats.v2.1.json`\n''' 
    (OUT_DIR / 'README.v2.1.md').write_text(readme, encoding='utf-8')
    print('Knowledge tree V2.1 written to', OUT_DIR)

if __name__ == '__main__':
    main()
