# 知识库架构说明

> 本文档详细说明 wiki 知识库的四层架构设计、工作流程和设计原则。

---

## 一、知识库定位

这个知识库不是单纯"把文档扔进去做全文检索"，而是一个 **LLM 管理的分层知识库**，目标很明确：

1. **以标题语义和段落级精确召回为主**
2. **优先返回原文，而不是先做总结**
3. **在原始资料、结构化卡片、主题页之间做分层组织**
4. **支持后续再做二次综合和摘要**

它更像一个**可追溯的知识中间层**，不是纯搜索引擎，也不是纯 wiki。

---

## 二、完整架构（四层分层）

### Layer 1: 原始资料层（Raw / Source of Truth）

这是最底层，存放原始文档，规则是：

- 原始材料不可随便改
- 作为最终事实依据
- 上层所有知识页、卡片、摘要都要能回链到这里

在 `AGENTS.md` 里明确写了：
- `raw/` 是 immutable source documents
- 不能直接修改 `raw/`

也就是说，原始资料层是**事实源头**。

**包含内容：**
- 原始白皮书
- 方案文档
- 技术规范
- 其他源资料

---

### Layer 2: 结构化卡片层（Cards / Knowledge Middle Layer）

这是当前知识库最核心的一层。从 `cards/README.md` 看，它被明确称为：**Knowledge Middle Layer**。

**结构：**

```
cards/
├── sections/*.json           # 每一段、每一节拆成独立 section card
├── manifest.json             # 所有卡片的全量索引
└── card_metadata.v1.json     # 每张卡的补充元数据
```

**Section Card 包含：**
- 原文内容
- 标签（tags）
- 路径（path）
- 来源文档（doc_file）
- 标题（title）

这一层本质上是把文档做成了**段落级知识单元**。

**这层的作用：**

1. **原文可精确定位**
   - 每个 section 都是独立 JSON，不需要整篇大文档一起读

2. **可以按语义打标签**
   - 比如：architecture、security、stability、meeting-control
   - 一条内容既可以按原文位置找，也可以按能力主题找

3. **可以给 LLM 更稳定的"检索颗粒度"**
   - 不是一整篇几十页白皮书，而是一个个可控 section

4. **能支撑"先召回原文，再综合"**
   - 这点非常重要，因为这个库默认**不鼓励先总结再回答**

---

### Layer 3: 元数据与索引层（Manifest + Metadata）

这层主要由两个文件承担：

#### cards/manifest.json

更偏**"目录索引"**：
- id
- doc_file
- title
- path
- tags
- char_count

相当于告诉系统：
- 这张卡来自哪个文档
- 标题是什么
- 在知识树上的路径是什么
- 属于哪些主题标签
- 内容量大概多大

#### cards/card_metadata.v1.json

更偏**"检索增强"**：
- aliases（别名）
- keywords（关键词）
- entity_tags（实体标签）
- scenario_tags（场景标签）
- card_type（卡片类型）
- quality_tier（质量等级）

相当于在 section card 之上又做了一层**检索辅助语义包装**。这层很关键，因为它把"原始段落"提升成了"可被路由、可被识别、可被分类的知识对象"。

---

### Layer 4: 主题聚合层（Topics / Synthesized Pages）

`cards/README.md` 提到的 `topics/*.md` 包括：
- security
- stability
- meeting-control
- architecture
- live-streaming
- recording
- signaling
- media-exchange
- multi-active
- monitoring
- ai

这一层不是原文，而是**按主题聚合出来的页面**。

**价值：**
- 把分散在不同白皮书、不同 section 的相关知识组织到一起
- 方便按"主题"而不是"文档"理解系统
- 为检索提供"先看主题，再落具体卡片"的路径

**关系：**
- 卡片层是精确知识单元
- 主题层是面向阅读和综合的知识编排层

---

### Layer 5: Wiki 合成层（wiki/）

`AGENTS.md` 定义的更完整的合成知识区：

```
wiki/
├── index.md          # 导航
├── log.md            # 演进记录
└── sources/          # 每个源文档对应的总结页
```

这一层比 cards 更偏"知识产物"：
- 更适合人读
- 更适合跨文档串联
- 更适合维护演进历史
- 但仍要求保留对 source 的链接

换句话说，这个系统并不是只做"RAG 卡片库"，它还想做成**持续维护的知识 wiki**。

---

## 三、数据流（Data Flow）

