#!/usr/bin/env bash
# 同步wiki_test完整数据到WebDAV备份

set -euo pipefail

# 自动检测脚本所在目录的父目录（即项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_DIR="$PROJECT_ROOT"
BACKUP_NAME="wiki_test_backup_$(date +%Y%m%d_%H%M%S)"
REMOTE_DIR="/下载/temp/${BACKUP_NAME}"
WEBDAV_URL="https://dav.jjb115799.fnos.net"
USER="jjb"
PASSWORD="jjb@115799"

echo "=== 开始同步知识库到WebDAV ==="
echo "源目录: $SOURCE_DIR"
echo "目标: $WEBDAV_URL${REMOTE_DIR}"
echo "备份名: $BACKUP_NAME"
echo ""

# 创建临时压缩包
echo "[1/4] 正在压缩数据..."
TAR_FILE="${TMPDIR:-/tmp}/${BACKUP_NAME}.tar.gz"
cd "$(dirname "$SOURCE_DIR")"
tar --exclude='.git' -czf "$TAR_FILE" "$(basename "$SOURCE_DIR")"
TAR_SIZE=$(du -h "$TAR_FILE" | cut -f1)
echo "压缩完成: $TAR_FILE ($TAR_SIZE)"
echo ""

# 创建WebDAV目录
echo "[2/4] 创建WebDAV目录..."
curl -s -u "${USER}:${PASSWORD}" -X MKCOL "${WEBDAV_URL}${REMOTE_DIR}" || echo "目录可能已存在，继续..."
echo ""

# 上传压缩包
echo "[3/4] 上传数据到WebDAV..."
echo "正在上传 $TAR_SIZE 的数据，请稍等..."
curl -s -u "${USER}:${PASSWORD}" -T "$TAR_FILE" "${WEBDAV_URL}${REMOTE_DIR}/wiki_test_full.tar.gz"
echo "上传完成"
echo ""

# 生成目录清单
echo "[4/4] 生成目录清单..."
MANIFEST_FILE="${TMPDIR:-/tmp}/${BACKUP_NAME}_manifest.txt"
cat > "$MANIFEST_FILE" << MANIFEST
知识库备份信息
================
备份时间: $(date '+%Y-%m-%d %H:%M:%S')
备份名称: ${BACKUP_NAME}
源目录大小: $(du -sh "$SOURCE_DIR" | cut -f1)
压缩包大小: $TAR_SIZE

目录结构:
$(find "$SOURCE_DIR" -maxdepth 2 -type d | head -50)

数据文件统计:
- $(find "$SOURCE_DIR" -type f | wc -l) 个文件
- $(find "$SOURCE_DIR" -type f -name "*.json" | wc -l) 个JSON文件
- $(find "$SOURCE_DIR" -type f -name "*.md" | wc -l) 个Markdown文件
- $(find "$SOURCE_DIR" -type f -name "*.xlsx" | wc -l) 个Excel文件
- $(find "$SOURCE_DIR" -type f -name "*.js" | wc -l) 个JS脚本
- $(find "$SOURCE_DIR" -type f -name "*.py" | wc -l) 个Python脚本
MANIFEST

curl -s -u "${USER}:${PASSWORD}" -T "$MANIFEST_FILE" "${WEBDAV_URL}${REMOTE_DIR}/manifest.txt"

# 清理临时文件
rm -f "$TAR_FILE" "$MANIFEST_FILE"

echo ""
echo "=== 备份完成 ==="
echo "备份位置: ${WEBDAV_URL}${REMOTE_DIR}/"
echo ""
echo "文件列表:"
echo "  - wiki_test_full.tar.gz (完整数据包)"
echo "  - manifest.txt (目录清单)"
