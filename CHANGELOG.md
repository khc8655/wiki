# Changelog

## V3.3 - 2026-05-08

### 意图驱动的结构化查询引擎

**核心优化：**
- 重新设计查询引擎架构：`用户查询 → 意图识别器 → SQL查询策略 → 结构化输出`
- 从"全量标注+hybrid搜索"改为"意图驱动+结构化查询"
- Excel数据核心是SQL查询，标注的目的是让系统理解"怎么查"

**新增意图分类：**
- `price_query`：价格查询 → 查pricing表，直接返回价格
- `category_list`：分类列举 → 查pricing表，按category分组
- `compare_table`：对比表格 → 查comparison表，按spec_name聚合
- `tender_params`：招标参数 → 查proposal表，用model精确匹配
- `accessory`：配件查询 → 查pricing表，按category字段匹配
- `eol_info`：停产信息 → 查pricing表，检查note字段
- `solution`：方案描述 → hybrid搜索cards

**数据修复：**
- pricing表中AI相关记录的category字段已补充
  - 本地AI语音转写 → `AI语音转写引擎本地部署（可选）`
  - 语音引擎对接 → `三方语音转写引擎对接服务（可选）`
  - 大模型对接 → `三方大模型对接（AI智能体必选）`
  - 智能体会议室授权许可 → `接入授权（私有云）`
  - 智能体专有会议室授权许可 → `接入授权（专有云）`
- proposal卡片标题自动包含型号信息（如"一体化视频终端 GE600 招标参数"）
- 配件查询支持category字段匹配

**引擎增强：**
- `lib/excel_db.py` — 新增`execute`方法支持自定义SQL查询
- `query_unified.py` — 新增`_search_category_list`、`_search_compare_table`等函数
- 对比表格聚合功能：将多型号的单条spec记录聚合成完整表格

**测试结果：11/11 全部通过**
1. AE800价格 ✅ 价格138000
2. PE8000价格 ✅ 价格252000+停产信息
3. AI报价分类 ✅ 6个分类全部命中
4. 云会议室方数 ✅ 11种全部命中
5. AE800配件 ✅ TP10/遥控器/NP30全部命中
6. AE800包含配件 ✅ 终端主机/摄像机/麦克风/传屏器
7. PE8000停产 ✅ 2026年6月30日停产
8. XE800 vs AE800对比 ✅ 完整20项对比表格
9. GE600招标参数 ✅ 标题包含"GE600"，内容完整
10. 公安行业应用 ✅ 8+条公安文档
11. 软硬件对比 ✅ 命中对比分析文档

---

## V3.2 - 2026-05-06

### Excel 分面 metadata 提取

**新增：**
- `lib/phase_field_map.yaml` — Excel 行值→facet 映射表（proposal/pricing/comparison 三表）
- `scripts/build_excel_knowledge.py` — 入库时自动打 facet 字段
  - proposal: `phase_types: ["channel", "proposal", "tender"]`
  - pricing: `pricing_type` 归一化为「规格参数/报价参数/维保参数/实施参数」
  - comparison: `comparison_type` 子串匹配为「硬件终端/平台/软件客户端」
- `lib/excel_db.py` — facet 列 + 索引，`get_*_facets()` 统计方法，`*_filter` 参数
- `query_unified.py` — `--facet` 参数支持分面过滤，结果 >5 条时自动输出分面摘要

**目录结构更新：**
- 新增 `db/excel_store.db`、`lib/phase_field_map.yaml`、`scripts/build_excel_knowledge.py`

**文档脱敏：**
- `QUICKSTART.md`、`API.md` 中的真实 API Key / 密码替换为占位符

---

## V3.1 - 2026-05-02

### Karpathy-style 自组织知识系统

**新增：**
- **反馈闭环** (`lib/feedback.py`, `lib/query_refiner.py`)
  - 每次查询自动记录到 `query_feedback.jsonl`
  - 低质量查询触发 LLM 驱动的对话式优化
  - 支持 `--verbose`, `--feedback`, `--ref-query-id`
- **权重优化** (`lib/weight_optimizer.py`)
  - 基于反馈数据自动调整 BM25/Vector 权重
  - Trust Region: 每次变更上限 ±0.15
  - 渐进优化: 每 50 条新反馈触发重新分析
- **卡片自组织** (`lib/card_organizer.py`, `scripts/organize_cards.py`)
  - embedding 余弦相似度发现相似卡片对
  - 高度相似建议合并 (≥0.92), 相关建议关联 (0.85-0.92)
  - 纯 numpy KMeans 聚类成主题
  - 过滤锅炉板壳卡片噪声

### 标注+检索链路重构

**重写：**
- `query_unified.py` — 四源路由引擎 (表格类/方案类/更新类/PPT类)
- `lib/annotator.py` — 段落级中文语义标注 (Qwen2.5-7B-Instruct)
- `lib/embedder.py` — 向量化构建 (bge-large-zh-v1.5)
- `lib/vector_search.py` — 余弦相似度向量检索
- `lib/hybrid_retriever.py` — BM25+Vector 融合 (0.4/0.6)
- `lib/llm_client.py` — SiliconFlow API 封装

**改造：**
- `lib/retrieval_bm25.py` — 索引含 semantic tags, boost 读新标注字段
- `lib/excel_db.py` — Excel → SQLite 多阶段查询

**数据：**
- 1773 张方案卡片全量段落级标注 + 1024维向量化
- 去除 WebDAV 中转和零碎索引

**性能：**
- "视频会议安全加密方案" 命中率 90-95%, 跨 6 份文档召回
- 9 项历史测试全部通过

---

## V3.0 - 2026-04-25

### 检索引擎升级

- **新增 BM25 检索引擎** (`lib/retrieval_bm25.py`)
- **新增 Content Hash 一致性检查** (`scripts/check_stale_cards.py`)
- **新增空结果提示机制**
- **仓库结构清理**（可移植到任意环境）

## V2.6 - 2026-04-20

### GitHub 同步边界重构

- 更新 `.gitignore` 和 `push_to_github.sh`，仅提交程序/规则/说明

## V2.5 - 2026-04-18

### 文档与版本整理

- 统一版本号为 `v2.5`，新增 `docs/query-workflow.md`, `docs/release-note-schema.md`

## V2.4 - 2026-04-18

### QMD 风格集合检索实验层

- 新增 `qmd_bridge/`, `build_qmd_bridge_index.py`, `query_qmd_bridge.py`

## V2.3 - 2026-04-15

### SQLite FTS5 本地检索底座

- 新增 `build_fts5_index.py`, `query_fts5.py`

## V2.2 - 2026-04-15

### 查询流程固化

- 固化统一查询链路，新增查询日志和反馈 CLI

## V2.1 - 2026-04-14

### 层级索引与反向召回

- 新增 `path_siblings_index`, `model_path_index`

## V2.0 - 2026-04-12

### 初始版本

- 四层架构：Raw → Cards → Topics → Wiki
- 意图路由 + 匹配度输出
