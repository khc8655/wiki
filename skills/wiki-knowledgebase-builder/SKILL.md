# wiki-knowledgebase-builder

Build and operate an LLM-managed knowledge base using the `wiki_test` method: layered storage, topic-guided retrieval, evidence-first answering, and iterative optimization.

## Use this skill when

Use this skill when the user wants to:
- create a new knowledge base project from documents, notes, whitepapers, or exported pages
- migrate an existing retrieval corpus into a structured wiki/cards/topics layout
- make another OpenClaw agent or workspace follow the same knowledge-base workflow
- standardize query behavior, evidence presentation, and retrieval optimization
- turn an ad-hoc retrieval project into a reusable method

Do not use this skill for one-off fact lookup inside an existing knowledge base unless the user is only asking a normal content question.

## Core method

This skill packages a reusable knowledge-base workflow with these principles:

1. **Layered architecture**
   - `raw/` is immutable source material
   - `cards/` is the main retrieval unit
   - `index_store/` and other indexes are precompiled retrieval metadata
   - `topics/` narrows a theme before reading evidence
   - `wiki/` stores synthesized long-term knowledge

2. **Evidence first**
   - Default to retrieving original evidence before summarizing
   - Separate retrieved evidence from synthesis
   - Prefer precise source-aligned sections over fluent but unsupported answers

3. **Fixed query chain**
   - Query understanding
   - Route selection
   - Structured recall
   - Evidence readback
   - Final answer

4. **No shortcut rule**
   - Do not jump from filename hits or memory directly to final conclusions
   - Always expose retrieval basis when doing knowledge-base work

5. **Continuous optimization**
   - Add indexes for common query patterns
   - Promote repeated retrieval routes into durable rules
   - Track query logs and feedback when useful

## Deliverables

When creating a new knowledge-base project, produce or update these categories as needed:

- workspace guidance: `AGENTS.md`
- project overview: `README.md`
- retrieval design: `docs/retrieval-v2-design.md`
- source corpus: `raw/`
- retrieval cards: `cards/sections/*.json`
- retrieval metadata: `cards/card_metadata.v2.json`, `index_store/*.json`
- topic pages: `topics/*.md`
- synthesized wiki: `wiki/`
- query scripts: `scripts/query_default.js`, `scripts/query_v2*.js`
- maintenance docs: `CHANGELOG.md`, feedback docs, usage docs

## Required workflow

### 1. Understand the target

First clarify:
- what corpus is being managed
- whether the user needs a new project, a migration, or a reusable skill/template
- whether the project is optimized for raw retrieval, synthesis, or both
- expected query types: product, capability, architecture, scenario, troubleshooting, etc.

### 2. Set up the layer model

Create or verify a structure equivalent to:

```text
raw/
cards/
index_store/
topics/
wiki/
scripts/
docs/
updates/
```

Keep `raw/` read-only once imported.

### 3. Define ingestion rules

For each source:
- preserve the original source in `raw/`
- split by section or paragraph into cards
- keep title, path, body, and source identity
- generate semantic metadata for retrieval
- build or refresh indexes
- update topic and wiki layers only after card-level evidence exists

### 4. Define query behavior

All knowledge-base queries should follow this fixed chain:

1. Query understanding
2. Route selection
3. Structured recall
4. Evidence readback
5. Answer generation

Default answer skeleton:
- Query理解
- 召回入口
- 命中证据
- 回答

If the user asks to find/locate/query content, return matched evidence first.
If the user asks for an introduction/comparison/summary/talk track, synthesize only after evidence is confirmed.

### 5. Add routing and indexes

Prefer fewer strong routes over many weak ones.
Typical useful indexes include:
- product/model index
- intent index
- concept index
- negative concept index
- path siblings index
- model reverse index

### 6. Add operating rules

Write durable rules into project docs, especially:
- query chain
- no shortcut rule
- evidence-first policy
- output format expectations
- update and changelog habits

### 7. Add optimization loop

If the project will evolve, add:
- query log collection
- user feedback collection
- analysis scripts
- route/index refinement process

## Recommendations

- Start simple, then compile more retrieval intelligence into indexes
- Promote repeated fixes into docs or scripts, not just one-off replies
- Prefer topic narrowing before reading many cards
- Keep raw evidence and synthesized knowledge clearly separated
- Version retrieval behavior in changelog/docs when it materially changes

## Anti-patterns

Avoid these:
- editing `raw/` after import
- answering from memory when evidence is available
- letting topic pages become unsupported summaries without card backing
- mixing retrieval evidence with synthesis without labeling the difference
- relying only on keyword grep when durable indexes would solve the query class

## File references

Read these local references when authoring or migrating a project:
- `references/method-summary.md`
- `references/project-template.md`

## Output expectation for this skill

When asked to create or adapt a project with this skill, produce:
- the concrete files or edits
- a short explanation of the chosen structure
- any remaining gaps or next steps
- a git commit when changes are made
