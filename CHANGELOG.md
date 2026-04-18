# Changelog

## V2.5 - 2026-04-18

### 文档与版本整理

- 统一当前版本号为 `v2.5`，收口此前 README / CHANGELOG / bridge 文档中的混用表述
- 删除说明文档中不必要的 skills 相关描述，改为围绕当前仓库内实际脚本与命令说明
- 新增 `docs/query-workflow.md`，明确查询流程中每一步该使用什么工具、何时使用、如何串联
- 新增 `docs/release-note-schema.md`，定义更新说明文档的推荐字段与最小可用字段集
- 更新 `README.md` 与 `qmd_bridge/README.md`，补齐命令级示例与工具定位说明
- 更新 `wiki/log.md`，同步当前版本状态与说明文档整理结果

---

## V2.4 - 2026-04-18

### QMD 风格集合检索实验层 + 文档双轨规则

- 新增 `qmd_bridge/doc_profiles.json`，声明 `solution / release_note` 两类文档
- 更新 `qmd_bridge/collections.json`，改为 `solution_cards / solution_topics / solution_wiki / release_notes`
- 新增 `scripts/build_qmd_bridge_index.py`，构建跨层 SQLite FTS5 集合索引，并按文档类型分流
- 更新 `scripts/query_default.js`，让默认查询入口可自动区分方案类与更新类问题
- 新增 `scripts/query_qmd_bridge.py`，提供按 collection 的显式检索入口
- `index_store/qmd_bridge.db` 作为本地生成索引产物，加入实验链路

---

## V2.3 - 2026-04-15

### SQLite FTS5 本地检索底座

- 新增 `scripts/build_fts5_index.py`，从 cards 和 metadata 构建本地 SQLite FTS5 索引
- 新增 `scripts/query_fts5.py`，提供本地全文检索入口
- 新增 `index_store/FTS5_USAGE.md`，说明 FTS5 的定位与使用方法
- `index_store/fts5_cards.db` 作为本地生成产物，加入 `.gitignore`
- 完成最小实验，确认 FTS5 可在当前环境中直接运行
- 补充产品/功能型查询的轻量规则优先级，改善 `AE700 产品介绍` 与 `AE700 支持串口绑定` 的区分召回

---

## V2.2 - 2026-04-15

### 查询流程固化

- 固化统一查询链路：Query 理解 → 检索入口 → 结构化召回 → 原文回读 → 最终输出
- 在 `AGENTS.md`、`README.md`、`docs/retrieval-v2-design.md` 中补充固定输出骨架与禁止快捷路径规则
- 新增查询日志、反馈 CLI、分析脚本：`query_logger.js`、`feedback_cli.js`、`analyze_feedback.js`
- `scripts/query_v2.js` 接入静默查询日志记录
- `updates/retrieval_feedback/README.md` 补充反馈与分析使用说明

---

## V2.1 - 2026-04-14

### 层级索引与反向召回

- 新增 `index_store/path_siblings_index.v2.json`
- 新增 `index_store/model_path_index.v2.json`
- 新增 `scripts/build_path_index.js` 与 `scripts/build_model_index.js`
- 查询硬件型号时支持走反向索引召回
- 命中卡片后自动补召回同父目录兄弟卡片

---

## V2.0 - 2026-04-12

### 初始版本

- 四层架构：Raw → Cards → Topics → Wiki
- 意图路由：跨云互通、安全、稳定性、双引擎等
- 匹配度输出：强命中 / 弱相关 / 排除项 + match_percent
