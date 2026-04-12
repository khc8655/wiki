#!/bin/bash
# GitHub 自动推送脚本
# 使用方法: ./push_to_github.sh [提交信息]

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 读取 token
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.github_token" ]; then
    TOKEN=$(cat "$SCRIPT_DIR/.github_token" | tr -d '[:space:]')
else
    echo -e "${RED}错误: 未找到 .github_token 文件${NC}"
    exit 1
fi

# 设置远程仓库 URL（使用 token）
REMOTE_URL="https://${TOKEN}@github.com/khc8655/wiki.git"

echo -e "${YELLOW}正在配置 GitHub 远程仓库...${NC}"
git remote set-url origin "$REMOTE_URL"

# 获取提交信息
if [ -z "$1" ]; then
    COMMIT_MSG="Update wiki content - $(date '+%Y-%m-%d %H:%M:%S')"
else
    COMMIT_MSG="$1"
fi

# 检查是否有变更
if git diff --quiet && git diff --staged --quiet; then
    echo -e "${YELLOW}没有检测到变更，跳过提交${NC}"
else
    echo -e "${YELLOW}正在添加变更...${NC}"
    git add .
    
    echo -e "${YELLOW}正在提交: ${COMMIT_MSG}${NC}"
    git commit -m "$COMMIT_MSG"
fi

# 推送
echo -e "${YELLOW}正在推送到 GitHub...${NC}"
git push origin main

echo -e "${GREEN}✓ 推送成功!${NC}"

# 恢复远程 URL（移除 token，避免留在配置中）
git remote set-url origin "https://github.com/khc8655/wiki.git"
