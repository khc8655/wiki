# 查询工作流与工具说明

本文只描述**当前实际使用的查询流程**，不讨论远期方案。

## 文档分类

知识库中的文档先分两类：

1. `solution`
   - 用途：日常写方案、架构能力说明、材料复用
   - 特点：细粒度切分，优先召回 `cards`

2. `release_note`
   - 用途：查询具体功能、型号、版本更新说明
   - 特点：粗粒度切分，优先按整节/整功能块召回

文档类型声明文件：
- `qmd_bridge/doc_profiles.json`

## 工具与定位

### 1. `node scripts/query_default.js --brief <query>`
**定位**：默认查询入口。

**作用**：
- 先判断问题更像 `solution` 还是 `release_note`
- 显式给出回答模式：默认 `evidence`，只有明确出现“总结 / 归纳 / 对比 / 话术 / 汇报 / 提炼 / 润色”等意图时才切到 `synthesis`
- 更新类问题优先转给 `query_qmd_bridge.py`
- 方案类问题继续走 `query_v2_core.js`

**什么时候用**：
- 不确定该走哪条链路时，先用它
- 日常检索默认先从这里进入

### 2. `node scripts/query_v2.js --json <query>`
**定位**：方案类精确检索入口。

**作用**：
- 使用 intent / concept / high-priority cards 做结构化召回
- 适合架构、能力、场景类问题

**什么时候用**：
- 你已经明确这是方案类问题
- 需要更稳定的结构化召回结果

### 3. `python3 scripts/query_fts5.py "<query>" --brief`
**定位**：宽召回入口。

**作用**：
- 用 SQLite FTS5 做硬召回
- 适合关键词散、别名多、措辞不稳定的查询

**什么时候用**：
- 默认查询命中不足
- 需要补充全文关键词搜索

### 4. `python3 scripts/query_qmd_bridge.py "<query>" ...`
**定位**：按文档类型分流的 collection 检索入口。

**常用 collection**：
- `solution_cards`
- `solution_topics`
- `solution_wiki`
- `release_notes`

**什么时候用**：
- 需要显式指定文档类型
- 需要先判断命中在哪一层
- 需要更新说明文档的粗粒度召回

### 5. `python3 scripts/build_qmd_bridge_index.py`
**定位**：重建 QMD bridge 索引。

**什么时候用**：
- 修改了 `qmd_bridge/doc_profiles.json`
- 新增了 `raw/*.md`
- 更新了 `cards/sections/*.json`
- 调整了 collection 或切分规则

## 推荐流程

### A. 方案类问题
示例：
- 跨云互通
- AVC SVC 双引擎
- 安全架构

流程：
1. 先用默认入口
   ```bash
   node scripts/query_default.js --brief "跨云互通"
   ```
2. 若要显式限制到方案层
   ```bash
   python3 scripts/query_qmd_bridge.py "跨云互通" -c solution_cards -c solution_topics --brief
   ```
3. 回读命中的 `cards/sections/*.json` 原文
4. 默认输出检索入口、命中路径、原文证据和必要的轻量定位说明；只有用户明确要求时再做总结/归纳

### B. 更新说明类问题
示例：
- AE700 新功能
- 风铃 迭代
- 某版本支持什么

流程：
1. 先用默认入口
   ```bash
   node scripts/query_default.js --brief "AE700 新功能"
   ```
2. 若要显式限制到更新说明层
   ```bash
   python3 scripts/query_qmd_bridge.py "AE700 新功能" -c release_notes --brief
   ```
3. 需要更完整上下文时，直接回读对应 `raw/*.md`
4. 默认输出版本、型号、功能块和对应原文块；不要默认把功能块再总结成一层结论，只有用户明确要求时再做总结/归纳

### C. 命中不足时补宽召回
```bash
python3 scripts/query_fts5.py "AE700 串口绑定" --brief
```

## 原文回读原则

- `solution` 问题，优先回读 `cards/sections/*.json`
- `release_note` 问题，优先回读对应 `raw/*.md` 的整节或整功能块
- 不直接凭检索标题作答
- 不把召回列表当最终答案
- 不默认把原文证据再交给模型做总结；默认输出应以原文块、证据和检索入口为主
- 默认回答模式为 `evidence`
- 只有用户明确提出“总结 / 归纳 / 对比 / 话术 / 润色成文”时，才允许切到 `synthesis` 做综合整理
