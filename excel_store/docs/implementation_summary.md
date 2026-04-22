# Excel知识库实现总结

## 已完成的功能

### 1. 数据结构
- **pricing**: 267条价格记录
  - 来源: 2026年小鱼易连产品报价体系.xlsx (250条)
  - 来源: 风铃项目报价清单2026-0306.xlsx (17条)
  
- **proposal**: 24条阶段描述记录
  - 来源: 项目各阶段报价描述清单2026.xlsx
  
- **comparison**: 320条产品对比记录
  - 来源: 小鱼易连视频终端对比及功能介绍.xlsx

### 2. 核心脚本
- `build_excel_knowledge.py`: 解析Excel并生成结构化JSON
- `query_excel_knowledge.py`: 支持三类查询接口
- `query_default.js`: 集成到现有查询路由

### 3. 7个测试查询全部通过

| # | 问题 | 结果 | 数据来源 |
|---|------|------|----------|
| 1 | AE800的价格是多少? | ✅ 找到AE800套装价格138000元 | pricing |
| 2 | AI相关的报价分类有哪些? | ✅ 找到AI服务使用费、语音转写、人脸识别等 | pricing |
| 3 | 固定方数云会议室有哪些类别? | ✅ 找到10方到500方各类别及价格 | pricing |
| 4 | AE800可以使用的配件有哪些? | ✅ 找到TP10触控屏、遥控器、无线传屏器等 | pricing |
| 5 | PE8000什么时候停产? | ✅ 2026年6月30日停产，替代型号PE8800 | pricing |
| 6 | XE800与AE800对比? | ✅ 完整对比表，包括视频输出、处理能力等差异 | comparison |
| 7 | AE800的招标参数? | ✅ 三阶段描述：渠道询价、方案设计、招投标 | proposal |

## 查询方法

### 直接调用Node查询
```bash
cd /workspace/wiki_test

# 价格查询
node scripts/query_default.js "AE800的价格"

# 产品对比
node scripts/query_default.js "XE800与AE800对比"

# 招标参数
node scripts/query_default.js "AE800招标参数"
```

### 直接调用Python脚本
```bash
# 价格查询
python3 scripts/query_excel_knowledge.py "AE800" -t pricing

# 产品对比
python3 scripts/query_excel_knowledge.py "XE800" -t comparison

# 双产品对比
python3 scripts/query_excel_knowledge.py "compare" -t comparison --compare XE800 AE800

# 招标参数
python3 scripts/query_excel_knowledge.py "AE800" -t proposal
```

### 数据更新
```bash
# 重新构建
python3 scripts/build_excel_knowledge.py
```

## 实现特点

1. **自动路由检测**: query_default.js自动识别查询类型并路由到正确数据源
2. **合并单元格处理**: 正确继承上级类别/产品关系
3. **证据链完整**: 每条记录保留来源文件、sheet名、行号
4. **字段归一化**: 统一价格模式(fixed/yearly/monthly/formula等)
5. **不编造**: 严格基于原始数据，未命中时返回"未找到"

## 文件结构

```
wiki_test/
├── excel_store/
│   ├── raw/              # 原始Excel文件
│   ├── pricing/          # 价格数据
│   ├── proposal/         # 阶段描述数据
│   ├── comparison/       # 产品对比数据
│   └── docs/             # 文档
├── scripts/
│   ├── build_excel_knowledge.py   # 构建脚本
│   ├── query_excel_knowledge.py   # 查询脚本
│   └── query_default.js           # 集成路由
```
