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
  if (q.includes('安全')) {
    return {
      intent: 'security-assurance',
      mustConcepts: ['立体式安全'],
      preferConcepts: ['传输安全', '存储安全', '鉴权与访问控制', '端到端加密'],
      excludeConcepts: ['跨云互通', 'AVC+SVC双引擎'],
      expectedTitleTerms: ['安全', '鉴权', '传输', '存储'],
      highPriorityCards: ['06-新一代视频会议系统建设方案模板-sec-225','06-新一代视频会议系统建设方案模板-sec-227','06-新一代视频会议系统建设方案模板-sec-228','06-新一代视频会议系统建设方案模板-sec-233','06-新一代视频会议系统建设方案模板-sec-270','06-新一代视频会议系统建设方案模板-sec-226'],
    };
  }
  if (q.includes('稳定') || q.includes('多活') || q.includes('热备') || q.includes('容灾')) {
    return {
      intent: 'stability-reliability',
      mustConcepts: ['平台稳定性'],
      preferConcepts: ['多活热备', '容灾可靠性', '网络适应性', '抗丢包', '高可用'],
      excludeConcepts: ['跨云互通'],
      expectedTitleTerms: ['稳定', '热备', '多活', '容灾'],
      highPriorityCards: ['02-小鱼易连安全稳定白皮书V1-20240829-sec-004','02-小鱼易连安全稳定白皮书V1-20240829-sec-003','06-新一代视频会议系统建设方案模板-sec-236','06-新一代视频会议系统建设方案模板-sec-237','06-新一代视频会议系统建设方案模板-sec-245','06-新一代视频会议系统建设方案模板-sec-269'],
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
  if ((queryPlan.highPriorityCards || []).includes(id)) {
    score += 18;
    reasons.push('高优先卡');
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
  } else if ((queryPlan.expectedTitleTerms || []).length > 0 && !(queryPlan.highPriorityCards || []).includes(id)) {
    score -= 12;
    reasons.push('标题弱命中');
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
  let bucket = '弱相关';
  if (score >= 85) bucket = '强命中';
  else if (score < 45) bucket = '排除项';
  return { score, reasons, bucket };
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
      bucket: scored.bucket,
      reasons: scored.reasons,
    };
  }).filter(item => item.match_percent >= 20)
    .sort((a, b) => b.match_percent - a.match_percent)
    .slice(0, 10);

  const summary = {
    candidate_count: results.length,
    strong_hits: results.filter(r => r.bucket === '强命中').length,
    weak_hits: results.filter(r => r.bucket === '弱相关').length,
    excluded_hits: results.filter(r => r.bucket === '排除项').length,
  };

  console.log(JSON.stringify({ query, plan, summary, results }, null, 2));
}

main();
