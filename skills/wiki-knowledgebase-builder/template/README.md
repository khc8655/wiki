# {{PROJECT_NAME}}

{{PROJECT_DESC}}

---

## Version

**Current version**: v0.1

---

## Architecture

This project follows a layered knowledge-base architecture:

```text
Layer 1: raw/          source of truth
Layer 2: cards/        retrieval units
Layer 3: topics/       theme narrowing layer
Layer 4: wiki/         synthesized knowledge
```

## Query workflow

All queries follow the same chain:
1. Query understanding
2. Route selection
3. Structured recall
4. Evidence readback
5. Final answer

Default answer skeleton:
- Query理解
- 召回入口
- 命中证据
- 回答

## Suggested entrypoints

```bash
node scripts/query_default.js --brief <query>
node scripts/query_v2.js --json <query>
```
