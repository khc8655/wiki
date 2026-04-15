# Retrieval V2 Design

## Goals

- heavy ingestion, light querying
- evidence-first retrieval
- iterative optimization

## Layers

- `raw/`
- `cards/sections/`
- `index_store/`
- `topics/`
- `wiki/`

## Card fields

Each card should preserve:
- id
- title
- path
- body
- source info
- semantic metadata

## Query flow

1. Query understanding
2. Candidate recall
3. Exclusion / rerank
4. Evidence readback
5. Final answer

## Optimization loop

Add query logs, feedback, and route/index updates over time.
