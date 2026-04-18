#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'index_store' / 'qmd_bridge.db'
CONFIG_PATH = ROOT / 'qmd_bridge' / 'collections.json'

HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$', re.M)


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def clean_text(text: str) -> str:
    text = text.replace('\u0000', ' ')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_markdown_sections(path: Path):
    text = clean_text(path.read_text(encoding='utf-8'))
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        body = text[:12000]
        if body:
            yield {
                'title': path.stem,
                'path_hint': path.as_posix(),
                'body': body,
                'anchor': 'full-document',
            }
        return

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        heading = match.group(2).strip()
        if not chunk:
            continue
        anchor = heading.lower().strip()
        anchor = re.sub(r'[^\w\-\u4e00-\u9fff]+', '-', anchor).strip('-')
        yield {
            'title': heading,
            'path_hint': path.as_posix(),
            'body': chunk[:12000],
            'anchor': f'{anchor}-{idx + 1}',
        }


def build_docid(collection: str, source_path: str, title: str, anchor: str = '') -> str:
    raw = f'{collection}:{source_path}:{title}:{anchor}'.encode('utf-8')
    return hashlib.sha1(raw).hexdigest()[:8]


def iter_card_docs(collection_name: str, collection_context: str):
    cards_dir = ROOT / 'cards' / 'sections'
    meta = json.loads((ROOT / 'cards' / 'card_metadata.v2.json').read_text(encoding='utf-8'))
    for path in sorted(cards_dir.glob('*.json')):
        card = json.loads(path.read_text(encoding='utf-8'))
        card_id = card['id']
        m = meta.get(card_id, {})
        title = card.get('title', '') or card_id
        body_parts = [
            card.get('body', ''),
            m.get('semantic_summary', ''),
            ' '.join(m.get('semantic_keywords', [])),
            ' '.join(m.get('concept_tags', [])),
        ]
        body = clean_text('\n'.join(part for part in body_parts if part))[:12000]
        yield {
            'docid': build_docid(collection_name, path.relative_to(ROOT).as_posix(), title, card_id),
            'collection': collection_name,
            'source_path': path.relative_to(ROOT).as_posix(),
            'title': title,
            'display_path': f"{card.get('doc_file', '')} :: {card.get('path', '')}".strip(' :'),
            'body': body,
            'context': collection_context,
            'source_ref': card_id,
            'anchor': '',
            'rank_hint': 1.0 + float(m.get('quality_score', 0) or 0),
        }


def iter_markdown_collection(collection_name: str, collection_context: str, patterns):
    for pattern in patterns:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file() or path.suffix.lower() != '.md':
                continue
            for section in parse_markdown_sections(path):
                source_path = path.relative_to(ROOT).as_posix()
                yield {
                    'docid': build_docid(collection_name, source_path, section['title'], section['anchor']),
                    'collection': collection_name,
                    'source_path': source_path,
                    'title': section['title'],
                    'display_path': source_path,
                    'body': section['body'],
                    'context': collection_context,
                    'source_ref': source_path,
                    'anchor': section['anchor'],
                    'rank_hint': 1.0,
                }


def iter_documents(config):
    collections = config['collections']
    for name, item in collections.items():
        context = item.get('context', '')
        if name == 'cards':
            yield from iter_card_docs(name, context)
        else:
            yield from iter_markdown_collection(name, context, item.get('include', []))


def build(db_path: Path):
    config = load_config()
    rows = list(iter_documents(config))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('DROP TABLE IF EXISTS docs')
    conn.execute('DROP TABLE IF EXISTS docs_fts')
    conn.execute(
        '''CREATE TABLE docs (
            docid TEXT PRIMARY KEY,
            collection TEXT,
            source_path TEXT,
            title TEXT,
            display_path TEXT,
            body TEXT,
            context TEXT,
            source_ref TEXT,
            anchor TEXT,
            rank_hint REAL
        )'''
    )
    conn.execute(
        '''CREATE VIRTUAL TABLE docs_fts USING fts5(
            docid UNINDEXED,
            collection,
            title,
            display_path,
            body,
            context,
            source_ref,
            tokenize = 'unicode61'
        )'''
    )
    conn.executemany(
        'INSERT INTO docs VALUES (:docid,:collection,:source_path,:title,:display_path,:body,:context,:source_ref,:anchor,:rank_hint)',
        rows,
    )
    conn.executemany(
        'INSERT INTO docs_fts VALUES (:docid,:collection,:title,:display_path,:body,:context,:source_ref)',
        rows,
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_docs_collection ON docs(collection)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_docs_source_path ON docs(source_path)')
    conn.commit()
    conn.close()
    return rows


def main():
    parser = argparse.ArgumentParser(description='Build experimental QMD-style collection index for wiki_test')
    parser.add_argument('--db', default=str(DB_PATH), help='output sqlite db path')
    args = parser.parse_args()
    rows = build(Path(args.db))
    by_collection = {}
    for row in rows:
        by_collection[row['collection']] = by_collection.get(row['collection'], 0) + 1
    print(json.dumps({'db': args.db, 'docs_indexed': len(rows), 'collections': by_collection}, ensure_ascii=False))


if __name__ == '__main__':
    main()
