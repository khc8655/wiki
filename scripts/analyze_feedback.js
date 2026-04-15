#!/usr/bin/env node
/**
 * Feedback Analyzer
 * 
 * 定期分析查询日志，生成优化建议报告
 * Usage: node scripts/analyze_feedback.js [--output report.json]
 */

const fs = require('fs');
const path = require('path');
const { analyzeLogs, readRecentLogs, LOG_FILE } = require('./query_logger');

const ROOT = path.resolve(__dirname, '..');

function generateRecommendations(stats) {
  const recommendations = [];
  
  // 检查低 precision 查询
  if (stats.avg_precision < 60) {
    recommendations.push({
      type: 'precision',
      severity: 'high',
      message: `平均检索精确度较低 (${stats.avg_precision}%)，建议检查 intent 匹配规则和 high_priority_cards`,
      action: 'review routes.v1.json 中的 intent 定义和 high_priority_cards'
    });
  }
  
  // 检查高频查询的 coverage
  stats.top_queries.forEach(([query, count]) => {
    if (count >= 5) {
      recommendations.push({
        type: 'coverage',
        severity: 'medium',
        message: `高频查询 "${query}" (${count}次) 建议优化专用路由`,
        action: `在 routes.v1.json 中为 "${query}" 添加专用 intent`
      });
    }
  });
  
  // 检查缺少 intent 的查询
  const logs = readRecentLogs(100);
  const noIntentQueries = logs
    .filter(l => !l.type && !l.intent)
    .map(l => l.query);
  
  if (noIntentQueries.length > 0) {
    const uniqueNoIntent = [...new Set(noIntentQueries)].slice(0, 5);
    recommendations.push({
      type: 'missing_intent',
      severity: 'medium',
      message: `发现 ${uniqueNoIntent.length} 个查询未命中 intent`,
      queries: uniqueNoIntent,
      action: '在 query_v2_core.js 的 parseQuery 中添加对应 intent 规则'
    });
  }
  
  // 检查低 precision 的具体查询
  if (stats.low_precision_queries.length > 0) {
    recommendations.push({
      type: 'low_precision_detail',
      severity: 'high',
      message: '以下查询精确度较低，需要优化',
      queries: stats.low_precision_queries,
      action: '检查这些查询的路由规则和排除项设置'
    });
  }
  
  return recommendations;
}

function main() {
  const args = process.argv.slice(2);
  const outputIdx = args.indexOf('--output');
  const outputFile = outputIdx >= 0 ? args[outputIdx + 1] : null;
  
  // 检查日志文件是否存在
  if (!fs.existsSync(LOG_FILE)) {
    console.log('No query logs found yet. Run some queries first with:');
    console.log('  node scripts/query_v2.js "your query"');
    process.exit(0);
  }
  
  const stats = analyzeLogs();
  const recommendations = generateRecommendations(stats);
  
  const report = {
    generated_at: new Date().toISOString(),
    statistics: stats,
    recommendations
  };
  
  if (outputFile) {
    const outputPath = path.resolve(ROOT, outputFile);
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
    console.log(`Report saved to: ${outputPath}`);
  } else {
    console.log(JSON.stringify(report, null, 2));
  }
}

main();
