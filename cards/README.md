# Knowledge Middle Layer

## Structure
- `cards/sections/*.json`: section cards with tags and original text
- `cards/manifest.json`: all section card metadata
- `topics/*.md`: topic aggregation pages

## Topics
- security
- stability
- meeting-control
- architecture

## Query flow
1. Match query through `query_router/routes.json`.
2. Read the matched topic or subtopic page.
3. Read exact card bodies.
4. Return original content first.
5. Summarize only on request.