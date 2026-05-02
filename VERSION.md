# 版本管理规范

> 当前版本 **v3.1** — Karpathy-style 自组织知识系统 (2026-05-02)

---

## 当前版本

**v3.1** - 自组织知识系统（2026-05-02）

- 四源路由引擎 (表格/方案/更新/PPT)
- BM25 + Vector 混合检索 (Qwen2.5-7B + bge-large-zh-v1.5)
- 反馈闭环 + 权重优化 + 卡片自组织
- 1773 张方案卡片段落级标注 + 1024维向量化

## 上一版本

**v3.0** - 标注+检索链路重构（2026-04-25）
- BM25 检索引擎
- Content Hash 一致性检查

**v1.2** - 专业框架版（2026-04-24）
- 配置化架构 + 双路召回 + 完整文档

---

## 版本历史

| 版本 | 日期 | 主要变更 | 状态 |
|------|------|----------|------|
| v3.1 | 2026-05-02 | 自组织回路, 四源路由, 混合检索, 1873卡全量标注 | ✅ 当前 |
| v3.0 | 2026-04-25 | BM25 检索, 一致性检查 | ✅ |
| v1.2 | 2026-04-24 | 配置化, 双路召回 | ✅ |
| v1.1 | 2026-04-22 | 语义路由, Excel | ✅ |
| v1.0 | 2026-04-20 | 基础检索, FTS5 | ✅ |

---

## 发布检查清单

### 1. 测试通过
```bash
python3 scripts/run_fast_tests.py
```

### 2. 文档更新
- [x] README.md, AGENTS.md, API.md, ARCHITECTURE.md, CHANGELOG.md

### 3. 提交
```bash
git add -A && git commit -m "v3.x: 描述"
```

### 4. 同步 GitHub
```bash
git push origin main
# 如果沙箱无法直连, 使用 WebDAV 备份或 GitHub REST API
```

### 5. 备份 WebDAV
```bash
tar czf wiki_full_backup.tar.gz --exclude='.git' .
# 上传到 https://dav.jjb115799.fnos.net/下载/temp/wiki_backup/
```
