#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'index_store' / 'fts5_cards.db'


def normalize_query(query: str) -> str:
    terms = [t.strip() for t in query.replace('/', ' ').replace('-', ' ').split() if t.strip()]
    if not terms:
        return query
    return ' OR '.join(f'"{t}"' for t in terms)


def run_query(db_path: Path, query: str, top_k: int):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    match_query = normalize_query(query)
    rows = conn.execute(
        '''SELECT c.card_id, c.title, c.path, c.doc_file, c.body, c.quality_score,
                  bm25(cards_fts, 10.0, 6.0, 4.0, 1.0, 1.0, 4.0, 3.0, 2.0, 2.0, 2.0, 1.0) AS score
           FROM cards_fts
           JOIN cards c ON c.card_id = cards_fts.card_id
           WHERE cards_fts MATCH ?
           ORDER BY score ASC, c.quality_score DESC
           LIMIT ?''',
        (match_query, top_k),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
