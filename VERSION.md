# 版本管理规范

> 确保本地、GitHub、文档三者同步，版本清晰可追溯。

---

## 当前版本

**v3.0** - 检索引擎升级版（2026-04-25）
- BM25 检索引擎（TF-IDF + 长度归一化）
- Content Hash 一致性检查
- 空结果智能提示
- 可移植路径（任意环境可用）

---

## 上一版本

**v1.2** - 专业框架版（2026-04-24）
- 配置化架构
- 双路召回（深度融合）
- 完整文档体系

---

## 版本号规则

格式：`v{主版本}.{次版本}.{修订}`

| 版本类型 | 示例 | 说明 |
|----------|------|------|
| 主版本 | v2.0 | 架构重构，不兼容变更 |
| 次版本 | v1.2 | 新功能，向后兼容 |
| 修订 | v1.2.1 | Bug 修复，文档更新 |

---

## 发布检查清单

每次发布前必须完成：

### 1. 代码检查 ✅

```bash
# 本地测试全部通过
python3 scripts/run_fast_tests.py

# 性能基准正常
python3 scripts/benchmark_fast_queries.py

# 无未提交变更
git status  # 应该是干净的
```

### 2. 文档更新 ✅

- [ ] README.md - 更新版本号、功能列表
- [ ] CHANGELOG.md - 添加变更条目
- [ ] API.md - 如有新接口
- [ ] ARCHITECTURE.md - 如有架构变更

### 3. 配置同步 ✅

- [ ] config.yaml - 新配置项已添加
- [ ] lib/config.py - 默认值已同步
- [ ] setup.py - 新检查项已添加

### 4. 提交规范 ✅

```bash
# 提交信息格式
git commit -m "v1.x: 简短描述

- 详细变更点 1
- 详细变更点 2
- 详细变更点 3"
```

### 5. 同步到 GitHub ✅

```bash
# 必须先拉取最新
git pull origin main

# 解决冲突后再推送
git push origin main

# 确认同步
git log --oneline -3
# 应该显示: 604f85f (HEAD -> main, origin/main) ...
```

### 6. 备份到 WebDAV ✅

```bash
# 打包（排除 .git）
tar czf /tmp/wiki_test_v{x}_{date}.tar.gz --exclude='.git' .

# 上传到 WebDAV
curl -T /tmp/wiki_test_v{x}_{date}.tar.gz \
  -u "jjb:jjb@115799" \
  "https://dav.jjb115799.fnos.net/下载/temp/"
```

---

## 文档更新规范

### README.md

必须包含：
- 当前版本号
- 主要功能列表
- 快速开始链接

### CHANGELOG.md

每条变更必须包含：
- 版本号
- 日期
- 变更类型（新增/修复/优化）
- 详细说明

示例：
```markdown
### v1.2 (2026-04-24)

**新增：**
- 配置化架构（config.yaml）
- 双路召回（原文 + 语义标签）

**修复：**
- 对比查询 source 格式问题

**优化：**
- 查询性能提升 20%
```

### API.md

新增接口必须包含：
- 用法示例
- 参数说明
- 返回格式
- 错误处理

### QUICKSTART.md

面向新用户，必须：
- 步骤清晰（1、2、3）
- 可复制粘贴
- 常见问题解答

---

## 新增功能流程

### 步骤 1：开发

```bash
# 基于最新 main 分支
git checkout main
git pull origin main

# 开发新功能
# ... coding ...
```

### 步骤 2：测试

```bash
# 运行全部测试
python3 scripts/run_fast_tests.py

# 新增测试用例（如需要）
# 编辑 scripts/run_fast_tests.py
```

### 步骤 3：更新配置

```yaml
# config.yaml 添加新配置
new_feature:
  enabled: true
  path: "./new_path"
```

```python
# lib/config.py 添加默认值
DEFAULT_CONFIG = {
    'new_feature': {
        'enabled': True,
        'path': './new_path'
    }
}
```

### 步骤 4：更新文档

```markdown
# README.md - 功能列表
- ✅ 新功能 X

# API.md - 接口文档
### new_feature.py
用法：...

# ARCHITECTURE.md - 架构图
# 更新架构图
```

### 步骤 5：提交

```bash
# 检查变更
git status

# 添加所有相关文件
git add config.yaml lib/config.py scripts/new_feature.py README.md API.md ARCHITECTURE.md

# 提交（详细说明）
git commit -m "v1.3: Add new feature X

- Add new_feature.py for xxx functionality
- Update config.yaml with new_feature settings
- Update API.md with usage documentation
- Add test case in run_fast_tests.py
- Performance: xxx"

# 推送
git push origin main
```

### 步骤 6：备份

```bash
# 打包并上传 WebDAV
tar czf /tmp/wiki_test_v1.3_$(date +%Y%m%d).tar.gz --exclude='.git' .
curl -T /tmp/wiki_test_v1.3_*.tar.gz -u "jjb:jjb@115799" \
  "https://dav.jjb115799.fnos.net/下载/temp/"
```

---

## 版本历史

| 版本 | 日期 | 主要变更 | 状态 |
|------|------|----------|------|
| v3.0 | 2026-04-25 | BM25 检索、一致性检查、智能提示 | ✅ 当前 |
| v1.2 | 2026-04-24 | 配置化架构、双路召回、完整文档 | ✅ |
| v1.1 | 2026-04-22 | 语义路由、Excel 数据源 | ✅ |
| v1.0 | 2026-04-20 | 基础检索、文档切片 | ✅ |

---

## 故障排查

### GitHub 不同步

```bash
# 检查远程状态
git fetch origin
git log --oneline HEAD..origin/main  # 看远程领先多少

# 如果本地落后
git pull origin main

# 如果远程落后（本地有未推送提交）
git push origin main

# 如果有冲突
git pull origin main
# 解决冲突后
git add .
git commit -m "Merge conflict resolution"
git push origin main
```

### 文档遗漏

发布前必须运行：
```bash
# 检查清单脚本（可添加到 setup.py）
python3 -c "
import yaml
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)
print('Config version:', cfg.get('version', 'N/A'))
"
```

---

## 责任人

- 版本发布：维护者
- 文档更新：功能开发者
- 备份管理：维护者

---

**记住：版本混乱的根源是"先改代码、后补文档"。正确顺序是：改代码 → 更新配置 → 更新文档 → 测试 → 提交 → 同步 → 备份。**
