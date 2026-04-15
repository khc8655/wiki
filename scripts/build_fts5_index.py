#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / 'cards' / 'sections'
META_PATH = ROOT / 'cards' / 'card_metadata.v2.json'
DB_PATH = ROOT / 'index_store' / 'fts5_cards.db'


def load_meta():
    return json.loads(META_PATH.read_text(encoding='utf-8'))


def iter_cards():
    meta = load_meta()
    for path in sorted(CARDS_DIR.glob('*.json')):
        card = json.loads(path.read_text(encoding='utf-8'))
        m = meta.get(card['id'], {})
        yield {
            'card_id': card['id'],
            'title': card.get('title', ''),
            'path': card.get('path', ''),
            'doc_file': card.get('doc_file', ''),
            'body': card.get('body', ''),
            'tags': ' '.join(card.get('tags', [])),
            'title_summary': m.get('title_summary', ''),
            'semantic_summary': m.get('semantic_summary', ''),
            'semantic_keywords': ' '.join(m.get('semantic_keywords', [])),
            'intent_tags': ' '.join(m.get('intent_tags', [])),
            'concept_tags': ' '.join(m.get('concept_tags', [])),
            'negative_concepts': ' '.join(m.get('negative_concepts', [])),
            'quality_score': float(m.get('quality_score', 0) or 0),
        }


def build(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('DROP TABLE IF EXISTS cards')
    conn.execute('DROP TABLE IF EXISTS cards_fts')
    conn.execute(
        '''CREATE TABLE cards (
            card_id TEXT PRIMARY KEY,
            title TEXT,
            path TEXT,
            doc_file TEXT,
            body TEXT,
            tags TEXT,
            title_summary TEXT,
            semantic_summary TEXT,
            semantic_keywords TEXT,
            intent_tags TEXT,
            concept_tags TEXT,
            negative_concepts TEXT,
            quality_score REAL
        )'''
    )
    conn.execute(
        '''CREATE VIRTUAL TABLE cards_fts USING fts5(
            card_id UNINDEXED,
            title,
            path,
            doc_file,
            body,
            tags,
            title_summary,
            semantic_summary,
            semantic_keywords,
            intent_tags,
            concept_tags,
            negative_concepts,
            tokenize = 'unicode61'
        )'''
    )

    rows = list(iter_cards())
    conn.executemany(
        '''INSERT INTO cards VALUES (
            :card_id,:title,:path,:doc_file,:body,:tags,:title_summary,:semantic_summary,
            :semantic_keywords,:intent_tags,:concept_tags,:negative_concepts,:quality_score
        )''',
        rows,
    )
    conn.executemany(
        '''INSERT INTO cards_fts VALUES (
            :card_id,:title,:path,:doc_file,:body,:tags,:title_summary,:semantic_summary,
            :semantic_keywords,:intent_tags,:concept_tags,:negative_concepts
        )''',
        rows,
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_doc_file ON cards(doc_file)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cards_quality ON cards(quality_score DESC)')
    conn.commit()
    conn.close()
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description='Build local SQLite FTS5 index for cards')
    parser.add_argument('--db', default=str(DB_PATH), help='output sqlite db path')
    args = parser.parse_args()
    count = build(Path(args.db))
    print(json.dumps({'db': args.db, 'cards_indexed': count}, ensure_ascii=False))


if __name__ == '__main__':
    main()
