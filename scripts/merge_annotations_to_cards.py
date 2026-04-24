#!/usr/bin/env python3
"""
Deep integration: merge annotation layer into card metadata.

Reads annotation_doc_index.json and writes semantic tags into corresponding
card files under cards/sections/ as native metadata.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / 'index_store' / 'annotation_doc_index.json'
CARDS_DIR = ROOT / 'cards' / 'sections'

# Tag normalization rules
TAG_NORMALIZATION = {
    # Unify hyphen vs underscore
    '-': '_',
    # Common typos or variants
    '公安': 'police',
    '指挥中心': 'command_center',
}


def normalize_tag(tag: str) -> str:
    """Normalize a single tag string."""
    if not isinstance(tag, str):
        return ''
    tag = tag.strip().lower()
    # Replace spaces with underscores
    tag = re.sub(r'\s+', '_', tag)
    # Apply normalization mappings
    for old, new in TAG_NORMALIZATION.items():
        tag = tag.replace(old, new)
    # Remove excessive underscores
    tag = re.sub(r'_+', '_', tag).strip('_')
    return tag


def normalize_tags(tags: list) -> list:
    """Normalize and deduplicate tags."""
    seen = set()
    result = []
    for t in tags:
        nt = normalize_tag(t)
        if nt and nt not in seen and len(nt) >= 2:
            seen.add(nt)
            result.append(nt)
    return result


def load_annotation_index():
    if not INDEX_PATH.exists():
        print(f"[ERROR] {INDEX_PATH} not found")
        return None
    return json.loads(INDEX_PATH.read_text(encoding='utf-8'))


def find_cards_for_doc(doc_stem: str):
    """Find all card files matching this doc stem.
    
    Cards follow pattern: NN-NN-{stem}-sec-XXX.json
    We match by looking for cards containing the stem.
    """
    # Match cards where the stem appears in the filename
    pattern = f"*-*-{doc_stem}-sec-*.json"
    return sorted(CARDS_DIR.glob(pattern))


def merge_tags_to_card(card_path: Path, annotation_entry: dict, dry_run: bool = False):
    """Merge annotation tags into a single card file."""
    try:
        card = json.loads(card_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"  [SKIP] Failed to read {card_path}: {e}")
        return False

    # Prepare semantic metadata
    semantic = {
        'intent_tags': normalize_tags(annotation_entry.get('top_intent_tags', [])),
        'feature_tags': normalize_tags(annotation_entry.get('top_feature_tags', [])),
        'concept_tags': normalize_tags(annotation_entry.get('top_concept_tags', [])),
        'scenario_tags': normalize_tags(annotation_entry.get('top_scenario_tags', [])),
        'doc_types': normalize_tags(annotation_entry.get('top_doc_types', [])),
        'boost_terms': normalize_tags(annotation_entry.get('boost_terms', [])),
        'annotation_model': annotation_entry.get('model'),
        'annotation_paragraph_count': annotation_entry.get('annotation_success_count', 0),
    }

    # Check if semantic layer already exists
    existing = card.get('semantic', {})
    if existing:
        # Merge instead of replace - take union of tags
        for key in ['intent_tags', 'feature_tags', 'concept_tags', 'scenario_tags', 'doc_types', 'boost_terms']:
            existing_set = set(existing.get(key, []))
            new_set = set(semantic.get(key, []))
            merged = sorted(existing_set | new_set)
            semantic[key] = merged

    card['semantic'] = semantic

    if not dry_run:
        card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding='utf-8')

    return True


def main():
    parser = argparse.ArgumentParser(description='Merge annotation layer into card metadata')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    args = parser.parse_args()

    print("=" * 60)
    print("Step 1: Loading annotation index...")
    index_data = load_annotation_index()
    if not index_data:
        return 1

    docs = index_data.get('docs', {})
    print(f"  Found {len(docs)} annotated documents")

    print("=" * 60)
    print("Step 2: Merging tags into cards...")

    stats = {'processed': 0, 'skipped': 0, 'cards_updated': 0}

    for doc_file, entry in docs.items():
        doc_stem = entry.get('doc_stem') or Path(doc_file).stem
        card_files = find_cards_for_doc(doc_stem)

        if not card_files:
            print(f"  [WARN] No cards found for {doc_stem}")
            stats['skipped'] += 1
            continue

        print(f"  {doc_stem}: {len(card_files)} cards")
        stats['processed'] += 1

        for card_path in card_files:
            if merge_tags_to_card(card_path, entry, dry_run=args.dry_run):
                stats['cards_updated'] += 1

    print("=" * 60)
    print("Step 3: Summary")
    print(f"  Documents processed: {stats['processed']}")
    print(f"  Documents skipped: {stats['skipped']}")
    print(f"  Cards updated: {stats['cards_updated']}")
    if args.dry_run:
        print("  [DRY RUN] No files were actually modified")

    return 0


if __name__ == '__main__':
    exit(main())
