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

V2 查询强调“先理解，再快速召回”。从现在起，这也是知识库的**统一固定流程**，所有查询默认都按这一条链路执行，不再因为问题简单就跳步。

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
- `python3 scripts/query_fts5.py "<query>" --brief` 作为宽召回补充入口

其中 FTS5 的角色是先把可能相关的 cards 捞出来，尤其适合措辞不稳定、关键词较散、别名较多的查询；后续仍然要回到结构化索引和原文回读做验证。

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

当前建议默认入口：

```bash
node scripts/query_default.js --brief <query>
```

当默认入口召回不足，或者用户问题更像宽搜索、关键词搜索、模糊找法时，可补充使用：

```bash
python3 scripts/query_fts5.py "<query>" --brief
```

### Step 5. 返回原文

默认返回强命中原文；只有在用户要求时再综合总结。

### Step 6. 固定输出骨架

所有查询结果建议统一按下面的逻辑输出：

1. **Query 理解**：我把问题理解成什么
2. **召回入口**：我先用了哪个 topic / index / route / script / FTS5
3. **命中证据**：命中了哪些 cards / sections / source pages
4. **回答**：原文摘录或基于证据的综合结论

### Step 7. 禁止快捷路径

以下做法视为不合规：
- 仅靠 `find` / 文件名搜索 命中后直接输出最终答案
- 明明可以回读 section card，却只凭记忆组织答案
- 输出结论但不交代召回依据
- 把 FTS5 命中列表直接当成最终答案，不再做结构化验证和原文回读
- 对类似查询使用不同随意流程，导致结果不可复现

---

## 6. 层级索引与反向召回（V2.1 新增）

为提升查询准确率和召回完整章节，新增两类预编译索引：

### 6.1 Path Siblings Index（路径兄弟索引）

**文件**: `index_store/path_siblings_index.v2.json`

**作用**: O(1) 查找同一父路径下的所有兄弟卡片

**示例**:
```json
{
  "硬件平台 > 硬件终端": [
    "10-...-sec-030",
    "10-...-sec-031",
    ...
  ]
}
```

**使用场景**:
- 查询命中某张卡片后，自动召回同章节的其他卡片
- 确保操作步骤、功能说明等连续内容完整返回

### 6.2 Model Path Index（硬件型号反向索引）

**文件**: `index_store/model_path_index.v2.json`

**作用**: 硬件型号 → 父路径映射，实现反向召回

**示例**:
```json
{
  "XE800": ["硬件平台 > 硬件终端"],
  "AE700": ["硬件平台 > 硬件终端"],
  "NP30V2": ["硬件平台 > 硬件终端"]
}
```

**使用场景**:
- 查询"XE800"时，通过型号反向找到"硬件终端"章节
- 无需关键词匹配，直接定位相关文档

### 6.3 查询流程更新

```
查询"XE800" → 匹配型号XE800
                ↓
         查 model_path_index
                ↓
         得到 "硬件平台 > 硬件终端"
                ↓
         查 path_siblings_index
                ↓
         秒级召回148张相关卡片
                ↓
         按匹配度排序返回
```

**优势**:
- 准确率: 通过型号精确锁定相关章节
- 召回率: 自动召回同章节兄弟卡片
- 速度: O(1) 索引查找，无需遍历991张卡片

---

## 7. 自动优化机制

### 7.1 文档更新驱动

当 raw 文档更新时：

1. 定位受影响 cards
2. 增量重建这些 cards 的语义字段
3. 增量更新索引和关系图（包括 path_siblings_index 和 model_path_index）
4. 标记可能过时的 topic/wiki 页面

**索引重建命令**:
```bash
# 重建路径兄弟索引
node scripts/build_path_index.js

# 重建硬件型号反向索引
node scripts/build_model_index.js
```

### 7.2 使用反馈驱动

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

当前已提供自动优化骨架：

```bash
python3 scripts/auto_refine_v2.py
```

输入目录：
- `updates/retrieval_feedback/*.json`

输出报告：
- `updates/retrieval_feedback/auto_refine_report.v2.json`

---

## 8. Lint / Health Check

建议周期性执行：

1. 检查 orphan cards / orphan pages
2. 检查 concept 重复或冲突
3. 检查高频 query 是否缺少专用 route
4. 检查 confusable pairs 是否缺少 excludes
5. 检查旧结论是否被新文档覆盖
6. **检查 path_siblings_index 和 model_path_index 是否需要重建**（新文档入库后）

---

## 9. 与 llm-wiki 思路的对应关系

V2 借鉴的关键点：

1. 不是在 query 时每次重推导，而是提前编译知识
2. 新文档进入时要更新已有知识，不只是新增
3. 高价值问答可以反向沉淀进 wiki
4. 需要 lint / health-check 机制维持知识库质量
5. **通过层级索引实现跨卡片的章节级召回**（V2.1新增）

---

## 10. 推荐实施顺序

### Phase 1
- 增加 `title_summary`
- 增加 `semantic_summary`
- 增加 `intent_tags`
- 增加 `negative_concepts`

### Phase 2
- 建 `intent_index.v2.json`
- 建 `concept_index.v2.json`
- 建 `negative_index.v2.json`
- 建 `path_siblings_index.v2.json`（V2.1 新增）
- 建 `model_path_index.v2.json`（V2.1 新增）
- 查询接入轻量 query parser

### Phase 3
- 增量刷新 pipeline
- query 反馈驱动 auto-refine
- topic / wiki 自动回写

---

## 11. 成功标准

V2 成功的标志不是“字段更多”，而是：

1. 高频 query precision 明显提升
2. 查询响应时间不因复杂度大幅增加（V2.1: O(1) 层级索引查询）
3. 新文档加入后，相关主题自动变准
4. 用户指出错误后，系统能在后续查询中自动变好
5. **硬件型号查询能精确召回相关章节**（V2.1 新增）
