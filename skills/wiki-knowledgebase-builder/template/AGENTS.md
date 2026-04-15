# Project AGENTS

## Goal

Maintain this repository as an LLM-managed knowledge base with evidence-first retrieval.

## Ingest workflow

1. Preserve original sources in `raw/`
2. Split sources into section/paragraph cards under `cards/sections/`
3. Generate retrieval metadata and indexes
4. Update topic pages
5. Update wiki synthesis pages

## Query workflow

Always use the fixed retrieval chain:
1. Query understanding
2. Route selection
3. Structured recall
4. Evidence readback
5. Answer generation

## Rules

- Never edit files under `raw/` after import
- Do not answer from memory when evidence can be read directly
- Separate retrieved evidence from synthesis
- Do not jump from filename hits directly to conclusions
