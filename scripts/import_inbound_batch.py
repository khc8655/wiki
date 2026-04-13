#!/usr/bin/env python3
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
INBOUND = WORKSPACE / 'media' / 'inbound'
RAW_DIR = ROOT / 'raw'
CARDS_DIR = ROOT / 'cards' / 'sections'
DOCS_DIR = ROOT / 'index_store' / 'docs'
MANIFEST_PATH = ROOT / 'cards' / 'manifest.json'

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

DOCS = [
    ('07', '2026年私有云3月迭代功能概要---a99734ea-43ff-4b22-bf94-51d47e460c19', '2026年私有云3月迭代功能概要.md'),
    ('08', '2026年私有云3月迭代功能概要文档---da553ac5-484e-4a5a-8b20-9c75ad157067.docx', '2026年私有云3月迭代功能概要文档.md'),
    ('09', '2026年私有云3月迭代版本新功能培训文档-云平台---c0648b82-4049-41f6-a40b-438e9e1a3dad', '2026年私有云3月迭代版本新功能培训文档-云平台.md'),
    ('10', '2026年私有云3月迭代版本新功能培训文档-终端---80e699f1-0dbc-46e4-bd90-1ecd411863fe', '2026年私有云3月迭代版本新功能培训文档-终端.md'),
    ('11', 'AVC_SVC双引擎云视频技术白皮书---8c6c9f8a-29db-4961-be06-cfaf9bb493eb', 'AVC_SVC双引擎云视频技术白皮书.md'),
    ('12', '软件定义架构与专用硬件架构的发展与区别---ce29180e-ad1b-4bbf-aaba-5e788be0e45d', '软件定义架构与专用硬件架构的发展与区别.md'),
    ('13', '视频会议的技术发展简述V8---c78b8a99-299e-425c-b299-b8f2b4871477', '视频会议的技术发展简述V8.md'),
    ('14', '视频会议技术路线选型及对比说明---a97b7591-cf3e-448f-a9fb-2ba7bf82174d', '视频会议技术路线选型及对比说明.md'),
    ('15', '视频会议抗丢包算法的简介---5bffc48d-7356-49f3-b930-9445a9692941', '视频会议抗丢包算法的简介.md'),
    ('16', '小鱼安全白皮书_V2.2---ab284570-af94-48d4-b9d5-cd35f864c3f2', '小鱼安全白皮书_V2.2.md'),
    ('17', '小鱼易连风铃系统1月迭代新功能培训文档---026e7e5f-cabc-4300-89d1-7e6e1452975d', '小鱼易连风铃系统1月迭代新功能培训文档.md'),
]


def read_text_from_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read('word/document.xml')
    root = ET.fromstring(xml)
    out = []
    for p in root.findall('.//w:body/w:p', NS):
        texts = [t.text or '' for t in p.findall('.//w:t', NS)]
        line = ''.join(texts).strip()
        if line:
            out.append(line)
        else:
            out.append('')
    cleaned = []
    prev_blank = False
    for line in out:
        if not line:
            if not prev_blank:
                cleaned.append('')
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False
    return '\n'.join(cleaned).strip() + '\n'


def read_source(path: Path) -> str:
    if path.suffix.lower() == '.docx':
        return read_text_from_docx(path)
    return path.read_text(encoding='utf-8', errors='ignore')


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


def infer_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip().lstrip('#').strip()
        if s and not s.startswith('|') and len(s) <= 80:
            return s
    return fallback


def is_heading(line: str) -> tuple[int, str] | None:
    s = line.strip()
    if not s:
        return None
    if s.startswith('#'):
        m = re.match(r'^(#+)\s*(.+)$', s)
        if m:
            return min(len(m.group(1)), 3), m.group(2).strip()
    if s.startswith('##'):
        return 2, s.lstrip('#').strip()
    if s.startswith('|') or s.startswith('![](') or s.startswith('---'):
        return None
    if len(s) <= 40 and not re.search(r'[。；：,.]{2,}', s):
        if any(ch in s for ch in ['功能说明', '适用环境', '功能背景', '说明', '部署方案', '安全相关', '运维相关', '部署&升级相关']):
            return 2, s
        if re.match(r'^[一二三四五六七八九十0-9A-Za-z【\[]', s):
            return 2, s
    return None


