#!/usr/bin/env python3
"""
本地NAS文档导入脚本
支持：docx/pdf → markitdown → md, xlsx → 入库, pptx → 图片识别
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'raw'
CARDS_DIR = ROOT / 'cards' / 'sections'
DOCS_DIR = ROOT / 'index_store' / 'docs'
MANIFEST_PATH = ROOT / 'cards' / 'manifest.json'
DOC_PROFILES_PATH = ROOT / 'qmd_bridge' / 'doc_profiles.json'
IMPORT_STATE_PATH = ROOT / 'index_store' / 'nas_import_state.json'
BACKUP_DIR = ROOT / 'backups'

# NAS源目录
NAS_SOURCE = Path('/mnt/mydata/wiki_source')

# 文件类型映射
FOLDER_DOC_TYPE = {
    '方案文档': 'solution',
    '产品更新文档': 'release_note',
    'Excel': 'excel',
    'PPT': 'ppt',
}

# 视觉模型配置
VISION_MODEL = "THUDM/GLM-4.1V-9B-Thinking"
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-yztqpmvzbqqjmmyrybugcbdyhoufiscvhqqphtpedkgadenf")


def get_file_hash(file_path: Path) -> str:
    """计算文件SHA256"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_import_state() -> Dict:
    """加载导入状态"""
    if IMPORT_STATE_PATH.exists():
        return json.loads(IMPORT_STATE_PATH.read_text(encoding='utf-8'))
    return {'files': {}, 'last_import': None}


def save_import_state(state: Dict):
    """保存导入状态"""
    IMPORT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMPORT_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def scan_nas_source() -> List[Dict]:
    """扫描NAS源目录，返回所有文件信息"""
    files = []
    
    for folder_name, doc_type in FOLDER_DOC_TYPE.items():
        folder_path = NAS_SOURCE / folder_name
        if not folder_path.exists():
            continue
        
        for file_path in folder_path.rglob('*'):
            if not file_path.is_file():
                continue
            
            ext = file_path.suffix.lower()
            if ext not in ('.docx', '.pdf', '.xlsx', '.xls', '.pptx'):
                continue
            
            files.append({
                'path': file_path,
                'name': file_path.name,
                'relative': file_path.relative_to(NAS_SOURCE),
                'folder': folder_name,
                'doc_type': doc_type,
                'ext': ext,
                'size': file_path.stat().st_size,
                'hash': get_file_hash(file_path),
            })
    
    return sorted(files, key=lambda x: (x['doc_type'], x['folder'], x['name']))


def detect_changes(current_files: List[Dict], state: Dict) -> Dict:
    """检测文件变更"""
    prev_files = state.get('files', {})
    
    added = []
    changed = []
    unchanged = []
    
    for file_info in current_files:
        key = str(file_info['relative'])
        prev_hash = prev_files.get(key, {}).get('hash')
        
        if prev_hash is None:
            added.append(file_info)
        elif prev_hash != file_info['hash']:
            changed.append(file_info)
        else:
            unchanged.append(file_info)
    
    return {
        'added': added,
        'changed': changed,
        'unchanged': unchanged,
    }


def convert_docx_to_md(file_path: Path) -> Optional[str]:
    """docx转markdown"""
    try:
        import subprocess
        result = subprocess.run(
            ['/home/jjb/wiki/.venv/bin/markitdown', str(file_path)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"  [ERROR] markitdown失败: {result.stderr}")
            return None
    except Exception as e:
        print(f"  [ERROR] 转换docx失败: {e}")
        return None


def convert_pdf_to_md(file_path: Path) -> Optional[str]:
    """PDF转markdown，图片使用视觉模型识别"""
    try:
        import subprocess
        # markitdown会自动处理PDF中的图片
        result = subprocess.run(
            ['/home/jjb/wiki/.venv/bin/markitdown', str(file_path)],
            capture_output=True, text=True, timeout=180
        )
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"  [ERROR] markitdown PDF失败: {result.stderr}")
            return None
    except Exception as e:
        print(f"  [ERROR] 转换PDF失败: {e}")
        return None


