#!/usr/bin/env python3
"""
处理本地raw目录的md文件，生成cards和索引
"""

import json
import re
import hashlib
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'raw'
CARDS_DIR = ROOT / 'cards' / 'sections'
DOCS_DIR = ROOT / 'index_store' / 'docs'
MANIFEST_PATH = ROOT / 'cards' / 'manifest.json'
DOC_PROFILES_PATH = ROOT / 'qmd_bridge' / 'doc_profiles.json'


def normalize_text(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\u00ad', '')
    text = text.replace('\u200b', '').replace('\ufeff', '')
    lines = [ln.rstrip() for ln in text.split('\n')]
    cleaned = []
    prev_blank = False
    for ln in lines:
        if not ln.strip():
            if not prev_blank:
                cleaned.append('')
            prev_blank = True
            continue
        cleaned.append(ln)
        prev_blank = False
    return '\n'.join(cleaned).strip() + '\n'


def clean_heading_text(s: str) -> str:
    s = s.strip()
    s = s.replace('**', '').replace('__', '')
    s = re.sub(r'^[#\-*•]+\s*', '', s)
    s = re.sub(r'^[lI|]\s+', '', s)
    s = re.sub(r'^\d+[)\.、]\s*', '', s)
    s = re.sub(r'^\d+\s+', '', s)
    return s.strip(' ：:|')


def infer_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        raw = line.strip().lstrip('#').strip()
        if not raw or raw.startswith('|') or raw.startswith('![](') or raw.startswith('---') or re.fullmatch(r'[\-|\s]+', raw):
            continue
        s = clean_heading_text(raw)
        if s and '--- | ---' not in s and len(s) <= 100 and len(s) > 2:
            return s
    return fallback


def is_heading(line: str):
    s = line.strip()
    if not s:
        return None
    if s.startswith('#'):
        m = re.match(r'^(#+)\s*(.+)$', s)
        if m:
            heading = clean_heading_text(m.group(2))
            if heading and not re.fullmatch(r'[0-9A-Za-zlI|]{1,2}', heading):
                return min(len(m.group(1)), 3), heading
            return None
    if s.startswith('|') or s.startswith('![](') or s.startswith('---') or re.fullmatch(r'[\-|\s]+', s):
        return None
    heading = clean_heading_text(s)
    if not heading or re.fullmatch(r'[0-9A-Za-zlI|]{1,2}', heading) or re.fullmatch(r'[\-|\s]+', heading):
        return None
    if len(heading) <= 50 and not re.search(r'[。；：,.]{2,}', heading):
        if any(ch in heading for ch in ['功能说明', '适用环境', '功能背景', '说明', '部署方案', '安全相关', '运维相关', '部署&升级相关']):
            return 2, heading
        if re.match(r'^[一二三四五六七八九十0-9A-Za-z【\[]', heading):
            return 2, heading
    return None


def infer_tags(blob: str):
    tags = set()
    if any(x in blob for x in ['安全', '鉴权', '密码', '加密', '国密', '隐私']):
        tags.add('security')
    if any(x in blob for x in ['稳定', '容灾', '多活', '抗丢包', '巡检', '高可用']):
        tags.add('stability')
    if any(x in blob for x in ['架构', '技术路线', '硬件架构', '软件定义', '双引擎']):
        tags.add('architecture')
    if any(x in blob for x in ['会控', '布局', '轮询', '会议', '拓扑']):
        tags.add('meeting-control')
    if any(x in blob for x in ['AI', '智能体', '语音转写', '智能纪要', '人脸识别', '同传字幕']):
        tags.add('ai')
    if any(x in blob for x in ['迭代', '新功能', '版本更新', '培训文档']):
        tags.add('release-note')
    return sorted(tags)


def split_large_body(body: str, max_chars: int = 1200):
    body = body.strip()
    if len(body) <= max_chars:
        return [body] if body else []

    blocks = [b.strip() for b in re.split(r'\n\s*\n+', body) if b.strip()]
    if len(blocks) <= 1:
        blocks = [ln.strip() for ln in body.splitlines() if ln.strip()]

    chunks = []
    cur = []
    cur_len = 0
    for block in blocks:
        hard_parts = re.split(r'(?=^\s*(?:[-*•]|\d+[\.、\)])\s+)', block, flags=re.M)
        parts = [p.strip() for p in hard_parts if p.strip()]
        if len(parts) == 1 and len(parts[0]) > max_chars:
            parts = re.split(r'(?<=。)|(?<=；)', parts[0])
            parts = [p.strip() for p in parts if p.strip()]
        for part in parts:
            extra = len(part) + (2 if cur else 0)
            if cur and cur_len + extra > max_chars:
                chunks.append('\n\n'.join(cur))
                cur = [part]
                cur_len = len(part)
            else:
                cur.append(part)
                cur_len += extra
    if cur:
        chunks.append('\n\n'.join(cur))
    return chunks


def sectionize(doc_code: str, doc_file: str, title: str, text: str, doc_type: str = 'solution'):
    lines = text.splitlines()
    sections = []
    stack = [(1, title)]
    current = None
    sec_num = 1
    fine_grained = doc_type == 'solution'

    def flush(cur):
        nonlocal sec_num
        if not cur:
            return
        body = '\n'.join(cur['body']).strip()
        if not body:
            return
        path = ' > '.join([x[1] for x in stack[:-1]] + [cur['title']]) if len(stack) > 1 else cur['title']
        bodies = split_large_body(body, 1200) if fine_grained else [body]
        for idx, part in enumerate(bodies, start=1):
            part_title = cur['title'] if len(bodies) == 1 else f"{cur['title']}（{idx}）"
            part_path = path if len(bodies) == 1 else f"{path} > 分段{idx}"
            blob = f"{part_path}\n{part}"
            sections.append({
                'id': f"{doc_code}-{Path(doc_file).stem}-sec-{sec_num:03d}",
                'doc_file': doc_file,
                'title': part_title,
                'level': cur['level'],
                'path': part_path,
                'line_start': cur['line_start'],
                'char_count': len(part),
                'body': part,
                'tags': infer_tags(blob),
            })
            sec_num += 1

    for i, line in enumerate(lines, start=1):
        h = is_heading(line)
        if h:
            flush(current)
            level, heading = h
            while stack and stack[-1][0] >= level:
                stack.pop()
            if not stack:
                stack = [(1, title)]
            stack.append((level, heading))
            current = {'title': heading, 'level': level, 'line_start': i + 1, 'body': []}
            continue
        if current is None:
            current = {'title': title, 'level': 1, 'line_start': 1, 'body': []}
        current['body'].append(line)
    flush(current)
    if not sections and text.strip():
        bodies = split_large_body(text.strip(), 1200) if fine_grained else [text.strip()]
        sections = [{
            'id': f"{doc_code}-{Path(doc_file).stem}-sec-{idx:03d}",
            'doc_file': doc_file,
            'title': title if len(bodies) == 1 else f"{title}（{idx}）",
            'level': 1,
            'path': title if len(bodies) == 1 else f"{title} > 分段{idx}",
            'line_start': 1,
            'char_count': len(body),
            'body': body,
            'tags': infer_tags(body),
        } for idx, body in enumerate(bodies, start=1)]
    return sections


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def get_doc_type(filename: str) -> str:
    """根据文件名判断文档类型"""
    if '迭代' in filename or '培训文档' in filename or '风铃' in filename:
        return 'release_note'
    return 'solution'


def process_raw_files():
    """处理raw目录下的所有md文件"""
    md_files = sorted(RAW_DIR.glob('*.md'))
    
    if not md_files:
        print("raw目录下没有md文件")
        return
    
    print(f"找到 {len(md_files)} 个md文件")
    
    # 清空旧的cards和docs
    if CARDS_DIR.exists():
        for f in CARDS_DIR.glob('*.json'):
            f.unlink()
    if DOCS_DIR.exists():
        for f in DOCS_DIR.glob('*.json'):
            f.unlink()
    
    manifest = []
    imported = []
    
    for idx, md_file in enumerate(md_files, start=1):
        doc_code = f'{idx:02d}'
        doc_type = get_doc_type(md_file.name)
        
        # 读取文件
        text = normalize_text(md_file.read_text(encoding='utf-8'))
        title = infer_title(text, md_file.stem)
        
        # 生成sections
        sections = sectionize(doc_code, md_file.name, title, text, doc_type)
        
        # 保存docs
        write_json(DOCS_DIR / f"{doc_code}-{md_file.stem}.json", sections)
        
        # 保存cards
        for sec in sections:
            card = {
                **sec,
                'related_topics': [],
                'aliases': [],
                'sibling_sections': [],
                'source_weight': 2,
            }
            write_json(CARDS_DIR / f"{sec['id']}.json", card)
            manifest.append({
                'id': sec['id'],
                'doc_file': sec['doc_file'],
                'title': sec['title'],
                'path': sec['path'],
                'tags': sec['tags'],
                'char_count': sec['char_count'],
            })
        
        imported.append({
            'doc_code': doc_code,
            'name': md_file.name,
            'title': title,
            'doc_type': doc_type,
            'section_count': len(sections),
            'char_count': len(text),
        })
        
        print(f"  {md_file.name}: {len(sections)} sections [{doc_type}]")
    
    # 保存manifest
    manifest.sort(key=lambda x: x['id'])
    write_json(MANIFEST_PATH, manifest)
    
    # 保存doc_profiles
    doc_profiles = {
        'defaults': {
            'solution': {
                'chunk_strategy': 'fine',
                'query_use_case': '方案写作、架构能力说明、材料复用',
            },
            'release_note': {
                'chunk_strategy': 'coarse',
                'query_use_case': '功能更新查询、版本变化确认',
            },
        },
        'docs': {
            item['name']: {'doc_type': item['doc_type']}
            for item in imported
        }
    }
    write_json(DOC_PROFILES_PATH, doc_profiles)
    
    print(f"\n处理完成:")
    print(f"  文档数: {len(imported)}")
    print(f"  卡片数: {len(manifest)}")


if __name__ == '__main__':
    process_raw_files()
