#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const load = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8'));

const meta = load('cards/card_metadata.v2.json');
const intentIndex = load('index_store/intent_index.v2.json');
const conceptIndex = load('index_store/concept_index.v2.json');
const cardsDir = path.join(ROOT, 'cards', 'sections');

const DOC_ROLE_PRIORITY = {
  '16-': 1,
  '02-': 2,
  '06-': 3,
  '03-': 4,
  '04-': 5,
  '09-': 6,
  '10-': 6,
  '07-': 7,
  '08-': 7,
  '17-': 7,
};

function parseQuery(query) {
  const q = query.toLowerCase();
  if (q.includes('跨云')) {
    return {
      intent: 'cross-cloud-interconnect',
      mustConcepts: ['跨云互通', '新旧系统对接'],
      preferConcepts: ['融合会管', 'MCU级联', '统一调度'],
      excludeConcepts: ['混合云部署', '跨网安全', '跨域安全'],
      expectedTitleTerms: ['华为', 'MCU', '互通', '会管'],
      highPriorityCards: ['06-新一代视频会议系统建设方案模板-sec-224', '06-新一代视频会议系统建设方案模板-sec-221'],
    };
  }
  if (q.includes('avc+svc') || q.includes('svc+avc') || q.includes('双引擎')) {
    return {
      intent: 'avc-svc-dual-engine',
      mustConcepts: ['AVC+SVC双引擎'],
      preferConcepts: ['兼容利旧', 'SVC柔性编码', 'AVC兼容互通'],
      excludeConcepts: ['跨云互通', '混合云部署', '跨网安全'],
      expectedTitleTerms: ['AVC+SVC', '双引擎', '双协议', '架构'],
      highPriorityCards: ['06-新一代视频会议系统建设方案模板-sec-055', '06-新一代视频会议系统建设方案模板-sec-201', '02-小鱼易连安全稳定白皮书V1-20240829-sec-002', '02-小鱼易连安全稳定白皮书V1-20240829-sec-006'],
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
      highPriorityCards: ['06-新一代视频会议系统建设方案模板-sec-076'],
    };
  }
  return {
    intent: null,
    mustConcepts: [],
    preferConcepts: [],
    excludeConcepts: [],
    expectedTitleTerms: [],
    highPriorityCards: [],
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
  const negativeHits = queryPlan.excludeConcepts.filter(c => (m.concept_tags || []).includes(c));
  if (negativeHits.length) {
    score -= negativeHits.length * 10;
    reasons.push(`排除概念命中:${negativeHits.join('、')}`);
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

function getDocRolePriority(cardId) {
  const key = `${cardId.split('-')[0]}-`;
  return DOC_ROLE_PRIORITY[key] || 99;
}

function normalizeText(s) {
  return (s || '')
    .replace(/!\[]\([^)]*\)/g, ' ')
    .replace(/[\*#>`]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function inferEvidenceCluster(card) {
  const title = `${card.title || ''} ${card.path || ''}`;
  const body = `${card.body || ''}`;

  if (/背景简介|安全性设计|安全性原则|立体式安全框架|架构级安全保障/i.test(title)) return 'security-overview';
  if (/会议前机制|会议中机制|会议后机制|会议应用安全/i.test(title)) return 'security-meeting-control';
  if (/鉴权与访问控制|应用权限安全|登录鉴权|访问控制/i.test(title)) return 'security-access-control';
  if (/数据存储安全|录制过程安全|录像存储安全|录制内容安全|账号密码存储/i.test(title)) return 'security-storage';
  if (/网络传输安全|端到端加密|消息通道加密|媒体通道加密|密钥安全机制|国密双引擎加密/i.test(title)) return 'security-transport';
  if (/基础架构安全|平台自主可控|IaaS运行平台|专有云|VPC/i.test(title)) return 'security-architecture';

  if (/会议前机制|会议中机制|会议后机制|会议应用安全/i.test(body)) return 'security-meeting-control';
  if (/鉴权|访问控制|黑名单|securitykey|签名|登录密码|短信验证码|双因子/i.test(body)) return 'security-access-control';
  if (/存储安全|录制过程安全|录像存储安全|录制内容安全|账号密码存储|sha-512|加盐/i.test(body)) return 'security-storage';
  if (/传输安全|端到端加密|消息通道加密|媒体通道加密|秘钥|密钥|tls|ssl|sm2|sm3|sm4/i.test(body)) return 'security-transport';
  if (/立体式安全|架构级安全保障|基础架构安全|自主可控|iaas|专有云|vpc/i.test(body)) return 'security-architecture';
  return 'generic';
}

function isValidSimilarSource(primary, candidate, cluster) {
  if (candidate.doc_file === primary.doc_file) return false;
  if (candidate.match_percent < 90) return false;
  if (candidate.bucket !== '强命中') return false;
  if ((candidate.raw_text || candidate.body || '').length < 40) return false;
  if (candidate.cluster !== cluster) return false;
  return true;
}

function getSectionNumber(cardId) {
  const m = String(cardId || '').match(/-sec-(\d+)$/);
  return m ? Number(m[1]) : null;
}

function isOverviewTitle(title) {
  return /背景简介|安全性设计|安全性原则|立体式安全框架|架构级安全保障|提升系统安全性/.test(title || '');
}

function isTitleAllowedForCluster(title, cluster) {
  const t = title || '';
  const rules = {
    'security-overview': /背景简介|安全性设计|安全性原则|立体式安全框架|架构级安全保障|提升系统安全性/,
    'security-architecture': /基础架构安全|平台自主可控|IaaS运行平台|专有云|VPC/,
    'security-transport': /网络传输安全|端到端加密|消息通道加密|媒体通道加密|密钥安全机制|国密双引擎加密/,
    'security-storage': /数据存储安全|录制过程安全|录像存储安全|录制内容安全|账号密码存储/,
    'security-access-control': /鉴权与访问控制|应用权限安全|登录鉴权|访问控制/,
    'security-meeting-control': /会议前机制|会议中机制|会议后机制|会议应用安全/,
  };
  return rules[cluster] ? rules[cluster].test(t) : true;
}

function mergeContinuousItems(items, cluster) {
  const allowed = items.filter(item => isTitleAllowedForCluster(item.title, cluster));
  if (!allowed.length) return [];
  allowed.sort((a, b) => {
    const sa = getSectionNumber(a.card_id) ?? 999999;
    const sb = getSectionNumber(b.card_id) ?? 999999;
    return sa - sb;
  });

  if (cluster === 'security-overview') {
    const primary = allowed.find(item => isOverviewTitle(item.title)) || allowed[0];
    return [{
      ...primary,
      merged_card_ids: [primary.card_id],
      merged_titles: [primary.title],
      raw_text: `${primary.title}\n${primary.body || ''}`.trim(),
    }];
  }

  const groups = [];
  let current = [];
  for (const item of allowed) {
    if (!current.length) {
      current.push(item);
      continue;
    }
    const prev = current[current.length - 1];
    const prevSec = getSectionNumber(prev.card_id);
    const curSec = getSectionNumber(item.card_id);
    if (prevSec != null && curSec != null && curSec - prevSec <= 1) {
      current.push(item);
    } else {
      groups.push(current);
      current = [item];
    }
  }
  if (current.length) groups.push(current);

  return groups.map(group => {
    const primary = [...group].sort((a, b) => b.match_percent - a.match_percent)[0];
    return {
      ...primary,
      merged_card_ids: group.map(x => x.card_id),
      merged_titles: group.map(x => x.title),
      raw_text: group.map(x => `${x.title}\n${x.body || ''}`.trim()).join('\n\n'),
    };
  });
}

function isCrossCloudEvidence(item) {
  const title = item.title || '';
  const path = item.path || '';
  const body = item.body || '';
  const text = `${title} ${path} ${body}`;

  if (/^新功能完整清单$/i.test(title)) return false;
  if (/^(说明|服务端API|【功能说明】|【功能背景】)$/i.test(title)) return false;
  if (/运维监控能力集成接口/i.test(title)) return false;

  const strongTerms = /华为|H\.323|互通|级联|跨云|呼叫|GK|通讯录|MCU级联/i;
  const mediumTerms = /会管|MCU/i;

  if (strongTerms.test(`${title} ${path}`)) return true;
  if (strongTerms.test(body)) return true;
  if (mediumTerms.test(`${title} ${path}`) && /跨云|级联|互通|通讯录|呼叫/.test(body)) return true;
  return false;
}

function dedupeByDocTitle(results) {
  const groups = new Map();
  for (const item of results) {
    const key = `${item.doc_file || 'unknown'}::${item.title || ''}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }

  return [...groups.values()].map(items => {
    items.sort((a, b) => {
      if (b.match_percent !== a.match_percent) return b.match_percent - a.match_percent;
      return (b.body || '').length - (a.body || '').length;
    });
    const primary = { ...items[0] };
    if (items.length > 1) {
      primary.similar_sources = [
        ...(primary.similar_sources || []),
        ...items.slice(1).map(x => ({
          doc_file: x.doc_file,
          card_ids: x.merged_card_ids || [x.card_id],
          match_percent: x.match_percent,
        })),
      ].slice(0, 5);
    }
    return primary;
  });
}

function dedupeEvidence(results, queryPlan) {
  if (queryPlan.intent === 'cross-cloud-interconnect') {
    const enriched = results.map(result => {
      const card = readCard(result.card_id);
      return {
        ...result,
        doc_file: card.doc_file,
        body: card.body,
      };
    });
    return dedupeByDocTitle(enriched.filter(isCrossCloudEvidence))
      .sort((a, b) => b.match_percent - a.match_percent);
  }

  if (queryPlan.intent !== 'security-assurance') return results;
  const groups = new Map();

  for (const result of results) {
    const card = readCard(result.card_id);
    const cluster = inferEvidenceCluster(card);
    const docKey = `${card.doc_file}::${cluster}`;
    const item = {
      ...result,
      doc_file: card.doc_file,
      body: card.body,
      cluster,
      doc_role_priority: getDocRolePriority(result.card_id),
      evidence_fingerprint: normalizeText(card.body).slice(0, 180),
    };
    if (!groups.has(docKey)) groups.set(docKey, []);
    groups.get(docKey).push(item);
  }

  const mergedDocs = [];
  for (const [docKey, items] of groups.entries()) {
    const cluster = items[0]?.cluster || 'generic';
    const merged = mergeContinuousItems(items, cluster);
    mergedDocs.push(...merged);
  }

  const clusterGroups = new Map();
  for (const item of mergedDocs) {
    if (!clusterGroups.has(item.cluster)) clusterGroups.set(item.cluster, []);
    clusterGroups.get(item.cluster).push(item);
  }

  const deduped = [];
  for (const [cluster, items] of clusterGroups.entries()) {
    items.sort((a, b) => {
      if (b.match_percent !== a.match_percent) return b.match_percent - a.match_percent;
      if (a.doc_role_priority !== b.doc_role_priority) return a.doc_role_priority - b.doc_role_priority;
      return (b.raw_text || '').length - (a.raw_text || '').length;
    });
    const primary = items[0];
    primary.similar_sources = items
      .filter(x => isValidSimilarSource(primary, x, cluster))
      .slice(0, 5)
      .map(x => ({
        doc_file: x.doc_file,
        card_ids: x.merged_card_ids,
        match_percent: x.match_percent,
      }));
    deduped.push(primary);
  }

  return deduped.sort((a, b) => b.match_percent - a.match_percent);
}

function runQuery(query, options = {}) {
  const topK = Number.isInteger(options.topK) ? options.topK : 10;
  const minScore = typeof options.minScore === 'number' ? options.minScore : 20;
  const includeExcluded = options.includeExcluded === true;

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

  let results = [...ids].map(id => {
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
  });

  if (!includeExcluded) {
    results = results.filter(item => item.match_percent >= minScore);
  }

  results = dedupeEvidence(results.sort((a, b) => b.match_percent - a.match_percent), plan).slice(0, topK);

  const summary = {
    candidate_count: results.length,
    strong_hits: results.filter(r => r.bucket === '强命中').length,
    weak_hits: results.filter(r => r.bucket === '弱相关').length,
    excluded_hits: results.filter(r => r.bucket === '排除项').length,
  };

  return { query, plan, summary, results };
}

module.exports = {
  parseQuery,
  scoreCard,
  runQuery,
};
