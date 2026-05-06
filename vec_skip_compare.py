import sys
sys.path.insert(0, 'lib')
from hybrid_retriever import get_hybrid

queries = ['视频会议安全加密方案', '小鱼易连怎么样', '国密加密']

for q in queries:
    h1 = get_hybrid()
    r_on  = h1.search(q, top_k=10, vec_skip_threshold=999)
    h2 = get_hybrid()
    r_off = h2.search(q, top_k=10, vec_skip_threshold=0.65)

    ids_on  = set(x['id'] for x in r_on)
    ids_off = set(x['id'] for x in r_off)
    overlap = len(ids_on & ids_off)
    avg_norm = sum(x['_bm25'] for x in r_off) / 10

    print(f'[{q}] bm25_avg={avg_norm:.3f} 重叠={overlap}/10')
    print(f'  vec-on:  {[x["id"] for x in r_on[:3]]}')
    print(f'  vec-skip:{[x["id"] for x in r_off[:3]]}')
    print()