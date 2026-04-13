# Wiki 知识库

云视频平台分层知识库 - 采用四层架构设计

---

## 版本信息

**当前版本**: v1.4

---

## 架构概览

本知识库采用**四层分层架构**，详细说明见 [docs/architecture.md](docs/architecture.md)：

```
Layer 4: Wiki 合成层 (Synthesized Knowledge)
├── wiki/index.md        # 导航首页
├── wiki/log.md          # 演进记录
└── wiki/sources/        # 源文档总结页

Layer 3: Topics 主题聚合层 (Synthesized Pages)
├── topics/architecture.md
├── topics/security.md
├── topics/meeting-control.md
└── ...

Layer 2: Cards 结构化卡片层 (Knowledge Middle Layer)
├── cards/sections/*.json    # 段落级卡片
├── cards/manifest.json      # 全量索引
└── cards/card_metadata.v1.json

Layer 1: Raw 原始资料层 (Source of Truth)
└── raw/                    # 原始文档（不可变）
```

---

## 文档清单

| 文档编号 | 文档名称 | 卡片数 |
|---------|---------|--------|
| 01 | 云视频技术架构优势V1.0-20211120 | 6 |
| 02 | 小鱼易连安全稳定白皮书V1-20240829 | 6 |
| 03 | 小鱼易连融合云视频会控技术白皮书V1.6 | 300 |
| 04 | 小鱼易连融合云视频平台技术白皮书V1.1 | 412 |
| 06 | 新一代视频会议系统建设方案模板 | 262 |

**总计**: ~991 张知识卡片

---

## 主题覆盖

- **architecture** - 系统总体架构
- **security** - 安全稳定
- **stability** - 稳定性保障
- **meeting-control** - 会控能力
- **live-streaming** - 直播能力
- **recording** - 录制回放
- **signaling** - 信令控制
- **media-exchange** - 媒体交换
- **multi-active** - 多活容灾
- **monitoring** - 监控运维
- **ai** - AI 智能

---

## 更新日志

### v1.5 (2026-04-13)

**V2 检索设计与脚手架**

- 新增: `docs/retrieval-v2-design.md`，明确“重入库、轻查询、持续自优化”的 V2 方案
- 新增: `scripts/build_v2_semantic_metadata.py`，生成 V2 语义元数据与 intent/concept/negative 索引
- 新增: `scripts/query_v2.js`，提供 V2 查询原型，支持轻量 query 理解 + 快速精排
- 补充: V2 card schema、自动优化与 lint 思路

### v1.4 (2026-04-12)

**初始版本发布**

- 导入 6 份原始白皮书/方案文档
- 生成约 991 张结构化知识卡片
- 建立完整的四层架构体系
- 创建主题聚合页和 Wiki 合成页
- 配置 GitHub 自动推送脚本

---

## 后续更新规范

### 更新流程

1. **准备更新内容**
   - 新增/修改原始文档 → 放入 `raw/` 目录
   - 生成新的 section cards → 放入 `cards/sections/`
   - 更新 `cards/manifest.json` 和 `cards/card_metadata.v1.json`

2. **更新主题页**
   - 修改相关的 `topics/*.md` 文件
   - 更新 `wiki/sources/*.md` 源文档总结页

3. **记录变更**
   - 在本文档「更新日志」部分添加新版本说明
   - 更新 `wiki/log.md` 文件

4. **提交推送**
   ```bash
   ./push_to_github.sh "v1.x: 更新说明"
   ```

### 版本号规则

- **v1.x** - 小版本更新（新增卡片、补充内容）
- **v2.0** - 大版本更新（架构调整、重大变更）

### 更新日志模板

```markdown
### v1.x (YYYY-MM-DD)

**更新内容**

- 新增: xxx
- 更新: xxx
- 修复: xxx

**统计**

- 新增卡片: xx 张
- 更新主题: xx 个
- 涉及文档: xxx
```

---

## 使用指南

### 查询知识

1. **按主题浏览**: 查看 `topics/` 目录下的主题页
2. **精确检索**: 通过 `cards/manifest.json` 查找卡片
3. **阅读原文**: 查看 `raw/` 目录下的原始文档

### 本地启动

本知识库为纯 Markdown + JSON 结构，无需服务器即可浏览。

---

## 仓库地址

https://github.com/khc8655/wiki

---

## 维护者

- 创建: khc8655
- 架构设计: 四层分层知识库架构

