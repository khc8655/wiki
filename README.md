# wiki_test 知识库系统

> 面向 Agent 的专业知识库框架：可配置、可扩展、零门槛上手。

[![Setup](https://img.shields.io/badge/setup-python3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

---

## 快速开始（5分钟）

```bash
# 1. 检查环境
python3 setup.py --check

# 2. 初始化目录
python3 setup.py --init

# 3. 配置 WebDAV（如需同步）
export WEBDAV_USER="jjb"
export WEBDAV_PASS="jjb@115799"

# 4. 运行测试
python3 scripts/run_fast_tests.py
```

**查看详细指南**：[QUICKSTART.md](QUICKSTART.md)

---

## 核心特性

### 🔍 智能查询路由
- 自动识别查询意图（价格、对比、参数、行业应用等）
- 双路召回：结构化数据（Excel）+ 非结构化文档（Cards）
- 深度融合语义标签，提升召回精准度

### ⚙️ 全配置化设计
- 单文件配置：`config.yaml`
- 环境变量支持：`WEBDAV_USER`, `WIKI_ROOT`, etc.
- 路径自动解析：支持绝对/相对路径

### 📦 模块化架构
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Config    │  │   Query     │  │   Data      │
│   Layer     │  │   Router    │  │   Store     │
└─────────────┘  └─────────────┘  └─────────────┘
       │                 │                │
       └─────────────────┴────────────────┘
                         │
              ┌──────────┴──────────┐
              │   Dual-Path         │
              │   Retrieval         │
              └─────────────────────┘
```

### 🧪 完整测试覆盖
- 9个核心测试用例
- 性能基准测试（~0.05s）
- 环境自动验证

---

## 架构概览

```
wiki_test/
├── config.yaml              # 主配置文件
├── setup.py                 # 环境检查/初始化
├── QUICKSTART.md            # 快速上手指南
├── ARCHITECTURE.md          # 架构设计文档
├── API.md                   # API 文档
│
├── lib/                     # 核心库
│   ├── __init__.py
│   └── config.py           # 配置管理
│
├── scripts/                 # 查询/处理脚本
│   ├── query_fast.py       # 主查询入口
│   ├── run_fast_tests.py   # 测试套件
│   └── ...
│
├── excel_store/            # Excel 数据源
│   ├── pricing/            # 价格表
│   ├── comparison/         # 产品对比
│   └── proposal/           # 招标参数
│
├── cards/                  # 文档切片
│   └── sections/           # 结构化卡片
│
├── raw/                    # 原始文档
├── index_store/            # 索引文件
└── logs/                   # 日志
```

**详细架构**：[ARCHITECTURE.md](ARCHITECTURE.md)

---

## 查询示例

```python
# Python API
from lib.config import config
import subprocess

# 运行查询
result = subprocess.run(
    ['python3', config.root / 'scripts' / 'query_fast.py', 
     'AE800多少钱', '--json'],
    capture_output=True, text=True
)
data = json.loads(result.stdout)

# 使用配置
raw_path = config.path('sources', 'raw', 'path')
username, password = config.get_webdav_credentials()
```

```bash
# CLI
python scripts/query_fast.py "AE800多少钱" --json
python scripts/run_fast_tests.py
python scripts/benchmark_fast_queries.py
```

**完整 API 文档**：[API.md](API.md)

---

## 数据源

| 类型 | 位置 | 典型查询 |
|------|------|----------|
| **Excel Store** | `excel_store/` | 价格、对比、参数 |
| **Cards** | `cards/sections/` | 行业应用、场景说明 |
| **Raw** | `raw/` | 原始文档 |

### 深度融合的语义标签

每张卡片包含自动化生成的语义标签：

```json
{
  "id": "24-24-行业应用口袋书-公安20220520-sec-005",
  "title": "公安部监管局（十三局）原有系统改造升级",
  "semantic": {
    "intent_tags": ["operation_maintenance", "integration"],
    "feature_tags": ["兼容现有视频会议系统", "视频会议"],
    "concept_tags": ["视频会议系统", "云视频平台"],
    "scenario_tags": ["police", "指挥调度"],
    "doc_types": ["solution"]
  }
}
```

---

## 配置管理

### 配置文件

`config.yaml`：
```yaml
workspace:
  root: "${WIKI_ROOT:-auto}"
  
webdav:
  base_url: "${WEBDAV_URL:-https://dav.jjb115799.fnos.net}"
  username: "${WEBDAV_USER:-}"
  password: "${WEBDAV_PASS:-}"

query:
  default_limit: 20
  price_keywords: ["价格", "报价", "多少钱"]
```

### 环境变量

```bash
# WebDAV 配置
export WEBDAV_USER="jjb"
export WEBDAV_PASS="jjb@115799"

# 工作目录
export WIKI_ROOT="/path/to/wiki"

# 调试
export LOG_LEVEL="DEBUG"
```

---

## 开发与扩展

### 添加新查询意图

```python
# 1. 在 query_fast.py:route_query() 添加识别规则
def route_query(query: str):
    if '新关键词' in query.lower():
        return 'new_intent', info
    
# 2. 实现查询函数
def new_intent_lookup(query: str) -> List[Dict]:
    # 实现查询逻辑
    pass

# 3. 在 main() 中添加路由
elif intent == 'new_intent':
    result['results'] = new_intent_lookup(query)
```

### 添加新数据源

```yaml
# config.yaml
sources:
  excel:
    new_source: "./excel_store/new_source"
```

```bash
# 生成索引
python scripts/build_excel_knowledge.py
```

---

## 测试与验证

```bash
# 运行全部测试
python scripts/run_fast_tests.py

# 性能基准
python scripts/benchmark_fast_queries.py

# 环境检查
python setup.py --check
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 5分钟快速上手 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 系统架构设计 |
| [API.md](API.md) | 脚本/API 参考 |
| [AGENTS.md](AGENTS.md) | Agent 工作流规范 |
| [CHANGELOG.md](CHANGELOG.md) | 版本更新日志 |

---

## 版本历史

### v1.2（深度融合）
- ✅ GLM-4-9B 标注层深度融合
- ✅ 双路召回（原文 + 语义标签）
- ✅ 配置化架构
- ✅ 完整测试覆盖

### v1.1（语义路由）
- ✅ 意图识别路由
- ✅ Excel 数据源支持
- ✅ 三类数据查询

### v1.0（基础检索）
- ✅ 文档切片（Cards）
- ✅ FTS5 全文检索
- ✅ 基础查询链路

---

## 贡献指南

1. 代码风格：PEP 8
2. 测试：添加新功能需配套测试用例
3. 文档：更新 API.md 和 ARCHITECTURE.md
4. 配置：新路径需加入 config.yaml

---

## License

MIT License

---

> 任何问题？运行 `python setup.py --quickstart` 查看帮助。
