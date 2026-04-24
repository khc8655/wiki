# wiki_test 架构设计文档

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Query Layer                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Query Input │→ │ Intent      │→ │ Router                  │  │
│  │ (User)      │  │ Classifier  │  │ (Excel/Cards/Mixed)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Excel Store  │     │  Cards Store    │     │  Dual-Path      │
│  (结构化数据)  │     │  (文档切片)      │     │  Retrieval      │
├───────────────┤     ├─────────────────┤     │  (深度融合)      │
│ pricing/      │     │ sections/*.json │     └─────────────────┘
│ comparison/   │     │                 │              │
│ proposal/     │     │  + semantic     │              ▼
└───────────────┘     │    metadata     │     ┌─────────────────┐
       │              └─────────────────┘     │  Result         │
       │                       │              │  Ranker         │
       │                       ▼              └─────────────────┘
       │              ┌─────────────────┐              │
       │              │  Annotation     │              ▼
       │              │  Layer          │     ┌─────────────────┐
       │              │  (Semantic      │     │  Output with    │
       │              │   Tags)         │     │  Source &       │
       │              └─────────────────┘     │  Hit Rate       │
       │                       │              └─────────────────┘
       └───────────────────────┴──────────────────────────────┘
```

## 2. 数据流

### 2.1 入库流程

```
Raw Documents → Card Generation → Semantic Annotation → Card Metadata
                    ↓                       ↓
              cards/sections/      annotation_doc_index.json
                    ↓
            merge_annotations_to_cards.py
                    ↓
              Cards with semantic tags
```

### 2.2 查询流程

```
User Query → Intent Classification → Data Source Selection
                                              ↓
                     ┌────────────────────────┼────────────────────────┐
                     ▼                        ▼                        ▼
              Excel Lookup              Card Text Match          Semantic Tag Match
                     │                        │                        │
                     └────────────────────────┴────────────────────────┘
                                              ↓
                                       Result Ranking
                                              ↓
                                    Output (source + hit_rate)
```

## 3. 核心组件

### 3.1 Intent Classifier

位置：`scripts/query_fast.py:route_query()`

识别以下意图：

| Intent | Trigger | Data Source |
|--------|---------|-------------|
| price | 型号 + 价格词 | excel_store/pricing |
| compare | 多型号 + 对比词 | excel_store/comparison |
| proposal | 型号 + 招标词 | excel_store/proposal + comparison |
| accessory | 型号 + 配件词 | excel_store/pricing |
| police_scene | "公安"关键词 | cards/sections (公安文档优先) |
| software_hardware | "软件端" + "硬件端" | cards/sections (对比文档优先) |
| ai_pricing | "AI" + "报价" | excel_store/pricing |
| yearly_room | 会议室 + 按年 | excel_store/pricing |

### 3.2 Dual-Path Retrieval

位置：`scripts/query_fast.py:search_cards_keywords()`

```python
# Path 1: Original text matching (weight: 15)
for term in query_terms:
    if term in card_body:
        score += 15

# Path 2: Semantic tag matching (weight: 25)
for term in query_terms:
    if term matches card.semantic_tags:
        score += 25  # Higher weight for semantic match
```

### 3.3 Annotation Layer

**原始设计**：旁路索引（单独存储）
- 位置：`index_store/annotation_doc_index.json`
- 用途：查询时加权

**深度融合后**：卡片原生 metadata
- 位置：`cards/sections/*.json` 中的 `semantic` 字段
- 包含：
  - `intent_tags`: 意图标签
  - `feature_tags`: 功能标签
  - `concept_tags`: 概念标签
  - `scenario_tags`: 场景标签（如 police）
  - `doc_types`: 文档类型
  - `boost_terms`: 增强词

## 4. 配置系统

### 4.1 配置文件

`config.yaml`：
```yaml
workspace:
  root: "${WIKI_ROOT:-auto}"      # 支持环境变量
  data_dir: "${WIKI_DATA_DIR:-./data}"

webdav:
  username: "${WEBDAV_USER:-}"    # 从环境读取
  password: "${WEBDAV_PASS:-}"
```

### 4.2 配置加载

```python
from lib.config import config

# 获取路径
raw_path = config.path('sources', 'raw', 'path')

# 获取 WebDAV 凭据
username, password = config.get_webdav_credentials()
```

## 5. 扩展点

### 5.1 添加新的查询意图

在 `query_fast.py:route_query()` 中添加：

```python
if '新关键词' in q:
    return 'new_intent', info
```

然后实现对应的 lookup 函数：

```python
def new_intent_lookup(query: str) -> List[Dict]:
    # 实现查询逻辑
    pass
```

### 5.2 添加新的数据源

在 `config.yaml` 中添加配置：

```yaml
sources:
  excel:
    new_source: "./excel_store/new_source"
```

创建数据目录并生成索引：

```bash
mkdir -p excel_store/new_source
python3 scripts/build_excel_knowledge.py  # 或自定义脚本
```

## 6. 性能优化

### 6.1 缓存策略

- `@lru_cache`：用于 Excel 数据加载
- 索引文件：本地 JSON/DB，避免重复解析

### 6.2 查询优化

| 优化点 | 实现 |
|--------|------|
| 意图预判 | 先匹配关键词，再执行查询 |
| 分层召回 | 优先 Excel（结构化），其次 Cards（非结构化） |
| 语义加权 | 标注标签匹配权重高于文本匹配 |
| 结果截断 | 默认返回 top 20 |

### 6.3 基准

```bash
python3 scripts/benchmark_fast_queries.py
```

预期性能：
- Excel 查询：0.04-0.05s
- 知识卡片查询：0.09-0.10s

## 7. 质量保证

### 7.1 测试用例

位置：`scripts/run_fast_tests.py`

覆盖场景：
1. AE800 价格查询
2. AI 报价分类
3. 按年云会议室
4. AE800 配件
5. PE8000 停产
6. XE800 vs AE800 对比
7. GE600 招标参数
8. 公安行业应用
9. 软件端 vs 硬件端对比

### 7.2 输出规范

每个结果必须包含：
- `source`: 文档出处（文件名 | 工作表 | 行号）
- `hit_rate`: 匹配度（0.0-1.0）
- 深度融合后：`semantic_tags`（可选）

### 7.3 验证脚本

```bash
python3 setup.py --check    # 环境检查
python3 setup.py --init     # 初始化
```

## 8. 部署模式

### 8.1 本地开发

```bash
export WEBDAV_USER="jjb"
export WEBDAV_PASS="jjb@115799"
./scripts/refresh_from_webdav.sh
python3 scripts/merge_annotations_to_cards.py
```

### 8.2 无 WebDAV 模式

手动准备数据：
- `raw/`：原始 Markdown 文件
- `excel_store/`：JSON 格式的 Excel 索引
- `cards/sections/`：卡片文件

### 8.3 GitHub 同步

```bash
./push_to_github.sh "commit message"
```

同步内容：
- ✅ 脚本、配置、文档
- ✅ Excel 索引（JSON）
- ❌ 生成的卡片数据
- ❌ 派生产物

## 9. 版本演进

### v1.0 → v1.1
- 新增：Excel 数据源
- 新增：语义意图路由

### v1.1 → v1.2（深度融合）
- 新增：GLM-4-9B 标注层
- 重构：双路召回（原文 + 语义）
- 改进：配置化设计

### 未来方向
- 向量检索层
- 多轮对话支持
- 自动标注 pipeline

## 10. 参考

- 配置文档：`config.yaml`
- 快速上手：`QUICKSTART.md`
- Agent 工作流：`AGENTS.md`
- API 文档：`scripts/` 中的 docstrings
