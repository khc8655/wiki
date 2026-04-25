#!/usr/bin/env bash
set -euo pipefail
# 自动检测脚本所在目录的父目录（即项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
./scripts/refresh_from_webdav.sh
python3 scripts/build_knowledge_tree_v2.py
python3 scripts/refine_knowledge_tree_v2_1.py
