#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
queries = [
    'AE800的价格是多少？',
    'AI相关的报价分类有哪些？',
    '可按年购买的固定方数云会议室有哪几种？',
    'AE800可以使用的配件有哪些？',
    'PE8000什么时候停产？',
    'XE800与AE800的接口对比',
    '给一个GE600的简单参数入招标参数',
    '云视频在公安行业的应用有哪些？',
    '写一个软件端与硬件端的对比',
]
for i, q in enumerate(queries, 1):
    proc = subprocess.run(['python3', 'scripts/query_fast.py', q, '--json'], cwd=ROOT, capture_output=True, text=True, timeout=40)
    print(f'==== CASE {i}: {q} ====')
    if proc.returncode != 0:
        print('ERROR', proc.stderr.strip() or proc.stdout.strip())
        continue
    data = json.loads(proc.stdout)
    print('intent=', data.get('intent'), 'models=', data.get('models'))
    res = data.get('results')
    if isinstance(res, list):
        print('len=', len(res))
        for item in res[:4]:
            if isinstance(item, dict):
                print('-', item.get('product_name') or item.get('model') or item.get('title') or item.get('id'))
            else:
                print('-', str(item)[:120])
    elif isinstance(res, dict):
        print(str(res)[:1200])
    else:
        print(str(res)[:1200])
    print()
