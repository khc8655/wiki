#!/usr/bin/env bash
# recall.sh — 知识库纯召回入口
# 不做总结、不修改一字，只输出引擎返回的原文+出处+命中率
# Usage: bash scripts/recall.sh "你的查询"
#        bash scripts/recall.sh "你的查询" --limit 50
#        bash scripts/recall.sh "你的查询" --verbose

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

QUERY="${1:-}"
shift 2>/dev/null || true

if [ -z "$QUERY" ]; then
  echo "Usage: bash scripts/recall.sh \"查询内容\" [--limit N] [--verbose]" >&2
  exit 1
fi

exec python3 "$PROJECT_DIR/query_unified.py" "$QUERY" "$@"
