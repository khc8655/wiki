# Project Template

Use this as a starting point for a new knowledge-base repository or workspace.

```text
project-root/
├── AGENTS.md
├── README.md
├── CHANGELOG.md
├── docs/
│   ├── architecture.md
│   └── retrieval-v2-design.md
├── raw/
├── cards/
│   ├── sections/
│   └── card_metadata.v2.json
├── index_store/
├── topics/
├── wiki/
│   ├── index.md
│   ├── log.md
│   └── sources/
├── scripts/
└── updates/
    └── retrieval_feedback/
```

## Minimum documentation to include

### `AGENTS.md`
- project goal
- ingest workflow
- fixed query workflow
- no shortcut rule
- output expectations

### `README.md`
- architecture summary
- corpus stats
- query entrypoints
- update workflow
- changelog summary

### `docs/retrieval-v2-design.md`
- card schema
- index design
- query flow
- optimization strategy

## Minimum script entrypoints

- `scripts/query_default.js`
- `scripts/query_v2.js`

## Nice-to-have extras

- query logger
- feedback CLI
- route analysis script
- index rebuild scripts

## Migration order

1. import raw sources
2. split into cards
3. generate metadata
4. build indexes
5. write topics
6. write wiki synthesis
7. fix retrieval routes
8. add feedback loop
```