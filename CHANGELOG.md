# Changelog

## V2.3 - 2026-04-15

### 查询流程固化

- 固化统一查询链路：Query 理解 → 检索入口 → 结构化召回 → 原文回读 → 最终输出
- 在 `AGENTS.md`、`README.md`、`docs/retrieval-v2-design.md` 中补充固定输出骨架与禁止快捷路径规则

### 产品型号查询修复

- 修复纯型号查询优先级，`AE700` 等型号默认优先走 `product_index.v1.json`
- 产品介绍类查询优先命中 `06-新一代视频会议系统建设方案模板` 中的产品卡片，而不是 09/10 中的迭代功能内容
- 保留功能型查询路径，例如“AE700 支持串口绑定”仍走迭代功能召回

### 主题检索与反馈系统补充

- 新增 `topics/meeting-control-v1.md` 与 `topics/stability-v1.md`
- `query_router/routes.v1.json` 新增 `meeting-control`、`stability` 路由
- 新增查询日志、反馈 CLI、分析脚本：`query_logger.js`、`feedback_cli.js`、`analyze_feedback.js`
- `scripts/query_v2.js` 接入静默查询日志记录
- `updates/retrieval_feedback/README.md` 补充反馈与分析使用说明

---

+## V2.2 - 2026-04-14

### 主题检索优化

#### 1. 会控主题精确召回
- **文件**: `topics/meeting-control-v1.md`
- **路由**: `routes.v1.json` 新增 `meeting-control` intent
- **覆盖场景**:
  - SVC vs AVC 架构对比
  - 会控入口（PC/Mac/App/NE60）
  - 会议模式（对话/授课/督导）
  - 分级会控与级联会议
  - 会议模板与预约会议
- **High-priority cards**: 6张核心卡片（sec-105~107, sec-140~141）

#### 2. 稳定性主题精确召回
- **文件**: `topics/stability-v1.md`
- **路由**: `routes.v1.json` 新增 `stability` intent
- **子主题**: 
  - stability-architecture（多活热备/容灾）
  - stability-network（抗丢包/弱网）
  - stability-operations（扩容/弹性）
- **High-priority cards**: 4张核心卡片（平台稳定性、多活热备、网络适应性）

### 查询日志与反馈系统

#### 1. 自动日志收集
- **文件**: `scripts/query_logger.js`
- **集成**: `query_v2.js` 自动调用 `logQuery()`
- **日志路径**: `updates/retrieval_feedback/query_log.jsonl`
- **记录内容**:
  - 查询文本、intent、precision_percent
  - top_titles、top_cards
  - strong_hits / weak_hits / excluded_hits

#### 2. 反馈 CLI
- **文件**: `scripts/feedback_cli.js`
- **用法**:
  ```bash
  node scripts/feedback_cli.js "svc对比avc" unhelpful "没找到avc" card_id
  ```

#### 3. 自动分析脚本
- **文件**: `scripts/analyze_feedback.js`
- **功能**:
  - 统计高频查询（Top 10）
  - 统计 intent 分布
  - 识别低 precision 查询
  - 生成优化建议报告
- **用法**:
  ```bash
  node scripts/analyze_feedback.js --output report.json
  ```

#### 4. 快速查看统计
```bash
# 查看整体统计
node scripts/query_logger.js stats

# 查看最近20条查询
node scripts/query_logger.js recent 20
```

### 文档更新

- `updates/retrieval_feedback/README.md`: 新增完整的反馈系统使用指南
- `query_router/routes.v1.json`: 新增会控和稳定性路由配置

---

## V2.1 - 2026-04-14

### 新增功能

#### 1. 层级路径索引（Path Siblings Index）
- **文件**: `index_store/path_siblings_index.v2.json`
- **脚本**: `scripts/build_path_index.js`
- **作用**: O(1) 查找同一父路径下的所有兄弟卡片
- **示例**: "硬件平台 > 硬件终端" → 148张卡片

#### 2. 硬件型号反向索引（Model Path Index）
- **文件**: `index_store/model_path_index.v2.json`
- **脚本**: `scripts/build_model_index.js`
- **作用**: 硬件型号 → 父路径映射，实现反向召回
- **支持型号**: XE800, AE700, AE800, GE300, GE600, NP30V2, TP860-S, TP650-S 等

#### 3. 查询增强
- 新增 `hardware-model` 意图路由
- 查询硬件型号时自动走反向索引召回
- 章节关联增强：命中卡片后自动召回同父目录兄弟卡片

### 优化效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 查询速度 | ~2分钟（全量遍历） | <1秒（O(1)索引） |
| XE800召回 | 需关键词匹配 | 型号→路径→章节精确召回 |
| 章节完整性 | 碎片化单张卡片 | 完整章节合并输出 |
| 准确率 | 依赖关键词密度 | 层级关联提升 |

### 使用示例

```bash
# 查询 XE800（走型号反向索引）
node scripts/query_default.js --brief 'XE800'

# 查询 XE800 BYOM（型号+功能联合召回）
node scripts/query_default.js --brief 'XE800 BYOM'

# 重建索引（新文档入库后执行）
node scripts/build_path_index.js
node scripts/build_model_index.js
```

### 文档更新

- `docs/retrieval-v2-design.md`: 新增第6节"层级索引与反向召回"

## V2.0 - 2026-04-12

### 初始版本
- 四层架构：Raw → Cards → Topics → Wiki
- 意图路由：跨云互通、安全、稳定性、双引擎等
- 匹配度输出：强命中/弱相关/排除项 + match_percent
