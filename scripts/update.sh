#!/usr/bin/env bash
# update.sh — 知识库增量更新入口
# 文档更新后一键刷新卡片、标注、索引、embeddings
#
# Usage:
#   bash scripts/update.sh              # 增量：只处理变化的部分
#   bash scripts/update.sh --full       # 全量：从头重建所有
#   bash scripts/update.sh --check      # 仅检测变更，不执行
#   bash scripts/update.sh --annotate-only  # 只重新标注 + 重建embeddings
#
# 架构：
#   文档变更 → 卡片重生成 → 标注(新增/变更卡片) → embedding重建 → 索引刷新 → 审计

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MODE="${1:-incremental}"
FULL=false
CHECK_ONLY=false
ANNOTATE_ONLY=false

case "$MODE" in
  --full)    FULL=true ;;
  --check)   CHECK_ONLY=true ;;
  --annotate-only) ANNOTATE_ONLY=true ;;
  incremental) ;;
  *) echo "Usage: bash scripts/update.sh [--full|--check|--annotate-only]" >&2; exit 1 ;;
esac

# ── Pre-flight ─────────────────────────────────────────────────────────────
echo "========================================="
echo "  wiki_test 知识库更新"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
if $FULL; then
  echo "  模式: 全量重建"
elif $CHECK_ONLY; then
  echo "  模式: 仅检测变更"
elif $ANNOTATE_ONLY; then
  echo "  模式: 仅标注 + embeddings"
else
  echo "  模式: 增量更新"
fi
echo "========================================="

# ── Step 1: Pull from WebDAV ───────────────────────────────────────────────
if ! $ANNOTATE_ONLY; then
  echo ""
  echo "[1/5] 从 WebDAV 同步文档..."
  python3 scripts/import_webdav_raw.py --user jjb --password 'jjb@115799'

  if $CHECK_ONLY; then
    # Check what changed by comparing webdav_import_state
    STATE_FILE="index_store/webdav_import_state.json"
    if [ -f "$STATE_FILE" ]; then
      CHANGED=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    s = json.load(f)
changed = s.get('changed_files', s.get('new_files', []))
if changed:
    print(f'变更文件: {len(changed)}')
    for f in changed[:5]:
        print(f'  - {f}')
    if len(changed) > 5:
        print(f'  ... 及其他 {len(changed)-5} 个')
else:
    print('无变更')
")
      echo "$CHANGED"
    fi
    echo ""
    echo "✅ 检测完成"
    exit 0
  fi

  # ── Step 2: Import Excel into SQLite ──────────────────────────────────────
  echo ""
  echo "[2/6] 导入 Excel 数据到 SQLite..."
  if [ -f scripts/build_excel_knowledge.py ]; then
    python3 scripts/build_excel_knowledge.py 2>/dev/null && echo "  OK" || echo "  [WARN] Excel 导入部分失败"
  fi

  # ── Step 3: Rebuild card metadata ──────────────────────────────────────────
  echo ""
  echo "[3/6] 重建卡片元数据..."
  python3 scripts/build_v2_semantic_metadata.py

  # ── Step 4: Rebuild indexes ────────────────────────────────────────────────
  echo ""
  echo "[4/6] 重建索引..."

  # Path index (JS)
  if [ -f scripts/build_path_index.js ]; then
    node scripts/build_path_index.js 2>/dev/null || echo "  [SKIP] path_index"
  fi

  # Model index (JS)
  if [ -f scripts/build_model_index.js ]; then
    node scripts/build_model_index.js 2>/dev/null || echo "  [SKIP] model_index"
  fi

  # FTS5 index
  if [ -f scripts/build_fts5_index.py ]; then
    python3 scripts/build_fts5_index.py 2>/dev/null || echo "  [SKIP] fts5_index"
  fi

  # QMD bridge
  if [ -f scripts/build_qmd_bridge_index.py ]; then
    python3 scripts/build_qmd_bridge_index.py 2>/dev/null || echo "  [SKIP] qmd_bridge"
  fi
fi

# ── Step 4: Annotate cards (only unannotated) ───────────────────────────────
echo ""
echo "[5/6] 标注卡片..."

# Detect how many cards need annotation
UNANNOTATED=$(python3 -c "
import json, os
cards_dir = 'cards/sections'
if not os.path.isdir(cards_dir):
    print(0)
    exit()
count = 0
for f in os.listdir(cards_dir):
    if not f.endswith('.json'): continue
    c = json.loads(open(os.path.join(cards_dir, f)).read())
    sem = c.get('semantic', {})
    if not sem.get('intent_tags'):
        count += 1
print(count)
")

if [ "$UNANNOTATED" -gt 0 ]; then
  echo "  发现 $UNANNOTATED 张卡片未标注，开始标注..."
  python3 scripts/annotate_cards.py --doc-type solution
else
  echo "  所有卡片已标注，跳过"
fi

# ── Step 5: Rebuild embeddings ──────────────────────────────────────────────
echo ""
echo "[6/6] 重建向量索引..."
python3 scripts/build_embeddings.py

# ── Audit (optional) ────────────────────────────────────────────────────────
if [ -f scripts/audit_solution_cards.py ]; then
  python3 scripts/audit_solution_cards.py 2>/dev/null || echo "  [SKIP] audit"
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  ✅ 更新完成"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="

# Stats
python3 -c "
import json, os
cards_dir = 'cards/sections'
total = 0
annotated = 0
if os.path.isdir(cards_dir):
    for f in os.listdir(cards_dir):
        if f.endswith('.json'):
            total += 1
            c = json.loads(open(os.path.join(cards_dir, f)).read())
            if c.get('semantic', {}).get('intent_tags'):
                annotated += 1
print(f'卡片总数: {total}')
print(f'已标注:   {annotated} ({annotated/total*100:.0f}%)' if total else '卡片总数: 0')
# Show intent distribution
from collections import Counter
ic = Counter()
if os.path.isdir(cards_dir):
    for f in os.listdir(cards_dir):
        if not f.endswith('.json'): continue
        c = json.loads(open(os.path.join(cards_dir, f)).read())
        for tag in c.get('semantic', {}).get('intent_tags', []):
            ic[tag] += 1
print('标注分布:')
for tag, cnt in ic.most_common(5):
    print(f'  {tag}: {cnt}')
" 2>/dev/null || true

echo ""
echo "下次文档更新时，直接运行: bash scripts/update.sh"
