# 知识库操作日志

> 格式: `## [YYYY-MM-DD HH:MM] action | subject`
> 操作类型: import, annotate, embed, query, lint, optimize

---

## [2026-05-04 17:44] import | WebDAV 全量导入

- 文档数: 31 个 Markdown
- Excel 数: 4 个
- PPT 数: 1 个
- 卡片数: 1885 张
- 导入耗时: ~60s

变更:
- 新增 SCHEMA.md — 标签分类定义
- 新增 cards/INDEX.md — 人工目录
- 修复 import_webdav_raw.py — 添加 Markdown sha256 漂移检测

---

## [2026-05-04 17:46] annotate | 卡片语义标注

- 模型: Qwen/Qwen2.5-7B-Instruct
- API: SiliconFlow
- 待标注: 1885 张
- 状态: 进行中...

---

## 待办

- [ ] 完成全量卡片标注
- [ ] 构建向量索引 (build_embeddings.py)
- [ ] 运行测试验证 (run_fast_tests.py)
- [ ] 实现卡片矛盾检测
