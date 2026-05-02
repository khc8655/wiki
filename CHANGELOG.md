# Changelog

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
