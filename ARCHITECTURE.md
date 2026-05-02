# wiki_test 架构设计文档 v3.1

## 1. 整体架构

```
用户查询
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  查询理解 (Qwen2.5-7B)                                │
│  ├─ 意图分类 → 四源路由                               │
│  └─ 关键词扩展                                        │
└──────────────────────────────────────────────────────┘
    │
    ├──→ 📊 表格类: SQLite (excel_db.py)
    ├──→ 📝 方案类: BM25+Vector 混合 (hybrid_retriever.py)
    ├──→ 🔄 更新类: BM25 粗粒度段落
    └──→ 🎞️ PPT类:  图片理解卡片
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  三环自组织回路                                        │
│  🔄 feedback.py     → 查询日志 + 反馈                  │
│  🔄 weight_optimizer → 自动权重调优                    │
│  🔄 card_organizer   → 卡片聚类/合并/主题               │
└──────────────────────────────────────────────────────┘
    │
    ▼
输出: 原文 + 出处 + 命中率 (不总结)
```

## 2. 数据流

### 2.1 入库流程

```
WebDAV 拉取 raw/*.md
    ↓
import_webdav_raw.py: sectionize (按标题层级切段)
    ↓ cards/sections/*.json (1885张)
    ├──→ 方案类: fine grained (≤1200字, 再切)
    └──→ 更新类: coarse (完整标题段, 不切细)
    ↓
annotate_cards.py: Qwen2.5-7B 段落级标注
    ↓ card["semantic"] 写入卡片
    ↓
build_embeddings.py: bge-large-zh-v1.5 向量化
    ↓ index_store/embeddings/
```

### 2.2 查询流程

```
User Query → classify_query() → 四源路由
    │
    ├─ excel    → search_excel()     → SQLite 列匹配
    ├─ knowledge → search_knowledge() → BM25+Vector 混合
    ├─ update   → search_updates()   → BM25 粗粒度
    └─ ppt      → search_ppt()       → 图片卡片
    │
    ▼
统一输出: title + body + source + hit_rate
feedback 自动记录到 query_feedback.jsonl
```

## 3. 核心组件

### 3.1 查询路由 (query_unified.py)

**classify_query()**: 规则引擎判断意图

| 条件 | 路由 |
|------|------|
| 有型号 + 价格/参数/招标/对比词 | excel |
| 版本/迭代/新功能/发版 | update |
| ppt/幻灯片 | ppt |
| 其他 | knowledge |

### 3.2 混合检索 (hybrid_retriever.py)

```
BM25 (retrieval_bm25.py):
  - 索引: title + body + semantic tags + path
  - 分词: 中文 bigram + 英文 word + 停用词过滤
  - 参数: k1=1.5, b=0.75

Vector (vector_search.py):
  - 模型: bge-large-zh-v1.5 (1024维)
  - 相似度: 余弦 (归一化后点积)
  - 快速: numpy 矩阵运算

融合: score = 0.4×bm25_norm + 0.6×vec_sim
动态权重: weight_optimizer.py 可自动调整
```

### 3.3 反馈闭环 (feedback.py + query_refiner.py)

```
每次查询 → 记录到 query_feedback.jsonl
  {query_id, timestamp, query, source_type, top5_hits, avg_hit_rate}

低质量检测:
  avg_hit_rate < 0.3 或 total_results < 3 → low_quality

优化建议:
  Qwen2.5-7B 分析意图 → 扩展关键词 + 建议改写 + 澄清问题
  LLM 失败 → 规则式降级
```

### 3.4 权重优化 (weight_optimizer.py)

```
analyze_feedback() → 提取统计
  - 命中率分布, BM25 vs Vector 贡献比, 来源表现
  ↓
suggest_weights() → 推导权重
  - Trust Region: 每次变更 ±0.15
  - 冷启动: 需 ≥20 条反馈
  ↓
apply_weights() → 写入 + 历史审计
  - optimized_weights.json + weight_history.jsonl
```

### 3.5 卡片自组织 (card_organizer.py)

```
find_similar_cards(threshold=0.85):
  - 全量 cosine 矩阵, 过滤壳卡片
  
suggest_merges():
  - ≥0.92 → 合并 (标注 merged_from/to)
  - 0.85-0.92 → 关联 (标注 related_cards)

cluster_cards(n=20):
  - 纯 numpy KMeans, 无 sklearn 依赖

build_cross_references():
  - feedback log 共现分析 (需积累数据)
  - 即使 embedding 不相似, 查询中共现也建立关联

原则: 不删除, 只标注关系
```

## 4. 模型配置

| 模型 | 角色 | 频次 |
|------|------|------|
| Qwen/Qwen2.5-7B-Instruct | 标注 + 查询理解 + 对话优化 | 入库/查询 |
| BAAI/bge-large-zh-v1.5 | 语义向量化 (1024维) | 入库/查询 |
| SiliconFlow API | 免费模型托管 | - |

## 5. 扩展点

### 添加新数据源

1. 在 `classify_query()` 添加路由规则
2. 实现 `search_xxx()` 函数
3. 返回统一格式: `{type, hit_rate, source, title, body}`

### 添加新模型

编辑 `lib/llm_client.py` 中的 `MODELS` 字典

---

参考: README.md | API.md | QUICKSTART.md | AGENTS.md
