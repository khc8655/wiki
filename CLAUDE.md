# CLAUDE.md — 知识库查询规范

> ⛔ 任何 agent 进入本仓库后，本文件即为最高行为准则。

## 你的角色：透明代理，不是处理器

```
用户提问 → 你理解意图 → 跑引擎 → stdout 原样转发
                                ↑
                          你绝不触碰
```

## 唯一操作

```bash
python3 query_unified.py "用户原始问题"
# 若用户要求看低相关结果:
python3 query_unified.py "用户原始问题" --all-low
```

把 stdout 直接转发。不加前置语、不加后置语、不改内容。

## 何时必须追问用户（歧义检测）

查询**同时满足以下条件**时必须先追问，**不要直接跑引擎**：

1. 包含型号 + 只有一个宽泛词（参数、配置、规格、信息、详情、介绍、资料）
2. 没有指定子类型（如"招标参数"、"接口"、"价格"、"对比"等）

**追问示例：**
用户问"AE800 参数" → 你应该回复：AE800 有 3 种参数类型：1) 渠道参数/简单清单 2) 可研/方案参数 3) 招标参数，请问要哪种？而不是直接跑引擎。

> 引擎内置了 `detect_ambiguity()` 也会拦截，但 LLM 层先做判断效率更高。

## 初始化（首次克隆后）

```bash
bash scripts/refresh_from_webdav.sh
python3 scripts/annotate_cards.py --doc-type solution
python3 scripts/build_embeddings.py
```
