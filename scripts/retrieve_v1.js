#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const load = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8'));

const routes = load('query_router/routes.v1.json');
const cardsDir = path.join(ROOT, 'cards', 'sections');
const meta = load('cards/card_metadata.v1.json');
const aliasIndex = load('index_store/alias_index.v1.json');
const keywordIndex = load('index_store/keyword_index.v1.json');
const intentIndex = load('index_store/intent_index.v1.json');

const STOPWORDS = new Set(['支持', '实现', '提供', '通过', '系统', '平台', '视频', '会议', '终端', '功能', '场景', '能力', '相关', '以及', '可以', '当前', '进行', '模块', '服务', '管理']);
const TOKEN_RE = /[A-Za-z0-9\-\+\.]+|[\u4e00-\u9fff]{2,}/gu;

function tokenize(text) {
  return (text.match(TOKEN_RE) || [])
    .map(s => s.trim().toLowerCase())
    .filter(s => s.length > 1 && !STOPWORDS.has(s));
}

function uniq(arr) {
  return [...new Set(arr)];
}

function detectRoute(query) {
  const q = query.toLowerCase();
  const candidates = [];
  for (const [name, route] of Object.entries(routes)) {
    const aliases = route.intent_aliases || [];
    const hitCount = aliases.filter(a => q.includes(String(a).toLowerCase())).length;
    if (hitCount > 0) {
      candidates.push({ name, route, hitCount, priority: route.priority || 99 });
    }
  }
  candidates.sort((a, b) => a.priority - b.priority || b.hitCount - a.hitCount);
  return candidates[0] || null;
}

function readCard(cardId) {
  return JSON.parse(fs.readFileSync(path.join(cardsDir, `${cardId}.json`), 'utf8'));
}

function scoreCard(query, card, metaItem, routeHit) {
  const q = query.toLowerCase();
  const qTokens = tokenize(query);
  const body = (card.body || '').toLowerCase();
  const title = (card.title || '').toLowerCase();
  const cardPath = (card.path || '').toLowerCase();
  const aliases = (metaItem.aliases || []).map(s => String(s).toLowerCase());
  const keywords = (metaItem.keywords || []).map(s => String(s).toLowerCase());
  const intentTags = new Set((metaItem.intent_tags || []).map(s => String(s).toLowerCase()));

  let score = 30;
  const reasons = [];

  if (routeHit) {
    const route = routeHit.route;
    if ((route.high_priority_cards || []).includes(card.id)) {
      score += 30;
      reasons.push('命中高优先卡');
    }
    if ((route.preferred_intent_tags || []).some(t => intentTags.has(String(t).toLowerCase()))) {
      score += 25;
      reasons.push('命中首选意图标签');
    }
    if ((route.excluded_intent_tags || []).some(t => intentTags.has(String(t).toLowerCase()))) {
      score -= 35;
      reasons.push('命中排除意图标签');
    }
    const req = route.required_terms_any || [];
    const reqHits = req.filter(t => q.includes(String(t).toLowerCase()) && (body.includes(String(t).toLowerCase()) || title.includes(String(t).toLowerCase()) || cardPath.includes(String(t).toLowerCase()) || aliases.includes(String(t).toLowerCase()) || keywords.includes(String(t).toLowerCase())));
    if (reqHits.length > 0) {
      score += 20 + reqHits.length * 4;
      reasons.push(`满足关键约束词:${reqHits.join('、')}`);
    } else if (req.length > 0) {
      score -= 18;
      reasons.push('未满足关键约束词');
    }
    const negativeHits = (route.negative_terms || []).filter(t => body.includes(String(t).toLowerCase()) || title.includes(String(t).toLowerCase()) || cardPath.includes(String(t).toLowerCase()) || aliases.includes(String(t).toLowerCase()) || keywords.includes(String(t).toLowerCase()));
    if (negativeHits.length > 0) {
      score -= negativeHits.length * 12;
      reasons.push(`命中负向词:${negativeHits.join('、')}`);
    }
  }

  const aliasHits = aliases.filter(a => q.includes(a));
  if (aliasHits.length) {
    score += aliasHits.length * 10;
    reasons.push(`别名命中:${aliasHits.join('、')}`);
  }

  const kwHits = qTokens.filter(t => keywords.includes(t) || body.includes(t) || title.includes(t) || cardPath.includes(t));
  if (kwHits.length) {
    score += Math.min(20, kwHits.length * 4);
    reasons.push(`关键词命中:${uniq(kwHits).join('、')}`);
  }

  if ((card.char_count || 0) < 80) {
    score -= 6;
    reasons.push('正文较短');
  }

  const normalized = Math.max(1, Math.min(99, Math.round(score)));
  let bucket = '弱相关';
  if (normalized >= 80) bucket = '强命中';
  else if (normalized < 35) bucket = '排除项';

  return { score: normalized, bucket, reasons: uniq(reasons) };
}

function gatherCandidates(query, routeHit) {
  const q = query.toLowerCase();
  const tokens = tokenize(query);
  const ids = new Set();

  for (const [alias, cardIds] of Object.entries(aliasIndex)) {
    if (q.includes(alias)) cardIds.forEach(id => ids.add(id));
  }
  tokens.forEach(t => (keywordIndex[t] || []).forEach(id => ids.add(id)));

  if (routeHit) {
    (routeHit.route.preferred_intent_tags || []).forEach(tag => (intentIndex[String(tag).toLowerCase()] || []).forEach(id => ids.add(id)));
    (routeHit.route.high_priority_cards || []).forEach(id => ids.add(id));
  }

  return [...ids];
}

function main() {
  const query = process.argv.slice(2).join(' ').trim();
  if (!query) {
    console.error('Usage: node scripts/retrieve_v1.js <query>');
    process.exit(1);
  }

  const routeHit = detectRoute(query);
  const candidates = gatherCandidates(query, routeHit)
    .map(id => {
      const card = readCard(id);
      const metaItem = meta[id] || {};
      const scored = scoreCard(query, card, metaItem, routeHit);
      return {
        card_id: id,
        title: card.title,
        path: card.path,
        match_percent: scored.score,
        bucket: scored.bucket,
        reasons: scored.reasons,
      };
    })
    .sort((a, b) => b.match_percent - a.match_percent)
    .slice(0, 12);

  const strong = candidates.filter(c => c.bucket === '强命中').length;
  const weak = candidates.filter(c => c.bucket === '弱相关').length;
  const excluded = candidates.filter(c => c.bucket === '排除项').length;
  const precision = candidates.length ? Math.round((strong / candidates.length) * 100) : 0;

  console.log(JSON.stringify({
    query,
    route: routeHit ? routeHit.name : null,
    summary: {
      candidate_count: candidates.length,
      strong_hits: strong,
      weak_hits: weak,
      excluded_hits: excluded,
      precision_percent: precision,
    },
    candidates,
  }, null, 2));
}

main();
