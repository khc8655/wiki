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
3. Use `card_metadata.v1.json` and `card_type_index.v1.json` to prefer `overview` / `scenario` / `product` cards over placeholders.
4. Read only the small set of candidate cards for body-level verification.
5. Fall back to `master_index.json` and `docs/*.json` only when the V1 indexes do not produce enough confident hits.

## Current status

Indexed documents: 6
Indexed sections: 1011

## Notes

This index is title-first and section-first. It is meant to replace slow full-document rescans for common retrieval questions.
