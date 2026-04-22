# Excel知识库查询指南

## 支持的数据类型

### 1. pricing (价格查询)
- **数据来源**: 2026年小鱼易连产品报价体系.xlsx, 风铃项目报价清单2026-0306.xlsx
- **查询方式**: 产品型号、产品名称、类别关键词
- **返回字段**: 产品名称、类别、编码、价格、单位、备注、来源位置
- **使用场景**: 查询产品价格、停产信息、替代型号

### 2. proposal (阶段描述查询)
- **数据来源**: 项目各阶段报价描述清单2026.xlsx
- **查询方式**: 产品型号
- **返回字段**: 产品名称、型号、渠道询价阶段描述、方案设计阶段描述、招投标阶段描述
- **使用场景**: 获取招标参数、各阶段话术

### 3. comparison (产品对比查询)
- **数据来源**: 小鱼易连视频终端对比及功能介绍.xlsx
- **查询方式**: 单个产品查询 或 两个产品对比
- **返回字段**: 功能项、各产品参数值
- **使用场景**: 产品能力对比、选型参考

## 查询示例

### 价格查询
```bash
# 查询AE800价格
node scripts/query_default.js "AE800的价格"

# 查询AI相关报价
node scripts/query_default.js "AI报价"

# 查询会议室类别
node scripts/query_default.js "会议室"

# 查询PE8000停产信息
node scripts/query_default.js "PE8000停产"
```

### 对比查询
```bash
# XE800与AE800对比
node scripts/query_default.js "XE800与AE800对比"
```

### 招标参数查询
```bash
# 获取AE800招标参数
node scripts/query_default.js "AE800招标参数"
```

## 直接调用Python脚本

```bash
# 价格查询
python3 scripts/query_excel_knowledge.py "AE800" -t pricing -k 5

# 对比查询
python3 scripts/query_excel_knowledge.py "XE800" -t comparison -k 10

# 两个产品对比
python3 scripts/query_excel_knowledge.py "compare" -t comparison --compare XE800 AE800

# 阶段描述查询
python3 scripts/query_excel_knowledge.py "AE800" -t proposal --phase tender
```

## 数据更新

```bash
# 重新构建Excel知识库
python3 scripts/build_excel_knowledge.py
```

## 数据结构

### pricing记录
```json
{
  "id": "pricing_000001",
  "source_file": "2026年小鱼易连产品报价体系.xlsx",
  "source_sheet": "项目型终端",
  "source_row": 5,
  "product_name": "小鱼易连AE800套装",
  "category": "AE800",
  "product_code": "70800-00001-001",
  "price_raw": "138000",
  "price_value": 138000,
  "price_mode": "fixed",
  "unit": "元/套",
  "note": "",
  "description": ""
}
```

### proposal记录
```json
{
  "id": "proposal_000001",
  "source_file": "项目各阶段报价描述清单2026.xlsx",
  "source_sheet": "硬件终端",
  "source_row": 10,
  "product_name": "大型会议室终端",
  "product_model": "AE800",
  "phase_channel": "渠道询价阶段描述...",
  "phase_proposal": "方案设计阶段描述...",
  "phase_tender": "招投标阶段描述..."
}
```

### comparison记录
```json
{
  "feature": "场景定位",
  "model": "AE800",
  "value": "大型会议室终端",
  "source_sheet": "终端功能参数对比",
  "source_row": 5
}
```
