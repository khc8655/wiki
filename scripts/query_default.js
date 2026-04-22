#!/usr/bin/env node
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

function isReleaseNoteQuery(query) {
  const q = query.toLowerCase();
  const modelHit = /\b(ae\d{3}[a-z]?|xe\d{3}[a-z]?|ge\d{3}[a-z]?|tp\d{3}-[a-z]|me\d{2}[a-z]?|nc\d{2}|np\d{2}v?2?)\b/i.test(q);
  const releaseTerms = ['迭代', '新功能', '升级', '优化', '修复', '支持', '版本', '新增', '变更'];
  return releaseTerms.some(term => q.includes(term)) || (modelHit && (q.includes('功能') || q.includes('支持') || q.includes('升级')));
}

function isPricingQuery(query) {
  const q = query.toLowerCase();
  const priceTerms = ['价格', '报价', '多少钱', '费用', '成本', '停产', '替代', '型号', '会议室', '类别', 'ai', '配件'];
  const modelPattern = /\b(ae\d{3}|xe\d{3}|ge\d{3}|pe\d{4}|tp\d{3}|ai)\b/i;
  return priceTerms.some(term => q.includes(term)) || modelPattern.test(q);
}

function isComparisonQuery(query) {
  const q = query.toLowerCase();
  const compareTerms = ['对比', '比较', '区别', '差异', 'vs', 'versus'];
  const modelPattern = /\b(ae\d{3}|xe\d{3}|ge\d{3})\b.*\b(ae\d{3}|xe\d{3}|ge\d{3})\b/i;
  return compareTerms.some(term => q.includes(term)) || modelPattern.test(q);
}

function isProposalQuery(query) {
  const q = query.toLowerCase();
  const proposalTerms = ['招标', '投标', '参数', '方案', '描述', '询价', '阶段'];
  const modelPattern = /\b(ae\d{3}|xe\d{3}|ge\d{3})\b/i;
  return (proposalTerms.some(term => q.includes(term)) && modelPattern.test(q));
}

function detectQueryType(query) {
  const types = [];
  
  // Check comparison first (most specific)
  if (isComparisonQuery(query)) {
    types.push('comparison');
  }
  // Check proposal before pricing (招标参数 queries)
  else if (isProposalQuery(query)) {
    types.push('proposal');
  }
  // Then pricing
  else if (isPricingQuery(query)) {
    types.push('pricing');
  }
  
  if (isReleaseNoteQuery(query)) {
    types.push('release_note');
  }
  
  return types.length > 0 ? types : ['semantic'];
}

function detectResponseMode(query, preferredMode = 'auto') {
  const normalized = (preferredMode || 'auto').toLowerCase();
  if (normalized === 'evidence' || normalized === 'synthesis') {
    return normalized;
  }

  const q = query.toLowerCase();
  const synthesisTerms = [
    '总结', '归纳', '对比', '话术', '汇报', '提炼', '润色', '整理成文', '客户版', '汇报版', 'polish', 'summary', 'compare'
  ];
  return synthesisTerms.some(term => q.includes(term)) ? 'synthesis' : 'evidence';
}

function runExcelQuery(query, type, topK, opts) {
  const script = path.join(__dirname, 'query_excel_knowledge.py');
  const args = [script, query, '-t', type, '-k', String(topK)];
  if (type === 'comparison' && opts && opts.compare) {
    args.push('--compare', ...opts.compare);
  }
  try {
    return execFileSync('python3', args, { encoding: 'utf8', timeout: 30000 });
  } catch (e) {
    return `Excel query error: ${e.message}`;
  }
}

