# 知识库处理规则

## 查询规则（强制）

1. **默认不总结** — 优先给出检索入口、原文证据、必要的轻量定位说明
2. **只有用户明确要求"总结"时才输出总结**
3. **必须标注来源** — 每个引用都要标明文件路径和来源
4. **命中率必须显示** — 每条结果标注匹配度

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
| Qwen/Qwen2.5-7B-Instruct | 段落标注 + 查询理解 + 对话优化 |
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
