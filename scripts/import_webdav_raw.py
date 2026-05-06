#!/usr/bin/env python3
import argparse
import base64
import json
import re
import shutil
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'raw'
CARDS_DIR = ROOT / 'cards' / 'sections'
DOCS_DIR = ROOT / 'index_store' / 'docs'
MANIFEST_PATH = ROOT / 'cards' / 'manifest.json'
DOC_PROFILES_PATH = ROOT / 'qmd_bridge' / 'doc_profiles.json'
IMPORT_STATE_PATH = ROOT / 'index_store' / 'webdav_import_state.json'
BACKUP_DIR = ROOT / 'backups'

BASE_URL = 'https://dav.jjb115799.fnos.net'
DEFAULT_REMOTE_ROOT = '/下载/temp/wiki_raw/'
FOLDER_DOC_TYPE = {
    '方案文档': 'solution',
    '产品更新文档': 'release_note',
    'excel': 'excel',
    'PPT': 'ppt',
}

BINARY_EXTENSIONS = {'.xlsx', '.pptx', '.xls'}


def auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f'{user}:{password}'.encode()).decode()
    return f'Basic {token}'


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
    s = re.sub(r'^\d+[\)\.、]\s*', '', s)
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


def request(url: str, method='GET', data=None, auth=''):
    req = urllib.request.Request(url, method=method, data=data)
    req.add_header('Authorization', auth)
    return req


def list_remote_files(base_url: str, remote_root: str, user: str, password: str):
    auth = auth_header(user, password)
    ctx = ssl._create_unverified_context()
    root_url = base_url + quote(remote_root, safe='/')
    propfind = b'<?xml version="1.0" encoding="utf-8" ?><propfind xmlns="DAV:"><allprop/></propfind>'

    req = request(root_url, method='PROPFIND', data=propfind, auth=auth)
    req.add_header('Depth', '1')
    with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
        xml_data = r.read()

    ns = {'D': 'DAV:'}
    root = ET.fromstring(xml_data)
    folders = []
    for resp in root.findall('D:response', ns):
        href = unquote(resp.findtext('D:href', default='', namespaces=ns))
        display = resp.find('.//D:displayname', ns)
        rtype = resp.find('.//D:resourcetype', ns)
        is_dir = rtype is not None and rtype.find('D:collection', ns) is not None
        if is_dir and href.rstrip('/') != remote_root.rstrip('/'):
            folders.append((href, display.text if display is not None else Path(href).name))

    files = []
    for folder_path, folder_name in folders:
        req = request(base_url + quote(folder_path, safe='/'), method='PROPFIND', data=propfind, auth=auth)
        req.add_header('Depth', '1')
        with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
            xml_data = r.read()
        subroot = ET.fromstring(xml_data)
        for resp in subroot.findall('D:response', ns):
            href = unquote(resp.findtext('D:href', default='', namespaces=ns))
            display = resp.find('.//D:displayname', ns)
            rtype = resp.find('.//D:resourcetype', ns)
            is_dir = rtype is not None and rtype.find('D:collection', ns) is not None
            if is_dir:
                continue
            name = display.text if display is not None else Path(href).name
            ext = Path(name).suffix.lower()
            # Accept .md (text docs) and .xlsx/.pptx/.xls (binary source files)
            if ext not in ('.md', '.xlsx', '.pptx', '.xls'):
                continue
            if name.startswith('._'):
                continue  # macOS resource forks
            files.append({
                'folder_name': folder_name,
                'doc_type': FOLDER_DOC_TYPE.get(folder_name, 'solution'),
                'remote_path': href,
                'name': name,
            })
    return sorted(files, key=lambda x: (x['doc_type'], x['folder_name'], x['name']))


def download_text(base_url: str, remote_path: str, user: str, password: str) -> str:
    auth = auth_header(user, password)
    ctx = ssl._create_unverified_context()
    req = request(base_url + quote(remote_path, safe='/'), auth=auth)
    with urllib.request.urlopen(req, context=ctx, timeout=120) as r:
        raw = r.read()
    return raw.decode('utf-8', errors='ignore')


def download_binary(base_url: str, remote_path: str, user: str, password: str) -> bytes:
    """Download binary file (Excel, PPT) as raw bytes."""
    auth = auth_header(user, password)
    ctx = ssl._create_unverified_context()
    req = request(base_url + quote(remote_path, safe='/'), auth=auth)
    with urllib.request.urlopen(req, context=ctx, timeout=300) as r:
        return r.read()


