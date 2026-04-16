# Index Store Usage

## What this is

This is the fast retrieval layer for `wiki_test`.

## Files

- `master_index.json`: all section metadata across all indexed documents
- `docs/*.json`: per-document section index with full section body
- `keyword_index.v1.json`: keyword -> card ids 的倒排索引
- `alias_index.v1.json`: alias / 别名 -> card ids 的倒排索引
- `product_index.v1.json`: 产品型号 -> card ids 的倒排索引
- `topic_index.v1.json`: topic / entity tag -> card ids 的倒排索引
- `scenario_index.v1.json`: 场景标签 -> card ids 的倒排索引
- `card_type_index.v1.json`: card_type -> card ids 的倒排索引
- `README.md`: human-readable section catalog
- `FTS5_USAGE.md`: SQLite FTS5 本地全文召回说明

## Retrieval strategy

### Legacy path
1. Match the query against section titles and paths.
2. Locate matching section ids in `master_index.json`.
3. Open the corresponding `docs/<doc>.json` file.
4. Return the exact `body` of the matched section.
5. Only summarize if the user explicitly asks.

### V1 fast path
1. Use `query_router/routes.v1.json` to route the query to a topic or product lane first.
2. Hit `alias_index.v1.json` / `product_index.v1.json` / `keyword_index.v1.json` to build a small candidate set.
3. Use `card_metadata.v1.json`, `card_type_index.v1.json`, and `intent_index.v1.json` to prefer intent-aligned cards and suppress known distractors.
4. Read only the small set of candidate cards for body-level verification.
5. Return candidates with `match_percent`, and explicitly label `强命中 / 弱相关 / 排除项` when the query needs precision.
6. Fall back to `master_index.json` and `docs/*.json` only when the V1 indexes do not produce enough confident hits.

## Current status

Indexed documents: 6
Indexed sections: 1011

## Notes

This index is title-first and section-first. It is meant to replace slow full-document rescans for common retrieval questions.

## Precision-oriented retrieval

For ambiguous queries like `跨云互通`, prefer the route-specific lane first instead of broad text matching.

### V1

```bash
node scripts/retrieve_v1.js 跨云互通
```

### V2

```bash
python3 scripts/build_v2_semantic_metadata.py
node scripts/query_default.js --brief 跨云互通
python3 scripts/query_fts5.py "跨云互通" --brief
node scripts/query_v2.js --json --top 5 AVC+SVC双引擎
python3 scripts/auto_refine_v2.py
```

V2 returns:
- parsed intent plan
- top candidates
- `match_percent`
- `强命中 / 弱相关 / 排除项`
- summary counts

FTS5 role:
- 负责宽松全文硬召回，适合模糊关键词、多词组合、别名不稳定的查询
- 不替代 topic / route / metadata 精排
- 命中后仍需回读 cards 或 source page 做最终确认

CLI options:
- `query_default.js --brief` 作为默认入口输出紧凑摘要
- `query_v2.js --json` 输出结构化 JSON
- `query_fts5.py --brief` 输出本地全文召回摘要
- `--top N` 控制返回条数
- `--min-score N` 控制最低分
- `--include-excluded` 保留排除项结果

Feedback loop:
- 写入 `updates/retrieval_feedback/*.json`
- 运行 `python3 scripts/auto_refine_v2.py`
- 查看 `auto_refine_report.v2.json` 建议下一轮精修
