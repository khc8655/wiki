#!/usr/bin/env node
const { runQuery, parseQuery } = require('./query_v2_core');

function printUsage() {
  console.error('Usage: node scripts/query_default.js [--brief] [--json] [--top N] <query>');
}

function parseArgs(argv) {
  const args = [...argv];
  const opts = {
    brief: false,
    json: false,
    topK: 8,
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
    break;
  }

  opts.query = args.join(' ').trim();
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.query) {
    printUsage();
    process.exit(1);
  }

  const plan = parseQuery(opts.query);
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
    lines.push(`query: ${payload.query}`);
    lines.push(`intent: ${payload.plan.intent || 'none'}`);
    lines.push(`summary: strong=${payload.summary.strong_hits}, weak=${payload.summary.weak_hits}, excluded=${payload.summary.excluded_hits}`);
    payload.results.forEach((r, i) => {
      const label = r.doc_file ? `${r.title} (${r.doc_file})` : r.title;
      const similar = (r.similar_sources || []).length ? ` (相似来源:${(r.similar_sources || []).length})` : '';
      lines.push(`${i + 1}. [${r.bucket}] ${r.match_percent}% ${label}${similar}`);
    });
    console.log(lines.join('\n'));
    return;
  }

  const output = {
    engine: useV2 ? 'v2' : 'v2-fallback',
    ...payload,
  };
  console.log(JSON.stringify(output, null, opts.json ? 2 : 2));
}

main();
