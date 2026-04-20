#!/usr/bin/env bash
set -euo pipefail
cd /workspace/wiki_test
python3 scripts/import_webdav_raw.py --user jjb --password 'jjb@115799'
python3 scripts/build_v2_semantic_metadata.py
node scripts/build_path_index.js
node scripts/build_model_index.js
python3 scripts/build_fts5_index.py
python3 scripts/build_qmd_bridge_index.py
