# Retrieval Feedback (V2)

这个目录用于存放检索反馈事件和查询日志，供 `scripts/analyze_feedback.js` 增量分析。

## 文件说明

- `query_log.jsonl` - 自动生成的查询日志（JSON Lines 格式）
- `auto_refine_report.v2.json` - 定期生成的优化建议报告

## 快速开始

### 1. 查看查询统计

```bash
node scripts/query_logger.js stats
```

### 2. 查看最近查询

```bash
node scripts/query_logger.js recent 20
```

### 3. 提交用户反馈

```bash
# 标记有帮助
node scripts/feedback_cli.js "跨云互通" helpful

# 标记无帮助并说明原因
node scripts/feedback_cli.js "svc对比avc" unhelpful "没找到avc相关内容" 11-11-AVC_SVC双引擎云视频技术白皮书-sec-082
```

### 4. 生成优化建议报告

```bash
# 输出到控制台
node scripts/analyze_feedback.js

# 保存到文件
node scripts/analyze_feedback.js --output updates/retrieval_feedback/auto_refine_report.v2.json
```

## 事件格式

### 查询日志事件

```json
{
  "timestamp": "2026-04-14T14:30:00.000Z",
  "query": "跨云互通",
  "intent": "cross-cloud-interconnect",
  "precision_percent": 100,
  "top_titles": ["海关总署云视频系统同华为系统呼叫方式"],
  "top_cards": ["06-新一代视频会议系统建设方案模板-sec-224"],
  "strong_hits": 5,
  "weak_hits": 2,
  "excluded_hits": 0
}
```

### 用户反馈事件

```json
{
  "timestamp": "2026-04-14T14:35:00.000Z",
  "type": "feedback",
  "query": "svc对比avc",
  "helpful": false,
  "comment": "没找到avc相关内容",
  "expected_cards": ["11-11-AVC_SVC双引擎云视频技术白皮书-sec-082"]
}
```

## 自动化收集

现在查询日志会自动记录。每次运行 `query_v2.js` 时：

```bash
node scripts/query_v2.js "跨云互通"
# 日志自动写入 updates/retrieval_feedback/query_log.jsonl
```

## 用途

- 统计高频 query
- 发现低 precision query
- 发现缺少 intent 的 query
- 发现容易混淆的主题对
- 追踪用户反馈趋势

## 优化工作流

1. 运行查询 → 日志自动收集
2. 定期运行 `analyze_feedback.js` 生成报告
3. 根据报告建议：
   - 补充缺失的 intent 规则（query_v2_core.js）
   - 优化主题页（topics/*.md）
   - 调整路由配置（routes.v1.json）
   - 更新 high_priority_cards
