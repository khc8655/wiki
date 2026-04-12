# Retrieval Policy

## Core objective

This knowledge base is optimized for **precise retrieval of original content by title and paragraph meaning**, not summary-first answering.

## User intent model

When the user asks a question such as:

- 云视频在安全方面的保障
- 稳定性相关内容
- 会控能力有哪些
- 兼容利旧相关内容

the system should:

1. Understand the meaning of the query.
2. Map the query to relevant titles, section headings, and paragraph-level topics.
3. Retrieve **all relevant original content** from the source documents.
4. Exclude unrelated content.
5. Avoid omission.
6. Preserve original wording as much as possible.

## Output rule

Default output is:

- list the matched source sections
- keep the original content
- do not summarize unless the user explicitly asks for summarization or extraction

## Retrieval priority

1. Exact title matches
2. Semantically equivalent titles
3. Paragraphs whose meaning directly matches the query
4. Only then, nearby supporting paragraphs when they are necessary for completeness

## Precision constraints

- Prefer missing nothing over aggressive compression.
- Do not include broad surrounding text unless it is necessary to preserve meaning.
- Do not mix in adjacent but irrelevant sections.
- If uncertain whether a paragraph is relevant, mark it as borderline instead of silently merging it.

## Secondary workflow

If the user later asks for:

- 总结
- 提炼
- 对比
- 汇总
- 形成答案

then the retrieved original content becomes the input for a second-pass synthesis.
