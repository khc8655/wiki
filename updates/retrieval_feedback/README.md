# Retrieval Feedback (V2)

这个目录用于存放检索反馈事件，供 `scripts/auto_refine_v2.py` 增量分析。

## 事件格式示例

```json
{
  "query": "跨云互通",
  "intent": "cross-cloud-interconnect",
  "precision_percent": 100,
  "top_titles": [
    "海关总署云视频系统同华为系统呼叫方式"
  ],
  "negative_hits": [
    "混合云部署"
  ]
}
```

## 用途

- 统计高频 query
- 发现低 precision query
- 发现缺少 intent 的 query
- 发现容易混淆的主题对

## 当前策略

- 先由人工或脚本写入事件
- `auto_refine_v2.py` 周期汇总建议
- 后续再考虑自动改写 route / metadata / topic hint
