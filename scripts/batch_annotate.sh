#!/bin/bash
# 分批标注脚本 - 每次100张，自动跳过已标注
cd ~/wiki

BATCH=100
TOTAL=1885

for i in $(seq 1 $BATCH $TOTAL); do
    python3 scripts/annotate_cards.py --limit $BATCH
    annotated=$(python3 -c "
import json, os
print(sum(1 for f in os.listdir('cards/sections') if f.endswith('.json') 
          and json.loads(open(f'cards/sections/{f}').read()).get('semantic',{}).get('intent_tags')))
")
    echo "进度: $annotated/1885"
    
    # 已全部完成
    if [ "$annotated" -ge "$TOTAL" ]; then
        echo "全部完成！"
        break
    fi
    
    sleep 2
done
