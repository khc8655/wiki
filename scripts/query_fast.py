#!/usr/bin/env python3
"""
Fast query entry for wiki_test.
Focuses on high-frequency business queries over Excel knowledge sources,
with graceful fallback to local retrieval for knowledge-card queries.
"""

import argparse
import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
EXCEL_STORE = ROOT / 'excel_store'

MODEL_RE = re.compile(r'(AE\d{3}[A-Z]?|XE\d{3}[A-Z]?|GE\d{3}[A-Z]?|PE\d{4}|TP\d{3}(?:-[A-Z])?|MX\d{2}|AC\d{2}|NC\d{2}|NP\d{2}(?:V?\d+)?)', re.I)

PRICE_KWS = ['价格', '报价', '多少钱', '费用']
PROPOSAL_KWS = ['招标', '投标', '参数', '规格', '配置']
COMPARE_KWS = ['对比', '比较', '区别', '差异', 'vs', '接口对比']
ACCESSORY_KWS = ['配件', '附件', '可用配件', '可使用的配件']
EOL_KWS = ['停产', '替代', '退市']


def normalize(text: str) -> str:
    text = (text or '').strip().lower()
    text = text.replace('\n', '').replace('\r', '').replace('\t', '')
    text = re.sub(r'\s+', '', text)
    text = text.replace('（', '(').replace('）', ')')
    return text


def extract_models(query: str) -> List[str]:
    return sorted({m.upper() for m in MODEL_RE.findall(query)})


