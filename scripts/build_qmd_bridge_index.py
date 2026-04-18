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
PROFILES_PATH = ROOT / 'qmd_bridge' / 'doc_profiles.json'

HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$', re.M)


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_config():
    return load_json(CONFIG_PATH)


def load_profiles():
    return load_json(PROFILES_PATH)


def clean_text(text: str) -> str:
    text = text.replace('\u0000', ' ')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def get_doc_type(doc_file: str, profiles: dict) -> str | None:
    return (profiles.get('docs', {}).get(doc_file) or {}).get('doc_type')


def normalize_anchor(heading: str, index: int) -> str:
    anchor = heading.lower().strip()
    anchor = re.sub(r'[^\w\-\u4e00-\u9fff]+', '-', anchor).strip('-')
    return f'{anchor or "section"}-{index}'


def parse_markdown_sections(path: Path, chunk_strategy: str):
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

    if chunk_strategy == 'coarse':
        selected = []
        for idx, match in enumerate(matches, start=1):
            level = len(match.group(1))
            if level <= 2:
                selected.append((idx, match))
        if not selected:
            selected = list(enumerate(matches, start=1))
        for pos, (idx, match) in enumerate(selected):
            start = match.start()
            end = selected[pos + 1][1].start() if pos + 1 < len(selected) else len(text)
            heading = match.group(2).strip()
            chunk = text[start:end].strip()
            if not chunk:
                continue
            yield {
                'title': heading,
                'path_hint': path.as_posix(),
                'body': chunk[:20000],
                'anchor': normalize_anchor(heading, idx),
            }
        return

    for idx, match in enumerate(matches, start=1):
        start = match.start()
        end = matches[idx].start() if idx < len(matches) else len(text)
        chunk = text[start:end].strip()
        heading = match.group(2).strip()
        if not chunk:
            continue
        yield {
            'title': heading,
            'path_hint': path.as_posix(),
            'body': chunk[:12000],
            'anchor': normalize_anchor(heading, idx),
        }


def build_docid(collection: str, source_path: str, title: str, anchor: str = '') -> str:
    raw = f'{collection}:{source_path}:{title}:{anchor}'.encode('utf-8')
    return hashlib.sha1(raw).hexdigest()[:8]


def iter_card_docs(collection_name: str, collection_context: str, doc_type: str, profiles: dict):
    cards_dir = ROOT / 'cards' / 'sections'
    meta = load_json(ROOT / 'cards' / 'card_metadata.v2.json')
    for path in sorted(cards_dir.glob('*.json')):
        card = load_json(path)
        card_id = card['id']
        if get_doc_type(card.get('doc_file', ''), profiles) != doc_type:
            continue
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
            'doc_type': doc_type,
            'source_path': path.relative_to(ROOT).as_posix(),
            'title': title,
            'display_path': f"{card.get('doc_file', '')} :: {card.get('path', '')}".strip(' :'),
            'body': body,
            'context': collection_context,
            'source_ref': card_id,
            'anchor': '',
            'rank_hint': 1.0 + float(m.get('quality_score', 0) or 0),
        }


def iter_markdown_collection(collection_name: str, collection_context: str, item: dict, profiles: dict):
    doc_type = item.get('doc_type')
    strategy = profiles.get('defaults', {}).get(doc_type, {}).get('chunk_strategy', 'fine')
    for pattern in item.get('include', []):
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file() or path.suffix.lower() != '.md':
                continue
            if get_doc_type(path.name, profiles) != doc_type:
                continue
            for section in parse_markdown_sections(path, strategy):
                source_path = path.relative_to(ROOT).as_posix()
                yield {
                    'docid': build_docid(collection_name, source_path, section['title'], section['anchor']),
                    'collection': collection_name,
                    'doc_type': doc_type,
                    'source_path': source_path,
                    'title': section['title'],
                    'display_path': source_path,
                    'body': section['body'],
                    'context': collection_context,
                    'source_ref': source_path,
                    'anchor': section['anchor'],
                    'rank_hint': 1.0,
                }


def iter_documents(config, profiles):
    for name, item in config['collections'].items():
        context = item.get('context', '')
        doc_type = item.get('doc_type')
        if name.endswith('_cards'):
            yield from iter_card_docs(name, context, doc_type, profiles)
        else:
            yield from iter_markdown_collection(name, context, item, profiles)


def build(db_path: Path):
    config = load_config()
    profiles = load_profiles()
    rows = list(iter_documents(config, profiles))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('DROP TABLE IF EXISTS docs')
    conn.execute('DROP TABLE IF EXISTS docs_fts')
    conn.execute(
        '''CREATE TABLE docs (
            docid TEXT PRIMARY KEY,
            collection TEXT,
            doc_type TEXT,
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
            doc_type,
            title,
            display_path,
            body,
            context,
            source_ref,
            tokenize = 'unicode61'
        )'''
    )
    conn.executemany(
        'INSERT INTO docs VALUES (:docid,:collection,:doc_type,:source_path,:title,:display_path,:body,:context,:source_ref,:anchor,:rank_hint)',
        rows,
    )
    conn.executemany(
        'INSERT INTO docs_fts VALUES (:docid,:collection,:doc_type,:title,:display_path,:body,:context,:source_ref)',
        rows,
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_docs_collection ON docs(collection)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_docs_doc_type ON docs(doc_type)')
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
    by_type = {}
    for row in rows:
        by_collection[row['collection']] = by_collection.get(row['collection'], 0) + 1
        by_type[row['doc_type']] = by_type.get(row['doc_type'], 0) + 1
    print(json.dumps({'db': args.db, 'docs_indexed': len(rows), 'collections': by_collection, 'doc_types': by_type}, ensure_ascii=False))


if __name__ == '__main__':
    main()
