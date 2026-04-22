#!/usr/bin/env bash
# GitHub 自动推送脚本
# 默认只同步程序、规则与说明文档，不同步原始数据和派生结果
# 使用方法: ./push_to_github.sh [提交信息]

set -euo pipefail

COMMIT_MSG="${1:-chore: sync code and rules}"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f .github_token ]; then
  echo "❌ 未找到 .github_token"
  exit 1
fi

TOKEN="$(tr -d '\r\n' < .github_token)"
if [ -z "$TOKEN" ]; then
  echo "❌ .github_token 为空"
  exit 1
fi

REMOTE_URL="https://${TOKEN}@github.com/khc8655/wiki.git"
BRANCH="main"

# 只保留程序与规则层的同步边界
KEEP_PATHS=(
  .gitignore
  AGENTS.md
  README.md
  CHANGELOG.md
  docs
  scripts
  qmd_bridge
  query_router
  cards/README.md
  push_to_github.sh
  excel_store/docs
)

DROP_FROM_INDEX=(
  raw
  cards/sections
  cards/manifest.json
  cards/card_metadata.v1.json
  cards/card_metadata.v2.json
  index_store
  relations
  tree
  topics
  wiki
  backups
  media
)

# 先把不该上 GitHub 的内容从索引移除，但保留本地文件
for path in "${DROP_FROM_INDEX[@]}"; do
  if git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    git rm -r --cached --ignore-unmatch "$path" >/dev/null 2>&1 || true
  fi
done

# 清空暂存区，避免把数据层顺手带上去
git reset >/dev/null 2>&1 || true

# 仅添加允许同步的路径
for path in "${KEEP_PATHS[@]}"; do
  if [ -e "$path" ]; then
    git add "$path"
  fi
done

if git diff --cached --quiet; then
  echo "ℹ️ 没有需要推送到 GitHub 的程序/规则变更"
  exit 0
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$REMOTE_URL"
else
  git remote set-url origin "$REMOTE_URL"
fi

git commit -m "$COMMIT_MSG"
git push origin "$BRANCH"

git remote set-url origin "https://github.com/khc8655/wiki.git"

echo "✅ 已推送到 GitHub（仅程序和规则，不含原始/派生数据）"
