# Changelog

## V2.1 - 2026-04-14

### 新增功能

#### 1. 层级路径索引（Path Siblings Index）
- **文件**: `index_store/path_siblings_index.v2.json`
- **脚本**: `scripts/build_path_index.js`
- **作用**: O(1) 查找同一父路径下的所有兄弟卡片
- **示例**: "硬件平台 > 硬件终端" → 148张卡片

#### 2. 硬件型号反向索引（Model Path Index）
- **文件**: `index_store/model_path_index.v2.json`
- **脚本**: `scripts/build_model_index.js`
- **作用**: 硬件型号 → 父路径映射，实现反向召回
- **支持型号**: XE800, AE700, AE800, GE300, GE600, NP30V2, TP860-S, TP650-S 等

#### 3. 查询增强
- 新增 `hardware-model` 意图路由
- 查询硬件型号时自动走反向索引召回
- 章节关联增强：命中卡片后自动召回同父目录兄弟卡片

### 优化效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 查询速度 | ~2分钟（全量遍历） | <1秒（O(1)索引） |
| XE800召回 | 需关键词匹配 | 型号→路径→章节精确召回 |
| 章节完整性 | 碎片化单张卡片 | 完整章节合并输出 |
| 准确率 | 依赖关键词密度 | 层级关联提升 |

### 使用示例

```bash
# 查询 XE800（走型号反向索引）
node scripts/query_default.js --brief 'XE800'

# 查询 XE800 BYOM（型号+功能联合召回）
node scripts/query_default.js --brief 'XE800 BYOM'

# 重建索引（新文档入库后执行）
node scripts/build_path_index.js
node scripts/build_model_index.js
```

### 文档更新

- `docs/retrieval-v2-design.md`: 新增第6节"层级索引与反向召回"

## V2.0 - 2026-04-12

### 初始版本
- 四层架构：Raw → Cards → Topics → Wiki
- 意图路由：跨云互通、安全、稳定性、双引擎等
- 匹配度输出：强命中/弱相关/排除项 + match_percent
