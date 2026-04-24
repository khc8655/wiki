# wiki_test API 文档

## 1. 快速查询入口

### query_fast.py

主查询脚本，支持智能路由和 JSON 输出。

**用法**：
```bash
python scripts/query_fast.py "查询内容" [--json]
```

**参数**：
- `query` (required): 查询文本
- `--json` (optional): 输出 JSON 格式

**返回示例**：
```json
{
  "query": "AE800多少钱",
  "intent": "price",
  "models": ["AE800"],
  "results": [
    {
      "product_name": "小鱼易连AE800套装",
      "price_raw": "¥38,000",
      "source": "产品价格表2026.xlsx | 硬件终端 | row 15",
      "hit_rate": 1.0
    }
  ]
}
```

**支持的查询类型**：
- 价格查询：`"AE800价格"`、`"多少钱"`
- 对比查询：`"XE800 vs AE800"`、`"对比"`
- 参数查询：`"AE800参数"`、`"规格"`
- 配件查询：`"AE800配件"`、`"附件"`
- 行业应用：`"公安行业"`、`"应用场景"`
- 软硬对比：`"软件端硬件端对比"`

---

## 2. 测试脚本

### run_fast_tests.py

运行全部测试用例，验证查询链路。

**用法**：
```bash
python scripts/run_fast_tests.py
```

**测试用例**：
1. AE800 价格查询
2. AI 报价分类
3. 按年云会议室
4. AE800 配件
5. PE8000 停产
6. XE800 vs AE800 对比
7. GE600 招标参数
8. 公安行业应用
9. 软件端 vs 硬件端对比

---

### benchmark_fast_queries.py

性能基准测试。

**用法**：
```bash
python scripts/benchmark_fast_queries.py
```

**输出**：
```
AE800的价格是多少？        avg=0.052s  min=0.052s  max=0.052s
AI相关的报价分类有哪些？    avg=0.047s  min=0.046s  max=0.047s
...
```

---

## 3. 数据同步脚本

### refresh_from_webdav.sh

从 WebDAV 同步原始文档和卡片数据。

**用法**：
```bash
./scripts/refresh_from_webdav.sh
```

**环境变量**：
```bash
export WEBDAV_USER="jjb"
export WEBDAV_PASS="jjb@115799"
```

**功能**：
- 拉取 `wiki_raw` 原始文档
- 生成卡片数据
- 重建索引

---

### import_webdav_raw.py

导入原始 Markdown 文档。

**用法**：
```bash
python scripts/import_webdav_raw.py --user jjb --password 'jjb@115799'
```

---

### import_webdav_annotations.py

导入标注层数据。

**用法**：
```bash
python scripts/import_webdav_annotations.py --user jjb --password 'jjb@115799'
```

---

## 4. 数据处理脚本

### merge_annotations_to_cards.py

将标注层深度融合到卡片 metadata。

**用法**：
```bash
# 预览（不实际写入）
python scripts/merge_annotations_to_cards.py --dry-run

# 实际执行
python scripts/merge_annotations_to_cards.py
```

**效果**：
- 读取 `index_store/annotation_doc_index.json`
- 将语义标签写入 `cards/sections/*.json` 的 `semantic` 字段

---

### build_excel_knowledge.py

重建 Excel 数据索引。

**用法**：
```bash
# 重建所有索引
python scripts/build_excel_knowledge.py

# 只重建特定类型
python scripts/build_excel_knowledge.py --type pricing
```

**类型**：
- `pricing`：价格数据
- `comparison`：产品对比数据
- `proposal`：招标参数数据

---

## 5. 配置管理

### setup.py

环境检查和初始化工具。

**用法**：
```bash
python setup.py                    # 完整检查
python setup.py --check            # 仅验证
python setup.py --init             # 初始化目录
python setup.py --env              # 显示环境变量
python setup.py --quickstart       # 显示快速开始指南
```

**检查项**：
- 目录结构
- Excel 数据存在
- 卡片数据存在
- WebDAV 配置
- 脚本完整性

---

## 6. 配置加载（Python API）

### config.py

统一的配置加载模块。

**用法**：
```python
from lib.config import config

# 获取路径
raw_path = config.path('sources', 'raw', 'path')
cards_path = config.path('sources', 'cards', 'path')

# 获取配置值
limit = config.get('query', 'default_limit', default=20)

# 获取 WebDAV 凭据
username, password = config.get_webdav_credentials()
```

**环境变量支持**：
```bash
# 覆盖 config.yaml 中的值
export WEBDAV_USER="user"
export WEBDAV_PASS="pass"
export WEBDAV_URL="https://..."
export WIKI_ROOT="/path/to/wiki"
export LOG_LEVEL="DEBUG"
```

---

## 7. 文件输出规范

### JSON 输出字段

**Excel 查询结果**：
```json
{
  "product_name": "产品名称",
  "price_raw": "¥价格",
  "category": "分类",
  "description": "描述",
  "source_file": "源文件名",
  "source_sheet": "工作表",
  "source_row": 行号,
  "source": "文件名 | 工作表 | row 行号",
  "hit_rate": 1.0
}
```

**卡片查询结果**（深度融合后）：
```json
{
  "id": "卡片ID",
  "title": "标题",
  "path": "文档路径",
  "doc_file": "源文档",
  "source": "文档 | 路径",
  "hit_rate": 1.0,
  "body_preview": "内容预览",
  "semantic_tags": ["标签1", "标签2"]
}
```

---

## 8. 错误处理

### 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `index_store/annotation_doc_index.json not found` | 未导入标注数据 | 运行 `import_webdav_annotations.py` |
| `cards/sections/` empty | 未生成卡片 | 运行 `refresh_from_webdav.sh` |
| `excel_store/*/records.json not found` | 未构建 Excel 索引 | 运行 `build_excel_knowledge.py` |
| `401 Not Authorized` | WebDAV 凭据错误 | 检查 `WEBDAV_USER` / `WEBDAV_PASS` |

---

## 9. 扩展开发

### 添加新查询类型

1. **修改 `query_fast.py`**：

```python
def route_query(query: str):
    # 添加意图识别规则
    if '新关键词' in query.lower():
        return 'new_type', info

# 添加查询实现
def new_type_lookup(query: str) -> List[Dict]:
    # 实现查询逻辑
    pass

# 在 main() 中添加路由
elif intent == 'new_type':
    result['results'] = new_type_lookup(query)
```

2. **更新测试用例**（`run_fast_tests.py`）

---

## 10. 参考

- 完整架构：`ARCHITECTURE.md`
- 快速开始：`QUICKSTART.md`
- 配置说明：`config.yaml`
