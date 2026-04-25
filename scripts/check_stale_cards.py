#!/usr/bin/env python3
"""
Check for stale cards by comparing content hash.
Ensures routing consistency when raw documents are updated.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple


def compute_content_hash(text: str) -> str:
    """Compute MD5 hash of content (first 8 chars for readability)."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]


def load_card_metadata(cards_dir: Path) -> Dict[str, Dict]:
    """Load all card metadata."""
    metadata_path = cards_dir.parent / 'card_metadata.v2.json'
    if metadata_path.exists():
        return json.loads(metadata_path.read_text(encoding='utf-8'))
    return {}


def check_stale_cards(cards_dir: Path, dry_run: bool = True) -> List[Tuple[str, str, str, str]]:
    """
    Check which cards need re-annotation.
    
    Returns:
        List of (card_id, old_hash, new_hash, status) tuples
    """
    metadata = load_card_metadata(cards_dir)
    stale_cards = []
    
    for card_file in cards_dir.glob('*.json'):
        try:
            card = json.loads(card_file.read_text(encoding='utf-8'))
            card_id = card.get('id', card_file.stem)
            
            # Compute current hash from body
            body = card.get('body', '')
            current_hash = compute_content_hash(body)
            
            # Get stored hash from metadata
            meta = metadata.get(card_id, {})
            stored_hash = meta.get('content_hash', '')
            
            if not stored_hash:
                # Never annotated
                stale_cards.append((card_id, 'N/A', current_hash, 'NEVER_ANNOTATED'))
            elif stored_hash != current_hash:
                # Content changed
                stale_cards.append((card_id, stored_hash, current_hash, 'STALE'))
            else:
                # No change
                stale_cards.append((card_id, stored_hash, current_hash, 'OK'))
                
        except Exception as e:
            stale_cards.append((card_file.stem, 'ERROR', str(e), 'ERROR'))
    
    return stale_cards


def update_hashes(cards_dir: Path) -> int:
    """Update content_hash in card_metadata.v2.json for all cards."""
    metadata_path = cards_dir.parent / 'card_metadata.v2.json'
    metadata = load_card_metadata(cards_dir)
    updated = 0
    
    for card_file in cards_dir.glob('*.json'):
        try:
            card = json.loads(card_file.read_text(encoding='utf-8'))
            card_id = card.get('id', card_file.stem)
            
            body = card.get('body', '')
            current_hash = compute_content_hash(body)
            
            if card_id not in metadata:
                metadata[card_id] = {}
            
            metadata[card_id]['content_hash'] = current_hash
            metadata[card_id]['version'] = 'v2.1'  # Track format version
            updated += 1
            
        except Exception as e:
            print(f"[ERROR] {card_file.name}: {e}")
    
    # Save back
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return updated


def main():
    parser = argparse.ArgumentParser(description='Check and update card content hashes')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Only check, do not update (default)')
    parser.add_argument('--update', action='store_true',
                        help='Update hashes in metadata')
    parser.add_argument('--cards-dir', type=str, default=None,
                        help='Path to cards/sections directory')
    
    args = parser.parse_args()
    
    if args.cards_dir:
        cards_dir = Path(args.cards_dir)
    else:
        cards_dir = Path(__file__).resolve().parents[1] / 'cards' / 'sections'
    
    print(f"Checking cards in: {cards_dir}")
    print("=" * 60)
    
    if args.update:
        # Update mode
        count = update_hashes(cards_dir)
        print(f"[DONE] Updated {count} card hashes in metadata")
        return
    
    # Check mode (default)
    stale_cards = check_stale_cards(cards_dir, dry_run=True)
    
    stale_count = 0
    never_count = 0
    ok_count = 0
    
    for card_id, old_hash, new_hash, status in sorted(stale_cards):
        if status == 'STALE':
            print(f"[STALE] {card_id}: hash changed ({old_hash} → {new_hash})")
            stale_count += 1
        elif status == 'NEVER_ANNOTATED':
            print(f"[NEW] {card_id}: never annotated (hash: {new_hash})")
            never_count += 1
        elif status == 'OK':
            ok_count += 1
    
    print("=" * 60)
    print(f"Summary: {stale_count} stale, {never_count} new, {ok_count} OK")
    
    if stale_count > 0:
        print(f"\n[SUGGESTION] Run annotation pipeline for {stale_count} stale cards")
        print("Estimated time: ~{}s".format(stale_count * 2))


if __name__ == '__main__':
    main()
