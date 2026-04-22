# 查询路由优化 v2

## 优化目标

解决五类数据源（solution/release_notes/pricing/comparison/proposal）的查询路由问题，实现：
1. **更准** - 精确识别查询意图
2. **更全** - 模糊查询时自动多源搜索
3. **更快** - 减少不必要的搜索

## 核心改进

### 1. 置信度评分系统

为每个查询计算五类数据源的匹配置信度（0-100）：

```
confidence = 关键词得分 + 实体匹配得分 × 权重
```

**得分规则**：
- 每个关键词命中 +15分
- 型号+意图词同时命中 +35~40分
- 应用类别权重（comparison最高1.2，solution最低0.9）

### 2. 智能路由决策

**决策流程**：
1. 提取实体（产品型号、关键词）
2. 计算五类置信度
3. 排序选择主数据源
4. 判断是否模糊查询
5. 决定单源或多源搜索

**模糊查询判定**：
- 最高置信度 < 30 → 模糊
- 最高与次高差距 < 20 → 模糊
- 只有一个型号但无明确意图 → 多源

### 3. 多源回退机制

模糊查询时，自动查询多个数据源并合并结果：

| 查询示例 | 识别意图 | 实际搜索 |
|---------|---------|---------|
| "AE800" | pricing (15分) | pricing + comparison + release_notes |
| "AE800多少钱" | pricing (70分) | pricing only |
| "XE800与AE800对比" | comparison (66分) | comparison only |
| "AE800参数" | proposal (60分) | proposal only |

### 4. 改进的实体提取

**产品型号识别**：
```python
# 支持格式
AE800, XE800, GE600, PE8000, TP650
# 也支持
AI, 会议室（作为特殊实体）
```

**关键词分类**：
- price_terms: 价格、多少钱、费用、停产、替代
- compare_terms: 对比、比较、区别、vs
- proposal_terms: 招标、投标、参数、方案
- feature_terms: 功能、新功能、迭代、支持

## 使用方式

### 命令行查询

```bash
# 基本查询
python3 scripts/query_enhanced_router.py "AE800多少钱"

# 显示置信度分析
python3 scripts/query_enhanced_router.py "AE800多少钱" --show-confidence

# 调整结果数量
python3 scripts/query_enhanced_router.py "AE800" -k 10
```

### 查询示例与路由

| 查询 | 主数据源 | 置信度 | 搜索范围 |
|------|---------|--------|---------|
| AE800多少钱 | pricing | 70 | pricing |
| XE800与AE800对比 | comparison | 66 | comparison |
| AE800参数 | proposal | 60.5 | proposal |
| AE800 | pricing | 15 | pricing+comparison+release_notes |
| AI相关报价 | pricing | 40 | pricing |
| 会议室价格 | pricing | 25 | pricing |

## 与原方案对比

| 特性 | 原方案 | 优化后 |
|------|--------|--------|
| 路由方式 | 关键词优先级 | 置信度评分 |
| 模糊处理 | 强制单源 | 智能多源 |
| 型号提取 | 简单正则 | 改进正则+特殊实体 |
| 结果排序 | 单源排序 | 跨源排序 |
| 可调参数 | 少 | 权重、阈值可调 |

## 后续优化方向

1. **学习反馈**：记录用户点击，优化置信度权重
2. **语义理解**：引入轻量级语义模型理解查询
3. **上下文记忆**：支持多轮对话上下文
4. **结果去重**：多源结果智能去重和合并