@lru_cache(maxsize=8)
def load_records(dtype: str) -> List[Dict]:
    return json.loads((EXCEL_STORE / dtype / 'records.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=8)
def load_indexes(dtype: str) -> Dict:
    return json.loads((EXCEL_STORE / dtype / 'indexes.json').read_text(encoding='utf-8'))


def score_model_record(record: Dict, model: str) -> int:
    score = 0
    blob = normalize(json.dumps(record, ensure_ascii=False))
    model_n = normalize(model)
    product_model = normalize(record.get('product_model', ''))
    product_name = normalize(record.get('product_name', ''))
    category = normalize(record.get('category', ''))
    note = normalize(record.get('note', ''))
    desc = normalize(record.get('description', ''))

    if model_n and model_n == product_model.replace('小鱼易连', ''):
        score += 130
    if model_n and model_n in product_model:
        score += 120
    if model_n and model_n in product_name:
        score += 100
    if model_n and model_n in category:
        score += 85
    if model_n and model_n in note:
        score += 40
    if model_n and model_n in desc:
        score += 35
    if model_n and model_n in blob:
        score += 20
    return score


def direct_model_lookup(dtype: str, model: str) -> List[Dict]:
    recs = load_records(dtype)
    scored = []
    for r in recs:
        s = score_model_record(r, model)
        if s > 0:
            rr = dict(r)
            rr['_score'] = s
            scored.append(rr)
    scored.sort(key=lambda x: (-x['_score'], x.get('source_row', 0)))
    return scored


def pricing_price_lookup(model: str) -> List[Dict]:
    recs = direct_model_lookup('pricing', model)
    strict = []
    model_n = normalize(model)
    for r in recs:
        if not (r.get('is_pricing_record') and str(r.get('price_raw', '')).strip()):
            continue
        name = normalize(r.get('product_name', ''))
        category = normalize(r.get('category', ''))
        if model_n in name or model_n in category:
            strict.append(r)
    return strict or recs[:3]


def proposal_lookup(model: str) -> List[Dict]:
    return direct_model_lookup('proposal', model)


def comparison_lookup(model: str) -> List[Dict]:
    idx = load_indexes('comparison')
    rows = idx.get('by_model', {}).get(model.upper(), [])
    if rows:
        return rows
    recs = load_records('comparison')
    return [r for r in recs if normalize(r.get('model', '')) == normalize(model)]


def search_pricing_text(query: str, top_k: int = 20) -> List[Dict]:
    qn = normalize(query)
    recs = load_records('pricing')
    scored = []
    for r in recs:
        score = 0
        name = normalize(r.get('product_name', ''))
        category = normalize(r.get('category', ''))
        desc = normalize(r.get('description', ''))
        note = normalize(r.get('note', ''))
        if qn in name:
            score += 120
        if qn in category:
            score += 80
        if qn in desc:
            score += 40
        if qn in note:
            score += 30
        for token in [t for t in re.split(r'[\s/]+', query) if t.strip()]:
            tn = normalize(token)
            if len(tn) < 2:
                continue
            if tn in name:
                score += 18
            if tn in category:
                score += 14
            if tn in desc:
                score += 8
            if tn in note:
                score += 6
        if score > 0:
            rr = dict(r)
            rr['_score'] = score
            scored.append(rr)
    scored.sort(key=lambda x: (-x['_score'], x.get('source_row', 0)))
    return scored[:top_k]


def ai_pricing_lookup() -> List[Dict]:
    wanted_terms = [
        'ai语音转写', '语音转写引擎', '三方语音转写引擎', '大模型对接',
        '接入授权', '智能体', '人脸识别'
    ]
    recs = load_records('pricing')
    ranked = []
    for r in recs:
        name = r.get('product_name') or ''
        cat = r.get('category') or ''
        blob = f"{name}\n{cat}\n{r.get('description','')}\n{r.get('note','')}"
        blob_n = normalize(blob)
        score = 0
        if 'ai' in blob.lower():
            score += 40
        for term in wanted_terms:
            if normalize(term) in blob_n:
                score += 40
        if '语音转写' in blob:
            score += 60
        if '大模型' in blob:
            score += 60
        if '人脸识别' in blob:
            score += 60
        if '接入授权' in blob:
            score += 50
        if score >= 60:
            rr = dict(r)
            rr['_score'] = score
            ranked.append(rr)
    ranked.sort(key=lambda x: (-x['_score'], x.get('source_row', 0)))

    exact_allow = ['语音转写', '大模型', '人脸识别', '智能体']
    result = []
    seen = set()
    for r in ranked:
        name = r.get('product_name') or ''
        key = normalize(name)
        if not any(k in name for k in exact_allow):
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(r)
    preferred = ['本地AI语音转写', '语音引擎对接', '大模型对接', '小鱼易连智能体会议室授权许可软件', '小鱼易连智能体专有会议室授权许可软件', '本地AI人脸识别']
    ordered = []
    for p in preferred:
        for r in result:
            if p in (r.get('product_name') or ''):
                ordered.append(r)
                break
    return ordered or result


def yearly_room_lookup() -> List[Dict]:
    recs = load_records('pricing')
    out = []
    seen = set()
    for r in recs:
        name = r.get('product_name', '')
        if (('会议室模式-多方云会议服务' in name or '云会议室服务费（大规模会议' in name) and '/年' in name):
            key = normalize(name)
            if key in seen:
                continue
            seen.add(key)
            rr = dict(r)
            rr['_score'] = 100 if '会议室模式-多方云会议服务' in name else 90
            out.append(rr)
    out.sort(key=lambda x: (-x['_score'], x.get('source_row', 0)))
    return out


def accessory_lookup(model: str) -> List[Dict]:
    recs = load_records('pricing')
    out = []
    mn = model.upper()
    for r in recs:
        blob = f"{r.get('product_name','')}\n{r.get('category','')}\n{r.get('description','')}\n{r.get('note','')}"
        score = 0
        if mn in blob.upper():
            score += 80
        if any(x in blob for x in ['摄像头', '麦克风', '传屏', '触控屏', '遥控器', '支架', '投屏器']):
            score += 30
        if score > 0 and (r.get('product_name') not in [model, f'小鱼易连{model}套装']):
            rr = dict(r)
            rr['_score'] = score
            out.append(rr)
    out.sort(key=lambda x: (-x['_score'], x.get('source_row', 0)))
    # de-dup
    seen = set()
    result = []
    for r in out:
        name = r.get('product_name') or r.get('id')
        if name in seen:
            continue
        seen.add(name)
        result.append(r)
    return result[:15]


def route_query(query: str) -> Tuple[str, Dict]:
    models = extract_models(query)
    q = query.lower()
    info = {'models': models}
    if models and any(k in q for k in EOL_KWS):
        return 'eol', info
    if models and any(k in q for k in PRICE_KWS):
        return 'price', info
    if 'ai' in q and ('报价' in q or '分类' in q):
        return 'ai_pricing', info
    if '会议室模式-多方云会议服务' in query or ('按年' in query and '会议室' in query and '方' in query):
        return 'yearly_room', info
    if models and any(k in q for k in ACCESSORY_KWS):
        return 'accessory', info
    if len(models) >= 2 and any(k in q for k in COMPARE_KWS):
        return 'compare', info
    if models and any(k in q for k in PROPOSAL_KWS):
        return 'proposal', info
    if models and ('简单参数' in q or '招标参数' in q):
        return 'proposal', info
    if '公安' in query or ('软件端' in query and '硬件端' in query):
        return 'knowledge', info
    return 'generic', info


def search_cards_keywords(query: str, limit: int = 12) -> List[Dict]:
    cards_dir = ROOT / 'cards' / 'sections'
    q = query
    required = []
    if '公安' in q:
        required = ['公安']
    elif '软件端' in q and '硬件端' in q:
        required = ['软件', '硬件']
    terms = [t for t in re.findall(r'[A-Za-z0-9\-\+\.]+|[\u4e00-\u9fff]{2,}', q) if len(t) >= 2]
    results = []
    for path in cards_dir.glob('*.json'):
        try:
            card = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        blob = f"{card.get('title','')}\n{card.get('path','')}\n{card.get('body','')}\n{card.get('doc_file','')}"
        score = 0
        if required and not all(r in blob for r in required):
            continue
        for term in terms:
            if term in blob:
                score += 15
        if '公安' in q and '公安' in card.get('doc_file', ''):
            score += 80
        if '公安' in q and '应用场景' in card.get('path', ''):
            score += 60
        if '软件端' in q and any(x in blob for x in ['软件客户端', 'PC客户端', '手机客户端']):
            score += 50
        if '硬件端' in q and any(x in blob for x in ['硬件终端', '会议室终端', '一体化终端']):
            score += 50
        if score > 0:
            results.append({
                'id': card.get('id'),
                'title': card.get('title'),
                'path': card.get('path'),
                'doc_file': card.get('doc_file'),
                'body_preview': (card.get('body', '')[:240] + '...') if len(card.get('body', '')) > 240 else card.get('body', ''),
                '_score': score,
            })
    results.sort(key=lambda x: (-x['_score'], x.get('doc_file', ''), x.get('title', '')))
    return results[:limit]


def run_knowledge_fallback(query: str) -> Dict:
    keyword_hits = search_cards_keywords(query)
    if keyword_hits:
        return {'engine': 'card_scan', 'hits': keyword_hits}
    cmd = ['node', 'scripts/retrieve_v1.js', query]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    if proc.returncode == 0:
        try:
            parsed = json.loads(proc.stdout)
            if parsed.get('summary', {}).get('candidate_count', 0) > 0:
                return {'engine': 'retrieve_v1', 'raw': parsed}
        except Exception:
            pass
    cmd = ['python3', 'scripts/query_fts5.py', query, '--brief']
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    return {'engine': 'fts5', 'raw': proc.stdout or proc.stderr}


def main():
    parser = argparse.ArgumentParser(description='Fast query for wiki_test')
    parser.add_argument('query', help='query text')
    parser.add_argument('--json', action='store_true', help='json output')
    args = parser.parse_args()

    query = args.query.strip()
    intent, info = route_query(query)
    models = info.get('models', [])
    result = {'query': query, 'intent': intent, 'models': models}

    if intent == 'price' and models:
        recs = pricing_price_lookup(models[0])
        result['results'] = recs[:5]
    elif intent == 'eol' and models:
        result['results'] = pricing_price_lookup(models[0])[:5]
    elif intent == 'proposal' and models:
        result['results'] = proposal_lookup(models[0])[:5]
    elif intent == 'compare' and len(models) >= 2:
        result['results'] = {m: comparison_lookup(m) for m in models}
        # Optional proposal comparison supplement
        result['proposal_supplement'] = {m: proposal_lookup(m)[:2] for m in models}
    elif intent == 'accessory' and models:
        result['results'] = accessory_lookup(models[0])
    elif intent == 'ai_pricing':
        result['results'] = ai_pricing_lookup()
    elif intent == 'yearly_room':
        result['results'] = yearly_room_lookup()
    elif intent == 'knowledge':
        result['results'] = run_knowledge_fallback(query)
    else:
        result['results'] = search_pricing_text(query)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"intent: {intent}")
    if models:
        print(f"models: {', '.join(models)}")
    print(json.dumps(result.get('results'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
