#!/usr/bin/env python3
"""
Offline script: build embeddings for all solution-type cards.
Uses bge-large-zh-v1.5 to generate 1024-dim vectors.

Usage:
    python3 scripts/build_embeddings.py                 # build all
    python3 scripts/build_embeddings.py --limit 100     # test with 100 cards
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.embedder import build_embeddings, save_embeddings


def load_cards(cards_dir: Path) -> list:
    cards = []
    for path in sorted(cards_dir.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
            cards.append(card)
        except Exception as e:
            print(f"[WARN] Failed to load {path.name}: {e}")
    return cards


def main():
    parser = argparse.ArgumentParser(description="Build card embeddings")
    parser.add_argument("--limit", type=int, default=0, help="Limit cards for testing")
    args = parser.parse_args()

    cards_dir = ROOT / "cards" / "sections"
    all_cards = load_cards(cards_dir)
    print(f"Loaded {len(all_cards)} cards")

    # Only embed solution-type cards (not update release notes)
    # Update cards are identified by 'release-note' tag
    cards = [c for c in all_cards if "release-note" not in c.get("tags", [])]
    print(f"Solution-type cards: {len(cards)}")

    if args.limit:
        cards = cards[:args.limit]
        print(f"Limited to {len(cards)} cards")

    if not cards:
        print("No cards to embed.")
        return

    matrix, card_ids = build_embeddings(cards, batch_size=32)
    output_dir = ROOT / "index_store" / "embeddings"
    save_embeddings(matrix, card_ids, output_dir)


if __name__ == "__main__":
    main()
