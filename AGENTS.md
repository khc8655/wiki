# 知识库处理规则

## 查询规则（强制）⛔

### 架构原则：大模型是代理，不是处理器

```
用户提问 → 大模型理解意图 → 运行 query_unified.py → stdout 原样转发给用户
                                                    ↑
                                              大模型绝不触碰
```

大模型在此知识库系统中的**唯一作用**：理解用户说了什么，决定跑哪个查询。
引擎输出 = 最终答案，大模型不参与内容生产。

### 操作（只有一种）

```bash
python3 query_unified.py "用户原始问题"
# 或
python3 query_unified.py "用户原始问题" --all
```

把 stdout 直接转发给用户。不加前置语、不加后置语、不改内容。

### 禁止行为

- ❌ 修改引擎输出的任何字词
- ❌ 将引擎输出压缩/提炼/重组/转述
- ❌ 在结果前后加"好的"、"为您查询"、"以上是"等
- ❌ 用自己的分析、评价、建议替换引擎输出
- ❌ 用 grep/read 手动搜索 raw/ 然后自行整理

## 知识库结构

```
wiki_test/
├── query_unified.py      # 统一查询入口（四源路由）
├── raw/                  # 原始文档
├── cards/sections/       # 结构化卡片（1885张, 含 semantic 标注）
├── topics/               # 主题聚合页
├── excel_store/          # Excel 表格数据
├── index_store/          # 索引 + embeddings + feedback log
└── lib/                  # 核心库模块
```

## 查询入口

> 外部 agent 请先看根目录 [CLAUDE.md](../CLAUDE.md)（跨平台自动发现）

### 主入口：query_unified.py（四源路由引擎）

```bash
# 表格类 - 型号/价格/参数/对比
python3 query_unified.py "AE700的接口参数"
python3 query_unified.py "GE600招标参数"

# 方案类 - 概念/场景/架构（跨文档混合检索）
python3 query_unified.py "视频会议安全加密方案"

# 更新类 - 版本迭代/新功能
python3 query_unified.py "3月迭代新功能"

# JSON 输出 + 反馈
python3 query_unified.py "查询" --json
python3 query_unified.py "查询" --feedback good
python3 query_unified.py "查询" --verbose
```

### 离线脚本

```bash
python3 scripts/annotate_cards.py           # 卡片标注
python3 scripts/build_embeddings.py         # 向量化构建
python3 scripts/organize_cards.py --dry-run # 卡片自组织分析
python3 scripts/run_fast_tests.py           # 9项测试
```

## 四源路由

| 意图 | 路由 | 检索方式 | 输出 |
|------|------|----------|------|
| 型号+价格/参数/对比 | 表格类 | SQLite 列语义映射 | 价格/参数原文 + 行号 |
| 概念/场景/架构 | 方案类 | BM25+Vector 混合 | 段落原文 + doc:path |
| 版本/迭代/更新 | 更新类 | BM25 粗粒度 | 完整段落原文 |
| PPT内容 | PPT类 | 图片理解卡片 | doc + 页码 |

## 模型配置

| 模型 | 角色 |
|------|------|
| Qwen/Qwen3-8B（关闭思考） | 段落标注 + 查询理解 + 对话优化 |
| BAAI/bge-large-zh-v1.5 | 1024维语义向量化 |
| API: SiliconFlow | 免费模型托管 |

## 输出格式示例

**正确：**
```
标题: 国密加密方案
正文原文: ......（不总结, 直接贴原文）
出处: 06-新一代视频会议系统建设方案模板.md | 安全保障 > 国密加密
命中率: 92%
```

**错误：**
- 直接输出总结列表
- 不标来源
- 不显示命中率

## 自组织回路

- 🔄 **反馈闭环**: 每次查询自动记录到 `index_store/query_feedback.jsonl`
- 🔄 **权重优化**: 积累反馈 → 自动调权（`--optimize`）
- 🔄 **卡片聚类**: embedding 相似性 → 建议合并/关联/主题提炼

---

**任何 agent 处理本知识库前，必须先读此文件。**
