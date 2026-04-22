#!/usr/bin/env node
/**
 * Query Router v3 - 语义意图+智能多源
 * 
 * 核心原则：宁多勿少，模糊查询自动多源，明确查询精准单源
 */

const { execFileSync } = require('child_process');
const path = require('path');
const { runQuery, parseQuery } = require('./query_v2_core');
const fs = require('fs');

function printUsage() {
  console.error('Usage: node scripts/query_default.js [--brief] [--json] [--top N] [--mode auto|evidence|synthesis] <query>');
}

function parseArgs(argv) {
  const args = [...argv];
  const opts = {
    brief: false,
    json: false,
    topK: 8,
    mode: 'auto',
    query: '',
  };

  while (args.length) {
    const cur = args[0];
    if (cur === '--brief') {
      opts.brief = true;
      args.shift();
      continue;
    }
    if (cur === '--json') {
      opts.json = true;
      args.shift();
      continue;
    }
    if (cur === '--top') {
      args.shift();
      opts.topK = Number(args.shift() || 8);
      continue;
    }
    if (cur === '--mode') {
      args.shift();
      opts.mode = (args.shift() || 'auto').trim();
      continue;
    }
    break;
  }

  opts.query = args.join(' ').trim();
  return opts;
}

/**
 * 语义意图识别 + 智能多源路由
 * 
 * 核心逻辑：
 * 1. 提取实体（产品型号、关键词）
 * 2. 识别用户意图
 * 3. 根据意图决定查询哪些数据源
 * 4. 模糊查询自动多源，明确查询精准单源
 */
function detectSemanticIntent(query) {
  const q = query.toLowerCase();
  
  // 提取产品型号
  const models = query.match(/\b(AE\d{3}|XE\d{3}|GE\d{3}|PE\d{4}|TP\d{3}|AI|会议室)\b/gi) || [];
  const uniqueModels = [...new Set(models.map(m => m.toUpperCase()))];
  
  // 关键词检测
  const hasPriceKw = ['价格', '多少钱', '费用', '钱', '元', '贵', '便宜', '折扣', '报价'].some(k => q.includes(k));
  const hasCompareKw = ['对比', '比较', '区别', '差异', 'vs', '和', '与', '哪个', '差别'].some(k => q.includes(k));
  const hasSpecKw = ['参数', '规格', '配置', '性能', '指标', '能力', '怎么样', '什么配置'].some(k => q.includes(k));
  const hasProcurementKw = ['招标', '投标', '询价', '采购', '方案'].some(k => q.includes(k));
  const hasFeatureKw = ['功能', '支持', '迭代', '新功能', '升级', '更新'].some(k => q.includes(k));
  const hasEolKw = ['停产', '替代', '退市', '下架'].some(k => q.includes(k));
  
  // 意图识别 + 数据源选择
  let intent = 'unknown';
  let sources = [];
  let confidence = 0;
  
  // 意图1: 对比决策（两个及以上型号 + 对比词）
  if (uniqueModels.length >= 2 && hasCompareKw) {
    intent = 'compare';
    sources = ['comparison'];
    confidence = 95;
  }
  // 意图2: 购买决策（型号 + 价格词）
  else if (uniqueModels.length >= 1 && hasPriceKw) {
    intent = 'purchase';
    sources = ['pricing'];
    // 停产信息也在pricing备注里
    if (hasEolKw) {
      confidence = 90;
    } else {
      confidence = 85;
    }
  }
  // 意图3: 技术选型（型号 + 参数/规格词）
  else if (uniqueModels.length >= 1 && hasSpecKw) {
    intent = 'technical_spec';
    // 参数查询需要规格+招标参数+价格（综合决策）
    sources = ['comparison', 'proposal', 'pricing'];
    confidence = 80;
  }
  // 意图4: 招标准备（型号 + 招标词）
  else if (uniqueModels.length >= 1 && hasProcurementKw) {
    intent = 'procurement';
    sources = ['proposal', 'comparison'];
    confidence = 90;
  }
  // 意图5: 功能了解（型号 + 功能词）
  else if (uniqueModels.length >= 1 && hasFeatureKw) {
    intent = 'feature';
    sources = ['comparison', 'release_note'];
    confidence = 75;
  }
  // 意图6: 单产品全面了解（仅型号，最模糊但最常见）
  else if (uniqueModels.length === 1) {
    intent = 'product_overview';
    // 宁多勿少：查价格+规格+招标
    sources = ['pricing', 'comparison', 'proposal'];
    confidence = 60; // 低置信度，多源补偿
  }
  // 意图7: 类别查询（AI/会议室等）
  else if (uniqueModels.length > 0) {
    intent = 'category';
    sources = ['pricing'];
    confidence = 70;
  }
  // 兜底：语义搜索
  else {
    intent = 'semantic';
    sources = ['semantic'];
    confidence = 30;
  }
  
  return {
    intent,
    sources,
    confidence,
    models: uniqueModels,
    isAmbiguous: confidence < 70
  };
}

function runExcelQuery(query, type, topK, models) {
  const script = path.join(__dirname, 'query_excel_knowledge.py');
  // 如果有型号，优先用型号查询，否则用原查询
  const searchQuery = models && models.length > 0 ? models[0] : query;
  const args = [script, searchQuery, '-t', type, '-k', String(topK)];
  try {
    return execFileSync('python3', args, { encoding: 'utf8', timeout: 30000 });
  } catch (e) {
    return `Excel query error: ${e.message}`;
  }
}

function runSemanticQuery(query, brief, topK) {
  const payload = runQuery(query, { topK, minScore: 20, includeExcluded: false });
  
  if (brief) {
    const lines = [];
    lines.push(`engine: v2`);
    lines.push(`query: ${payload.query}`);
    lines.push(`results: ${payload.results.length}`);
    payload.results.forEach((r, i) => {
      lines.push(`${i + 1}. [${r.bucket}] ${r.match_percent}% ${r.title}`);
    });
    return lines.join('\n');
  }
  
  return JSON.stringify(payload, null, 2);
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.query) {
    printUsage();
    process.exit(1);
  }

  // 语义意图识别
  const intentInfo = detectSemanticIntent(opts.query);
  const sources = intentInfo.sources;
  
  // 输出调试信息（非JSON模式）
  if (!opts.json) {
    console.log(`=== 查询意图分析 ===`);
    console.log(`查询: ${opts.query}`);
    console.log(`意图: ${intentInfo.intent} (置信度: ${intentInfo.confidence}%)`);
    console.log(`数据源: ${sources.join(', ')}`);
    if (intentInfo.models.length > 0) {
      console.log(`识别型号: ${intentInfo.models.join(', ')}`);
    }
    console.log(`是否模糊: ${intentInfo.isAmbiguous ? '是' : '否'}`);
    console.log('');
  }
  
  // 执行查询
  const allResults = [];
  
  for (const source of sources) {
    if (source === 'semantic') {
      const output = runSemanticQuery(opts.query, opts.brief, opts.topK);
      if (opts.brief) {
        console.log(output);
      } else {
        console.log(output);
      }
    } else {
      // Excel数据源 - 传入型号列表用于精确查询
      const output = runExcelQuery(opts.query, source, opts.topK, intentInfo.models);
      if (!opts.json) {
        console.log(`--- ${source.toUpperCase()} ---`);
      }
      console.log(output);
    }
  }
}

main();
