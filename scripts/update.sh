#!/usr/bin/env bash
# update.sh — 知识库更新入口
#
# Usage:
#   bash scripts/update.sh              # --auto: 检测变更，有则更新
#   bash scripts/update.sh --auto       # 同上（默认模式）
#   bash scripts/update.sh --full       # 全量：强制从头重建
#   bash scripts/update.sh --check      # 仅检测变更，不执行
#   bash scripts/update.sh --annotate-only  # 仅标注+embeddings
#
# --auto 流程（默认）:
#   WebDAV拉取 → 检测变更 → 无变更则退出 → 有变更则跑完整流水线

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MODE="${1:---auto}"
FULL=false
CHECK_ONLY=false
ANNOTATE_ONLY=false
AUTO=true   # default

case "$MODE" in
  --full)    FULL=true; AUTO=false ;;
  --check)   CHECK_ONLY=true; AUTO=false ;;
  --annotate-only) ANNOTATE_ONLY=true; AUTO=false ;;
  --auto|incremental) ;;
  *) echo "Usage: bash scripts/update.sh [--auto|--full|--check|--annotate-only]" >&2; exit 1 ;;
esac

echo "========================================="
echo "  wiki_test 知识库管理"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
if $FULL; then
  echo "  模式: 全量重建"
elif $CHECK_ONLY; then
  echo "  模式: 仅检测变更"
elif $ANNOTATE_ONLY; then
  echo "  模式: 仅标注+embeddings"
else
  echo "  模式: 自动检测更新"
fi
echo "========================================="

# ── Step 1: Pull from WebDAV ───────────────────────────────────────────────
if ! $ANNOTATE_ONLY; then
  echo ""
  echo "[1/6] 从 WebDAV 同步文档..."
  python3 scripts/import_webdav_raw.py --user jjb --password 'jjb@115799'

  # ── Check for changes ────────────────────────────────────────────────────
  STATE_FILE="index_store/webdav_import_state.json"
  HAS_CHANGES=false
  CHANGED_FILES=""

  # Compare new import state with previous to detect changes
  if [ -f "$STATE_FILE" ]; then
    CHANGED_FILES=$(python3 -c "
import json, sys
with open('$STATE_FILE') as f:
    s = json.load(f)

# Check for new/changed binary files (excel/ppt)
prev = s.get('_previous_docs', [])
curr = s.get('docs', [])

changes = []
prev_names = {d.get('local_name',''): d for d in prev}
curr_names = {d.get('local_name',''): d for d in curr}

for name, doc in curr.items():
    if name not in prev_names:
        changes.append(f'新增: {name}')
    elif doc.get('sha256') and doc['sha256'] != prev_names[name].get('sha256',''):
        changes.append(f'更新: {name}')

for name in prev_names:
    if name not in curr_names:
        changes.append(f'删除: {name}')

if changes:
    for c in changes[:15]:
        print(f'    - {c}')
    if len(changes) > 15:
        print(f'    ... 及其他 {len(changes)-15} 项变更')
    sys.exit(1)
" 2>&1) && HAS_CHANGES=false || HAS_CHANGES=true
  else
    # First run — state file doesn't exist yet
    HAS_CHANGES=true
    CHANGED_FILES='    (首次导入)'
  fi

  if $CHECK_ONLY; then
    if $HAS_CHANGES; then
      echo ""
      echo "📋 检测到变更："
      echo "$CHANGED_FILES"
    else
      echo ""
      echo "✅ 无变更，知识库已是最新"
    fi
    exit 0
  fi

  if $AUTO; then
    if ! $HAS_CHANGES; then
      echo ""
      echo "✅ 无变更，知识库已是最新，无需更新"
      exit 0
    fi
    echo ""
    echo "📋 检测到以下文件变更："
    echo "$CHANGED_FILES"
    echo ""
    echo "开始增量更新..."
  fi

  # ── Step 2: Import Excel into SQLite ────────────────────────────────────
  echo ""
  echo "[2/6] 导入 Excel 数据到 SQLite..."
  if [ -f scripts/build_excel_knowledge.py ]; then
    python3 scripts/build_excel_knowledge.py 2>/dev/null && echo "  ✓" || echo "  ⚠️ 部分失败"
  fi

  # ── Step 3: Card metadata ───────────────────────────────────────────────
  echo ""
  echo "[3/6] 重建卡片元数据..."
  python3 scripts/build_v2_semantic_metadata.py && echo "  ✓"

  # ── Step 4: Indexes ─────────────────────────────────────────────────────
  echo ""
  echo "[4/6] 重建索引..."
  [ -f scripts/build_path_index.js ] && node scripts/build_path_index.js 2>/dev/null && echo "  path_index ✓"
  [ -f scripts/build_model_index.js ] && node scripts/build_model_index.js 2>/dev/null && echo "  model_index ✓"
  [ -f scripts/build_fts5_index.py ] && python3 scripts/build_fts5_index.py 2>/dev/null && echo "  fts5 ✓"
  [ -f scripts/build_qmd_bridge_index.py ] && python3 scripts/build_qmd_bridge_index.py 2>/dev/null && echo "  qmd_bridge ✓"
fi

# ── Step 5: Annotate (incremental only) ────────────────────────────────────
echo ""
echo "[5/6] 卡片标注..."

UNANNOTATED=$(python3 -c "
import json, os
d='cards/sections'
if not os.path.isdir(d):
    print(0)
    exit()
c=sum(1 for f in os.listdir(d) if f.endswith('.json') and not
      json.loads(open(os.path.join(d,f)).read()).get('semantic',{}).get('intent_tags'))
print(c)
")

if [ "$UNANNOTATED" -gt 0 ]; then
  echo "  ${UNANNOTATED} 张卡片待标注..."
  python3 scripts/annotate_cards.py --doc-type solution && echo "  ✓"
else
  echo "  全部已标注 ✓"
fi

# ── Step 6: Embeddings ────────────────────────────────────────────────────
echo ""
echo "[6/6] 向量索引..."
python3 scripts/build_embeddings.py && echo "  ✓"

# ── Audit ─────────────────────────────────────────────────────────────────
[ -f scripts/audit_solution_cards.py ] && python3 scripts/audit_solution_cards.py 2>/dev/null

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  ✅ 更新完成  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
python3 -c "
import json, os
from collections import Counter
d='cards/sections'
total=0; annotated=0
ic=Counter()
if os.path.isdir(d):
    for f in os.listdir(d):
        if not f.endswith('.json'): continue
        total+=1
        c=json.loads(open(os.path.join(d,f)).read())
        tags=c.get('semantic',{}).get('intent_tags',[])
        if tags: annotated+=1
        for t in tags: ic[t]+=1
print(f'卡片: {total}  |  已标注: {annotated}')
print('标注分布:', ', '.join(f'{t}({c})' for t,c in ic.most_common(5)))
"
echo ""