def infer_tags(blob: str):
    tags = set()
    text = blob.lower()
    if any(x in blob for x in ['安全', '鉴权', '密码', '加密']):
        tags.add('security')
    if any(x in blob for x in ['稳定', '容灾', '多活', '抗丢包', '巡检']):
        tags.add('stability')
    if any(x in blob for x in ['架构', '技术路线', '硬件架构', '软件定义', '双引擎']):
        tags.add('architecture')
    if any(x in blob for x in ['会控', '布局', '轮询', '会议', '拓扑']):
        tags.add('meeting-control')
    if any(x in blob for x in ['风铃', '培训文档']):
        tags.add('overview')
    return sorted(tags)


def sectionize(doc_code: str, doc_file: str, title: str, text: str):
    lines = text.splitlines()
    sections = []
    stack = [(1, title)]
    current = None
    start_line = 1
    sec_num = 1

    def flush(cur, end_line):
        nonlocal sec_num
        if not cur:
            return
        body = '\n'.join(cur['body']).strip()
        path = ' > '.join([x[1] for x in stack[:-1]] + [cur['title']]) if len(stack) > 1 else cur['title']
        blob = f"{path}\n{body}"
        sections.append({
            'id': f"{doc_code}-{Path(doc_file).stem}-sec-{sec_num:03d}",
            'doc_file': doc_file,
            'title': cur['title'],
            'level': cur['level'],
            'path': path,
            'line_start': cur['line_start'],
            'char_count': len(body),
            'body': body,
            'tags': infer_tags(blob),
        })
        sec_num += 1

    for i, line in enumerate(lines, start=1):
        h = is_heading(line)
        if h:
            flush(current, i - 1)
            level, heading = h
            while stack and stack[-1][0] >= level:
                stack.pop()
            if not stack:
                stack = [(1, title)]
            stack.append((level, heading))
            current = {'title': heading, 'level': level, 'line_start': i + 1, 'body': []}
            start_line = i + 1
            continue
        if current is None:
            current = {'title': title, 'level': 1, 'line_start': 1, 'body': []}
        current['body'].append(line)
    flush(current, len(lines))
    if not sections:
        sections = [{
            'id': f"{doc_code}-{Path(doc_file).stem}-sec-001",
            'doc_file': doc_file,
            'title': title,
            'level': 1,
            'path': title,
            'line_start': 1,
            'char_count': len(text.strip()),
            'body': text.strip(),
            'tags': infer_tags(text),
        }]
    return sections


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    all_manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    existing_prefixes = {f"{code}-" for code, _, _ in DOCS}
    all_manifest = [m for m in all_manifest if not any(m['id'].startswith(p) for p in existing_prefixes)]

    for code, src_name, raw_name in DOCS:
        src = INBOUND / src_name
        if not src.exists():
            print(f'skip missing {src_name}')
            continue
        text = normalize_text(read_source(src))
        title = infer_title(text, Path(raw_name).stem)
        raw_path = RAW_DIR / f"{code}-{raw_name}"
        raw_path.write_text(text, encoding='utf-8')
        sections = sectionize(code, raw_path.name, title, text)
        write_json(DOCS_DIR / f"{code}-{Path(raw_name).stem}.json", sections)
        for sec in sections:
            card = {
                **sec,
                'related_topics': [],
                'aliases': [],
                'sibling_sections': [],
                'source_weight': 2,
            }
            (CARDS_DIR / f"{sec['id']}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            all_manifest.append({
                'id': sec['id'],
                'doc_file': sec['doc_file'],
                'title': sec['title'],
                'path': sec['path'],
                'tags': sec['tags'],
                'char_count': sec['char_count'],
            })
        print(f"imported {raw_path.name}: {len(sections)} sections")

    all_manifest.sort(key=lambda x: x['id'])
    write_json(MANIFEST_PATH, all_manifest)


if __name__ == '__main__':
    main()
