#!/usr/bin/env bash
# 从NAS刷新知识库
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=== 知识库NAS导入 ==="
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 检查NAS挂载
if ! mountpoint -q /mnt/mydata; then
    echo "[ERROR] NAS未挂载: /mnt/mydata"
    echo "请先挂载NAS: sudo mount -t cifs //NAS_IP/wiki /mnt/mydata -o username=xxx,password=xxx"
    exit 1
fi

# 2. 检查源目录
if [ ! -d "/mnt/mydata/wiki_source" ]; then
    echo "[ERROR] NAS源目录不存在: /mnt/mydata/wiki_source"
    exit 1
fi

# 3. 扫描文件
echo "扫描NAS源目录..."
python3 scripts/import_from_nas.py --scan

# 4. 执行导入
echo ""
echo "执行导入..."
python3 scripts/import_from_nas.py

# 5. 重建卡片（如果raw目录有变化）
if ls raw/*.md 1>/dev/null 2>&1; then
    echo ""
    echo "重建卡片..."
    python3 scripts/import_webdav_raw.py
fi

# 6. 重建向量索引
echo ""
echo "重建向量索引..."
python3 scripts/build_embeddings.py

echo ""
echo "=== 导入完成 ==="
