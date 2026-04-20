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

When answering a question, always use the same fixed retrieval chain. Do not skip steps just because you already know the answer.

### Mandatory fixed workflow

1. **Query understanding**
   - Normalize the user's query into: object / intent / required constraints / optional preferences / exclusions.
   - Default to **raw evidence** or **brief extraction**.
   - Only choose **final synthesis** when the user explicitly asks for summary / comparison / talk track / polished writeup.

2. **Route selection**
   - Product or model queries: first check product/model indexes or topic hints.
   - Capability / architecture / scenario queries: first check topic pages and retrieval indexes.
   - Unknown / mixed queries: start from `node scripts/query_default.js --brief <query>`.
   - Broad keyword / wording-uncertain / multi-term queries: allow `python3 scripts/query_fts5.py "<query>" --brief` as a hard-recall entry, then still return to structured verification.

3. **Structured recall**
   - Use the selected index / topic / route / FTS5 entry to retrieve candidate cards.
   - Record which topic, route, index, or hint produced the candidates.
   - Treat FTS5 as a hard-recall layer, not final evidence ranking.
   - If one card is clearly in a section, expand to sibling cards when needed for completeness.

4. **Evidence readback**
   - Read the top matching section cards or source-aligned pages.
   - Prefer exact original content and preserve the source boundary.
   - Do not answer from memory when the evidence can be read directly.

5. **Answer generation**
   - Default output should explicitly show: **query understanding → recall basis → evidence → answer**.
   - If the user asked to “find / query / locate”, return the matched original content first.
   - Do **not** synthesize by default for requests like “介绍 / 详细介绍 / 看看更新了什么 / 有哪些功能”; these still default to evidence-first output unless the user explicitly asks for summary / comparison / talk track / polished writeup.
   - Synthesize only after evidence is confirmed and only when the user explicitly asks for it.

6. **No shortcut rule**
   - Do not jump directly from a filename hit or a remembered section to a final answer.
   - Do not hide the retrieval basis.
   - All future queries follow this same chain unless the user explicitly asks for a faster informal answer.

### Output expectations

- Always mention the retrieval entry you used, for example: topic page, model index, default query script, FTS5 recall, or specific card path.
- Always separate **retrieved evidence** from **your synthesis**.
- For retrieval tasks, precision is more important than fluency.
- For synthesis tasks, evidence still comes first.

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
