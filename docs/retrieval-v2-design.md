# 知识库检索与入库 V2 设计稿

> 目标：重入库、轻查询、持续自优化。

---

## 1. 设计目标

V2 的目标不是把更多复杂度堆到查询时，而是：

1. 在**入库阶段完成更多语义编译**
2. 在**查询阶段只做轻量意图理解和快速精排**
3. 在**新文档进入和真实使用后持续自动优化**

核心原则：

- Raw 只读，不修改
- Cards 是主检索单元
- Topics / Wiki 是综合展示层
- 查询默认返回原文证据
- 精度优先于表达流畅
- 增量优化优先于全量重建

---

## 2. V2 架构

### Layer 1: Raw

- 目录：`raw/`
- 角色：事实源头，永不改写
- 输入：白皮书、方案文档、技术材料、网页导出等

### Layer 2: Semantic Cards

- 目录：`cards/sections/*.json`
- 角色：主检索单元
- V2 中每张 card 不再只是原文块，而是“被理解过的知识对象”

### Layer 3: Retrieval Metadata / Indexes

- 目录：`cards/card_metadata.v2.json`
- 目录：`index_store/*.v2.json`
- 角色：预编译的检索增强层

### Layer 4: Topics

- 目录：`topics/*.md`
- 角色：主题聚合页
- 用于“先收束主题，再落具体证据”

### Layer 5: Wiki

- 目录：`wiki/`
- 角色：综合知识产物与长期沉淀层
- 允许把高价值问答、对比、分析回写成页面

---

## 3. Card V2 Schema

建议为每张 card 增加如下字段：

```json
{
  "id": "06-...-sec-224",
  "title": "海关总署云视频系统同华为系统呼叫方式",
  "path": "与第三方业务系统对接 > 海关总署云视频系统同华为系统呼叫方式",
  "body": "...",
  "tags": ["architecture", "meeting-control"],

  "title_summary": "标题层语义摘要，概括该 section 主要讨论的主题边界",
  "semantic_summary": "正文层语义摘要，概括该 section 实际描述的能力/场景/方案",

  "semantic_keywords": ["跨云", "融合会管", "统一调度"],
  "intent_tags": ["cross-cloud-interconnect"],
  "concept_tags": ["第三方互通", "MCU级联", "新旧系统对接"],
  "scenario_tags": ["跨云互通", "存量系统对接"],

  "negative_concepts": ["混合云部署", "跨网安全", "多运营商接入"],
  "related_cards": ["06-...-sec-222", "06-...-sec-223"],
  "relation_hints": {
    "similar_to": ["..."],
    "supports": ["..."],
    "confusable_with": ["..."],
    "excludes": ["..."]
  },

  "card_type": "scenario",
  "quality_tier": "high",
  "quality_score": 0.93,
  "version": "v2"
}
```

---

## 4. 入库流程

### Step 1. 原始文档切分

将原文按 section / paragraph 切分为 card，保留：
- 标题
- 路径
- 正文
- 来源信息

### Step 2. 标题层理解

只基于 title + path 生成：
- `title_summary`
- 一级/二级主题判断
- 初始 `intent_tags`
- 初始 `concept_tags`

这一步主要解决“这段大概属于什么主题”。

### Step 3. 正文层理解

基于 body 补充：
- `semantic_summary`
- `semantic_keywords`
- `scenario_tags`
- `negative_concepts`

这一步主要解决“这段实际讲的是什么，不是什么”。

### Step 4. 关系生成

自动生成 card 间关系：
- `similar_to`
- `supports`
- `confusable_with`
- `excludes`

### Step 5. 索引编译

编译出 V2 索引：
- `alias_index.v2.json`
- `keyword_index.v2.json`
- `intent_index.v2.json`
- `concept_index.v2.json`
- `negative_index.v2.json`
- `relation_graph.v2.json`

### Step 6. Topic / Wiki 更新

自动触发：
- 相关 topic 页更新
- source 页更新
- index / log 更新

---

## 5. 查询流程

V2 查询强调“先理解，再快速召回”。

### Step 1. Query 理解

将 query 转成轻量结构：

```json
{
  "intent": "cross-cloud-interconnect",
  "must_concepts": ["跨云", "互通"],
  "prefer_concepts": ["融合会管", "统一调度"],
  "exclude_concepts": ["混合云部署", "跨网安全"],
  "expected_card_types": ["scenario", "architecture"]
}
```

### Step 2. 候选召回

优先使用：
- `intent_index.v2.json`
- `concept_index.v2.json`
- `semantic_keywords`
- `high_priority_cards`

### Step 3. 快速排除

按以下规则降权或排除：
- 命中 `negative_concepts`
- 命中 `excluded_intent_tags`
- card_type 不符合预期

### Step 4. 少量候选精排

只对小规模候选集做精排，输出：
- `match_percent`
- `强命中 / 弱相关 / 排除项`
- `reasons`
- `summary`

建议将查询能力封装为可复用接口，而不是只保留一次性脚本。当前建议暴露统一方法：

```js
runQuery(query, { topK, minScore, includeExcluded })
```

便于后续接入：
- CLI
- agent 内部调用
- HTTP 服务
- 批量评测脚本

### Step 5. 返回原文

默认返回强命中原文；只有在用户要求时再综合总结。

---

## 6. 自动优化机制

### 6.1 文档更新驱动

当 raw 文档更新时：

1. 定位受影响 cards
2. 增量重建这些 cards 的语义字段
3. 增量更新索引和关系图
4. 标记可能过时的 topic/wiki 页面

### 6.2 使用反馈驱动

根据真实 query 自动优化：

采集：
- 高频 query
- 低 precision query
- 被人工指出“召回不准”的 query
- 经常混淆的主题对

自动动作：
- 新增 route
- 补 intent tag
- 补 negative concept
- 生成 retrieval note / topic hint

---

## 7. Lint / Health Check

建议周期性执行：

1. 检查 orphan cards / orphan pages
2. 检查 concept 重复或冲突
3. 检查高频 query 是否缺少专用 route
4. 检查 confusable pairs 是否缺少 excludes
5. 检查旧结论是否被新文档覆盖

---

## 8. 与 llm-wiki 思路的对应关系

V2 借鉴的关键点：

1. 不是在 query 时每次重推导，而是提前编译知识
2. 新文档进入时要更新已有知识，不只是新增
3. 高价值问答可以反向沉淀进 wiki
4. 需要 lint / health-check 机制维持知识库质量

---

## 9. 推荐实施顺序

### Phase 1
- 增加 `title_summary`
- 增加 `semantic_summary`
- 增加 `intent_tags`
- 增加 `negative_concepts`

### Phase 2
- 建 `intent_index.v2.json`
- 建 `concept_index.v2.json`
- 建 `negative_index.v2.json`
- 查询接入轻量 query parser

### Phase 3
- 增量刷新 pipeline
- query 反馈驱动 auto-refine
- topic / wiki 自动回写

---

## 10. 成功标准

V2 成功的标志不是“字段更多”，而是：

1. 高频 query precision 明显提升
2. 查询响应时间不因复杂度大幅增加
3. 新文档加入后，相关主题自动变准
4. 用户指出错误后，系统能在后续查询中自动变好
