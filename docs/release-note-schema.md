# Release Note 字段规范

本文定义 `release_note` 类型文档的推荐字段，用于后续把“版本 / 型号 / 功能块”查得更稳。

## 目标

`release_note` 文档不追求像方案文档那样细粒度切分。

它更关注：
- 这一版改了什么
- 哪些型号受影响
- 是新增、优化还是修复
- 适用环境、前置条件、兼容性、是否支持回退

所以推荐以**整节 / 整功能块**作为主召回单元，再在块上补结构化字段。

## 推荐字段

### 1. 基础字段

```json
{
  "doc_type": "release_note",
  "title": "【AE700系列】支持串口绑定",
  "source": "raw/10-2026年私有云3月迭代版本新功能培训文档-终端.md",
  "version": "2603",
  "product_line": "硬件终端",
  "module": "终端配置",
  "chunk_type": "feature_block"
}
```

字段说明：
- `doc_type`：固定为 `release_note`
- `title`：功能块标题
- `source`：来源文档
- `version`：版本号或迭代标识
- `product_line`：产品线，如云平台、终端、风铃
- `module`：所属模块
- `chunk_type`：推荐值 `feature_block` / `chapter_block`

### 2. 检索增强字段

```json
{
  "feature_name": "支持串口绑定",
  "change_type": "new_feature",
  "keywords": ["AE700", "串口", "RS232", "HDMI绑定"],
  "models": ["AE700"],
  "scenarios": ["终端侧配置", "串口控制"],
  "summary": "AE700 终端支持启用 RS232 串口并与 HDMI 输入接口建立绑定关系。"
}
```

字段说明：
- `feature_name`：功能名
- `change_type`：推荐枚举
  - `new_feature`
  - `optimization`
  - `bugfix`
  - `compatibility`
  - `rollback_support`
- `keywords`：检索关键词
- `models`：涉及型号
- `scenarios`：适用场景
- `summary`：块级摘要

### 3. 交付与适配字段

```json
{
  "applicable_env": ["私有云5.2通用", "私有云5.2信创"],
  "preconditions": ["终端侧配置开启串口功能"],
  "compatibility": "需要配套终端版本支持",
  "upgrade_required": true,
  "rollback": "未说明"
}
```

字段说明：
- `applicable_env`：适用环境
- `preconditions`：前置条件
- `compatibility`：兼容性说明
- `upgrade_required`：是否依赖升级
- `rollback`：是否支持回退或文档是否明确说明

## 最小可用字段集

如果先做一版轻量实现，建议至少保证下面这些字段：

```json
{
  "doc_type": "release_note",
  "version": "2603",
  "feature_name": "支持串口绑定",
  "change_type": "new_feature",
  "models": ["AE700"],
  "keywords": ["AE700", "串口绑定"],
  "summary": "AE700 系列支持串口绑定。"
}
```

## 当前建议接入方式

1. `raw/*.md` 继续按粗粒度切分为功能块
2. 每个功能块补上述字段
3. 默认查询入口继续先判断是否属于 `release_note`
4. 命中后优先返回整块原文，再基于字段做聚合展示

## 推荐后续能力

1. 按 `version + models + change_type` 建立索引
2. 对 `AE700 新功能` 这类查询先聚合到型号，再展开功能块
3. 对 `2603 终端新增功能` 这类查询先聚合到版本，再展开模块