def backup_existing_state():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_root = BACKUP_DIR / f'pre_webdav_import_{ts}'
    backup_root.mkdir(parents=True, exist_ok=True)
    for rel in ['raw', 'cards/sections', 'index_store/docs', 'cards/manifest.json', 'qmd_bridge/doc_profiles.json']:
        src = ROOT / rel
        if not src.exists():
            continue
        dst = backup_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    return backup_root


def clear_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def reset_workspace():
    """Clear generated files but preserve binary source files (.xlsx/.pptx) in raw/."""
    # Only remove .md files from raw/ (keep Excel/PPT)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for item in RAW_DIR.iterdir():
        if item.is_file() and item.suffix.lower() == '.md':
            item.unlink()
    clear_dir(CARDS_DIR)
    clear_dir(DOCS_DIR)
    write_json(MANIFEST_PATH, [])


def build_doc_profiles(entries):
    return {
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
            entry['local_name']: {'doc_type': entry['doc_type']}
            for entry in entries
        }
    }


def import_all(base_url: str, remote_root: str, user: str, password: str):
    files = list_remote_files(base_url, remote_root, user, password)
    if not files:
        raise SystemExit('No files found under remote root')

    backup_root = backup_existing_state()
    reset_workspace()

    manifest = []
    imported = []
    
    # Separate text docs (.md) from binary source files (.xlsx/.pptx)
    text_files = [f for f in files if Path(f['name']).suffix.lower() == '.md']
    binary_files = [f for f in files if Path(f['name']).suffix.lower() in BINARY_EXTENSIONS]

    # ── Process text documents (.md) ──────────────────────────────────────
    for idx, remote in enumerate(text_files, start=1):
        doc_code = f'{idx:02d}'
        local_name = f"{doc_code}-{remote['name']}"
        text = normalize_text(download_text(base_url, remote['remote_path'], user, password))
        title = infer_title(text, Path(remote['name']).stem)
        raw_path = RAW_DIR / local_name
        raw_path.write_text(text, encoding='utf-8')
        import hashlib
        text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        sections = sectionize(doc_code, local_name, title, text, remote['doc_type'])
        write_json(DOCS_DIR / f"{doc_code}-{Path(remote['name']).stem}.json", sections)
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
            **remote,
            'doc_code': doc_code,
            'local_name': local_name,
            'title': title,
            'section_count': len(sections),
            'char_count': len(text),
            'sha256': text_hash,
        })
        print(f"imported {local_name}: {len(sections)} sections [{remote['doc_type']}]")

    # ── Process binary source files (.xlsx, .pptx) ────────────────────────
    for remote in binary_files:
        import hashlib
        data = download_binary(base_url, remote['remote_path'], user, password)
        raw_path = RAW_DIR / remote['name']
        raw_path.write_bytes(data)
        file_hash = hashlib.sha256(data).hexdigest()
        imported.append({
            **remote,
            'doc_code': None,
            'local_name': remote['name'],
            'title': remote['name'],
            'section_count': 0,
            'char_count': len(data),
            'sha256': file_hash,
        })
        print(f"imported {remote['name']}: {len(data):,} bytes [{remote['doc_type']}]")

    manifest.sort(key=lambda x: x['id'])
    write_json(MANIFEST_PATH, manifest)
    write_json(DOC_PROFILES_PATH, build_doc_profiles(imported))

    # Load previous state for change detection
    prev_docs = []
    if IMPORT_STATE_PATH.exists():
        prev_state = json.loads(IMPORT_STATE_PATH.read_text(encoding='utf-8'))
        prev_docs = prev_state.get('docs', [])

    write_json(IMPORT_STATE_PATH, {
        'imported_at': datetime.now().isoformat(timespec='seconds'),
        'remote_root': remote_root,
        'backup_root': backup_root.relative_to(ROOT).as_posix(),
        'doc_count': len(imported),
        'section_count': sum(x['section_count'] for x in imported),
        'docs': imported,
        '_previous_docs': prev_docs,  # for change detection
    })
    print(json.dumps({
        'doc_count': len(imported),
        'section_count': sum(x['section_count'] for x in imported),
        'backup_root': backup_root.relative_to(ROOT).as_posix(),
        'import_state': IMPORT_STATE_PATH.relative_to(ROOT).as_posix(),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description='Import markdown docs from WebDAV wiki_raw into wiki_test')
    parser.add_argument('--base-url', default=BASE_URL)
    parser.add_argument('--remote-root', default=DEFAULT_REMOTE_ROOT)
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', required=True)
    args = parser.parse_args()
    import_all(args.base_url, args.remote_root, args.user, args.password)


if __name__ == '__main__':
    main()
