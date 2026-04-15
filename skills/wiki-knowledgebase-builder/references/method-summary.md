# Method Summary

This reference captures the reusable method extracted from `wiki_test`.

## Architecture

- `raw/`: immutable source of truth
- `cards/sections/*.json`: paragraph/section retrieval units
- `cards/card_metadata.v2.json`: semantic metadata
- `index_store/*.json`: retrieval indexes
- `topics/*.md`: theme narrowing layer
- `wiki/`: synthesized durable knowledge

## Retrieval philosophy

- First retrieve original evidence, then synthesize
- Precision is more important than fluent summary
- Topic narrowing is preferred before broad card reading
- Retrieval basis should be visible in the answer

## Fixed query chain

1. Query understanding
2. Route selection
3. Structured recall
4. Evidence readback
5. Final answer

## Default output skeleton

- Query理解
- 召回入口
- 命中证据
- 回答

## Durable rules

- No shortcut from filename hit to final answer
- Do not answer from memory when cards/source can be read directly
- Keep evidence and synthesis explicitly separated
- Repeated retrieval fixes should be promoted into routes, indexes, docs, or scripts

## Common optimization patterns

- product/model index for hardware or named entities
- intent routes for repeated capability/scenario questions
- path siblings index for section completeness
- reverse index from model/entity to parent path
- query logs and feedback for iterative refinement
