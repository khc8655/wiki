#!/usr/bin/env node
const { runQuery } = require('./query_v2_core');

function printUsage() {
  console.error('Usage: node scripts/query_v2.js [--json] [--brief] [--top N] [--min-score N] [--include-excluded] <query>');
}

function parseArgs(argv) {
  const args = [...argv];
  const opts = {
    json: false,
    brief: false,
    topK: 10,
    minScore: 20,
    includeExcluded: false,
    query: '',
  };

  while (args.length) {
    const cur = args[0];
    if (cur === '--json') {
      opts.json = true;
      args.shift();
      continue;
    }
    if (cur === '--brief') {
      opts.brief = true;
      args.shift();
      continue;
    }
    if (cur === '--include-excluded') {
      opts.includeExcluded = true;
      args.shift();
      continue;
    }
    if (cur === '--top') {
      args.shift();
      opts.topK = Number(args.shift() || 10);
      continue;
    }
    if (cur === '--min-score') {
      args.shift();
      opts.minScore = Number(args.shift() || 20);
      continue;
    }
    break;
  }

  opts.query = args.join(' ').trim();
  return opts;
}

function toBrief(payload) {
  const lines = [];
  lines.push(`query: ${payload.query}`);
  lines.push(`intent: ${payload.plan.intent || 'none'}`);
  lines.push(`summary: strong=${payload.summary.strong_hits}, weak=${payload.summary.weak_hits}, excluded=${payload.summary.excluded_hits}`);
  payload.results.forEach((r, i) => {
    lines.push(`${i + 1}. [${r.bucket}] ${r.match_percent}% ${r.card_id} | ${r.title}`);
  });
  return lines.join('\n');
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.query) {
    printUsage();
    process.exit(1);
  }

  const payload = runQuery(opts.query, {
    topK: opts.topK,
    minScore: opts.minScore,
    includeExcluded: opts.includeExcluded,
  });

  if (opts.brief) {
    console.log(toBrief(payload));
    return;
  }

  console.log(JSON.stringify(payload, null, opts.json ? 2 : 2));
}

main();
