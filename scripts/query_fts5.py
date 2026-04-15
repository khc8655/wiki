#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'index_store' / 'fts5_cards.db'
PRODUCT_INDEX_PATH = ROOT / 'index_store' / 'product_index.v1.json'


def load_product_index():
    return json.loads(PRODUCT_INDEX_PATH.read_text(encoding='utf-8'))


def normalize_query(query: str) -> str:
    terms = [t.strip() for t in query.replace('/', ' ').replace('-', ' ').split() if t.strip()]
    if not terms:
        return query
    return ' OR '.join(f'"{t}"' for t in terms)


def parse_query_plan(query: str):
    q = query.lower()
    model_match = re.search(r'\b(ae\d{3}[a-z]?|xe\d{3}[a-z]?|ge\d{3}[a-z]?|tp\d{3}-[a-z]|me\d{2}[a-z]?|nc\d{2}|np\d{2}v?2?)\b', q, re.I)
    feature_terms = ['迭代', '新功能', '升级', '支持', '配置', '入口', 'web', '串口', 'byom', '驱动', '安装']
    product_terms = ['介绍', '简介', '产品', '特点', '组成', '配置清单', '连线', '连接', '是什么']
    plan = {
        'model': None,
        'preferred_doc_prefixes': [],
        'depreferred_doc_prefixes': [],
        'preferred_card_ids': set(),
    }
    if model_match:
        model = model_match.group(1).upper()
        plan['model'] = model
        product_index = load_product_index()
        product_cards = product_index.get(model, [])
        is_feature_query = any(term in q for term in feature_terms)
        is_product_query = (not is_feature_query) or any(term in q for term in product_terms)
        if is_product_query and product_cards:
            plan['preferred_doc_prefixes'] = ['06-']
            plan['depreferred_doc_prefixes'] = ['09-', '10-']
            plan['preferred_card_ids'] = {cid for cid in product_cards if str(cid).startswith('06-')}
        elif is_feature_query:
            plan['preferred_doc_prefixes'] = ['10-', '09-']
    return plan


def score_row(row, plan):
    bonus = 0.0
    doc_file = row['doc_file'] or ''
    card_id = row['card_id'] or ''
    title_blob = f"{row['title'] or ''} {row['path'] or ''}"
    reasons = []

    if card_id in plan['preferred_card_ids']:
        bonus -= 3.0
        reasons.append('preferred_card')
    if any(card_id.startswith(prefix) for prefix in plan['preferred_doc_prefixes']):
        bonus -= 1.5
        reasons.append('preferred_doc')
    if any(card_id.startswith(prefix) for prefix in plan['depreferred_doc_prefixes']):
        bonus += 1.2
        reasons.append('depreferred_doc')
    if plan['model'] and plan['model'] in title_blob.upper():
        bonus -= 0.8
        reasons.append('model_in_title')
    if '产品' in title_blob or '简介' in title_blob or '特点' in title_blob or '组成' in title_blob or '系统连接' in title_blob:
        bonus -= 0.6
        reasons.append('productish_title')

    final_score = float(row['score']) + bonus
    enriched = dict(row)
    enriched['score'] = final_score
    enriched['reasons'] = reasons
    return enriched


def run_query(db_path: Path, query: str, top_k: int):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    match_query = normalize_query(query)
    plan = parse_query_plan(query)
    rows = conn.execute(
        '''SELECT c.card_id, c.title, c.path, c.doc_file, c.body, c.quality_score,
                  bm25(cards_fts, 10.0, 6.0, 4.0, 1.0, 1.0, 4.0, 3.0, 2.0, 2.0, 2.0, 1.0) AS score
           FROM cards_fts
           JOIN cards c ON c.card_id = cards_fts.card_id
           WHERE cards_fts MATCH ?
           LIMIT 100''',
        (match_query,),
    ).fetchall()
    conn.close()
    ranked = [score_row(dict(r), plan) for r in rows]
    ranked.sort(key=lambda x: (x['score'], -(x.get('quality_score') or 0)))
    return ranked[:top_k]


def main():
    parser = argparse.ArgumentParser(description='Query local SQLite FTS5 card index')
    parser.add_argument('query', help='query string')
    parser.add_argument('--db', default=str(DB_PATH), help='sqlite db path')
    parser.add_argument('--top', type=int, default=8, help='top k results')
    parser.add_argument('--brief', action='store_true', help='print concise output')
    args = parser.parse_args()

    results = run_query(Path(args.db), args.query, args.top)
    if args.brief:
        print(f'engine: fts5')
        print(f'query: {args.query}')
        print(f'hits: {len(results)}')
        for i, row in enumerate(results, 1):
            print(f'{i}. {row["title"]} ({row["doc_file"]}) score={row["score"]:.4f}')
        return
    print(json.dumps({'engine': 'fts5', 'query': args.query, 'hits': len(results), 'results': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
