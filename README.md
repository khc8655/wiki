# wiki_test v1.1

一个可迁移的知识库框架仓库。

这个仓库在 GitHub 上只保存：
- 程序脚本
- 入库规则
- 检索规则
- 使用说明

不保存：
- 原始文档
- 卡片数据
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
- `cards/README.md`：卡片层说明
- `AGENTS.md`、`README.md`、`CHANGELOG.md`
- `.gitignore`
- `push_to_github.sh`

### 不会同步到 GitHub
- `raw/`
- `cards/sections/`
- `cards/manifest.json`
- `cards/card_metadata.v1.json`
- `cards/card_metadata.v2.json`
- `index_store/`
- `relations/`
- `tree/`
- `topics/`
- `wiki/`
- `backups/`

---

## 2. 原始文档来源

当前默认原始文档来自 WebDAV：

- 根目录：`/下载/temp/wiki_raw/`
- 子目录一：`方案文档`
- 子目录二：`产品更新文档`

文档类型映射：
- `方案文档` -> `solution`
- `产品更新文档` -> `release_note`

说明：
- `solution` 文档走细粒度切片
- `release_note` 文档走更新说明查询链路

---

## 3. 日常使用

### 3.1 轻量刷新，默认用这个

```bash
cd /workspace/wiki_test
./scripts/refresh_from_webdav.sh
```

这个脚本会做：
1. 从 WebDAV 重新拉取 `wiki_raw` 文档
2. 清空并重建本地 `raw/`
3. 重建 `cards/sections/`
4. 重建 `cards/manifest.json`
5. 重建 `cards/card_metadata.v2.json`
6. 重建以下检索相关索引：
   - `index_store/fts5_cards.db`
   - `index_store/qmd_bridge.db`
   - `index_store/path_siblings_index.v2.json`
   - `index_store/model_path_index.v2.json`

适用场景：
- WebDAV 新增或替换原始文档
- 调整入库规则后重新刷卡片
- 调整检索规则后重建基础索引

---

### 3.2 完整重建

```bash
cd /workspace/wiki_test
./scripts/rebuild_from_webdav.sh
```

这个脚本会先执行轻量刷新，然后再补跑：
- `tree/knowledge_tree.v2.json`
- `tree/knowledge_tree.v2.1.json`
- 相关 title / paragraph / stats 文件

适用场景：
- 需要连知识树一起重建
- 需要验证完整派生产物

---

## 4. 卡片关联刷新规则

如果这次变更不仅影响卡片切片，还影响“卡片之间的关联结果”，需要额外刷新 relations 层。

### 4.1 什么情况下要刷卡片关联

满足以下任一情况，建议补刷：
- 新增了一批方案类文档，里面包含新的产品型号、能力、场景、组件关系
- 修改了切片规则，导致 section 边界变化明显
- 修改了 `cards/card_metadata.v1.json` 的生成逻辑或依赖字段
- 修改了产品能力、组件、场景、数据流相关术语规则
- 需要重新生成 `relations/` 目录下的关联结果

### 4.2 刷新顺序

先刷新卡片，再刷新关联：

```bash
cd /workspace/wiki_test
./scripts/refresh_from_webdav.sh
python3 scripts/build_v1_indexes.py
python3 scripts/enrich_relations_v1.py
python3 scripts/refine_relations_v1_1.py
```

### 4.3 这些脚本分别做什么

- `python3 scripts/build_v1_indexes.py`
  - 重建 `cards/card_metadata.v1.json`
  - 重建 V1 的 keyword / alias / product / topic / scenario / intent 等索引

- `python3 scripts/enrich_relations_v1.py`
  - 生成第一版关联结果
  - 输出到 `relations/`，例如：
    - `relation_graph.v1.json`
    - `product_to_components.v1.json`
    - `product_to_capabilities.v1.json`
    - `capability_to_scenarios.v1.json`

- `python3 scripts/refine_relations_v1_1.py`
  - 在 V1 基础上做 typed relation refine
  - 增加置信度和更干净的关系拆分
  - 输出例如：
    - `relation_graph.v1.1.json`
    - `product_to_components.v1.1.json`
    - `product_to_external_devices.v1.1.json`
    - `product_to_capabilities.v1.1.json`
    - `capability_to_scenarios.v1.1.json`

### 4.4 默认策略

