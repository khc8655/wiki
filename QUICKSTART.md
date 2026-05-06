# wiki 快速上手指南 v3.2

> 5 分钟跑通知识库查询。

---

## 1. 环境检查（30秒）

```bash
cd wiki
python3 setup.py --check
python3 -c "import numpy, requests; print('deps OK')"
```

## 2. 设置 API Key（30秒）

```bash
export SILICONFLOW_API_KEY="your-siliconflow-api-key"
```

## 3. 查询（1分钟）

```bash
# 表格类 - 型号查询
python3 query_unified.py "AE700的接口参数"
python3 query_unified.py "PE8800参数"
python3 query_unified.py "GE600招标参数"

# 分面过滤
python3 query_unified.py "小鱼易连"              # 自动输出分面摘要
python3 query_unified.py "小鱼易连" --facet tender   # 只查招标参数

# 方案类 - 概念场景
python3 query_unified.py "视频会议安全加密方案"
python3 query_unified.py "公安行业解决方案"
python3 query_unified.py "多活热备容灾"

# 更新类 - 版本迭代
python3 query_unified.py "3月迭代新功能"

# JSON 格式
python3 query_unified.py "AE700的接口参数" --json

# 反馈 + 诊断
python3 query_unified.py "查询内容" --feedback good
python3 query_unified.py "查询内容" --verbose
```

## 4. 离线任务

```bash
# 入库新文档
./scripts/refresh_from_webdav.sh

# 全量标注 + 向量化（每次入库后运行）
python3 scripts/annotate_cards.py --doc-type solution
python3 scripts/build_embeddings.py

# Excel 入库（含分面提取）
python3 scripts/build_excel_knowledge.py

# 卡片自组织分析
python3 scripts/organize_cards.py --dry-run --cluster 10
python3 scripts/organize_cards.py --merge --related --topics --all

# 反馈分析 + 权重优化
python3 query_unified.py --optimize
python3 query_unified.py --optimize --optimize-apply
```

## 5. 数据源

| 类型 | 位置 | 检索 |
|------|------|------|
| 表格类 (Excel) | `excel_store/` → `db/excel_store.db` | SQLite + facet 分面 |
| 方案类 (MD) | `cards/sections/*.json` | BM25+Vector |
| 更新类 (MD) | `cards/sections/*.json` | BM25 粗粒度 |
| PPT类 | `ppt_analysis/` | 图片理解 |

## 6. 项目结构

```
wiki/
├── query_unified.py          # 四源路由引擎（主入口）
├── db/excel_store.db         # SQLite 数据库（含分面 facet 字段）
├── lib/
│   ├── phase_field_map.yaml  # Excel 行值→facet 映射表
│   ├── excel_db.py           # Excel SQLite 查询引擎
│   └── ...                   # 其他核心模块
├── scripts/
│   ├── annotate_cards.py     # 标注
│   ├── build_embeddings.py   # 向量化
│   ├── build_excel_knowledge.py  # Excel 入库
│   ├── organize_cards.py     # 聚类/主题
│   └── run_fast_tests.py     # 9项测试
├── cards/sections/           # 1885张卡片
├── index_store/              # embeddings + feedback log
└── raw/                      # 原始文档
```

## 7. 故障排查

```bash
# 缺少依赖
pip install numpy requests --break-system-packages

# 向量检索失败（首次使用先跑）
python3 scripts/build_embeddings.py

# 查询为空（检查索引）
ls index_store/embeddings/card_embeddings.npy
ls db/excel_store.db
```

---

完整文档: `README.md` | `API.md` | `ARCHITECTURE.md` | `AGENTS.md`
