# LLM Wiki Reference

Source URL: https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw/ac46de1ad27f92b28ac95459c782c07f6b8c964a/llm-wiki.md

> Imported from an external reference article for testing the wiki workflow.

## Summary

This reference proposes a three-layer personal knowledge base pattern:

1. Raw sources: immutable source documents.
2. Wiki: LLM-maintained markdown pages that accumulate synthesized knowledge.
3. Schema: instructions that constrain how the LLM ingests, updates, queries, and lint-checks the wiki.

Key operational loops:

- Ingest: process each new source, update summaries and linked pages.
- Query: answer questions from the wiki, and optionally file valuable answers back into the wiki.
- Lint: periodically detect contradictions, stale claims, missing links, and knowledge gaps.

Key design point: the wiki is a persistent, compounding artifact, not just retrieval over raw files.
