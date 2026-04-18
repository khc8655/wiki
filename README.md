# Wiki 知识库

云视频平台分层知识库 - 采用四层架构设计

---

## 版本信息

**当前版本**: v2.5

---

## 架构概览

本知识库采用**四层分层架构**，详细说明见 [docs/architecture.md](docs/architecture.md)：

```
Layer 4: Wiki 合成层 (Synthesized Knowledge)
├── wiki/index.md        # 导航首页
├── wiki/log.md          # 演进记录
└── wiki/sources/        # 源文档总结页

Layer 3: Topics 主题聚合层 (Synthesized Pages)
├── topics/architecture.md
├── topics/security.md
├── topics/meeting-control.md
└── ...

Layer 2: Cards 结构化卡片层 (Knowledge Middle Layer)
├── cards/sections/*.json    # 段落级卡片
├── cards/manifest.json      # 全量索引
└── cards/card_metadata.v1.json

Layer 1: Raw 原始资料层 (Source of Truth)
└── raw/                    # 原始文档（不可变）
```

---

## 文档清单

| 文档编号 | 文档名称 | 卡片数 |
|---------|---------|--------|
| 01 | 云视频技术架构优势V1.0-20211120 | 6 |
| 02 | 小鱼易连安全稳定白皮书V1-20240829 | 6 |
| 03 | 小鱼易连融合云视频会控技术白皮书V1.6 | 300 |
| 04 | 小鱼易连融合云视频平台技术白皮书V1.1 | 419 |
| 05 | llm-wiki-reference | 5 |
| 06 | 新一代视频会议系统建设方案模板 | 275 |
| 07 | 2026年私有云3月迭代功能概要 | 11 |
| 08 | 2026年私有云3月迭代功能概要文档 | 3 |
| 09 | 2026年私有云3月迭代版本新功能培训文档-云平台 | 180 |
| 10 | 2026年私有云3月迭代版本新功能培训文档-终端 | 147 |
| 11 | AVC_SVC双引擎云视频技术白皮书 | 98 |
| 12 | 软件定义架构与专用硬件架构的发展与区别 | 1 |
| 13 | 视频会议的技术发展简述V8 | 6 |
| 14 | 视频会议技术路线选型及对比说明 | 13 |
| 15 | 视频会议抗丢包算法的简介 | 1 |
| 16 | 小鱼安全白皮书_V2.2 | 23 |
| 17 | 小鱼易连风铃系统1月迭代新功能培训文档 | 60 |

**总计**: 17 份文档，1554 张知识卡片

---

## 主题覆盖

- **architecture** - 系统总体架构
- **security** - 安全稳定
- **stability** - 稳定性保障
- **meeting-control** - 会控能力
- **live-streaming** - 直播能力
- **recording** - 录制回放
- **signaling** - 信令控制
- **media-exchange** - 媒体交换
- **multi-active** - 多活容灾
- **monitoring** - 监控运维
- **ai** - AI 智能

---

## 更新日志

### v2.5 (2026-04-18)

**文档与查询流程整理**

- 统一当前版本号为 `v2.5`，收口此前混用的 `v2.0-beta / V2.4` 等表述
- 新增: `docs/query-workflow.md`，明确当前查询流程、所需工具、调用顺序与命令示例
- 更新: `README.md`，改为以“当前状态 + 工具流程”为主，不再只写抽象原则
- 更新: `qmd_bridge/README.md`，写清楚方案文档 / 更新说明文档分别该用什么工具
- 更新: `CHANGELOG.md` 与 `wiki/log.md`，统一版本记录口径

### v2.4 (2026-04-18)

**QMD 风格集合检索实验层 + 文档双轨规则**

- 新增: `qmd_bridge/doc_profiles.json`，声明 `solution / release_note` 两类文档
- 更新: `qmd_bridge/collections.json`，改为 `solution_cards / solution_topics / solution_wiki / release_notes`
- 更新: `qmd_bridge/README.md`，记录两类文档的切分与查询定位
- 新增: `scripts/build_qmd_bridge_index.py`，构建跨层 SQLite FTS5 集合索引，并按文档类型分流
- 更新: `scripts/query_default.js`，让默认查询入口可自动区分方案类与更新类问题
- 新增: `scripts/query_qmd_bridge.py`，提供 collection-aware 检索入口
- 新增: `index_store/qmd_bridge.db` 作为实验索引输出路径（本地生成）

### v2.3 (2026-04-15)

**SQLite FTS5 本地检索底座**

- 新增: `scripts/build_fts5_index.py` 本地索引构建脚本
- 新增: `scripts/query_fts5.py` 本地全文查询脚本
- 新增: `index_store/FTS5_USAGE.md` 使用说明
- 更新: `.gitignore` 忽略本地生成的 `index_store/fts5_cards.db`

### v1.8 (2026-04-15)

**查询流程固化与检索优化**

- 更新: 固化统一查询链路与固定输出骨架
- 修复: 产品型号查询优先召回产品介绍内容
- 新增: 会控/稳定性主题路由与主题页
- 新增: 查询日志、反馈 CLI、分析脚本
- 更新: 检索反馈说明文档

### v1.7 (2026-04-13)

**批量导入新增资料**

- 新增: 11 份原始资料导入 `raw/`
- 新增: 对应 `index_store/docs/*.json` 文档级索引
- 新增: 543 张 section cards
- 新增: `scripts/import_inbound_batch.py` 批量入库脚本
- 更新: `cards/manifest.json`、V1/V2 检索索引

