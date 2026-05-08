# wiki_test 知识库系统

> Karpathy-style 自组织知识库：意图驱动 · 结构化查询 · 反馈闭环 · 卡片进化

[![Version](https://img.shields.io/badge/version-v3.4-blue.svg)]()
[![Setup](https://img.shields.io/badge/setup-python3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

---

## 快速开始

> ⛔ **Agent / AI 用户必读：先看 [CLAUDE.md](CLAUDE.md)** — 定义了本知识库的查询行为规范，违反即错误。  
> 人类用户请直接看下方示例。

```bash
git clone https://github.com/khc8655/wiki.git
cd wiki

# 环境检查
python3 setup.py --check

# 运行测试
python3 scripts/run_fast_tests.py

# 查询
python3 query_unified.py "视频会议安全加密方案"
python3 query_unified.py "AE700的接口参数" --json
```

---

## 意图驱动的结构化查询

```
用户查询
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  意图识别器                                           │
│  ├─ price_query: 价格查询 → SQL查pricing表            │
│  ├─ category_list: 分类列举 → SQL按category分组       │
│  ├─ compare_table: 对比表格 → SQL聚合comparison表     │
│  ├─ tender_params: 招标参数 → SQL查proposal表         │
│  ├─ spec_query: 参数查询 → SQL查comparison+proposal   │
│  ├─ accessory: 配件查询 → SQL按category匹配          │
│  ├─ eol_info: 停产信息 → SQL检查note字段             │
│  └─ solution: 方案描述 → hybrid搜索cards              │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  SQL查询策略                                          │
│  ├─ 结构化查询：直接SQL，保留表格关系                  │
│  ├─ 分组聚合：按category/spec_name分组               │
│  ├─ 精确匹配：用model字段精确匹配                    │
│  └─ 多意图过滤：根据关键词过滤参数类型               │
└──────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  结构化输出                                           │
│  ├─ 价格：动态评分 + 去重 + 实际出处                  │
│  ├─ 分类：汇总表格 + 详情                            │
│  ├─ 对比：聚合表格 + 差异摘要                        │
│  ├─ 参数：结构化表格（单模型竖排/多模型对比）         │
│  └─ 招标：完整招标参数                               │
└──────────────────────────────────────────────────────┘
```

---

## v3.4 更新内容

### 🔴 关键修复
- **spec_query 路由修复**：接口参数查询现在走SQL而非知识库搜索
- **价格去重**：PE8000等重复行合并，空价格行过滤

### 🟡 体验优化
- **动态命中率**：精确匹配=1.0，名称包含=0.9，category匹配=0.7
- **实际出处**：从硬编码"pricing表"改为 `文件:Sheet:行号`
- **对比摘要**：自动标注差异项和相同项
- **配件排除**：配件查询不再包含主产品本身
- **多意图支持**："简单参数和招标参数"同时返回两种类型

### ⚪ 算法改进
- **BM25归一化**：从max-norm改为true min-max
- **tag_boost修复**：hybrid检索现在正确传递tags/keywords/semantic
- **超5条汇总**：大量结果先输出汇总表格再输出详情

---

## 查询示例

```bash
# 表格类 - 型号+意图
python3 query_unified.py "AE700的接口参数"
python3 query_unified.py "GE600招标参数"
python3 query_unified.py "XE800与AE800对比"

# 多意图查询
python3 query_unified.py "GE600的简单参数和招标参数"  # 同时返回渠道参数+招标参数

# 分面过滤（结果 >5 条时自动输出分面摘要）
python3 query_unified.py "小鱼易连"            # 输出: 招标参数(phase_tender):N | 方案参数(phase_proposal):N
python3 query_unified.py "小鱼易连" --facet tender   # 只查招标参数
python3 query_unified.py "小鱼易连" --facet 规格参数  # 只查规格参数

# 方案类 - 概念/场景
python3 query_unified.py "视频会议安全加密方案"
python3 query_unified.py "公安行业解决方案"

# 更新类 - 版本/迭代
python3 query_unified.py "3月迭代新功能"
python3 query_unified.py "终端功能更新"

# 反馈 + 优化
python3 query_unified.py "查询内容" --feedback good
python3 query_unified.py "查询内容" --verbose    # 显示诊断信息
python3 query_unified.py --optimize              # 分析反馈, 建议权重

# 卡片组织
python3 scripts/organize_cards.py --dry-run --cluster 10
python3 scripts/organize_cards.py --merge --related --topics --all
```

---

## 目录结构

```
wiki/
├── query_unified.py          # 统一查询入口 (四源路由)
├── db/excel_store.db         # SQLite 数据库（含分面 facet 字段）
├── config.yaml               # 主配置
├── setup.py                  # 环境检查
├── lib/
│   ├── phase_field_map.yaml  # Excel 行值→facet 映射表
│   ├── excel_db.py          # Excel → SQLite 查询引擎
│   ├── llm_client.py        # SiliconFlow API 封装
│   ├── annotator.py         # 段落级语义标注
│   ├── embedder.py          # 向量化构建
│   ├── retrieval_bm25.py    # BM25 关键词检索
│   ├── vector_search.py     # 余弦相似度向量检索
│   ├── hybrid_retriever.py  # BM25+Vector 融合
│   ├── feedback.py          # 查询日志 + 反馈记录
│   ├── query_refiner.py     # 低质量查询对话优化
│   ├── weight_optimizer.py  # 基于反馈的自动权重调优
│   └── card_organizer.py    # 卡片自组织 (相似/聚类/合并)
│
├── scripts/                  # 离线脚本
│   ├── annotate_cards.py    # 全量卡片标注
│   ├── build_embeddings.py  # 向量化构建
│   ├── build_excel_knowledge.py  # Excel 入库（含分面提取）
│   ├── organize_cards.py    # 卡片聚类 + 主题生成
│   ├── run_fast_tests.py    # 11项测试用例
│   ├── import_from_nas.py   # NAS数据导入
│   └── refresh_from_nas.sh  # NAS数据刷新
│
├── cards/sections/           # 1885张结构化卡片 (含 semantic 标注)
├── cards/manifest.json       # 卡片清单
├── excel_store/              # Excel 数据源
├── index_store/              # 索引 + embeddings + feedback log
├── raw/                      # 原始 Markdown 文档
└── topics/                   # 主题聚合页
```

---

## 数据源

| 类型 | 存储 | 检索方式 | 粒度 |
|------|------|----------|------|
| 表格类 | `excel_store/` → `db/excel_store.db` | SQLite + 列语义映射 | 行列 |
| 方案类 | `cards/sections/*.json` | BM25 + Vector (1024维) | 段落级 |
| 更新类 | `cards/sections/*.json` | BM25 粗粒度 | 整标题段 |
| PPT类 | `ppt_analysis/` | 图片理解卡片 | 页级 |

---

## 版本历史

### v3.4 — 查询引擎全面优化
- 🔴 spec_query 路由修复（接口参数走SQL而非知识库）
- 🔴 价格去重 + 空价格过滤
- 🟡 动态命中率评分（1.0→0.9→0.7）
- 🟡 实际出处显示（非硬编码）
- 🟡 对比查询差异摘要
- 🟡 配件查询排除主产品
- 🟡 多意图查询支持
- ⚪ BM25 min-max 归一化
- ⚪ tag_boost 数据传递修复
- ⚪ 超5条结果汇总表格
- ⚪ SQL注入修复

### v3.3 — 意图驱动架构重构
- ✅ 7种意图各走SQL策略
- ✅ pricing表category字段补充AI分类和配件关联
- ✅ proposal卡片标题自动包含型号

### v3.1 — Karpathy-style 自组织知识系统
- 🔄 反馈闭环：查询自动记录, 低质量触发对话式优化
- ⚖️ 权重优化：基于反馈自动调权 (Trust Region, 渐进式)
- 🧩 卡片聚类：embedding 相似性 → 合并/关联/主题提炼
- 📝 query_unified.py 重写：统一四源路由入口

### v3.0 — 标注+检索链路重构
- ✅ Qwen2.5-7B 段落级中文语义标注
- ✅ bge-large-zh-v1.5 向量化 (1773卡全量)
- ✅ BM25 + Vector 混合检索取代残缺 semantic boost
- ✅ 去除 WebDAV 中转和零碎索引

### v1.2 — 深度融合
- ✅ GLM-4-9B 标注层深度融合
- ✅ 双路召回（原文 + 语义标签）

### v1.1 — 语义路由
- ✅ 意图识别路由
- ✅ Excel 数据源支持

### v1.0 — 基础检索
- ✅ 文档切片 + FTS5 全文检索

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [AGENTS.md](AGENTS.md) | **Agent 必读**：工作流规范、查询规则 |
| [QUICKSTART.md](QUICKSTART.md) | 5分钟快速上手 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构设计 |
| [API.md](API.md) | 脚本/API 参考 |
| [CHANGELOG.md](CHANGELOG.md) | 版本更新日志 |
| [docs/nas_import_guide.md](docs/nas_import_guide.md) | NAS数据导入指南 |

---

## License

MIT License
