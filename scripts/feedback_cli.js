#!/usr/bin/env node
/**
 * Feedback CLI
 * 
 * 用于手动提交查询反馈
 * Usage: node scripts/feedback_cli.js "查询内容" [helpful|unhelpful] ["评论"] [expected_card_id]
 */

const { logFeedback } = require('./query_logger');

function printUsage() {
  console.error('Usage: node scripts/feedback_cli.js <query> <helpful|unhelpful> ["comment"] [expected_card_id]');
  console.error('Examples:');
  console.error('  node scripts/feedback_cli.js "跨云互通" helpful');
  console.error('  node scripts/feedback_cli.js "svc对比avc" unhelpful "没找到avc相关内容" 11-11-AVC_SVC双引擎云视频技术白皮书-sec-082');
}

function main() {
  const args = process.argv.slice(2);
  
  if (args.length < 2) {
    printUsage();
    process.exit(1);
  }
  
  const query = args[0];
  const helpfulStr = args[1].toLowerCase();
  const helpful = helpfulStr === 'helpful' || helpfulStr === 'true' || helpfulStr === 'yes';
  const comment = args[2] || '';
  const expectedCards = args[3] ? [args[3]] : [];
  
  const event = logFeedback(query, helpful, comment, expectedCards);
  console.log('Feedback recorded:', JSON.stringify(event, null, 2));
}

main();