function runReleaseBridge(query, brief, mode) {
  const script = path.join(__dirname, 'query_qmd_bridge.py');
  const args = [script, query, '-c', 'release_notes', '--mode', mode];
  if (brief) args.push('--brief');
  else args.push('--json');
  try {
    return execFileSync('python3', args, { encoding: 'utf8' });
  } catch (e) {
    return `Release query error: ${e.message}`;
  }
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.query) {
    printUsage();
    process.exit(1);
  }

  const responseMode = detectResponseMode(opts.query, opts.mode);
  const queryTypes = detectQueryType(opts.query);

  // Prioritize Excel queries
  if (queryTypes.includes('pricing')) {
    // Extract model/product name or key terms from query
    const modelMatch = opts.query.match(/\b(ae\d{3}[a-z]?|xe\d{3}[a-z]?|ge\d{3}[a-z]?|pe\d{4}|tp\d{3}|ai|会议室|人脸识别|语音转写)\b/i);
    const searchQuery = modelMatch ? modelMatch[0] : opts.query;
    const output = runExcelQuery(searchQuery, 'pricing', opts.topK);
    process.stdout.write(output);
    return;
  }

  if (queryTypes.includes('comparison')) {
    const modelMatch = opts.query.match(/\b(ae\d{3}[a-z]?|xe\d{3}[a-z]?|ge\d{3}[a-z]?)\b/gi);
    if (modelMatch && modelMatch.length >= 2) {
      const output = runExcelQuery(modelMatch[0], 'comparison', opts.topK, { compare: modelMatch.slice(0, 2) });
      process.stdout.write(output);
    } else {
      const searchQuery = modelMatch ? modelMatch[0] : opts.query;
      const output = runExcelQuery(searchQuery, 'comparison', opts.topK);
      process.stdout.write(output);
    }
    return;
  }

  if (queryTypes.includes('proposal')) {
    const modelMatch = opts.query.match(/\b(ae\d{3}[a-z]?|xe\d{3}[a-z]?|ge\d{3}[a-z]?)\b/i);
    const searchQuery = modelMatch ? modelMatch[0] : opts.query;
    const output = runExcelQuery(searchQuery, 'proposal', opts.topK);
    process.stdout.write(output);
    return;
  }

  if (queryTypes.includes('release_note')) {
    const output = runReleaseBridge(opts.query, opts.brief || !opts.json, responseMode);
    process.stdout.write(output);
    return;
  }

  // Default semantic search
  const plan = parseQuery(opts.query);
  const isColdQuery = !plan.intent;
  const useV2 = Boolean(plan.intent);
  const payload = runQuery(opts.query, { topK: opts.topK, minScore: 20, includeExcluded: false });

  if (opts.brief) {
    const lines = [];
    lines.push(`engine: ${useV2 ? 'v2' : 'v2-fallback'}`);
    lines.push(`mode: ${responseMode}`);
    lines.push(`query: ${payload.query}`);
    lines.push(`intent: ${payload.plan.intent || 'none'}`);
    lines.push(`summary: strong=${payload.summary.strong_hits}, weak=${payload.summary.weak_hits}, excluded=${payload.summary.excluded_hits}`);
    payload.results.forEach((r, i) => {
      const label = r.doc_file ? `${r.title} (${r.doc_file})` : r.title;
      const similar = (r.similar_sources || []).length ? ` (相似来源:${(r.similar_sources || []).length})` : '';
      lines.push(`${i + 1}. [${r.bucket}] ${r.match_percent}% ${label}${similar}`);
    });
    
    if (isColdQuery && payload.results.length > 0) {
      lines.push('');
      lines.push('=== 冷查询反馈 ===');
      lines.push('未命中特定路由规则，以上是基于语义召回的最佳结果。');
      lines.push('如果答案满意，请回复"满意"，系统将学习此路由。');
      lines.push('如果不满意，请回复"不满意"，系统将记录为负样本。');
    }
    
    console.log(lines.join('\n'));
    return;
  }

  const output = {
    engine: useV2 ? 'v2' : 'v2-fallback',
    mode: responseMode,
    ...payload,
  };
  console.log(JSON.stringify(output, null, 2));
}

main();
