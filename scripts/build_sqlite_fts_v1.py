#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE_DIR = ROOT / 'tree'
REL_DIR = ROOT / 'relations'
OUT_DB = ROOT / 'index_store' / 'knowledge_v1.db'


def load_json(path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def main():
    titles = load_json(TREE_DIR / 'title_index.v2.1.json')
    paragraphs = load_json(TREE_DIR / 'paragraph_index.v2.1.json')
    relations = load_json(REL_DIR / 'relation_graph.v1.1.json')

    OUT_DB.parent.mkdir(parents=True, exist_ok=True)
    if OUT_DB.exists():
        OUT_DB.unlink()

    conn = sqlite3.connect(OUT_DB)
    cur = conn.cursor()

    cur.executescript('''
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    PRAGMA temp_store=MEMORY;

    CREATE TABLE titles (
      id INTEGER PRIMARY KEY,
      card_id TEXT,
      l1 TEXT,
      l2 TEXT,
      l3 TEXT,
      title TEXT,
      path TEXT,
      source_doc TEXT,
      card_type TEXT
    );

    CREATE TABLE paragraphs (
      id INTEGER PRIMARY KEY,
      paragraph_id TEXT,
      card_id TEXT,
      l1 TEXT,
      l2 TEXT,
      l3 TEXT,
      title TEXT,
      path TEXT,
      source_doc TEXT,
      text TEXT,
      match_percent REAL
    );

    CREATE TABLE relations (
      id INTEGER PRIMARY KEY,
      rel_type TEXT,
      src TEXT,
      dst TEXT,
      confidence REAL,
      card_id TEXT
    );

    CREATE VIRTUAL TABLE titles_fts USING fts5(
      card_id UNINDEXED,
      l1,
      l2,
      l3,
      title,
      path,
      source_doc,
      card_type,
      content='titles',
      content_rowid='id'
    );

    CREATE VIRTUAL TABLE paragraphs_fts USING fts5(
      paragraph_id UNINDEXED,
      card_id UNINDEXED,
      l1,
      l2,
      l3,
      title,
      path,
      source_doc,
      text,
      content='paragraphs',
      content_rowid='id'
    );

    CREATE VIRTUAL TABLE relations_fts USING fts5(
      rel_type,
      src,
      dst,
      card_id UNINDEXED,
      content='relations',
      content_rowid='id'
    );

    CREATE INDEX idx_titles_card_id ON titles(card_id);
    CREATE INDEX idx_titles_l1_l2 ON titles(l1, l2);
    CREATE INDEX idx_paragraphs_card_id ON paragraphs(card_id);
    CREATE INDEX idx_paragraphs_l1_l2 ON paragraphs(l1, l2);
    CREATE INDEX idx_paragraphs_match ON paragraphs(match_percent DESC);
    CREATE INDEX idx_relations_src ON relations(src);
    CREATE INDEX idx_relations_dst ON relations(dst);
    CREATE INDEX idx_relations_type ON relations(rel_type);
    ''')

    for t in titles:
        cur.execute(
            'INSERT INTO titles(card_id,l1,l2,l3,title,path,source_doc,card_type) VALUES (?,?,?,?,?,?,?,?)',
            (t.get('card_id'), t.get('l1'), t.get('l2'), t.get('l3'), t.get('title'), t.get('path'), t.get('source_doc'), t.get('card_type'))
        )
        rowid = cur.lastrowid
        cur.execute(
            'INSERT INTO titles_fts(rowid,card_id,l1,l2,l3,title,path,source_doc,card_type) VALUES (?,?,?,?,?,?,?,?,?)',
            (rowid, t.get('card_id'), t.get('l1'), t.get('l2'), t.get('l3'), t.get('title'), t.get('path'), t.get('source_doc'), t.get('card_type'))
        )

    for p in paragraphs:
        cur.execute(
            'INSERT INTO paragraphs(paragraph_id,card_id,l1,l2,l3,title,path,source_doc,text,match_percent) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (p.get('paragraph_id'), p.get('card_id'), p.get('l1'), p.get('l2'), p.get('l3'), p.get('title'), p.get('path'), p.get('source_doc'), p.get('text'), p.get('match_percent'))
        )
        rowid = cur.lastrowid
        cur.execute(
            'INSERT INTO paragraphs_fts(rowid,paragraph_id,card_id,l1,l2,l3,title,path,source_doc,text) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (rowid, p.get('paragraph_id'), p.get('card_id'), p.get('l1'), p.get('l2'), p.get('l3'), p.get('title'), p.get('path'), p.get('source_doc'), p.get('text'))
        )

    for r in relations:
        cur.execute(
            'INSERT INTO relations(rel_type,src,dst,confidence,card_id) VALUES (?,?,?,?,?)',
            (r.get('type'), r.get('from'), r.get('to'), r.get('confidence'), r.get('card_id'))
        )
        rowid = cur.lastrowid
        cur.execute(
            'INSERT INTO relations_fts(rowid,rel_type,src,dst,card_id) VALUES (?,?,?,?,?)',
            (rowid, r.get('type'), r.get('from'), r.get('to'), r.get('card_id'))
        )

    conn.commit()

    stats = {
        'db_path': str(OUT_DB),
        'titles': cur.execute('SELECT COUNT(*) FROM titles').fetchone()[0],
        'paragraphs': cur.execute('SELECT COUNT(*) FROM paragraphs').fetchone()[0],
        'relations': cur.execute('SELECT COUNT(*) FROM relations').fetchone()[0],
        'sqlite_version': sqlite3.sqlite_version,
    }
    (ROOT / 'index_store' / 'knowledge_v1.stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    conn.close()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
