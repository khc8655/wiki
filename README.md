# wiki_test v1.1

一个可迁移的知识库框架仓库。

这个仓库在 GitHub 上只保存：
- 程序脚本
- 入库规则
- 检索规则
- 使用说明
- Excel数据源定义和原始文件

不保存：
- 原始文档（来自WebDAV）
- 生成的卡片数据
- 本地索引
- 关联结果
- 知识树和其他派生产物

---

## 1. 目录定位

### 会同步到 GitHub
- `scripts/`：入库、刷新、检索、重建脚本
- `docs/`：补充说明文档
- `qmd_bridge/`：文档类型与集合规则
- `query_router/`：查询路由规则
- `excel_store/`：Excel数据源（原始文件+索引+查询脚本）
  - `raw/`：原始Excel文件
  - `pricing/`：价格数据索引
  - `comparison/`：产品对比索引
  - `proposal/`：阶段描述索引
  - `docs/`：查询文档
- `cards/README.md`：卡片层说明
- `AGENTS.md`、`README.md`、`CHANGELOG.md`
- `.gitignore`
- `push_to_github.sh`

### 不会同步到 GitHub
- `raw/`：原始文档（来自WebDAV）
- `cards/sections/`：生成的卡片数据
- `cards/manifest.json`
- `cards/card_metadata.v*.json`
- `index_store/`
- `relations/`
- `tree/`
- `topics/`
- `wiki/`
- `backups/`
- `updates/`

---

## 2. 五类数据源

知识库支持五类数据查询：

| 类别 | 数据源 | 典型查询 |
|------|--------|----------|
| **solution** | 原始白皮书/方案文档 | "小鱼架构优势"、"跨云互通原理" |
| **release_notes** | 迭代功能文档 | "AE700新功能"、"2026年3月迭代" |
| **pricing** | 报价表Excel | "AE800多少钱"、"PE8000停产" |
| **comparison** | 产品对比Excel | "XE800与AE800对比" |
| **proposal** | 阶段描述Excel | "AE800招标参数" |

### 数据来源

**原始文档（WebDAV）**：
- 根目录：`/下载/temp/wiki_raw/`
- 子目录：`方案文档/` → `solution`
- 子目录：`产品更新文档/` → `release_note`

**Excel数据（本地）**：
- `excel_store/raw/pricing/`：报价表
- `excel_store/raw/comparison/`：对比表
- `excel_store/raw/proposal/`：阶段描述表

---

## 3. 查询路由系统 v3

### 核心设计：语义意图 + 智能多源

`scripts/query_default.js` 实现了基于用户意图的智能路由：

| 意图 | 触发条件 | 数据源 |
|------|----------|--------|
| **compare** | 两个型号 + 对比词 | `comparison` |
| **purchase** | 型号 + 价格词 | `pricing` |
| **technical_spec** | 型号 + 参数词 | `comparison` + `proposal` + `pricing` |
| **procurement** | 型号 + 招标词 | `proposal` + `comparison` |
| **product_overview** | 仅型号（模糊） | `pricing` + `comparison` + `proposal` |
| **semantic** | 无明确匹配 | `solution` + `release_notes` |

### 核心原则：宁多勿少

- **明确查询**：精准单源（如"AE800多少钱"→pricing）
- **模糊查询**：自动多源（如"AE800参数"→3个源）

### 使用方式

```bash
cd /workspace/wiki_test

# 默认查询（自动路由）
node scripts/query_default.js "AE800多少钱"

# 查看意图分析
node scripts/query_default.js "XE800与AE800对比"

# JSON输出
node scripts/query_default.js --json "AE800参数"
```

---

## 4. Excel数据查询

### 构建索引

```bash
# 构建所有Excel索引
python3 scripts/build_excel_knowledge.py

# 构建单类索引
python3 scripts/build_excel_knowledge.py --type pricing
```

### 直接查询

```bash
# 价格查询
python3 scripts/query_excel_knowledge.py "AE800" -t pricing

# 对比查询
python3 scripts/query_excel_knowledge.py "XE800" -t comparison

# 阶段描述查询
python3 scripts/query_excel_knowledge.py "AE800" -t proposal
```

---

## 5. 日常使用

### 5.1 轻量刷新（原始文档变更）

```bash
cd /workspace/wiki_test
./scripts/refresh_from_webdav.sh
```

执行内容：
1. 从 WebDAV 拉取 `wiki_raw` 文档
2. 重建本地 `raw/`
3. 重建 `cards/sections/`
4. 重建索引文件

### 5.2 完整重建

```bash
cd /workspace/wiki_test
./scripts/rebuild_from_webdav.sh
```

额外重建：
- `tree/knowledge_tree.v*.json`
- title / paragraph / stats 文件

### 5.3 卡片关联刷新

如需刷新卡片间关联关系：

```bash
cd /workspace/wiki_test
./scripts/refresh_from_webdav.sh
python3 scripts/build_v1_indexes.py
python3 scripts/enrich_relations_v1.py
python3 scripts/refine_relations_v1_1.py
```

---

## 6. GitHub 推送

只同步程序和规则：

```bash
cd /workspace/wiki_test
./push_to_github.sh "提交信息"
```

### 推送内容
- ✅ 脚本、文档、配置文件
- ✅ Excel原始文件和索引
- ❌ 生成的卡片数据
- ❌ 派生索引和知识树

### 网络问题处理

如遇TLS错误，先配置：
```bash
git config http.postBuffer 524288000
git config http.version HTTP/2
```

---

## 7. 版本历史

### v1.1 (2026-04-22)

**新增：语义意图路由 v3**

实现了三种查询方案的对比测试，最终采用"方案3：语义意图+智能多源"：
- 7种意图识别（compare/purchase/technical_spec/procurement/feature/product_overview/semantic）
- 置信度评分（0-100分）
- 模糊查询自动多源召回

**新增：三类Excel数据源**
- **pricing**：267条价格记录
- **comparison**：320条对比记录
- **proposal**：24条阶段描述记录

新增脚本：
- `scripts/query_default.js` - 语义意图路由
- `scripts/compare_approaches.py` - 方案对比测试
- `excel_store/docs/` - 查询优化文档

### v1.0 (2026-04-20)

初始版本：
- solution (方案文档) 细粒度切片
- release_notes (更新文档) 查询链路
- 基础语义检索系统
