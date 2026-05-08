# 知识库文件处理系统

## 架构概览

```
用户文档 → NAS挂载 → 扫描检测 → 转换处理 → 入库索引
         ↓
    /mnt/mydata/wiki_source/
    ├── 方案文档/        → docx/pdf → markitdown → md
    ├── 产品更新文档/    → docx/pdf → markitdown → md
    ├── Excel/          → xlsx → 直接入库
    └── PPT/            → pptx → 文本提取 → md
```

## 目录结构

```
/mnt/mydata/wiki_source/          # NAS源目录
├── 方案文档/                      # 方案类文档
│   ├── *.docx
│   └── *.pdf
├── 产品更新文档/                  # 更新类文档
│   ├── *.docx
│   └── *.pdf
├── Excel/                        # Excel表格
│   └── *.xlsx
└── PPT/                          # PPT演示文稿
    └── *.pptx

/home/jjb/wiki/                   # 知识库主目录
├── raw/                          # 转换后的markdown文件
├── cards/sections/               # 结构化卡片
├── db/excel_store.db             # Excel数据库
├── index_store/                  # 索引+向量
└── scripts/
    └── import_from_nas.py        # 导入脚本
```

## 使用方法

### 1. 挂载NAS（如未自动挂载）

```bash
# SMB挂载示例
sudo mount -t cifs //NAS_IP/wiki /mnt/mydata -o username=xxx,password=xxx

# NFS挂载示例
sudo mount NAS_IP:/volume1/wiki /mnt/mydata
```

### 2. 扫描NAS文件

```bash
python3 scripts/import_from_nas.py --scan
```

### 3. 执行导入

```bash
# 增量导入（只处理新增和变更的文件）
python3 scripts/import_from_nas.py

# 强制重新导入所有文件
python3 scripts/import_from_nas.py --force
```

### 4. 查看导入状态

```bash
python3 scripts/import_from_nas.py --status
```

### 5. 重建索引（导入后）

```bash
python3 scripts/import_webdav_raw.py  # 重建卡片
python3 scripts/build_embeddings.py   # 重建向量
```

## 文件处理流程

### docx/pdf → markdown

1. 使用 `markitdown` 转换为markdown
2. 标准化文本格式
3. 保存到 `raw/` 目录
4. 自动生成卡片和索引

### xlsx → SQLite

1. 直接读取Excel文件
2. 解析为结构化数据
3. 存入 `db/excel_store.db`
4. 支持价格/对比/方案查询

### pptx → markdown

1. 提取PPT中的文本内容
2. 按页面组织为markdown
3. 保存到 `raw/` 目录

## 更新机制

### 增量更新

脚本会记录每个文件的SHA256哈希值。下次运行时：
- **新增文件**：哈希值不存在 → 处理并导入
- **变更文件**：哈希值不同 → 重新处理
- **未变文件**：哈希值相同 → 跳过

### 手动触发更新

```bash
# 1. 将新文件放入NAS对应目录
cp new_doc.docx /mnt/mydata/wiki_source/方案文档/

# 2. 运行导入
python3 scripts/import_from_nas.py

# 3. 重建索引
python3 scripts/import_webdav_raw.py
python3 scripts/build_embeddings.py
```

## 状态文件

导入状态保存在 `index_store/nas_import_state.json`：

```json
{
  "files": {
    "方案文档/xxx.docx": {
      "hash": "sha256...",
      "imported_at": "2026-05-08T07:09:00",
      "output": "01-xxx.md"
    }
  },
  "last_import": "2026-05-08T07:09:00",
  "last_import_count": 5
}
```

## 注意事项

1. **文件命名**：建议使用有意义的文件名，会自动添加序号前缀
2. **目录结构**：保持四个子目录结构不变
3. **文件格式**：支持 `.docx`, `.pdf`, `.xlsx`, `.xls`, `.pptx`
4. **备份**：每次导入前会自动备份状态文件到 `backups/`
5. **编码**：所有输出文件使用UTF-8编码

## 故障排除

### markitdown转换失败

```bash
# 检查markitdown是否安装
/home/jjb/wiki/.venv/bin/markitdown --version

# 手动测试转换
/home/jjb/wiki/.venv/bin/markitdown test.docx
```

### Excel入库失败

```bash
# 检查import_excel.py脚本
python3 scripts/import_excel.py test.xlsx
```

### 磁盘空间不足

```bash
# 检查磁盘空间
df -h /mnt/mydata
df -h /home/jjb/wiki

# 清理旧备份
rm -rf backups/pre_nas_import_*.json
```
