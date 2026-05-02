#!/usr/bin/env python3
"""
Organize Cards — CLI entry point for the CardOrganizer system.

Usage:
  python3 scripts/organize_cards.py                  # full analysis (read-only)
  python3 scripts/organize_cards.py --dry-run         # preview, no writes
  python3 scripts/organize_cards.py --merge           # execute merge annotations
  python3 scripts/organize_cards.py --related         # add related_cards links
  python3 scripts/organize_cards.py --cluster 20      # cluster into N themes
  python3 scripts/organize_cards.py --topics          # generate topics/ files
  python3 scripts/organize_cards.py --all             # run everything including writes
  python3 scripts/organize_cards.py --threshold 0.88  # custom similarity threshold

Flags can be combined:
  python3 scripts/organize_cards.py --dry-run --cluster 15 --threshold 0.87
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from lib.card_organizer import CardOrganizer


def main():
    parser = argparse.ArgumentParser(
        description="卡片自组织系统：发现关联、合并相似、聚类主题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="预览模式，不写入任何文件 (默认)",
    )
    parser.add_argument(
        "--merge", action="store_true",
        help="应用合并建议 (添加 merged_from/merged_to 字段)",
    )
    parser.add_argument(
        "--related", action="store_true",
        help="添加 related_cards 关联字段",
    )
    parser.add_argument(
        "--cluster", type=int, default=None, metavar="N",
        help="聚类为 N 个主题 (默认 20)",
    )
    parser.add_argument(
        "--topics", action="store_true",
        help="生成/更新 topics/ 目录文件",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.85,
        help="相似度阈值 (默认 0.85)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="执行所有操作 (含写入)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="以 JSON 格式输出结果",
    )
    parser.add_argument(
        "--top-n", type=int, default=20,
        help="展示前 N 条相似卡片对 (默认 20)",
    )

    args = parser.parse_args()

    # --all implies --merge --related --topics --cluster 20
    if args.all:
        args.merge = True
        args.related = True
        args.topics = True
        args.cluster = args.cluster or 20
        args.dry_run = False

    org = CardOrganizer()

    # ── Step 1: Find similar cards ──
    print("=" * 70)
    print("📊 步骤 1: 查找相似卡片对")
    print("=" * 70)
    pairs = org.find_similar_cards(threshold=args.threshold)
    n_high = sum(1 for _, _, s in pairs if s >= 0.92)
    n_rel = sum(1 for _, _, s in pairs if 0.85 <= s < 0.92)

    print(f"  总相似对 (cosine >= {args.threshold}): {len(pairs)}")
    print(f"  高度重复 (>=0.92): {n_high}")
    print(f"  相关但独立 (0.85-0.92): {n_rel}")
    print()

    # Show top similar pairs
    display_n = min(args.top_n, len(pairs))
    if display_n > 0:
        print(f"  Top {display_n} 最相似卡片对:")
        print(f"  {'相似度':>8}  {'标题 A':<30}  {'标题 B':<30}")
        print(f"  {'-'*8}  {'-'*30}  {'-'*30}")
        for a, b, s in pairs[:display_n]:
            ca = org.cards.get(a, {})
            cb = org.cards.get(b, {})
            ta = (ca.get("title", "?") or "?")[:28]
            tb = (cb.get("title", "?") or "?")[:28]
            marker = "🔴" if s >= 0.92 else "🟡"
            print(f"  {marker} {s:.4f}  {ta:<30}  {tb:<30}")

    # ── Step 2: Merge / Related suggestions ──
    suggestions = org.suggest_merges(pairs)
    print()
    print("=" * 70)
    print("📋 步骤 2: 合并与关联建议")
    print("=" * 70)
    print(f"  建议合并 (>=0.92): {len(suggestions['merges'])}")
    print(f"  建议关联 (0.85-0.92): {len(suggestions['related'])}")

    if suggestions["merges"]:
        print(f"\n  合并候选 (保留内容较长者):")
        for m in suggestions["merges"][:10]:
            wa = org.cards.get(m["winner"], {})
            la = org.cards.get(m["loser"], {})
            print(f"    {m['similarity']:.4f} | 保留: {wa.get('title','?')} (len={m.get('body_len_a', '?')})")
            print(f"           | 标记: {la.get('title','?')} (len={m.get('body_len_b', '?')})")

    # ── Apply merges if requested ──
    if args.merge and suggestions["merges"]:
        result = org.apply_merges(suggestions["merges"], dry_run=args.dry_run)
        print(f"\n  ⚡ 合并操作: {result['applied']} 张卡片已标注")
        if args.dry_run:
            print("     (dry-run 模式，未实际写入)")

    if args.related and suggestions["related"]:
        result = org.apply_related(suggestions["related"], dry_run=args.dry_run)
        print(f"\n  ⚡ 关联操作: {result['applied']} 张卡片已添加 related_cards")
        if args.dry_run:
            print("     (dry-run 模式，未实际写入)")

    # ── Step 3: Clustering ──
    if args.cluster:
        n = args.cluster
        print()
        print("=" * 70)
        print(f"🧩 步骤 3: 聚类分析 (KMeans, n={n})")
        print("=" * 70)

        clustering = org.cluster_cards(n_clusters=n)
        print(f"  聚类数: {n}")
        print(f"  各簇大小:")
        for k in sorted(clustering["clusters"].keys(), key=lambda x: -clustering["sizes"][x]):
            theme = clustering["themes"][k]
            size = clustering["sizes"][k]
            bar = "█" * max(1, size // 10)
            print(f"    簇{k:>2}: {size:>4} 张 {bar} → {theme['name']}")

    else:
        clustering = None

    # ── Step 4: Cross-references ──
    print()
    print("=" * 70)
    print("🔗 步骤 4: 交叉引用分析")
    print("=" * 70)
    cross = org.build_cross_references()
    if cross.get("note"):
        print(f"  {cross['note']}")
    else:
        print(f"  发现 {cross['total_pairs']} 对共现关联")
        for xr in cross.get("cross_refs", [])[:10]:
            print(f"    {xr['co_count']:>4}x | {xr['card_a'][:50]} ⇄ {xr['card_b'][:50]}")

    # ── Step 5: Generate topics ──
    if args.topics:
        print()
        print("=" * 70)
        print("📝 步骤 5: 生成主题文件")
        print("=" * 70)
        if clustering is None:
            clustering = org.cluster_cards(n_clusters=args.cluster or 20)
        topic_result = org.refine_topics(clustering)
        print(f"  已生成 {topic_result['topics_written']} 个主题文件:")
        for f in topic_result["files"]:
            print(f"    {f}")
    else:
        topic_result = None

    # ── Final summary ──
    print()
    print("=" * 70)
    print("✅ 分析完成")
    print("=" * 70)

    output = {
        "similar_pairs_total": len(pairs),
        "highly_similar_092": n_high,
        "related_085_092": n_rel,
        "merge_suggestions": len(suggestions["merges"]),
        "related_suggestions": len(suggestions["related"]),
        "clusters": args.cluster,
        "cluster_sizes": clustering["sizes"] if clustering else None,
        "cross_references": cross.get("total_pairs", 0),
        "topics_generated": topic_result["topics_written"] if topic_result else 0,
        "dry_run": args.dry_run,
    }

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        for k, v in output.items():
            if v is not None:
                print(f"  {k}: {v}")

    if args.dry_run and not args.json:
        print()
        print("  💡 提示: 当前为 dry-run 模式。")
        print("     使用 --merge --related 应用关联标注。")
        print("     使用 --topics 生成主题文件。")
        print("     使用 --all 执行所有操作。")


if __name__ == "__main__":
    main()
