#!/usr/bin/env python3
"""
Sync annotation-layer results from WebDAV and build a lightweight doc-level index
for mainline retrieval boosting.

This does not replace raw evidence retrieval. It only adds an annotation-backed
recall layer that can help route and rank candidate docs/cards.
"""

import argparse
import base64
import json
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / 'index_store'
OUT_PATH = INDEX_DIR / 'annotation_doc_index.json'

BASE_URL = 'https://dav.jjb115799.fnos.net'
DEFAULT_REMOTE_ROOT = '/下载/temp/gemma_results/'


def auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f'{user}:{password}'.encode()).decode()
    return f'Basic {token}'


def fetch_json(url: str, headers: dict, ctx) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=120) as r:
        return json.loads(r.read().decode('utf-8'))


def list_remote_jsons(remote_root: str, headers: dict, ctx):
    req = urllib.request.Request(BASE_URL + quote(remote_root), headers=headers, method='PROPFIND')
    with urllib.request.urlopen(req, context=ctx, timeout=120) as r:
        root = ET.fromstring(r.read())
    ns = {'D': 'DAV:'}
    items = []
    for resp in root.findall('D:response', ns):
        href = resp.findtext('D:href', namespaces=ns)
        name = resp.findtext('.//D:displayname', namespaces=ns)
        if not href or not name or not name.endswith('_result.json'):
            continue
        items.append((name, unquote(href)))
    return sorted(items)


def build_doc_entry(data: dict) -> dict:
    filename = data.get('filename') or ''
    stem = data.get('stem') or Path(filename).stem
    results = data.get('results') or []

    tag_counts = {
        'intent_tags': Counter(),
        'feature_tags': Counter(),
        'concept_tags': Counter(),
        'scenario_tags': Counter(),
        'doc_type_hint': Counter(),
    }
    previews = []
    raw_success = 0
    for item in results:
        if not isinstance(item, dict) or item.get('_status') != 'success':
            continue
        raw_success += 1
        for key in ['intent_tags', 'feature_tags', 'concept_tags', 'scenario_tags']:
            for v in item.get(key) or []:
                if isinstance(v, str) and v.strip():
                    tag_counts[key][v.strip()] += 1
        dt = item.get('doc_type_hint')
        if isinstance(dt, str) and dt.strip():
            tag_counts['doc_type_hint'][dt.strip()] += 1
        preview = item.get('_paragraph_preview')
        if isinstance(preview, str) and preview.strip() and len(previews) < 12:
            previews.append(preview.strip())

    top = lambda c, n=20: [k for k, _ in c.most_common(n)]
    boost_terms = []
    for bucket in ['feature_tags', 'concept_tags', 'scenario_tags']:
        boost_terms.extend(top(tag_counts[bucket], 30))
    # de-dup keep order
    seen = set()
    dedup_terms = []
    for term in boost_terms:
        if term in seen:
            continue
        seen.add(term)
        dedup_terms.append(term)

    return {
        'doc_file': filename,
        'doc_stem': stem,
        'model': data.get('model'),
        'paragraph_count': data.get('paragraph_count', 0),
        'success_count': data.get('success_count', 0),
        'empty_count': data.get('empty_count', 0),
        'error_count': data.get('error_count', 0),
        'annotation_success_count': raw_success,
        'top_intent_tags': top(tag_counts['intent_tags'], 10),
        'top_feature_tags': top(tag_counts['feature_tags'], 20),
        'top_concept_tags': top(tag_counts['concept_tags'], 20),
        'top_scenario_tags': top(tag_counts['scenario_tags'], 20),
        'top_doc_types': top(tag_counts['doc_type_hint'], 8),
        'boost_terms': dedup_terms[:60],
        'preview_samples': previews,
    }


def main():
    parser = argparse.ArgumentParser(description='Import annotation results from WebDAV into local annotation index')
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--remote-root', default=DEFAULT_REMOTE_ROOT)
    args = parser.parse_args()

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    headers = {'Authorization': auth_header(args.user, args.password)}
    ctx = ssl.create_default_context()

    docs = {}
    files = list_remote_jsons(args.remote_root, headers, ctx)
    for name, href in files:
        data = fetch_json(BASE_URL + quote(href), headers, ctx)
        entry = build_doc_entry(data)
        docs[entry['doc_file']] = entry

    payload = {
        'remote_root': args.remote_root,
        'doc_count': len(docs),
        'docs': docs,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {OUT_PATH} with {len(docs)} docs')


if __name__ == '__main__':
    main()
