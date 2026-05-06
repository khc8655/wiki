#!/usr/bin/env python3
"""
Offline script: annotate all cards using Qwen3-8B (thinking disabled).
Writes semantic tags directly into card JSON files under the 'semantic' key.

Usage:
    python3 scripts/annotate_cards.py                    # annotate all (resume from checkpoint)
    python3 scripts/annotate_cards.py --limit 50         # annotate first 50 cards (testing)
    python3 scripts/annotate_cards.py --doc-type solution # only solution-type cards
    python3 scripts/annotate_cards.py --dry-run          # preview without writing
    python3 scripts/annotate_cards.py --restart           # start from beginning (ignore checkpoint)
"""

import argparse
import json
import sys
import signal
import atexit
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.annotator import annotate_all

CHECKPOINT_FILE = ROOT / "index_store" / "annotate_checkpoint.json"


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


def load_checkpoint() -> dict:
    """Load checkpoint if exists."""
    if not CHECKPOINT_FILE.exists():
        return {}
    try:
        return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_checkpoint(processed_ids: set, failed_ids: set):
    """Save current progress."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(
        json.dumps({
            "processed": list(processed_ids),
            "failed": list(failed_ids),
        }, ensure_ascii=False),
        encoding="utf-8"
    )


def is_annotated(card: dict) -> bool:
    return bool(card.get("semantic", {}).get("intent_tags"))


def filter_cards(cards: List[Dict], doc_type: str = None, skip_annotated: bool = True) -> List[Dict]:
    """Filter cards by document type and skip already annotated."""
    result = []
    for c in cards:
        # Skip already annotated
        if skip_annotated and is_annotated(c):
            continue

        # Filter by doc type
        if not doc_type:
            result.append(c)
            continue

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
    parser.add_argument("--restart", action="store_true", help="Ignore checkpoint, start from beginning")
    args = parser.parse_args()

    cards_dir = ROOT / "cards" / "sections"
    cards = load_cards(cards_dir)
    print(f"Loaded {len(cards)} cards from {cards_dir}", flush=True)

    filtered = filter_cards(cards, args.doc_type)
    print(f"After filter: {len(filtered)} cards", flush=True)

    if args.limit:
        filtered = filtered[:args.limit]
        print(f"Limited to {len(filtered)} cards", flush=True)

    if not filtered:
        print("No cards to annotate.")
        return

    # ── Checkpoint / resume logic ──────────────────────────────────────────
    checkpoint = {} if args.restart else load_checkpoint()
    processed_ids: set = set(checkpoint.get("processed", []))
    failed_ids: set = set(checkpoint.get("failed", []))

    # Resume: skip already processed (unless restart)
    if not args.restart and processed_ids:
        before = len(filtered)
        filtered = [c for c in filtered if c["id"] not in processed_ids]
        print(f"Resume: skipping {before - len(filtered)} already processed, {len(filtered)} remaining", flush=True)

    if not filtered:
        print("All cards already processed.")
        return

    # ── Signal handling: save checkpoint on Ctrl+C / SIGTERM ──────────────
    interrupted = False

    def signal_handler(sig, frame):
        nonlocal interrupted
        interrupted = True
        print(f"\n[INTERRUPT] Saving checkpoint ({len(processed_ids)} processed) before exit...", flush=True)
        save_checkpoint(processed_ids, failed_ids)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(lambda: save_checkpoint(processed_ids, failed_ids))

    # ── Run annotation ────────────────────────────────────────────────────
    cards_dir = ROOT / "cards" / "sections"
    total = len(filtered)

    for i, card in enumerate(filtered):
        if interrupted:
            break

        ann = annotate_all([card], batch_size=1, delay=0)
        ann = ann[0]

        card["semantic"] = ann
        if not args.dry_run:
            card_path = cards_dir / f"{card['id']}.json"
            card_path.write_text(
                json.dumps(card, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

        processed_ids.add(card["id"])

        # Progress: every 50 cards + final
        progress = i + 1
        if progress % 50 == 0 or progress == total:
            pct = progress * 100 // total
            print(f"[{progress}/{total} | {pct}%] done", flush=True)

    # Final save
    save_checkpoint(processed_ids, failed_ids)
    print(f"\nDone. {len(processed_ids)} cards processed, {len(failed_ids)} failed.", flush=True)


if __name__ == "__main__":
    main()
