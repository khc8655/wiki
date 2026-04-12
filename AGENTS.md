# wiki_test AGENTS

## Goal

Maintain `wiki_test` as an LLM-managed knowledge base, with **title-driven and paragraph-precise retrieval as the primary mode**.

## Layers

- `raw/`: immutable source documents
- `wiki/`: synthesized markdown pages
- `wiki/index.md` and `wiki/log.md`: navigation and chronology

## Ingest workflow

When a new source is added:

1. Read the source.
2. Create or update one source summary page under `wiki/sources/`.
3. Update relevant topic/system/capability/operations pages.
4. Add links from synthesized pages back to source pages.
5. Update `wiki/index.md` if new pages appear.
6. Append an entry to `wiki/log.md`.

## Query workflow

When answering a question:

1. First understand the user's query at the level of title meaning and paragraph meaning.
2. Read `wiki/heading-index.md` and relevant source pages to identify the likely matching sections.
3. Prefer exact original content from the source-aligned pages.
4. Return the matched original content in full, without summarizing, unless the user explicitly asks for summary or extraction.
5. If the user asks for synthesis later, treat the retrieved original content as the source material for a second-pass summary.

## Lint workflow

Periodically check for:

- orphan pages
- missing cross-links
- contradictory claims
- topic pages that are still scaffolds
- source pages lacking structured extraction

## Rules

- Never edit files under `raw/`.
- Prefer updating existing synthesized pages over creating duplicates.
- Mark provisional conclusions clearly when full extraction is incomplete.
- Keep pages concise, link-rich, and evidence-backed.
- For retrieval tasks, precision is more important than fluent summary.
- Do not summarize by default when the user asks to find content.
- Avoid both omission and irrelevant spillover.
