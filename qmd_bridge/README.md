# QMD Bridge 实验层

这是给 `wiki_test` 加的一层 **QMD 风格集合检索入口**。

这次又进一步按你的想法拆成两类文档：

- **方案文档**，用于日常写方案、写材料时召回
- **更新说明文档**，用于查询具体功能、型号、版本变化

核心原则：

- 保留现有四层知识库结构不动
- 同一个知识库框架内，按 `solution / release_note` 两套规则处理
- 方案文档走细粒度召回
- 更新说明走粗粒度召回，不切得太散

## 为什么这样拆

现有知识库强在：
- 原文可追溯
- 结构化 cards 清晰
- topic/wiki 可沉淀稳定结论

这层补的是：
- 文档类型分流
- collection-aware 检索
- 更像 QMD 的 `search / get context / files` 使用方式

## 当前映射

| collection | 对应目录 | 文档类型 | 用途 |
|---|---|---|---|
| `solution_cards` | `cards/sections/*.json` | solution | 方案文档主证据层，细粒度召回 |
| `solution_topics` | `topics/*.md` | solution | 方案主题入口层 |
| `solution_wiki` | `wiki/*.md` | solution | 方案沉淀结论层 |
| `release_notes` | `raw/*.md` 中被标记为 release_note 的文档 | release_note | 更新说明粗粒度召回层 |

配套文件：

- `qmd_bridge/doc_profiles.json`：文档类型声明
- `qmd_bridge/collections.json`：collection 映射

> 说明：`raw/*.bin` 仍然保持原样，不直接纳入这个实验索引。

## 切分策略

### 方案文档
- `doc_type = solution`
- `chunk_strategy = fine`
- 主要依赖已有 `cards/sections/*.json`
- 适合按能力、架构、组件、场景细切

### 更新说明文档
- `doc_type = release_note`
- `chunk_strategy = coarse`
- 从 `raw/*.md` 直接构建粗粒度块
- 优先按 H1/H2 或整功能块召回
- 目标是查“这一版改了什么”，不是过度细切

## 构建索引

```bash
python3 scripts/build_qmd_bridge_index.py
```

默认会生成：

- `index_store/qmd_bridge.db`

## 查询示例

```bash
# 方案类问题
python3 scripts/query_qmd_bridge.py "跨云互通" -c solution_cards -c solution_topics --brief
python3 scripts/query_qmd_bridge.py "AVC SVC 双引擎" -c solution_cards --brief

# 更新说明类问题
python3 scripts/query_qmd_bridge.py "风铃 迭代" -c release_notes --brief
python3 scripts/query_qmd_bridge.py "AE700 新功能" -c release_notes --brief
```

## 查询流程中具体用什么工具

### A. 先用默认入口判断问题类型
```bash
node scripts/query_default.js --brief "<query>"
```

用途：
- 先判断问题更像方案类还是更新类
- 更新类问题会优先路由到 `release_notes`
- 方案类问题继续走现有 V2 结构化检索

### B. 方案文档查询时用什么
1. 默认入口
   ```bash
   node scripts/query_default.js --brief "跨云互通"
   ```
2. 需要显式限制到方案层时
   ```bash
   python3 scripts/query_qmd_bridge.py "跨云互通" -c solution_cards -c solution_topics --brief
   ```
3. 需要更稳定结构化召回时
   ```bash
   node scripts/query_v2.js --json "跨云互通"
   ```
4. 最后回读
   - `cards/sections/*.json`

### C. 更新说明查询时用什么
1. 默认入口
   ```bash
   node scripts/query_default.js --brief "AE700 新功能"
   ```
2. 需要显式限制到更新说明层时
   ```bash
   python3 scripts/query_qmd_bridge.py "AE700 新功能" -c release_notes --brief
   ```
3. 最后回读
   - 对应 `raw/*.md` 的整节或整功能块

### D. 默认命中不足时补什么
```bash
python3 scripts/query_fts5.py "<query>" --brief
```

用途：
- 做宽召回
- 补关键词、别名、模糊表达的硬召回

## 当前定位

`query_qmd_bridge.py` 现在的定位很明确：

- 不是唯一入口
- 是**按文档类型分流的显式检索入口**
- 适合人工指定查询范围，也适合后续给 agent 做 collection-aware 召回

## 当前状态

当前已经完成：
1. 默认查询入口可区分 `solution / release_note`
2. `release_note` 走粗粒度召回
3. 文档类型声明、collection 映射、索引构建脚本都已落地

## 下一步可继续补

1. 给 release note 增加版本号、型号、功能类型等字段
2. 在此索引上增加 embedding 召回
3. 加入 reranker 做最终精排
