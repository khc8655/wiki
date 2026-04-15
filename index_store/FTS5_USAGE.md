# SQLite FTS5 本地检索底座

这是一个只依赖本机 SQLite FTS5 的轻量检索底座，用于给知识库提供本地全文召回能力。

## 文件

- `scripts/build_fts5_index.py`：从 `cards/sections/*.json` 和 `cards/card_metadata.v2.json` 构建本地 SQLite FTS5 索引
- `scripts/query_fts5.py`：查询本地 FTS5 索引
- `index_store/fts5_cards.db`：生成后的本地索引库

## 构建索引

```bash
python3 scripts/build_fts5_index.py
```

## 查询示例

```bash
python3 scripts/query_fts5.py "AE700 产品介绍" --brief
python3 scripts/query_fts5.py "应急指挥 调度" --top 10
```

## 当前定位

FTS5 适合承担：
- 型号、版本号、产品名的硬召回
- 全文检索
- 本地低成本 BM25 排序
- 配合轻量规则做 doc/type/product 优先级修正
- 作为后续 BCE / reranker 的候选召回底座

## 建议组合

推荐后续采用：
- FTS5 负责硬召回
- BCE embedding 负责软语义召回
- reranker 负责最终精排
