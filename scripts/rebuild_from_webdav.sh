#!/usr/bin/env bash
set -euo pipefail
cd /workspace/wiki_test
./scripts/refresh_from_webdav.sh
python3 scripts/build_knowledge_tree_v2.py
python3 scripts/refine_knowledge_tree_v2_1.py
