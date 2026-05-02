#!/usr/bin/env python3
"""
Card Organizer: Karpathy-style self-organizing knowledge system.

Discovers relationships, merges near-duplicates, clusters into themes,
and builds cross-references — all driven by embedding similarity and
optional feedback co-occurrence patterns.
"""

import json
import os
import re
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter
from datetime import datetime

from lib.vector_search import get_searcher, VectorSearcher


# ---------------------------------------------------------------------------
# Pure numpy KMeans (no sklearn dependency)
# ---------------------------------------------------------------------------
def _kmeans(
    X: np.ndarray,
    n_clusters: int,
    max_iters: int = 100,
    seed: int = 42,
    tol: float = 1e-4,
) -> Tuple[np.ndarray, np.ndarray]:
    """Simple KMeans clustering on float32 matrix [N x D]."""
    rng = np.random.RandomState(seed)
    idx = rng.choice(len(X), n_clusters, replace=False)
    centroids = X[idx].copy()

    for _ in range(max_iters):
        # (N, C) distance via broadcasting
        diff = X[:, np.newaxis, :] - centroids[np.newaxis, :, :]  # (N, C, D)
        distances = np.linalg.norm(diff, axis=2)                    # (N, C)
        labels = np.argmin(distances, axis=1)

        new_centroids = np.array(
            [X[labels == k].mean(axis=0) for k in range(n_clusters)],
            dtype=np.float32,
        )
        # Handle empty clusters: re-init from a random point
        for k in range(n_clusters):
            if np.isnan(new_centroids[k]).any():
                new_centroids[k] = X[rng.choice(len(X))]

        shift = np.linalg.norm(new_centroids - centroids)
        centroids = new_centroids
        if shift < tol:
            break

    return labels, centroids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _slugify(text: str) -> str:
    """Turn a Chinese/English theme name into a filename-safe slug."""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80] or "untitled"


