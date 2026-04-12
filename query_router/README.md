# Query Router

## Purpose

Route a user query to the best matching topic or subtopic before reading section cards.

## Flow

1. Match query text against `intent_aliases`.
2. Prefer the highest-priority specific route when available.
3. Read the mapped subtopic page(s).
4. Read the referenced section cards.
5. Return original content first, summarize only on request.

## Examples

- “云视频系统在安全方面有哪些保障措施” -> `security`
- “传输安全怎么做” -> `security-transport`
- “录像和存储安全怎么保障” -> `security-storage`
- “鉴权和权限控制有哪些措施” -> `security-access-control`
- “稳定性保障措施有哪些” -> `stability`
- “多活热备和无单点故障怎么实现” -> `stability-architecture`
- “弱网和抗丢包能力如何” -> `stability-network`
- “怎么扩容和做运维保障” -> `stability-operations`
- “云视频平台在AI方面有哪些应用场景” -> `ai` / `ai-overview` (V1)
- “AE700包含哪些组件” -> `product-ae700` (V1)

## V1 additions

- `routes.v1.json` adds AI and product-specific routes for faster recall.
- Prefer V1 routes before falling back to the legacy generic routes.
- Pair route hits with `index_store/*.v1.json` to avoid whole-library rescans.
