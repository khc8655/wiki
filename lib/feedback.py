#!/usr/bin/env python3
"""
Query feedback logger: records each search to JSONL and accepts user feedback.
Stores data in index_store/query_feedback.jsonl (one JSON object per line).
"""

import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_PATH = ROOT / "index_store" / "query_feedback.jsonl"

# In-memory conversation context (session-scoped)
_last_query_id: Optional[str] = None


def _now_iso() -> str:
    tz = timezone(timedelta(hours=8))  # Asia/Shanghai
    return datetime.now(tz).isoformat(timespec="seconds")


def _make_query_id(query: str) -> str:
    ts = int(time.time() * 1000)
    rnd = random.randint(1000, 9999)
    short = query[:20].replace(" ", "_").replace("/", "_")
    return f"q_{ts}_{rnd}_{short}"


def log_query(
    query: str,
    source_type: str,
    models: List[str],
    total_results: int,
    results: List[Dict],
    top_n: int = 5,
    referenced_query_id: Optional[str] = None,
) -> str:
    """
    Record a search query to the feedback log.

    Args:
        query: User's search query text
        source_type: Route type ('excel'|'knowledge'|'update'|'ppt')
        models: Extracted model numbers
        total_results: Total results before truncation
        results: Full result list (dicts with at least 'id','title','hit_rate')
        top_n: How many top results to record
        referenced_query_id: If this is a follow-up to a previous query

    Returns:
        query_id: The generated query identifier for later feedback
    """
    global _last_query_id
    query_id = _make_query_id(query)

    top5 = []
    for r in results[:top_n]:
        top5.append({
            "id": r.get("id", r.get("source", "")),
            "title": (r.get("title", "") or "")[:120],
            "hit_rate": r.get("hit_rate", 0),
            "source": r.get("source", "")[:200],
        })

    # Determine if low quality: all top-5 hit_rates < 0.3 OR very few results
    all_low = (
        len(top5) > 0
        and all(h["hit_rate"] < 0.3 for h in top5)
    )
    too_few = total_results < 3
    low_quality = all_low or too_few

    record = {
        "query_id": query_id,
        "timestamp": _now_iso(),
        "query": query,
        "source_type": source_type,
        "models": models,
        "total_results": total_results,
        "top5_hits": top5,
        "low_quality": low_quality,
        "referenced_query_id": referenced_query_id,
        "feedback": None,          # "good" | "bad" | None
        "feedback_timestamp": None,
        "selected_results": [],    # Which results the user clicked/chose
        "follow_up_queries": [],   # query_ids of follow-ups
    }

    _append_record(record)
    _last_query_id = query_id
    return query_id


def record_feedback(
    query_id: str,
    feedback: str,
    selected_results: Optional[List[str]] = None,
) -> bool:
    """
    Append user feedback to the most recent matching query record.

    Args:
        query_id: The query identifier from log_query()
        feedback: 'good', 'bad', or 'skip'
        selected_results: List of result IDs the user found useful

    Returns:
        True if the feedback was written, False otherwise
    """
    if not FEEDBACK_PATH.exists():
        print("[Feedback] No feedback log file exists yet")
        return False

    lines = []
    updated = False
    with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue

            if rec.get("query_id") == query_id and rec.get("feedback") is None:
                rec["feedback"] = feedback
                rec["feedback_timestamp"] = _now_iso()
                if selected_results:
                    rec["selected_results"] = selected_results
                updated = True

            lines.append(json.dumps(rec, ensure_ascii=False))

    if updated:
        with open(FEEDBACK_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[Feedback] Recorded '{feedback}' for {query_id}")
        return True

    print(f"[Feedback] Query {query_id} not found or already has feedback")
    return False


def record_follow_up(parent_query_id: str, child_query_id: str) -> bool:
    """
    Link a follow-up query to its parent query in the log.

    Args:
        parent_query_id: The earlier query this one references
        child_query_id: The new follow-up query ID

    Returns:
        True if updated, False otherwise
    """
    if not FEEDBACK_PATH.exists():
        return False

    lines = []
    updated = False
    with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue

            if rec.get("query_id") == parent_query_id:
                fups = rec.get("follow_up_queries", [])
                if child_query_id not in fups:
                    fups.append(child_query_id)
                    rec["follow_up_queries"] = fups
                    updated = True

            lines.append(json.dumps(rec, ensure_ascii=False))

    if updated:
        with open(FEEDBACK_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return updated


def get_last_query_id() -> Optional[str]:
    """Return the query ID of the most recently logged query in this session."""
    return _last_query_id


def get_stats() -> Dict:
    """Compute aggregate statistics from the feedback log."""
    if not FEEDBACK_PATH.exists():
        return {"total_queries": 0, "good": 0, "bad": 0, "skip": 0, "low_quality": 0}

    counts = {"total_queries": 0, "good": 0, "bad": 0, "skip": 0, "low_quality": 0}
    avg_rates = []

    with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            counts["total_queries"] += 1
            fb = rec.get("feedback")
            if fb in ("good", "bad", "skip"):
                counts[fb] += 1
            if rec.get("low_quality"):
                counts["low_quality"] += 1
            for h in rec.get("top5_hits", []):
                avg_rates.append(h.get("hit_rate", 0))

    out = dict(counts)
    if avg_rates:
        out["avg_hit_rate_top5"] = round(sum(avg_rates) / len(avg_rates), 3)
    else:
        out["avg_hit_rate_top5"] = 0.0
    return out


def _append_record(record: Dict):
    """Atomically append a JSON line to the feedback file."""
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    qid = log_query(
        "视频会议安全加密方案",
        source_type="knowledge",
        models=[],
        total_results=12,
        results=[
            {"id": "c1", "title": "端到端加密方案", "hit_rate": 0.85, "source": "doc1"},
            {"id": "c2", "title": "会议室安全部署", "hit_rate": 0.62, "source": "doc2"},
        ],
    )
    print(f"Logged: {qid}")
    record_feedback(qid, "good", selected_results=["c1"])

    qid2 = log_query(
        "不存在的查询测试",
        source_type="knowledge",
        models=[],
        total_results=1,
        results=[
            {"id": "c3", "title": "无关段落", "hit_rate": 0.12, "source": "doc3"},
        ],
    )
    print(f"Logged: {qid2} (low_quality={True})")

    stats = get_stats()
    print(f"Stats: {json.dumps(stats, ensure_ascii=False)}")
    print(f"File size: {os.path.getsize(FEEDBACK_PATH)} bytes")