def _sanitize_filename(name: str) -> str:
    """Remove characters unsafe for filenames."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _load_all_cards(sections_dir: Path) -> Dict[str, dict]:
    """Load every card JSON from cards/sections/ into {card_id: card}."""
    cards: Dict[str, dict] = {}
    if not sections_dir.is_dir():
        return cards
    for fp in sorted(sections_dir.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            cid = data.get("id")
            if cid:
                cards[cid] = data
        except (json.JSONDecodeError, KeyError):
            continue
    return cards


def _load_feedback_log(feedback_path: Path) -> List[dict]:
    """Load JSONL feedback log. Returns [] if file missing."""
    if not feedback_path.is_file():
        return []
    entries = []
    for line in feedback_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ---------------------------------------------------------------------------
# CardOrganizer
# ---------------------------------------------------------------------------
class CardOrganizer:
    """卡片自组织系统：发现关联、合并相似、提炼主题"""

    def __init__(self, project_root: Optional[Path] = None):
        if project_root is None:
            project_root = Path(__file__).resolve().parents[1]
        self.root = Path(project_root)

        self.sections_dir = self.root / "cards" / "sections"
        self.topics_dir = self.root / "topics"
        self.feedback_path = self.root / "updates" / "retrieval_feedback" / "query_log.jsonl"

        # Load all cards into memory
        self.cards = _load_all_cards(self.sections_dir)
        print(f"[CardOrganizer] Loaded {len(self.cards)} cards")

        # Vector searcher (only cards with embeddings)
        self.searcher = get_searcher()
        self._emb_card_ids = self.searcher.card_ids  # 1773 ids
        self._emb_matrix = self.searcher._normalized  # (1773, 1024) normalized

        # Build fast lookup: card_id -> index in embedding matrix
        self._id_to_idx: Dict[str, int] = {cid: i for i, cid in enumerate(self._emb_card_ids)}

    # ------------------------------------------------------------------
    # 1. find_similar_cards
    # ------------------------------------------------------------------
    def find_similar_cards(
        self,
        threshold: float = 0.85,
        top_k: int = 5,
    ) -> List[Tuple[str, str, float]]:
        """
        Find similar card pairs via embedding cosine similarity.

        Returns:
            List of (card_id_a, card_id_b, cosine_similarity), each pair
            appears only once (id_a < id_b lexicographically).
        """
        M = self._emb_matrix  # (N, D) normalized
        N = M.shape[0]

        if N < 2:
            return []

        # Compute full similarity matrix in chunks to avoid O(N² D) memory spike
        # but N=1773 is small enough for direct matmul
        sim = M @ M.T  # (N, N)

        # Zero out diagonal
        np.fill_diagonal(sim, 0.0)

        # For each row, find top-k above threshold
        pairs: List[Tuple[str, str, float]] = []
        seen: Set[Tuple[str, str]] = set()

        # Process in one pass: only keep pairs where i < j
        for i in range(N):
            row = sim[i]
            # Find indices where sim >= threshold
            candidates = np.where(row >= threshold)[0]
            if len(candidates) == 0:
                continue
            # Sort by similarity descending and take top_k
            scores = row[candidates]
            if len(candidates) > top_k:
                top_local = np.argpartition(-scores, top_k)[:top_k]
                top_local = top_local[np.argsort(-scores[top_local])]
                candidates = candidates[top_local]
                scores = row[candidates]

            for j, score in zip(candidates, scores):
                cid_i = self._emb_card_ids[i]
                cid_j = self._emb_card_ids[j]
                # Enforce canonical order
                key = (cid_i, cid_j) if cid_i < cid_j else (cid_j, cid_i)
                if key in seen:
                    continue
                seen.add(key)

                # Filter: skip pairs where both cards are near-empty or boilerplate stubs
                # (title-only cards with almost no body produce identical embeddings)
                # Also skip shared boilerplate titles like 【适用环境】 across docs
                BOILERPLATE_TITLES = {'【适用环境】', '【功能背景】', '【功能说明】', '【前置条件】',
                                     '适用环境', '功能背景', '功能说明', '前置条件',
                                     '说明', '【说明】'}
                bi = len(self.cards.get(cid_i, {}).get("body", ""))
                bj = len(self.cards.get(cid_j, {}).get("body", ""))
                ti = self.cards.get(cid_i, {}).get("title", "").strip()
                tj = self.cards.get(cid_j, {}).get("title", "").strip()
                if score >= 0.995 and bi < 30 and bj < 30 and bi == bj:
                    continue
                if (bi < 100 or bj < 100) and (ti in BOILERPLATE_TITLES or tj in BOILERPLATE_TITLES):
                    continue

                pairs.append((key[0], key[1], float(score)))

        # Sort by similarity descending
        pairs.sort(key=lambda x: -x[2])
        return pairs

    # ------------------------------------------------------------------
    # 2. suggest_merges
    # ------------------------------------------------------------------
    def suggest_merges(self, similar_pairs: List[Tuple[str, str, float]]) -> Dict:
        """
        Classify similar pairs into merge candidates vs related-card links.

        Returns dict with keys:
          - merges:   list of dicts {card_a, card_b, similarity, winner, reason}
          - related:  list of dicts {card_a, card_b, similarity}
        """
        merges: List[Dict] = []
        related: List[Dict] = []

        for cid_a, cid_b, score in similar_pairs:
            if score >= 0.92:
                card_a = self.cards.get(cid_a, {})
                card_b = self.cards.get(cid_b, {})
                len_a = len(card_a.get("body", ""))
                len_b = len(card_b.get("body", ""))
                winner = cid_a if len_a >= len_b else cid_b
                merges.append({
                    "card_a": cid_a,
                    "card_b": cid_b,
                    "similarity": score,
                    "winner": winner,
                    "loser": cid_b if winner == cid_a else cid_a,
                    "body_len_a": len_a,
                    "body_len_b": len_b,
                    "reason": "高度重复 (cosine >= 0.92)，建议合并，保留内容较长者",
                })
            elif score >= 0.85:
                related.append({
                    "card_a": cid_a,
                    "card_b": cid_b,
                    "similarity": score,
                })

        return {
            "merges": merges,
            "related": related,
            "stats": {
                "total_pairs": len(similar_pairs),
                "merge_candidates": len(merges),
                "related_candidates": len(related),
            },
        }

    # ------------------------------------------------------------------
    # 3. cluster_cards
    # ------------------------------------------------------------------
    def cluster_cards(self, n_clusters: int = 20) -> Dict:
        """
        Cluster cards into themes using KMeans on embeddings.

        Returns dict:
          - labels:       cluster label per card in _emb_card_ids order
          - clusters:     {cluster_id: [card_id, ...]}
          - themes:       {cluster_id: {name, top_intents, top_concepts, size}}
        """
        M = self._emb_matrix  # already normalized; use unnormalized for better cluster separation
        # Re-load unnormalized matrix for KMeans
        raw_matrix = self.searcher.matrix  # (N, D) not normalized

        labels, centroids = _kmeans(raw_matrix, n_clusters)

        # Build cluster -> card_ids
        clusters: Dict[int, List[str]] = {k: [] for k in range(n_clusters)}
        for i, label in enumerate(labels):
            clusters[int(label)].append(self._emb_card_ids[i])

        # Generate theme names from tag frequencies
        themes: Dict[int, Dict] = {}
        for k, card_ids in clusters.items():
            intent_counter: Counter = Counter()
            concept_counter: Counter = Counter()
            for cid in card_ids:
                card = self.cards.get(cid, {})
                sem = card.get("semantic", {})
                for tag in sem.get("intent_tags", []):
                    intent_counter[tag] += 1
                for tag in sem.get("concept_tags", []):
                    concept_counter[tag] += 1

            top_intents = [t for t, _ in intent_counter.most_common(5)]
            top_concepts = [t for t, _ in concept_counter.most_common(8)]

            # Build theme name
            if top_intents:
                name = " · ".join(top_intents[:3])
            elif top_concepts:
                name = " · ".join(top_concepts[:3])
            else:
                name = f"主题-{k + 1}"

            themes[k] = {
                "name": name,
                "top_intents": top_intents,
                "top_concepts": top_concepts,
                "size": len(card_ids),
            }

        return {
            "n_clusters": n_clusters,
            "labels": labels.tolist(),
            "clusters": {str(k): v for k, v in clusters.items()},
            "themes": {str(k): v for k, v in themes.items()},
            "sizes": {str(k): len(v) for k, v in clusters.items()},
        }

    # ------------------------------------------------------------------
    # 4. build_cross_references
    # ------------------------------------------------------------------
    def build_cross_references(
        self,
        feedback_log: Optional[List[dict]] = None,
    ) -> Dict:
        """
        Build cross-references from feedback co-occurrence patterns.

        If feedback_log is None, try loading from the default path.

        Returns:
          - co_occurrences: { (cid_a, cid_b): count }
          - cross_refs:     list of {card_a, card_b, co_count}
        """
        if feedback_log is None:
            feedback_log = _load_feedback_log(self.feedback_path)

        if not feedback_log:
            return {
                "co_occurrences": {},
                "cross_refs": [],
                "note": "无 feedback log，跳过交叉引用分析",
            }

        # Collect cards co-occurring in the same query result
        pair_counter: Counter = Counter()
        for entry in feedback_log:
            top_cards = entry.get("top_cards", [])
            if len(top_cards) < 2:
                continue
            for i in range(len(top_cards)):
                for j in range(i + 1, len(top_cards)):
                    a, b = top_cards[i], top_cards[j]
                    key = (a, b) if a < b else (b, a)
                    pair_counter[key] += 1

        cross_refs = [
            {"card_a": a, "card_b": b, "co_count": cnt}
            for (a, b), cnt in pair_counter.most_common(200)
        ]

        return {
            "co_occurrences": {f"{a}|||{b}": cnt for (a, b), cnt in pair_counter.most_common(200)},
            "cross_refs": cross_refs,
            "total_pairs": len(cross_refs),
        }

    # ------------------------------------------------------------------
    # 5. refine_topics
    # ------------------------------------------------------------------
    def refine_topics(self, clustering: Optional[Dict] = None) -> Dict:
        """
        Generate / update topic markdown files from clustering results.

        If clustering is None, runs cluster_cards() first.
        """
        if clustering is None:
            clustering = self.cluster_cards()

        self.topics_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        written: List[Path] = []

        for cluster_id_str, theme in clustering["themes"].items():
            theme_name = theme["name"]
            slug = _slugify(theme_name)
            filename = _sanitize_filename(f"theme-{slug}-c{cluster_id_str}.md")
            out_path = self.topics_dir / filename

            card_ids = clustering["clusters"].get(cluster_id_str, [])
            # Build card list table
            lines = [
                f"# {theme_name}",
                "",
                f"> 自动生成于 {ts} | {len(card_ids)} 张卡片 | 聚类 ID {cluster_id_str}",
                "",
                "## 关键意图",
            ]
            for intent in theme.get("top_intents", []):
                lines.append(f"- {intent}")

            lines.append("")
            lines.append("## 关键概念")
            for concept in theme.get("top_concepts", []):
                lines.append(f"- {concept}")

            lines.append("")
            lines.append("## 卡片列表")
            lines.append("")
            lines.append("| # | Card ID | Title | Body Preview |")
            lines.append("|---|---------|-------|-------------|")

            for idx, cid in enumerate(card_ids, 1):
                card = self.cards.get(cid, {})
                title = card.get("title", "—")
                body_preview = (card.get("body", "") or "")[:80].replace("\n", " ").replace("|", "/")
                lines.append(f"| {idx} | `{cid}` | {title} | {body_preview} |")

            out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            written.append(out_path)

        return {
            "topics_written": len(written),
            "files": [str(p.relative_to(self.root)) for p in written],
        }

    # ------------------------------------------------------------------
    # 6. apply (write changes to cards)
    # ------------------------------------------------------------------
    def apply_merges(self, merge_suggestions: List[Dict], dry_run: bool = True) -> Dict:
        """
        Apply merge suggestions by adding merged_from/merged_to fields.

        Does NOT delete any cards — only annotates relationships.
        """
        modified: List[str] = []
        for suggestion in merge_suggestions:
            winner = suggestion["winner"]
            loser = suggestion["loser"]
            w_card = self.cards.get(winner)
            l_card = self.cards.get(loser)
            if not w_card or not l_card:
                continue

            if dry_run:
                modified.append(f"{loser} → {winner} (sim={suggestion['similarity']:.4f})")
                continue

            # Tag winner
            w_card.setdefault("merged_from", [])
            if loser not in w_card["merged_from"]:
                w_card["merged_from"].append(loser)

            # Tag loser
            l_card.setdefault("merged_to", winner)

            # Persist
            self._write_card(winner, w_card)
            self._write_card(loser, l_card)
            modified.append(f"{loser} → {winner}")

        return {"applied": len(modified), "changes": modified, "dry_run": dry_run}

    def apply_related(self, related_suggestions: List[Dict], dry_run: bool = True) -> Dict:
        """Add related_cards links based on embedding similarity."""
        modified: Set[str] = set()
        for rel in related_suggestions:
            cid_a, cid_b = rel["card_a"], rel["card_b"]
            card_a = self.cards.get(cid_a)
            card_b = self.cards.get(cid_b)
            if not card_a or not card_b:
                continue

            if dry_run:
                modified.add(cid_a)
                continue

            card_a.setdefault("related_cards", [])
            card_b.setdefault("related_cards", [])

            # Add bidirectional reference with similarity score
            ref_a = {"card_id": cid_b, "similarity": rel["similarity"], "source": "embedding"}
            ref_b = {"card_id": cid_a, "similarity": rel["similarity"], "source": "embedding"}

            existing_a = {r["card_id"] for r in card_a["related_cards"]}
            existing_b = {r["card_id"] for r in card_b["related_cards"]}

            if cid_b not in existing_a:
                card_a["related_cards"].append(ref_a)
            if cid_a not in existing_b:
                card_b["related_cards"].append(ref_b)

            self._write_card(cid_a, card_a)
            self._write_card(cid_b, card_b)
            modified.add(cid_a)
            modified.add(cid_b)

        return {"applied": len(modified), "cards_modified": sorted(modified), "dry_run": dry_run}

    def apply_cross_refs(self, cross_refs: List[Dict], dry_run: bool = True) -> Dict:
        """Add related_cards links from feedback co-occurrence."""
        modified: Set[str] = set()
        for xref in cross_refs:
            cid_a, cid_b = xref["card_a"], xref["card_b"]
            card_a = self.cards.get(cid_a)
            card_b = self.cards.get(cid_b)
            if not card_a or not card_b:
                continue

            if dry_run:
                modified.add(cid_a)
                continue

            card_a.setdefault("related_cards", [])
            card_b.setdefault("related_cards", [])

            ref_a = {"card_id": cid_b, "co_occurrence_count": xref["co_count"], "source": "feedback"}
            ref_b = {"card_id": cid_a, "co_occurrence_count": xref["co_count"], "source": "feedback"}

            # Only add if not already present (embedding refs take priority)
            existing_a = {r["card_id"] for r in card_a["related_cards"]}
            existing_b = {r["card_id"] for r in card_b["related_cards"]}

            if cid_b not in existing_a:
                card_a["related_cards"].append(ref_a)
            if cid_a not in existing_b:
                card_b["related_cards"].append(ref_b)

            self._write_card(cid_a, card_a)
            self._write_card(cid_b, card_b)
            modified.add(cid_a)
            modified.add(cid_b)

        return {"applied": len(modified), "cards_modified": sorted(modified), "dry_run": dry_run}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _write_card(self, card_id: str, card: dict):
        """Write a single card JSON back to disk."""
        # Card filenames match {card_id}.json
        out_path = self.sections_dir / f"{card_id}.json"
        out_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run_full_analysis(self) -> Dict:
        """Convenience: run all analysis steps and return a summary dict."""
        print("\n[1/4] Finding similar cards...")
        pairs = self.find_similar_cards(threshold=0.85)

        print(f"[2/4] Suggesting merges ({len(pairs)} pairs)...")
        suggestions = self.suggest_merges(pairs)

        print(f"[3/4] Clustering cards...")
        clustering = self.cluster_cards(n_clusters=20)

        print(f"[4/4] Building cross-references...")
        feedback = _load_feedback_log(self.feedback_path)
        cross_refs = self.build_cross_references(feedback)

        # Summary
        n_high = sum(1 for _, _, s in pairs if s >= 0.92)
        n_related = sum(1 for _, _, s in pairs if 0.85 <= s < 0.92)

        return {
            "similar_pairs_total": len(pairs),
            "highly_similar_092": n_high,
            "related_085_092": n_related,
            "merge_suggestions": len(suggestions["merges"]),
            "related_suggestions": len(suggestions["related"]),
            "clusters": clustering["n_clusters"],
            "cluster_sizes": clustering["sizes"],
            "cross_references": cross_refs.get("total_pairs", 0),
        }


# ---------------------------------------------------------------------------
# CLI test block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    org = CardOrganizer()

    print("=" * 60)
    print("Card Organizer — Dry Run")
    print("=" * 60)

    summary = org.run_full_analysis()
    print("\nSummary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # Show top merge candidates
    pairs = org.find_similar_cards(threshold=0.92)
    print(f"\nTop merge candidates (cosine >= 0.92): {len(pairs)}")
    for a, b, s in pairs[:10]:
        ca = org.cards.get(a, {})
        cb = org.cards.get(b, {})
        print(f"  {s:.4f} | {ca.get('title','?')} ⇄ {cb.get('title','?')}")
        print(f"         | {a}")
        print(f"         | {b}")
