# Cross-cloud Interconnect Retrieval Topic (V1)

## Coverage
- 跨云视频会议系统互通
- 原 MCU 与云视频 MCU 融合会管
- 新旧系统统一调度与会议控制

## High-priority cards
- 06-新一代视频会议系统建设方案模板-sec-224

## Exclude unless user explicitly asks
- 06-新一代视频会议系统建设方案模板-sec-076 （混合云部署）
- 06-新一代视频会议系统建设方案模板-sec-226 （跨网/跨域安全）

## Retrieval advice
1. 查询包含“跨云”时，先命中 `routes.v1.json` 中的 `cross-cloud-interconnect`。
2. 优先读取 `intent_index.v1.json` 中的 `cross-cloud-interconnect` 候选。
3. 若候选仅命中“混合云 / 跨网 / 跨域”而不含“跨云 / 融合会管 / 原MCU / 云视频MCU”，应降权或排除。
4. 回答时展示每条候选的匹配度，并区分“强命中 / 弱相关 / 排除项”。
