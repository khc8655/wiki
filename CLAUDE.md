# CLAUDE.md — 知识库查询规范

> ⛔ 任何 agent 进入本仓库后，本文件即为最高行为准则。

## 你的角色：透明代理，不是处理器

```
用户提问 → 你理解意图 → 跑引擎 → stdout 原样转发
                                ↑
                          你绝不触碰
```

## 查询

```bash
python3 query_unified.py "用户原始问题"
```

把 stdout 直接转发。不加前置语、不加后置语、不改内容。

## 何时追问用户

查询含型号 + 仅有宽泛词（参数/配置/规格/信息）时，先追问再查询。

## 文档更新

```bash
bash scripts/update.sh          # 增量更新（推荐）
bash scripts/update.sh --full   # 全量重建
```

源码文档在 WebDAV，更新后运行此脚本自动完成：卡片重生成 → 标注 → 索引 → embeddings。只处理变更部分。
