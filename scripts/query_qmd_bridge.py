#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'index_store' / 'qmd_bridge.db'

COLLECTION_BOOST = {
    'solution_cards': -1.6,
    'solution_topics': -1.0,
    'solution_wiki': -0.6,
    'release_notes': -1.1,
}

DOC_TYPE_BOOST = {
    'solution': -0.3,
    'release_note': -0.2,
}


def normalize_query(query: str) -> str:
    terms = [t.strip() for t in re.split(r'[\s/\-]+', query) if t.strip()]
    if not terms:
        return query
    uniq = []
    seen = set()
    for term in terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(term)
    return ' OR '.join(f'"{t}"' for t in uniq)


def build_snippet(text: str, query: str, width: int = 180) -> str:
    clean = re.sub(r'\s+', ' ', text)
    if not clean:
        return ''
    terms = [t for t in re.split(r'[\s/\-]+', query) if t]
    idx = -1
    for term in terms:
        pos = clean.lower().find(term.lower())
        if pos >= 0:
            idx = pos
            break
    if idx < 0:
        return clean[:width]
    start = max(0, idx - width // 3)
    end = min(len(clean), start + width)
    snippet = clean[start:end]
    if start > 0:
        snippet = '…' + snippet
    if end < len(clean):
        snippet = snippet + '…'
    return snippet


def fallback_search(conn, query: str, collections=None, limit: int = 100):
    terms = [t for t in re.split(r'[\s/\-]+', query) if t]
    sql = '''SELECT docid, collection, doc_type, source_path, title, display_path, body, context, source_ref, anchor, rank_hint
             FROM docs'''
    params = []
    if collections:
        placeholders = ','.join('?' for _ in collections)
        sql += f' WHERE collection IN ({placeholders})'
        params.extend(collections)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    ranked = []
    for row in rows:
        haystack_title = f"{row['title']} {row['display_path']} {row['context']}".lower()
        haystack_body = (row.get('body') or '').lower()
        hit_score = 0.0
        matched = 0
        for term in terms:
            t = term.lower()
            if t in haystack_title:
                hit_score += 6.0
                matched += 1
            elif t in haystack_body:
                hit_score += 2.5
                matched += 1
        if matched == 0:
            continue
        row['score'] = -(hit_score + matched * 0.5)
        ranked.append(row)
    ranked.sort(key=lambda x: x['score'])
    return ranked[:limit]


def run_query(db_path: Path, query: str, top_k: int = 8, collections=None):
    match_query = normalize_query(query)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sql = '''SELECT d.docid, d.collection, d.doc_type, d.source_path, d.title, d.display_path, d.body, d.context,
                    d.source_ref, d.anchor, d.rank_hint,
                    bm25(docs_fts, 1.5, 1.0, 8.0, 5.0, 1.0, 1.0, 1.0) AS score
             FROM docs_fts
             JOIN docs d ON d.docid = docs_fts.docid
             WHERE docs_fts MATCH ?'''
    params = [match_query]
    if collections:
        placeholders = ','.join('?' for _ in collections)
        sql += f' AND d.collection IN ({placeholders})'
        params.extend(collections)
    sql += ' LIMIT 100'
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    if not rows:
        rows = fallback_search(conn, query, collections, 100)
    conn.close()

    ranked = []
    for row in rows:
        bonus = COLLECTION_BOOST.get(row['collection'], 0.0)
        bonus += DOC_TYPE_BOOST.get(row.get('doc_type'), 0.0)
        bonus -= float(row.get('rank_hint') or 0) * 0.08
        row['score'] = float(row['score']) + bonus
        row['snippet'] = build_snippet(row.get('body') or '', query)
        ranked.append(row)

    ranked.sort(key=lambda x: x['score'])
    deduped = []
    seen = set()
    for row in ranked:
        key = (row['collection'], row['display_path'], row['title'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= top_k:
            break
    return deduped


def print_brief(query: str, results, mode: str):
    print('engine: qmd-bridge')
    print(f'mode: {mode}')
    print(f'query: {query}')
    print(f'hits: {len(results)}')
    for idx, row in enumerate(results, 1):
        print(f"{idx}. [{row['collection']}] {row['title']} ({row['display_path']}) score={row['score']:.4f}")
        if row['snippet']:
            print(f"   snippet: {row['snippet']}")


def print_files(results):
    for row in results:
        print(f"{row['docid']},{row['score']:.4f},{row['collection']},{row['display_path']},{row['context']}")


def main():
    parser = argparse.ArgumentParser(description='Query experimental QMD-style bridge index for wiki_test')
    parser.add_argument('query', help='query string')
    parser.add_argument('--db', default=str(DB_PATH), help='sqlite db path')
    parser.add_argument('-c', '--collection', action='append', dest='collections', help='limit to collection, repeatable')
    parser.add_argument('--top', type=int, default=8, help='top k results')
    parser.add_argument('--mode', choices=['evidence', 'synthesis'], default='evidence', help='response mode hint')
    parser.add_argument('--brief', action='store_true', help='print concise output')
    parser.add_argument('--files', action='store_true', help='print file-oriented output')
    parser.add_argument('--json', action='store_true', help='print JSON output')
    args = parser.parse_args()

    results = run_query(Path(args.db), args.query, args.top, args.collections)

    if args.files:
        print_files(results)
        return
    if args.brief:
        print_brief(args.query, results, args.mode)
        return
    print(json.dumps({
        'engine': 'qmd-bridge',
        'mode': args.mode,
        'query': args.query,
        'collections': args.collections or [],
        'hits': len(results),
        'results': results,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