当前默认策略是：
- **日常刷新不自动刷关联关系**
- 只有在明确需要 relation 结果时，才手动补跑上面这三步

这样做的目的是：
- 缩短日常刷新时间
- 避免每次都重建不必要的派生产物
- 让 GitHub 继续保持“规则仓库”而不是“数据仓库”

---

## 5. 查询入口

### 默认入口
```bash
node scripts/query_default.js --brief "你的问题"
```

### 方案类问题
```bash
node scripts/query_v2.js --json "跨云互通"
python3 scripts/query_qmd_bridge.py "跨云互通" -c solution_cards -c solution_topics --brief
```

### 更新说明类问题
```bash
python3 scripts/query_qmd_bridge.py "AE700 新功能" -c release_notes --brief
```

### 宽召回补充
```bash
python3 scripts/query_fts5.py "关键词" --brief
```

---

## 6. GitHub 推送

推送时只会同步程序和规则：

```bash
cd /workspace/wiki_test
./push_to_github.sh "你的提交信息"
```

当前 push 脚本会：
1. 只添加白名单路径
2. 把原始数据和派生数据从 Git 索引中移除
3. 推送到 GitHub `main`

GitHub 的定位是：
- 可迁移
- 可复用
- 可在别的地方重新接 WebDAV 后直接使用

不是线上数据备份仓库。

---

## 7. 推荐工作流

### 只更新原始文档
1. 把文档放进 WebDAV `wiki_raw`
2. 执行：
   ```bash
   ./scripts/refresh_from_webdav.sh
   ```

### 更新了切片/检索规则
1. 修改 `scripts/`、`qmd_bridge/`、`query_router/`
2. 执行：
   ```bash
   ./scripts/refresh_from_webdav.sh
   ```
3. 如需同步框架到 GitHub：
   ```bash
   ./push_to_github.sh "chore: update rules"
   ```

### 更新了路由规则

知识库在日常使用中，需要根据真实问法持续刷新路由，不是只做一次静态配置。

**路由规则文件：**
- `query_router/routes.json`：基础路由
- `query_router/routes.v1.json`：扩展路由

**什么情况下要刷新路由：**
- 用户高频问法命中不稳定
- 新增了新的产品、能力、场景、版本问法
- 同一个问题总是先落到错误主题
- 需要补充别名、意图词、负向词、优先级

**怎么改：**
- 在 `query_router/routes*.json` 里补：
  - `intent_aliases`
  - `subtopics`
  - `priority`
  - 必要时补 `required_terms_any`、`negative_terms`
  - 必要时补 `high_priority_cards`
- 如果路由依赖查询逻辑中的显式规则，还要同步检查：
  - `scripts/query_default.js`
  - `scripts/query_v2_core.js`

**改完之后怎么刷新：**
```bash
cd /workspace/wiki_test
./scripts/refresh_from_webdav.sh
```

说明：
- 路由文件本身属于 GitHub 应同步内容
- 路由刷新不等于关联刷新
- 只有在卡片边界或关系术语也变了时，才需要额外补刷关联层

### 更新了关联规则
1. 先刷新卡片：
   ```bash
   ./scripts/refresh_from_webdav.sh
   ```
2. 再补刷关联：
   ```bash
   python3 scripts/build_v1_indexes.py
   python3 scripts/enrich_relations_v1.py
   python3 scripts/refine_relations_v1_1.py
   ```

---

## 8. 版本历史

### v1.1 (2026-04-22)
新增三类Excel数据源查询：
- **pricing** (价格查询)：支持产品报价、停产信息、替代型号查询
- **comparison** (产品对比)：支持终端功能对比矩阵查询
- **proposal** (招标参数)：支持三阶段描述（询价/方案/招投标）查询

数据来源：
- 2026年小鱼易连产品报价体系.xlsx
- 风铃项目报价清单2026-0306.xlsx
- 项目各阶段报价描述清单2026.xlsx
- 小鱼易连视频终端对比及功能介绍.xlsx

实现脚本：
- `scripts/build_excel_knowledge.py` - Excel解析与索引构建
- `scripts/query_excel_knowledge.py` - 三类查询接口
- `excel_store/docs/` - 查询指南与分类策略文档

### v1.0 (2026-04-20)
初始版本，支持：
- solution (方案文档) 细粒度切片与检索
- release_notes (更新文档) 查询链路
- 语义检索与路由系统
