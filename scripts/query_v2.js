#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const load = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8'));

const meta = load('cards/card_metadata.v2.json');
const intentIndex = load('index_store/intent_index.v2.json');
const conceptIndex = load('index_store/concept_index.v2.json');
const negativeIndex = load('index_store/negative_index.v2.json');
const cardsDir = path.join(ROOT, 'cards', 'sections');

function parseQuery(query) {
  const q = query.toLowerCase();
  if (q.includes('跨云')) {
    return {
      intent: 'cross-cloud-interconnect',
      mustConcepts: ['跨云互通', '新旧系统对接'],
      preferConcepts: ['融合会管', 'MCU级联', '统一调度'],
      excludeConcepts: ['混合云部署', '跨网安全', '跨域安全'],
      expectedTitleTerms: ['华为', 'MCU', '互通', '会管'],
    };
  }
  if (q.includes('avc+svc') || q.includes('svc+avc') || q.includes('双引擎')) {
    return {
      intent: 'avc-svc-dual-engine',
      mustConcepts: ['AVC+SVC双引擎'],
      preferConcepts: ['兼容利旧', 'SVC柔性编码', 'AVC兼容互通'],
      excludeConcepts: ['跨云互通', '混合云部署', '跨网安全'],
      expectedTitleTerms: ['AVC+SVC', '双引擎', '双协议', '架构'],
    };
  }
  if (q.includes('混合云') || q.includes('专有云')) {
    return {
      intent: 'hybrid-deployment',
      mustConcepts: ['混合云部署'],
      preferConcepts: ['媒体本地处理', '专有云'],
      excludeConcepts: ['跨云互通'],
      expectedTitleTerms: ['专有云', '混合云', '部署'],
    };
  }
  return {
    intent: null,
    mustConcepts: [],
    preferConcepts: [],
    excludeConcepts: [],
    expectedTitleTerms: [],
  };
}

function readCard(id) {
  return JSON.parse(fs.readFileSync(path.join(cardsDir, `${id}.json`), 'utf8'));
}

function scoreCard(queryPlan, id) {
  const m = meta[id] || {};
  const card = readCard(id);
  let score = 35;
  const reasons = [];
  const titleBlob = `${card.title || ''} ${card.path || ''}`;

  if (queryPlan.intent && (m.intent_tags || []).includes(queryPlan.intent)) {
    score += 28;
    reasons.push('intent命中');
  }
  const mustHits = queryPlan.mustConcepts.filter(c => (m.concept_tags || []).includes(c));
  if (mustHits.length) {
    score += mustHits.length * 18;
    reasons.push(`must命中:${mustHits.join('、')}`);
  }
  const preferHits = (queryPlan.preferConcepts || []).filter(c => (m.concept_tags || []).includes(c));
  if (preferHits.length) {
    score += preferHits.length * 8;
    reasons.push(`prefer命中:${preferHits.join('、')}`);
  }
  const titleHits = (queryPlan.expectedTitleTerms || []).filter(t => titleBlob.includes(t));
  if (titleHits.length) {
    score += titleHits.length * 6;
    reasons.push(`标题命中:${titleHits.join('、')}`);
  }
  const negativeHits = queryPlan.excludeConcepts.filter(c => (m.negative_concepts || []).includes(c));
  if (negativeHits.length) {
    score -= negativeHits.length * 10;
    reasons.push(`negative命中:${negativeHits.join('、')}`);
  }
  if ((m.quality_score || 0) > 0.85) {
    score += 5;
    reasons.push('高质量card');
  }

  score = Math.max(1, Math.min(99, Math.round(score)));
  return { score, reasons };
}

function main() {
  const query = process.argv.slice(2).join(' ').trim();
  if (!query) {
    console.error('Usage: node scripts/query_v2.js <query>');
    process.exit(1);
  }

  const plan = parseQuery(query);
  const ids = new Set();

  if (plan.intent && intentIndex[plan.intent]) {
    intentIndex[plan.intent].forEach(id => ids.add(id));
  }
  plan.mustConcepts.forEach(c => (conceptIndex[c] || []).forEach(id => ids.add(id)));
  if (plan.intent && intentIndex[plan.intent]) {
    ids.clear();
    intentIndex[plan.intent].forEach(id => ids.add(id));
  }

  const results = [...ids].map(id => {
    const card = readCard(id);
    const scored = scoreCard(plan, id);
    return {
      card_id: id,
      title: card.title,
      path: card.path,
      match_percent: scored.score,
      reasons: scored.reasons,
    };
  }).filter(item => item.match_percent >= 20)
    .sort((a, b) => b.match_percent - a.match_percent)
    .slice(0, 10);

  console.log(JSON.stringify({ query, plan, results }, null, 2));
}

main();
