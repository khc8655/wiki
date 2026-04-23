#!/usr/bin/env python3
import statistics
import subprocess
import time
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
for q in queries:
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        proc = subprocess.run(['python3', 'scripts/query_fast.py', q, '--json'], cwd=ROOT, capture_output=True, text=True, timeout=40)
        dt = time.perf_counter() - t0
        times.append(dt)
        if proc.returncode != 0:
            print(q, 'ERROR')
            break
    print(f'{q}\tavg={statistics.mean(times):.3f}s\tmin={min(times):.3f}s\tmax={max(times):.3f}s')
