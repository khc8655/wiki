# wiki_test API 文档 - v3.1

## 1. 主查询入口

### query_unified.py

四源路由引擎，支持智能意图分类和 JSON 输出。

```bash
python3 query_unified.py "查询内容" [--json] [--limit N] [--all]
```

**参数：**
- `query` (required): 查询文本
- `--json` (optional): JSON 格式输出
- `--limit N` (optional): 最多返回 N 条 (默认 5)
- `--all` (optional): 返回全部结果
- `--verbose` / `-v`: 显示反馈诊断信息
- `--feedback good|bad|skip`: 标记查询质量
- `--ref-query-id ID`: 关联上一轮查询（追问链）
- `--optimize`: 分析反馈并建议权重优化
- `--optimize-apply`: 应用优化权重

**返回示例**：
```json
{
  "query": "视频会议安全加密方案",
  "source_type": "knowledge",
  "models": [],
  "total": 30,
  "shown": 5,
  "results": [
    {
      "type": "方案类-段落",
      "hit_rate": 0.95,
      "title": "视频系统信息加密",
      "body": "视频通话媒体流采用端到端安全加密...",
      "source": "20-气象方案.md | 安全性设计 > 视频系统信息加密"
    }
  ]
}
```

**四源路由**：
| 查询特征 | 路由 | 说明 |
|----------|------|------|
| 型号 + 价格/参数/招标/对比/接口 | excel | SQLite 精准匹配 |
| 概念/场景/架构/安全/部署 | knowledge | BM25+Vector 混合 |
| 版本/迭代/新功能/发版 | update | BM25 粗粒度段落 |
| ppt/幻灯片 | ppt | 图片理解卡片 |

---

## 2. 离线脚本

### annotate_cards.py

全量卡片标注（Qwen2.5-7B）。

```bash
python3 scripts/annotate_cards.py                    # 全量标注
python3 scripts/annotate_cards.py --limit 50         # 测试前50张
python3 scripts/annotate_cards.py --doc-type solution # 仅方案类
python3 scripts/annotate_cards.py --dry-run           # 预览
```

### build_embeddings.py

向量化构建（bge-large-zh-v1.5, 1024维）。

```bash
python3 scripts/build_embeddings.py              # 全量
python3 scripts/build_embeddings.py --limit 100 # 测试前100张
```

### organize_cards.py

卡片自组织系统（相似合并/聚类/主题生成）。

```bash
python3 scripts/organize_cards.py --dry-run --cluster 10  # 预览10簇
python3 scripts/organize_cards.py --merge --related       # 应用标注
python3 scripts/organize_cards.py --topics --cluster 20   # 生成主题
python3 scripts/organize_cards.py --all --threshold 0.88  # 全量执行
```

---

## 3. 测试脚本

### run_fast_tests.py

```bash
python3 scripts/run_fast_tests.py
```

**9 项测试**：AE800价格、AI报价、按年云会议室、AE800配件、PE8000停产、XE800 vs AE800、GE600招标、公安行业、软硬对比。

---

## 4. 数据同步

### refresh_from_webdav.sh

```bash
./scripts/refresh_from_webdav.sh
# 凭据环境变量: WEBDAV_USER=jjb WEBDAV_PASS=jjb@115799
```

### import_webdav_raw.py

```bash
python3 scripts/import_webdav_raw.py --user jjb --password 'jjb@115799'
```

---

## 5. 核心库模块

| 模块 | 功能 |
|------|------|
| `lib/llm_client.py` | SiliconFlow API 封装 (chat + embed) |
| `lib/annotator.py` | 段落级中文语义标注 |
| `lib/embedder.py` | 向量化构建 + 存储 |
| `lib/retrieval_bm25.py` | BM25 关键词检索 |
| `lib/vector_search.py` | 余弦相似度向量检索 |
| `lib/hybrid_retriever.py` | BM25+Vector 融合 (0.4/0.6) |
| `lib/feedback.py` | 查询日志 + 反馈记录 |
| `lib/query_refiner.py` | 低质量查询对话优化 |
| `lib/weight_optimizer.py` | 基于反馈的自动权重调优 |
| `lib/card_organizer.py` | 卡片自组织系统 |
| `lib/excel_db.py` | Excel → SQLite 查询 |

---

## 6. 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| `No module named 'numpy'` | 缺少依赖 | `pip install numpy requests` |
| `[LLM] API error 401` | API key 未设置 | 检查 `SILICONFLOW_API_KEY` 环境变量 |
| `[Embed] API error 413` | 批量超过限制 | batch_size <= 32, text <= 450 chars |

---

## 7. 参考

- 架构设计: `ARCHITECTURE.md`
- 快速上手: `QUICKSTART.md`
- 版本历史: `CHANGELOG.md`