### v1.6 (2026-04-13)

**V2 默认查询入口与自动优化骨架**

- 新增: `scripts/query_v2_core.js`，抽出可复用查询核心
- 新增: `scripts/query_default.js`，作为默认查询入口，优先走 V2
- 新增: `scripts/auto_refine_v2.py`，生成自动优化建议报告
- 新增: `updates/retrieval_feedback/README.md`，定义检索反馈事件目录与格式
- 更新: `index_store/USAGE.md` 与 `docs/retrieval-v2-design.md`

### v1.5 (2026-04-13)

**V2 检索设计与脚手架**

- 新增: `docs/retrieval-v2-design.md`，明确“重入库、轻查询、持续自优化”的 V2 方案
- 新增: `scripts/build_v2_semantic_metadata.py`，生成 V2 语义元数据与 intent/concept/negative 索引
- 新增: `scripts/query_v2.js`，提供 V2 查询原型，支持轻量 query 理解 + 快速精排
- 补充: V2 card schema、自动优化与 lint 思路

### v1.4 (2026-04-12)

**初始版本发布**

- 导入 6 份原始白皮书/方案文档
- 生成约 991 张结构化知识卡片
- 建立完整的四层架构体系
- 创建主题聚合页和 Wiki 合成页
- 配置 GitHub 自动推送脚本

---

## 后续更新规范

### 更新流程

1. **准备更新内容**
   - 新增/修改原始文档 → 放入 `raw/` 目录
   - 生成新的 section cards → 放入 `cards/sections/`
   - 更新 `cards/manifest.json` 和 `cards/card_metadata.v1.json`

2. **更新主题页**
   - 修改相关的 `topics/*.md` 文件
   - 更新 `wiki/sources/*.md` 源文档总结页

3. **记录变更**
   - 在本文档「更新日志」部分添加新版本说明
   - 更新 `wiki/log.md` 文件

4. **提交推送**
   ```bash
   ./push_to_github.sh "v1.x: 更新说明"
   ```
   或
   ```bash
   git add . && git commit -m "v1.x: 更新说明" && git push origin main
   ```

### 版本号规则

- **v1.x** - 小版本更新（新增卡片、补充内容）
- **v2.0** - 大版本更新（架构调整、重大变更）

### 更新日志模板

```markdown
### v1.x (YYYY-MM-DD)

**更新内容**

- 新增: xxx
- 更新: xxx
- 修复: xxx

**统计**

- 新增卡片: xx 张
- 更新主题: xx 个
- 涉及文档: xxx
```

---

## 使用指南

### 查询知识

知识库当前按两类文档建模：

- **方案文档（solution）**: 用于日常写方案、架构能力说明、材料复用，采用细粒度切分
- **更新说明文档（release_note）**: 用于查询具体功能、型号、版本变化，采用粗粒度切分

完整说明见：`docs/query-workflow.md`

#### 查询时使用什么工具

1. **默认入口**: `node scripts/query_default.js --brief <query>`
   - 用途：先判断该问题更像方案类还是更新类
   - 适合：绝大多数日常查询先从这里进

2. **方案类精确检索**: `node scripts/query_v2.js --json <query>`
   - 用途：走 intent / concept / high-priority cards 结构化召回
   - 适合：架构、能力、场景类问题

3. **宽召回入口**: `python3 scripts/query_fts5.py "<query>" --brief`
   - 用途：关键词散、别名多、默认命中不足时补召回

4. **按文档类型显式查询**: `python3 scripts/query_qmd_bridge.py "<query>" ...`
   - 方案类问题优先：`-c solution_cards -c solution_topics`
   - 更新类问题优先：`-c release_notes`

#### 推荐流程

1. 先用默认入口：
   ```bash
   node scripts/query_default.js --brief "<query>"
   ```
2. 若是方案类问题，再视需要补：
   ```bash
   node scripts/query_v2.js --json "<query>"
   python3 scripts/query_qmd_bridge.py "<query>" -c solution_cards -c solution_topics --brief
   ```
3. 若是更新类问题，再视需要补：
   ```bash
   python3 scripts/query_qmd_bridge.py "<query>" -c release_notes --brief
   ```
4. 若命中仍不足，再补 FTS5：
   ```bash
   python3 scripts/query_fts5.py "<query>" --brief
   ```
5. 最后必须回读原文再输出：
   - `solution` 问题优先回读 `cards/sections/*.json`
   - `release_note` 问题优先回读对应 `raw/*.md` 的整节或整功能块

### 检索与优化常用命令

```bash
python3 scripts/build_v2_semantic_metadata.py
python3 scripts/build_qmd_bridge_index.py
node scripts/query_default.js --brief 跨云互通
python3 scripts/query_fts5.py "跨云互通" --brief
python3 scripts/query_qmd_bridge.py "跨云互通" -c solution_cards -c solution_topics --brief
python3 scripts/query_qmd_bridge.py "AE700 新功能" -c release_notes --brief
node scripts/query_v2.js --json --top 5 AVC+SVC双引擎
python3 scripts/auto_refine_v2.py
```

### 自动优化反馈

- 检索反馈事件目录: `updates/retrieval_feedback/`
- 自动建议报告: `updates/retrieval_feedback/auto_refine_report.v2.json`

### 本地启动

本知识库为纯 Markdown + JSON 结构，无需服务器即可浏览。

---

## 仓库地址

https://github.com/khc8655/wiki

---

## 维护者

- 创建: khc8655
- 架构设计: 四层分层知识库架构

