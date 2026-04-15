#!/usr/bin/env node
/**
 * Query Logger Module
 * 
 * 用于记录查询请求和结果，支持反馈收集
 * 日志保存到 updates/retrieval_feedback/
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FEEDBACK_DIR = path.join(ROOT, 'updates', 'retrieval_feedback');
const LOG_FILE = path.join(FEEDBACK_DIR, 'query_log.jsonl');

// 确保反馈目录存在
function ensureDir() {
  if (!fs.existsSync(FEEDBACK_DIR)) {
    fs.mkdirSync(FEEDBACK_DIR, { recursive: true });
  }
}

/**
 * 记录查询事件
 * @param {Object} payload - 查询结果payload
 * @param {Object} metadata - 额外元数据
 */
function logQuery(payload, metadata = {}) {
  ensureDir();
  
  const event = {
    timestamp: new Date().toISOString(),
    query: payload.query,
    intent: payload.plan?.intent || null,
    precision_percent: calculatePrecision(payload),
    top_titles: payload.results?.slice(0, 5).map(r => r.title) || [],
    top_cards: payload.results?.slice(0, 5).map(r => r.card_id) || [],
    strong_hits: payload.summary?.strong_hits || 0,
    weak_hits: payload.summary?.weak_hits || 0,
    excluded_hits: payload.summary?.excluded_hits || 0,
    ...metadata
  };
  
  fs.appendFileSync(LOG_FILE, JSON.stringify(event) + '\n');
  return event;
}

/**
 * 记录用户反馈
 * @param {string} query - 原始查询
 * @param {boolean} helpful - 是否有帮助
 * @param {string} comment - 用户评论（可选）
 * @param {Array} expected_cards - 用户期望的卡片（可选）
 */
function logFeedback(query, helpful, comment = '', expected_cards = []) {
  ensureDir();
  
  const event = {
    timestamp: new Date().toISOString(),
    type: 'feedback',
    query,
    helpful,
    comment,
    expected_cards
  };
  
  fs.appendFileSync(LOG_FILE, JSON.stringify(event) + '\n');
  return event;
}

/**
 * 计算检索精确度（简单估算）
 */
function calculatePrecision(payload) {
  const results = payload.results || [];
  if (results.length === 0) return 0;
  
  const strongHits = results.filter(r => r.match_percent >= 80).length;
  return Math.round((strongHits / results.length) * 100);
}

/**
 * 读取最近N条日志
 */
function readRecentLogs(n = 100) {
  if (!fs.existsSync(LOG_FILE)) return [];
  
  const lines = fs.readFileSync(LOG_FILE, 'utf8').trim().split('\n');
  return lines.slice(-n).map(line => {
    try {
      return JSON.parse(line);
    } catch (e) {
      return null;
    }
  }).filter(Boolean);
}

/**
 * 分析日志并生成统计报告
 */
function analyzeLogs() {
  const logs = readRecentLogs(1000);
  const queries = logs.filter(l => !l.type || l.type === 'query');
  const feedbacks = logs.filter(l => l.type === 'feedback');
  
  // 统计高频查询
  const queryCounts = {};
  queries.forEach(l => {
    queryCounts[l.query] = (queryCounts[l.query] || 0) + 1;
  });
  
  // 统计 intent 分布
  const intentCounts = {};
  queries.forEach(l => {
    if (l.intent) {
      intentCounts[l.intent] = (intentCounts[l.intent] || 0) + 1;
    }
  });
  
  // 统计低 precision 查询
  const lowPrecisionQueries = queries
    .filter(l => l.precision_percent < 50)
    .map(l => l.query);
  
  return {
    total_queries: queries.length,
    total_feedbacks: feedbacks.length,
    top_queries: Object.entries(queryCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10),
    top_intents: Object.entries(intentCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10),
    low_precision_queries: [...new Set(lowPrecisionQueries)].slice(0, 10),
    avg_precision: queries.length > 0 
      ? Math.round(queries.reduce((sum, l) => sum + (l.precision_percent || 0), 0) / queries.length)
      : 0
  };
}

module.exports = {
  logQuery,
  logFeedback,
  readRecentLogs,
  analyzeLogs,
  LOG_FILE
};

// CLI 用法
if (require.main === module) {
  const args = process.argv.slice(2);
  const cmd = args[0];
  
  if (cmd === 'stats') {
    console.log(JSON.stringify(analyzeLogs(), null, 2));
  } else if (cmd === 'recent') {
    const n = parseInt(args[1]) || 10;
    console.log(JSON.stringify(readRecentLogs(n), null, 2));
  } else {
    console.log('Usage: node query_logger.js [stats|recent [n]]');
  }
}
