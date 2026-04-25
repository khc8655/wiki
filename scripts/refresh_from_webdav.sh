#!/usr/bin/env bash
set -euo pipefail
# 自动检测脚本所在目录的父目录（即项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"
python3 scripts/import_webdav_raw.py --user jjb --password 'jjb@115799'
python3 scripts/build_v2_semantic_metadata.py
node scripts/build_path_index.js
node scripts/build_model_index.js
python3 scripts/build_fts5_index.py
python3 scripts/build_qmd_bridge_index.py
python3 scripts/audit_solution_cards.py
