#!/usr/bin/env node
/**
 * Build path-level index for fast sibling lookup
 * Creates: index_store/path_siblings_index.v2.json
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const cardsDir = path.join(ROOT, 'cards', 'sections');
const outputFile = path.join(ROOT, 'index_store', 'path_siblings_index.v2.json');

// Build index: parent_path -> [child_card_ids]
const pathIndex = new Map();

for (const filename of fs.readdirSync(cardsDir)) {
  if (!filename.endsWith('.json')) continue;
  
  const cardPath = path.join(cardsDir, filename);
  const card = JSON.parse(fs.readFileSync(cardPath, 'utf8'));
  
  const cardId = card.id || filename.replace('.json', '');
  const fullPath = card.path || '';
  
  // Parse path levels: "L1 > L2 > L3 > L4"
  const levels = fullPath.split(' > ').map(s => s.trim()).filter(Boolean);
  
  // Index at each level
  for (let i = 0; i < levels.length; i++) {
    const parentPath = levels.slice(0, i + 1).join(' > ');
    if (!pathIndex.has(parentPath)) {
      pathIndex.set(parentPath, []);
    }
    if (!pathIndex.get(parentPath).includes(cardId)) {
      pathIndex.get(parentPath).push(cardId);
    }
  }
  
  // Also index by doc_file + path combination
  if (card.doc_file) {
    const docPath = `${card.doc_file}::${fullPath}`;
    if (!pathIndex.has(docPath)) {
      pathIndex.set(docPath, []);
    }
    if (!pathIndex.get(docPath).includes(cardId)) {
      pathIndex.get(docPath).push(cardId);
    }
  }
}

// Convert to plain object and save
const indexObj = {};
for (const [key, value] of pathIndex) {
  indexObj[key] = value;
}

fs.writeFileSync(outputFile, JSON.stringify(indexObj, null, 2));

console.log(`Built path siblings index:`);
console.log(`- Total parent paths: ${Object.keys(indexObj).length}`);
console.log(`- Sample entries:`);
Object.entries(indexObj).slice(0, 5).forEach(([k, v]) => {
  console.log(`  "${k}": ${v.length} cards`);
});
console.log(`\nSaved to: ${outputFile}`);
