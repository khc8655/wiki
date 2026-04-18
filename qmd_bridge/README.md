# QMD Bridge 实验层

这是给 `wiki_test` 加的一层 **QMD 风格集合检索入口**，对应方案 A：

- 保留现有四层知识库结构不动
- 把 `cards / topics / wiki / raw(md)` 映射成可检索 collections
- 用一个单独的 SQLite FTS5 索引承担跨层召回
- 查询结果显式返回 collection、display path、context，方便后续给 Agent 使用

## 为什么加这一层

现有知识库强在：
- 原文可追溯
- 结构化 cards 清晰
- topic/wiki 可沉淀稳定结论

这一层补的是：
- 跨层统一入口
- collection-aware 检索
- 更像 QMD 的 `search / get context / files` 使用方式

## 当前映射

| QMD 风格 collection | 对应目录 | 用途 |
|---|---|---|
| `cards` | `cards/sections/*.json` | 主证据层，段落级召回 |
| `topics` | `topics/*.md` | 主题入口层 |
| `wiki` | `wiki/*.md` | 导航与沉淀结论层 |
| `raw` | `raw/*.md` | 原始 Markdown 资料补充入口 |

> 说明：`raw/*.bin` 仍然保持原样，不直接纳入这个实验索引。

## 构建索引

```bash
python3 scripts/build_qmd_bridge_index.py
```

默认会生成：

- `index_store/qmd_bridge.db`

## 查询示例

```bash
python3 scripts/query_qmd_bridge.py "跨云互通" --brief
python3 scripts/query_qmd_bridge.py "AVC SVC 双引擎" --brief
python3 scripts/query_qmd_bridge.py "风铃 迭代" -c raw -c topics --brief
python3 scripts/query_qmd_bridge.py "AE700" --files
```

## 当前定位

这不是要替代现有 `query_default.js / query_v2.js / query_fts5.py`，而是新增一个实验入口：

- 适合先粗看“哪个层最先命中”
- 适合给 Agent 做 collection-aware 召回
- 适合后续接 BCE embedding / reranker / doc body retrieval

## 下一步可继续补

1. 在此索引上增加 embedding 召回
2. 加入 reranker 做最终精排
3. 支持 `get / multi-get` 风格的正文回读
4. 给不同 collection 设更细的 boost 策略