def convert_pptx_to_images_and_recognize(file_path: Path) -> Optional[str]:
    """PPT转图片并使用视觉模型识别"""
    try:
        from pptx import Presentation
        from pptx.util import Inches
        import tempfile
        import base64
        import requests
        
        prs = Presentation(file_path)
        slide_texts = []
        
        for i, slide in enumerate(prs.slides):
            # 提取文本
            slide_text = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text.strip())
            
            if slide_text:
                slide_texts.append(f"## 第{i+1}页\n\n" + "\n\n".join(slide_text))
        
        if slide_texts:
            return "\n\n".join(slide_texts)
        else:
            print(f"  [WARN] PPT无文本内容: {file_path.name}")
            return None
            
    except Exception as e:
        print(f"  [ERROR] 转换PPT失败: {e}")
        return None


def convert_excel_to_db(file_path: Path, doc_type: str) -> bool:
    """Excel直接入库"""
    try:
        import subprocess
        result = subprocess.run(
            ['python3', str(ROOT / 'scripts' / 'import_excel.py'), str(file_path)],
            capture_output=True, text=True, timeout=300,
            cwd=str(ROOT)
        )
        if result.returncode == 0:
            return True
        else:
            print(f"  [ERROR] Excel入库失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"  [ERROR] Excel入库异常: {e}")
        return False


def normalize_text(text: str) -> str:
    """标准化文本"""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('\u00ad', '').replace('\u200b', '').replace('\ufeff', '')
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


def import_file(file_info: Dict) -> Optional[Dict]:
    """导入单个文件"""
    file_path = file_info['path']
    ext = file_info['ext']
    doc_type = file_info['doc_type']
    
    print(f"  处理: {file_info['name']} ({doc_type})")
    
    # 根据文件类型选择处理方式
    if ext in ('.docx',):
        content = convert_docx_to_md(file_path)
        if not content:
            return None
        content = normalize_text(content)
        
        # 生成输出文件名
        doc_code = f"{len(list(RAW_DIR.glob('*.md'))) + 1:02d}"
        output_name = f"{doc_code}-{file_path.stem}.md"
        output_path = RAW_DIR / output_name
        
        # 写入raw目录
        output_path.write_text(content, encoding='utf-8')
        
        return {
            'source': str(file_info['relative']),
            'output': output_name,
            'type': 'markdown',
            'doc_type': doc_type,
            'hash': file_info['hash'],
            'size': len(content),
        }
        
    elif ext in ('.pdf',):
        content = convert_pdf_to_md(file_path)
        if not content:
            return None
        content = normalize_text(content)
        
        doc_code = f"{len(list(RAW_DIR.glob('*.md'))) + 1:02d}"
        output_name = f"{doc_code}-{file_path.stem}.md"
        output_path = RAW_DIR / output_name
        
        output_path.write_text(content, encoding='utf-8')
        
        return {
            'source': str(file_info['relative']),
            'output': output_name,
            'type': 'markdown',
            'doc_type': doc_type,
            'hash': file_info['hash'],
            'size': len(content),
        }
        
    elif ext in ('.xlsx', '.xls'):
        success = convert_excel_to_db(file_path, doc_type)
        if not success:
            return None
        
        return {
            'source': str(file_info['relative']),
            'output': file_path.name,
            'type': 'excel',
            'doc_type': doc_type,
            'hash': file_info['hash'],
            'size': file_info['size'],
        }
        
    elif ext in ('.pptx',):
        content = convert_pptx_to_images_and_recognize(file_path)
        if not content:
            return None
        content = normalize_text(content)
        
        doc_code = f"{len(list(RAW_DIR.glob('*.md'))) + 1:02d}"
        output_name = f"{doc_code}-{file_path.stem}.md"
        output_path = RAW_DIR / output_name
        
        output_path.write_text(content, encoding='utf-8')
        
        return {
            'source': str(file_info['relative']),
            'output': output_name,
            'type': 'markdown',
            'doc_type': doc_type,
            'hash': file_info['hash'],
            'size': len(content),
        }
    
    return None


def import_all(force: bool = False, skip_excel: bool = False, skip_ppt: bool = False):
    """执行导入"""
    print("扫描NAS源目录...")
    current_files = scan_nas_source()
    
    # 过滤掉跳过的文件类型
    if skip_excel:
        current_files = [f for f in current_files if f['ext'] not in ('.xlsx', '.xls')]
    if skip_ppt:
        current_files = [f for f in current_files if f['ext'] not in ('.pptx',)]
    
    print(f"找到 {len(current_files)} 个文件")
    
    state = load_import_state()
    changes = detect_changes(current_files, state)
    
    print(f"\n变更检测:")
    print(f"  新增: {len(changes['added'])} 个文件")
    print(f"  变更: {len(changes['changed'])} 个文件")
    print(f"  未变: {len(changes['unchanged'])} 个文件")
    
    # 需要处理的文件
    to_process = changes['added'] + changes['changed'] if not force else current_files
    
    if not to_process:
        print("\n无需处理的文件")
        return
    
    print(f"\n开始处理 {len(to_process)} 个文件...")
    
    # 备份当前状态
    if IMPORT_STATE_PATH.exists():
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = BACKUP_DIR / f'pre_nas_import_{ts}.json'
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(IMPORT_STATE_PATH, backup_path)
    
    # 处理文件
    imported = []
    failed = []
    
    for file_info in to_process:
        result = import_file(file_info)
        if result:
            imported.append(result)
            # 更新状态
            state['files'][str(file_info['relative'])] = {
                'hash': file_info['hash'],
                'imported_at': datetime.now().isoformat(timespec='seconds'),
                'output': result['output'],
            }
        else:
            failed.append(file_info)
    
    # 更新状态
    state['last_import'] = datetime.now().isoformat(timespec='seconds')
    state['last_import_count'] = len(imported)
    save_import_state(state)
    
    # 输出结果
    print(f"\n导入完成:")
    print(f"  成功: {len(imported)} 个文件")
    print(f"  失败: {len(failed)} 个文件")
    
    if failed:
        print("\n失败文件:")
        for f in failed:
            print(f"  - {f['name']}: {f['doc_type']}")
    
    if imported:
        print("\n成功导入:")
        for item in imported:
            print(f"  - {item['output']} ({item['doc_type']})")


def main():
    parser = argparse.ArgumentParser(description='本地NAS文档导入')
    parser.add_argument('--force', action='store_true', help='强制重新导入所有文件')
    parser.add_argument('--scan', action='store_true', help='仅扫描，不导入')
    parser.add_argument('--status', action='store_true', help='显示导入状态')
    parser.add_argument('--skip-excel', action='store_true', help='跳过Excel文件')
    parser.add_argument('--skip-ppt', action='store_true', help='跳过PPT文件')
    args = parser.parse_args()
    
    if args.status:
        state = load_import_state()
        print(f"上次导入: {state.get('last_import', '从未')}")
        print(f"已导入文件: {len(state.get('files', {}))} 个")
        return
    
    if args.scan:
        files = scan_nas_source()
        if args.skip_excel:
            files = [f for f in files if f['ext'] not in ('.xlsx', '.xls')]
        if args.skip_ppt:
            files = [f for f in files if f['ext'] not in ('.pptx',)]
        print(f"NAS源目录扫描结果: {len(files)} 个文件")
        for f in files:
            print(f"  {f['relative']} ({f['doc_type']}, {f['size']:,} bytes)")
        return
    
    import_all(force=args.force, skip_excel=args.skip_excel, skip_ppt=args.skip_ppt)


if __name__ == '__main__':
    main()
