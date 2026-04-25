# wiki_test 快速上手指南

> **目标**：让任何 agent 在 5 分钟内跑通知识库查询。

---

## 1. 环境检查（30秒）

```bash
# 进入项目目录（根据实际情况调整路径）
cd <project_root>
python3 setup.py --check
```

预期输出：
```
============================================================
  Directory Structure Check
============================================================
  [✓] Raw source                             ./raw
  [✓] Cards                                  ./cards/sections
  [✓] Excel pricing                          ./excel_store/pricing
  ...

============================================================
  Summary
============================================================
  [✓] Directory Structure                    OK
  [✓] Excel Data                             OK
  ...
```

如果有 ❌，运行修复：
```bash
python3 setup.py --init        # 创建缺失的目录
```

---

## 2. 配置 WebDAV（如果需要同步数据）

```bash
export WEBDAV_USER="jjb"
export WEBDAV_PASS="jjb@115799"
```

验证连接：
```bash
python3 setup.py --check
# 应该显示:
#   [✓] Username                               jjb
#   [✓] Password                               ***
```

---

## 3. 快速测试查询（1分钟）

### 3.1 运行全部测试用例
```bash
python3 scripts/run_fast_tests.py
```

### 3.2 单个查询测试
```bash
# 价格查询
python3 scripts/query_fast.py "AE800多少钱"

# JSON 格式输出
python3 scripts/query_fast.py "AE800多少钱" --json

# 对比查询
python3 scripts/query_fast.py "XE800与AE800对比" --json

# 行业应用
python3 scripts/query_fast.py "公安行业应用" --json
```

---

## 4. 数据源说明

### Excel 数据（本地）
位置：`excel_store/`

| 目录 | 用途 | 典型查询 |
|------|------|----------|
| `pricing/` | 价格表 | "AE800多少钱" |
| `comparison/` | 产品对比 | "XE800 vs AE800" |
| `proposal/` | 招标参数 | "AE800招标参数" |

### 卡片数据（原始文档切片）
位置：`cards/sections/*.json`

每张卡片包含：
- `title`: 标题
- `body`: 正文内容
- `semantic`: 语义标签（标注层深度融合）

### 原始文档
位置：`raw/`

从 WebDAV 同步的原始 Markdown 文件。

---

## 5. 常见任务

### 从 WebDAV 拉取最新文档
```bash
./scripts/refresh_from_webdav.sh
```

### 重建 Excel 索引
```bash
python3 scripts/build_excel_knowledge.py
```

### 融合标注数据
```bash
python3 scripts/merge_annotations_to_cards.py
```

### 性能测试
```bash
python3 scripts/benchmark_fast_queries.py
```

---

## 6. 查询类型与路由

系统会自动识别查询意图：

| 查询词 | 意图 | 数据源 |
|--------|------|--------|
| "价格" "多少钱" | price | excel_store/pricing |
| "对比" "vs" | compare | excel_store/comparison |
| "招标" "参数" | proposal | excel_store/proposal |
| "公安" | police_scene | cards/sections |
| "软件端" "硬件端" | software_hardware | cards/sections |

---

## 7. 输出格式

### 标准输出
```json
{
  "query": "AE800多少钱",
  "intent": "price",
  "models": ["AE800"],
  "results": [
    {
      "product_name": "小鱼易连AE800套装",
      "price_raw": "¥38,000",
      "source": "产品价格表2026.xlsx | 硬件终端 | row 15",
      "hit_rate": 1.0
    }
  ]
}
```

### 关键字段
- `source`: 文档出处（文件名 | 工作表 | 行号）
- `hit_rate`: 匹配度（0.0-1.0）
- `intent`: 识别到的查询意图

---

## 8. 故障排查

### 问题：查询返回空结果
```bash
# 检查 Excel 索引是否存在
ls excel_store/pricing/records.json

# 检查卡片是否存在
ls cards/sections/*.json | wc -l
```

### 问题：WebDAV 同步失败
```bash
# 检查凭据
export WEBDAV_USER="jjb"
export WEBDAV_PASS="jjb@115799"

# 重新运行
python3 setup.py --check
```

### 问题：查询速度慢
```bash
# 运行性能测试
python3 scripts/benchmark_fast_queries.py
```

---

## 9. 项目结构速览

```
wiki_test/
├── config.yaml              # 配置文件
├── setup.py                 # 环境检查/初始化
├── QUICKSTART.md            # 本文档
│
├── scripts/                 # 查询脚本
│   ├── query_fast.py        # 主查询入口
│   ├── run_fast_tests.py    # 测试用例
│   └── ...
│
├── excel_store/             # Excel 数据
│   ├── pricing/
│   ├── comparison/
│   └── proposal/
│
├── cards/                   # 文档卡片
│   └── sections/
│
├── raw/                     # 原始文档
├── index_store/             # 索引文件
└── lib/                     # 配置模块
    └── config.py
```

---

## 10. 下一步

- 查看完整文档：`README.md`
- 了解查询策略：`docs/`
- 查看 agent 工作流：`AGENTS.md`

---

**需要帮助？** 运行 `python3 setup.py --quickstart` 查看完整指南。
