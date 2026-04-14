#!/usr/bin/env node
/**
 * Build hardware model -> parent path index
 * Creates: index_store/model_path_index.v2.json
 * Example: "XE800" -> "硬件平台 > 硬件终端"
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const cardsDir = path.join(ROOT, 'cards', 'sections');
const outputFile = path.join(ROOT, 'index_store', 'model_path_index.v2.json');

// 硬件型号正则匹配
const MODEL_PATTERNS = [
  // 系列+型号: AE800系列、XE800系列、GE300系列、TP860-S系列
  /([A-Z]{2}\d{3}[A-Z]?)(?:\s*系列|:)/gi,
  // 具体型号: AE800、XE800、GE300、TP860-S
  /\b(AE\d{3}[A-Z]?|XE\d{3}[A-Z]?|GE\d{3}[A-Z]?|TP\d{3}-[A-Z]|ME\d{2}[A-Z]?|NC\d{2}|NP\d{2}v?2?)\b/gi,
];

const modelIndex = {};

for (const filename of fs.readdirSync(cardsDir)) {
  if (!filename.endsWith('.json')) continue;
  
  const cardPath = path.join(cardsDir, filename);
  const card = JSON.parse(fs.readFileSync(cardPath, 'utf8'));
  
  const text = `${card.title || ''} ${card.body || ''}`;
  const parentPath = card.path ? card.path.split(' > ').slice(0, 2).join(' > ') : '';
  
  if (!parentPath.includes('硬件终端')) continue;  // 只处理硬件终端相关
  
  // 提取所有型号
  const models = new Set();
  for (const pattern of MODEL_PATTERNS) {
    const matches = text.matchAll(pattern);
    for (const match of matches) {
      const model = match[1] || match[0];
      if (model) models.add(model.toUpperCase());
    }
  }
  
  // 建立型号 -> 父路径映射
  for (const model of models) {
    if (!modelIndex[model]) {
      modelIndex[model] = new Set();
    }
    modelIndex[model].add(parentPath);
  }
}

// Convert to plain object
const output = {};
for (const [model, paths] of Object.entries(modelIndex)) {
  output[model] = [...paths];
}

fs.writeFileSync(outputFile, JSON.stringify(output, null, 2));

console.log('Built hardware model index:');
console.log(`- Total models: ${Object.keys(output).length}`);
console.log(`- Sample entries:`);
Object.entries(output).slice(0, 10).forEach(([k, v]) => {
  console.log(`  "${k}": ${v.join(', ')}`);
});
console.log(`\nSaved to: ${outputFile}`);
