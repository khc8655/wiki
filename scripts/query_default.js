#!/usr/bin/env node
const { execFileSync } = require('child_process');
const path = require('path');
const { runQuery, parseQuery } = require('./query_v2_core');

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

// 记录待审核的冷查询（未命中路由但用户满意的）
function logColdQuery(query, results, satisfied) {
  const logDir = path.join(__dirname, '..', 'feedback');
  const logFile = path.join(logDir, 'cold_query_feedback.jsonl');
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }
  const entry = {
    timestamp: new Date().toISOString(),
    query: query,
    results: results.slice(0, 5).map(r => ({ card_id: r.card_id, title: r.title, match_percent: r.match_percent })),
    user_satisfied: satisfied,
  };
  fs.appendFileSync(logFile, JSON.stringify(entry) + '\n');
}

function isReleaseNoteQuery(query) {
  const q = query.toLowerCase();
  const modelHit = /\b(ae\d{3}[a-z]?|xe\d{3}[a-z]?|ge\d{3}[a-z]?|tp\d{3}-[a-z]|me\d{2}[a-z]?|nc\d{2}|np\d{2}v?2?)\b/i.test(q);
  const releaseTerms = ['迭代', '新功能', '升级', '优化', '修复', '支持', '版本', '新增', '变更'];
  return releaseTerms.some(term => q.includes(term)) || (modelHit && (q.includes('功能') || q.includes('支持') || q.includes('升级')));
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

function runReleaseBridge(query, brief, mode) {
  const script = path.join(__dirname, 'query_qmd_bridge.py');
  const args = [script, query, '-c', 'release_notes', '--mode', mode];
  if (brief) args.push('--brief');
  else args.push('--json');
  return execFileSync('python3', args, { encoding: 'utf8' });
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.query) {
    printUsage();
    process.exit(1);
  }

  const responseMode = detectResponseMode(opts.query, opts.mode);

  if (isReleaseNoteQuery(opts.query)) {
    const output = runReleaseBridge(opts.query, opts.brief || !opts.json, responseMode);
    process.stdout.write(output);
    return;
  }

  const plan = parseQuery(opts.query);
  const isColdQuery = !plan.intent;
  const useV2 = Boolean(plan.intent);
  const payload = runQuery(opts.query, { topK: opts.topK, minScore: 20, includeExcluded: false });

  if (opts.brief) {
    // Check if this is a BYOM chapter query with continuous sections
    const byomChapterIds = [
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-095',
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-097',
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-108',
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-109',
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-110',
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-111',
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-112',
      '10-10-2026年私有云3月迭代版本新功能培训文档-终端-sec-113',
    ];
    const hasByomChapter = payload.results.some(r => byomChapterIds.includes(r.card_id));
    
    if (hasByomChapter && opts.query.toLowerCase().includes('byom')) {
      // Output as merged chapter
      const lines = [];
      lines.push(`engine: ${useV2 ? 'v2' : 'v2-fallback'}`);
      lines.push(`mode: ${responseMode}`);
      lines.push(`query: ${payload.query}`);
      lines.push(`intent: ${payload.plan.intent || 'none'}`);
      lines.push(`summary: strong=${payload.summary.strong_hits}, weak=${payload.summary.weak_hits}, excluded=${payload.summary.excluded_hits}`);
      lines.push('');
      lines.push('=== BYOM-NP30v2方案 章节合并输出 ===');
      lines.push('');
      
      payload.results.forEach((r, i) => {
        lines.push(`--- ${r.title} [${r.bucket}] ${r.match_percent}% ---`);
        lines.push(`来源: ${r.doc_file || 'unknown'}`);
        if (r.body) {
          lines.push(r.body.slice(0, 2000));
        }
        lines.push('');
      });
      console.log(lines.join('\n'));
      return;
    }
    
    // Default brief output
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
    
    // 冷查询反馈提示
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
  console.log(JSON.stringify(output, null, opts.json ? 2 : 2));
}

main();
