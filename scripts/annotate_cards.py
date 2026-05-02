#!/usr/bin/env python3
"""
Offline script: annotate all cards using Qwen2.5-7B-Instruct.
Writes semantic tags directly into card JSON files under the 'semantic' key.

Usage:
    python3 scripts/annotate_cards.py                    # annotate all cards
    python3 scripts/annotate_cards.py --limit 50         # annotate first 50 cards (testing)
    python3 scripts/annotate_cards.py --doc-type solution  # only solution-type cards
    python3 scripts/annotate_cards.py --dry-run          # preview without writing
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.annotator import annotate_all


def load_cards(cards_dir: Path) -> List[Dict]:
    """Load all card JSONs."""
    cards = []
    for path in sorted(cards_dir.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
            cards.append(card)
        except Exception as e:
            print(f"[WARN] Failed to load {path.name}: {e}")
    return cards


def filter_cards(cards: List[Dict], doc_type: str = None) -> List[Dict]:
    """Filter cards by document type."""
    if not doc_type:
        return cards
    
    result = []
    for c in cards:
        doc_file = c.get("doc_file", "")
        tags = c.get("tags", [])
        # Update docs have 'release-note' tag
        if doc_type == "solution" and "release-note" not in tags:
            result.append(c)
        elif doc_type == "update" and "release-note" in tags:
            result.append(c)
    return result


def main():
    parser = argparse.ArgumentParser(description="Annotate wiki cards using LLM")
    parser.add_argument("--limit", type=int, default=0, help="Limit cards (for testing)")
    parser.add_argument("--doc-type", choices=["solution", "update"], help="Filter by doc type")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--batch-delay", type=float, default=0.3, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    cards_dir = ROOT / "cards" / "sections"
    cards = load_cards(cards_dir)
    print(f"Loaded {len(cards)} cards from {cards_dir}")

    filtered = filter_cards(cards, args.doc_type)
    print(f"After filter: {len(filtered)} cards")

    if args.limit:
        filtered = filtered[:args.limit]
        print(f"Limited to {len(filtered)} cards")

    if not filtered:
        print("No cards to annotate.")
        return

    # Run annotation
    annotations = annotate_all(filtered, batch_size=20)

    # Write back to card files
    updated = 0
    for card, ann in zip(filtered, annotations):
        card["semantic"] = ann
        if not args.dry_run:
            card_path = cards_dir / f"{card['id']}.json"
            card_path.write_text(
                json.dumps(card, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        updated += 1

    if args.dry_run:
        print(f"[DRY RUN] Would update {updated} cards")
        # Show a sample
        if filtered:
            print(f"Sample: {json.dumps(filtered[0].get('semantic', {}), ensure_ascii=False, indent=2)}")
    else:
        print(f"Updated {updated} cards with semantic annotations")


if __name__ == "__main__":
    main()