```
原始文档 (Raw)
    ↓
拆分 section → 生成结构化卡片 (Cards)
    ↓
建立 manifest / metadata 索引
    ↓
聚合成 topic pages (Topics)
    ↓
进一步沉淀为 wiki pages (Wiki)
    ↓
用户查询时按标题语义和段落语义检索
    ↓
返回原文
    ↓
用户再要求时做二次总结
```

这是典型的**分层检索 + 可追溯综合**架构。

---

## 四、查询工作流程

标准查询流程：

### 第一步：理解问题
先理解用户问的到底是什么，重点是：
- 标题语义
- 段落语义

不是只做关键词匹配。

### 第二步：定位候选范围
系统会优先看：
- `wiki/heading-index.md`
- 相关 source pages
- 或 cards manifest / metadata

去判断应该命中哪些 section / 哪些主题页。

### 第三步：读命中的 topic 或 source 页面
- 如果问题更偏主题，就先读 topic page
- 如果问题更具体，就直接落到 section card

### 第四步：读取精确 card body
也就是具体段落原文。

### 第五步：默认返回原文

> **Return original content first. Summarize only on request.**

这条规则非常重要。

也就是说，这个知识库的默认姿势是：
- **先给证据**
- **再给归纳**

而不是反过来。

---

## 五、入库工作流程

当新增一个 source 时，流程是：

1. 读取原始资料 → 放入 `raw/`
2. 在 `wiki/sources/` 下创建或更新该 source 的总结页
3. 拆分 section，创建 `cards/sections/*.json`
4. 更新 `cards/manifest.json` 和 `cards/card_metadata.v1.json`
5. 更新相关 topic / system / capability / operations 页面
6. 从这些综合页反链回 source page
7. 如果新增页面，更新 `wiki/index.md`
8. 在 `wiki/log.md` 里追加变更记录

这个流程说明它不是一次性静态构建，而是**持续演化的知识库**。

---

## 六、设计原则

### 1. 原文优先
避免 LLM 一上来就"编得很顺"。

### 2. 分层组织
不是把知识糊成一层，而是：
- source
- card
- metadata
- topic
- wiki

每层职责都不一样。

### 3. 精确召回优先于表达流畅

AGENTS.md 里明确写了：
> precision is more important than fluent summary

这其实很对，尤其技术知识库里，宁可硬一点，也不能答偏。

### 4. 合成页面必须可追溯
综合页不能脱离 source 独立漂浮。

### 5. 避免重复造页
优先更新已有页面，而不是反复造新页面。

---

## 七、当前能力覆盖

结合现有 `manifest.json`，已经有比较完整的知识面：

- 云视频平台总体架构
- 会控架构
- 安全稳定
- 直播 / 录制 / VOD
- 信令控制
- 分布式媒体交换
- 多活与容灾
- 监控融合
- AI 智能模块
- 运维监控与大数据分析

而且每个 section 已经做了：
- 标题化
- 路径化
- 标签化
- 检索关键词化

说明它已经不是"原始资料堆"，而是**半结构化知识系统**了。

---

## 八、一句话概括

这套知识库本质上是一个：

> **以原始文档为事实底座、以 section card 为检索中间层、以 topic/wiki 为综合展示层、以标题语义和段落精确命中为核心检索策略的分层知识库系统。**

---

## 九、结构图

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: Wiki 合成层                                        │
│  ├── wiki/index.md (导航)                                    │
│  ├── wiki/log.md (演进记录)                                  │
│  └── wiki/sources/ (源文档总结)                              │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Topics 主题聚合层                                  │
│  ├── topics/architecture.md                                  │
│  ├── topics/security.md                                      │
│  ├── topics/meeting-control.md                               │
│  └── ...                                                     │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 元数据与索引层                                     │
│  ├── cards/manifest.json (全量索引)                          │
│  └── cards/card_metadata.v1.json (检索增强)                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Cards 结构化卡片层                                 │
│  └── cards/sections/*.json (段落级知识单元)                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Raw 原始资料层                                     │
│  └── raw/ (不可变源文档)                                     │
└─────────────────────────────────────────────────────────────┘

                          ↓

┌─────────────────────────────────────────────────────────────┐
│  Query Engine 查询引擎                                       │
│  ├── 理解用户问题 (标题语义 + 段落语义)                      │
│  ├── 定位候选范围 (manifest/metadata/topic)                  │
│  ├── 读取精确 card (返回原文)                                │
│  └── 按需二次总结                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 十、相关文档

- [AGENTS.md](../AGENTS.md) - 知识库工作指南
- [cards/README.md](../cards/README.md) - 卡片层详细说明
- [README.md](../README.md) - 项目总览
