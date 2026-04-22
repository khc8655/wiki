#!/usr/bin/env python3
"""
Build Excel Knowledge Base
Parses Excel files from WebDAV and generates structured JSON for:
- pricing (价格查询)
- proposal (阶段描述)
- comparison (产品对比)
"""

import json
import re
import base64
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote, unquote
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCEL_STORE = ROOT / 'excel_store'
RAW_DIR = EXCEL_STORE / 'raw'

BASE_URL = 'https://dav.jjb115799.fnos.net'
EXCEL_REMOTE_ROOT = '/下载/temp/wiki_raw/excel/'

NS = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    'docrel': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
}

def col_to_num(col):
    n = 0
    for c in col:
        n = n * 26 + ord(c) - 64
    return n

def parse_xlsx(path: Path):
    """Parse xlsx file and return sheets data"""
    with ZipFile(path) as z:
        # Load shared strings
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            sroot = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in sroot.findall('main:si', NS):
                texts = []
                for t in si.iterfind('.//main:t', NS):
                    texts.append(t.text or '')
                shared.append(''.join(texts))
        
        # Load workbook
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap = {r.attrib['Id']: r.attrib['Target'] for r in rels.findall('rel:Relationship', NS)}
        
        sheets = []
        for sh in wb.findall('main:sheets/main:sheet', NS):
            name = sh.attrib['name']
            rid = sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = relmap[rid]
            if not target.startswith('xl/'):
                target = 'xl/' + target
            
            # Parse sheet
            root = ET.fromstring(z.read(target))
            merged_ranges = [mc.attrib['ref'] for mc in root.findall('.//main:mergeCell', NS)]
            
            rows = []
            max_col = 0
            for row in root.findall('.//main:sheetData/main:row', NS):
                vals = {}
                for c in row.findall('main:c', NS):
                    ref = c.attrib.get('r', '')
                    m = re.match(r'([A-Z]+)(\d+)', ref)
                    if not m:
                        continue
                    col = col_to_num(m.group(1))
                    max_col = max(max_col, col)
                    
                    t = c.attrib.get('t')
                    v = c.find('main:v', NS)
                    isel = c.find('main:is/main:t', NS)
                    
                    value = ''
                    if t == 's' and v is not None:
                        idx = int(v.text)
                        value = shared[idx] if idx < len(shared) else ''
                    elif t == 'inlineStr' and isel is not None:
                        value = isel.text or ''
                    elif v is not None:
                        value = v.text or ''
                    vals[col] = value
                rows.append((int(row.attrib['r']), vals))
            
            sheets.append({
                'name': name,
                'rows': rows,
                'max_col': max_col,
                'merged_ranges': merged_ranges
            })
        
        return sheets

def expand_merged_cells(rows, merged_ranges):
    """Expand merged cells - inherit values from merged region"""
    merge_map = {}
    
    for rng in merged_ranges:
        m = re.match(r'([A-Z]+)(\d+):([A-Z]+)(\d+)', rng)
        if m:
            col1, row1, col2, row2 = m.groups()
            c1, c2 = col_to_num(col1), col_to_num(col2)
            r1, r2 = int(row1), int(row2)
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    merge_map[(r, c)] = (r1, c1, r2, c2)
    
    merged_values = {}
    for (r, c), (r1, c1, r2, c2) in merge_map.items():
        key = (r1, c1, r2, c2)
        if key not in merged_values:
            for row_num, vals in rows:
                if row_num == r1 and c1 in vals:
                    merged_values[key] = vals[c1]
                    break
            if key not in merged_values:
                merged_values[key] = ''
    
    expanded = []
    for row_num, vals in rows:
        new_vals = dict(vals)
        max_c = max(vals.keys()) if vals else 1
        for c in range(1, max_c + 1):
            if c not in new_vals and (row_num, c) in merge_map:
                r1, c1, r2, c2 = merge_map[(row_num, c)]
                new_vals[c] = merged_values.get((r1, c1, r2, c2), '')
        expanded.append((row_num, new_vals))
    
    return expanded

def normalize_price(text):
    """Extract price information from text"""
    if not text:
        return {'raw': '', 'value': None, 'mode': 'unknown'}
    
    text = str(text).strip()
    
    if text in ['按项目咨询', '面议', '第三方', '']:
        return {'raw': text, 'value': None, 'mode': 'consultation'}
    
    if '元/个/年' in text or '/年' in text:
        mode = 'yearly'
    elif '元/个/月' in text or '/月' in text:
        mode = 'monthly'
    elif '元/天' in text or '/天' in text:
        mode = 'daily'
    elif '元/方/分钟' in text or '/分钟' in text:
        mode = 'per_minute'
    elif '元/GB' in text:
        mode = 'per_gb'
    elif '*N' in text or 'N*' in text:
        mode = 'formula'
    else:
        mode = 'fixed'
    
    clean = re.sub(r'[￥,，\s]', '', text)
    clean = re.sub(r'元.*$', '', clean)
    
    try:
        if '*' in clean:
            value = clean
        else:
            value = float(clean) if clean else None
    except:
        value = None
    
    return {'raw': text, 'value': value, 'mode': mode}

def is_section_header(text):
    """Check if text is a section header like '一、XY自有产品'"""
    if not text:
        return False
    return bool(re.match(r'^[一二三四五六七八九十]+[、\.\s]', text.strip()))

def parse_pricing_sheets(sheets, source_file):
    """Parse pricing sheets"""
    records = []
    record_id = 0
    
    for sheet in sheets:
        sheet_name = sheet['name']
        rows = expand_merged_cells(sheet['rows'], sheet['merged_ranges'])
        
        # Try to detect header
        header_cols = {}
        data_start = 1
        
        for row_num, vals in rows[:3]:
            row_texts = [vals.get(i, '').strip().lower() for i in range(1, 15)]
            if any('序号' in t for t in row_texts):
                # This is header row
                for col, val in vals.items():
                    val_clean = val.strip().lower()
                    if '序号' in val_clean:
                        header_cols['seq'] = col
                    elif '类别' in val_clean or '型号' in val_clean:
                        header_cols['category'] = col
                    elif '名称' in val_clean:
                        header_cols['name'] = col
                    elif '描述' in val_clean:
                        header_cols['desc'] = col
                    elif '报价' in val_clean or '价格' in val_clean:
                        header_cols['price'] = col
                    elif '编码' in val_clean:
                        header_cols['code'] = col
                    elif '单位' in val_clean:
                        header_cols['unit'] = col
                    elif '备注' in val_clean:
                        header_cols['note'] = col
                data_start = row_num + 1
                break
        
        # Default column mapping if not detected
        if not header_cols:
            header_cols = {1: 'seq', 2: 'category', 4: 'code', 5: 'name', 6: 'desc', 8: 'price', 9: 'unit', 10: 'note'}
        
        current_section = sheet_name
        
        for row_num, vals in rows:
            if row_num < data_start:
                continue
            
            # Check if this is a section header row
            for col, val in vals.items():
                if is_section_header(val):
                    current_section = val.strip()
                    break
            
            # Extract fields
            seq = vals.get(header_cols.get('seq', 1), '').strip()
            category = vals.get(header_cols.get('category', 2), '').strip()
            name = vals.get(header_cols.get('name', 5), '').strip()
            code = vals.get(header_cols.get('code', 4), '').strip()
            desc = vals.get(header_cols.get('desc', 6), '').strip()
            price_text = vals.get(header_cols.get('price', 8), '').strip()
            unit = vals.get(header_cols.get('unit', 9), '').strip()
            note = vals.get(header_cols.get('note', 10), '').strip()
            
            # Skip empty rows and summary rows
            if not name and not category:
                continue
            if name in ['小计', '总计', '合计']:
                continue
            
            price_info = normalize_price(price_text)
            
            record = {
                'id': f'pricing_{record_id:06d}',
                'source_file': source_file,
                'source_sheet': sheet_name,
                'source_row': row_num,
                'section': current_section,
                'seq': seq,
                'category': category,
                'product_name': name,
                'product_code': code,
                'description': desc,
                'price_raw': price_info['raw'],
                'price_value': price_info['value'],
                'price_mode': price_info['mode'],
                'unit': unit,
                'note': note,
                'is_pricing_record': price_info['mode'] != 'unknown' or bool(price_text),
                'record_type': 'product' if price_info['mode'] != 'unknown' else 'other'
            }
            
            records.append(record)
            record_id += 1
    
    return records

def parse_proposal_sheets(sheets, source_file):
    """Parse proposal stage description sheets"""
    records = []
    record_id = 0
    
    for sheet in sheets:
        sheet_name = sheet['name']
        rows = expand_merged_cells(sheet['rows'], sheet['merged_ranges'])
        
        # Detect header
        header_cols = {}
        data_start = 1
        
        for row_num, vals in rows[:5]:
            row_texts = [vals.get(i, '').strip().lower() for i in range(1, 10)]
            if any('序号' in t for t in row_texts):
                for col, val in vals.items():
                    val_clean = val.strip().lower()
                    if '序号' in val_clean:
                        header_cols['seq'] = col
                    elif '产品' in val_clean and '名称' in val_clean:
                        header_cols['product'] = col
                    elif '型号' in val_clean:
                        header_cols['model'] = col
                    elif '渠道' in val_clean or '询价' in val_clean:
                        header_cols['channel'] = col
                    elif '方案' in val_clean or '设计' in val_clean or '可研' in val_clean:
                        header_cols['proposal'] = col
                    elif '招标' in val_clean or '投标' in val_clean:
                        header_cols['tender'] = col
                    elif '备注' in val_clean:
                        header_cols['note'] = col
                data_start = row_num + 1
                break
        
        if not header_cols:
            header_cols = {1: 'seq', 2: 'product', 3: 'model', 4: 'channel', 5: 'proposal', 6: 'tender', 7: 'note'}
        
        for row_num, vals in rows:
            if row_num < data_start:
                continue
            
            seq = vals.get(header_cols.get('seq', 1), '').strip()
            product = vals.get(header_cols.get('product', 2), '').strip()
            model = vals.get(header_cols.get('model', 3), '').strip()
            channel = vals.get(header_cols.get('channel', 4), '').strip()
            proposal = vals.get(header_cols.get('proposal', 5), '').strip()
            tender = vals.get(header_cols.get('tender', 6), '').strip()
            note = vals.get(header_cols.get('note', 7), '').strip()
            
            if not product and not model:
                continue
            
            record = {
                'id': f'proposal_{record_id:06d}',
                'source_file': source_file,
                'source_sheet': sheet_name,
                'source_row': row_num,
                'seq': seq,
                'product_name': product,
                'product_model': model,
                'phase_channel': channel,
                'phase_proposal': proposal,
                'phase_tender': tender,
                'note': note
            }
            
            records.append(record)
            record_id += 1
    
    return records

def parse_comparison_sheets(sheets, source_file):
    """Parse product comparison matrix"""
    records = []
    
    for sheet in sheets:
        sheet_name = sheet['name']
        rows = expand_merged_cells(sheet['rows'], sheet['merged_ranges'])
        
        if not rows:
            continue
        
        # First row is header with model names
        header_row = rows[0]
        header_vals = header_row[1]
        
        # Column 1 is feature name, columns 2+ are model values
        models = []
        for col in sorted(header_vals.keys()):
            if col > 1:
                model = header_vals[col].strip()
                if model:
                    models.append({'col': col, 'name': model})
        
        # Parse feature rows
        for row_num, vals in rows[1:]:
            feature = vals.get(1, '').strip()
            if not feature:
                continue
            
            for model_info in models:
                value = vals.get(model_info['col'], '').strip()
                if value:
                    record = {
                        'feature': feature,
                        'model': model_info['name'],
                        'value': value,
                        'source_sheet': sheet_name,
                        'source_row': row_num
                    }
                    records.append(record)
    
    return records

def build_indexes(records, data_type):
    """Build search indexes"""
    indexes = {
        'by_id': {},
        'by_model': {},
        'by_name': {},
        'by_category': {},
        'by_feature': {} if data_type == 'comparison' else None
    }
    
    for record in records:
        rid = record.get('id', '')
        if rid:
            indexes['by_id'][rid] = record
        
        if data_type == 'comparison':
            model = record.get('model', '')
            if model:
                if model not in indexes['by_model']:
                    indexes['by_model'][model] = []
                indexes['by_model'][model].append(record)
            
            feature = record.get('feature', '')
            if feature:
                if feature not in indexes['by_feature']:
                    indexes['by_feature'][feature] = []
                indexes['by_feature'][feature].append(record)
        else:
            name = record.get('product_name', '')
            if name:
                if name not in indexes['by_name']:
                    indexes['by_name'][name] = []
                indexes['by_name'][name].append(record)
            
            category = record.get('category', '')
            if category:
                if category not in indexes['by_category']:
                    indexes['by_category'][category] = []
                indexes['by_category'][category].append(record)
            
            model = record.get('product_model', '')
            if model:
                if model not in indexes['by_model']:
                    indexes['by_model'][model] = []
                indexes['by_model'][model].append(record)
    
    # Remove None values
    return {k: v for k, v in indexes.items() if v is not None}

def main():
    """Main entry point"""
    # Create directories
    for d in ['pricing', 'proposal', 'comparison']:
        (EXCEL_STORE / d).mkdir(parents=True, exist_ok=True)
    
    # Process pricing files
    pricing_records = []
    
    # 2026年小鱼易连产品报价体系.xlsx
    pricing_file1 = RAW_DIR / '2026年小鱼易连产品报价体系.xlsx'
    if pricing_file1.exists():
        print(f'Parsing {pricing_file1.name}...')
        sheets = parse_xlsx(pricing_file1)
        records = parse_pricing_sheets(sheets, pricing_file1.name)
        pricing_records.extend(records)
        print(f'  -> {len(records)} pricing records')
    
    # 风铃项目报价清单2026-0306.xlsx
    pricing_file2 = RAW_DIR / '风铃项目报价清单2026-0306.xlsx'
    if pricing_file2.exists():
        print(f'Parsing {pricing_file2.name}...')
        sheets = parse_xlsx(pricing_file2)
        records = parse_pricing_sheets(sheets, pricing_file2.name)
        pricing_records.extend(records)
        print(f'  -> {len(records)} pricing records')
    
    # Save pricing data
    with open(EXCEL_STORE / 'pricing' / 'records.json', 'w', encoding='utf-8') as f:
        json.dump(pricing_records, f, ensure_ascii=False, indent=2)
    
    with open(EXCEL_STORE / 'pricing' / 'indexes.json', 'w', encoding='utf-8') as f:
        json.dump(build_indexes(pricing_records, 'pricing'), f, ensure_ascii=False, indent=2)
    
    print(f'Total pricing records: {len(pricing_records)}')
    
    # Process proposal file
    proposal_file = RAW_DIR / '项目各阶段报价描述清单2026.xlsx'
    if proposal_file.exists():
        print(f'Parsing {proposal_file.name}...')
        sheets = parse_xlsx(proposal_file)
        proposal_records = parse_proposal_sheets(sheets, proposal_file.name)
        
        with open(EXCEL_STORE / 'proposal' / 'records.json', 'w', encoding='utf-8') as f:
            json.dump(proposal_records, f, ensure_ascii=False, indent=2)
        
        with open(EXCEL_STORE / 'proposal' / 'indexes.json', 'w', encoding='utf-8') as f:
            json.dump(build_indexes(proposal_records, 'proposal'), f, ensure_ascii=False, indent=2)
        
        print(f'  -> {len(proposal_records)} proposal records')
    
    # Process comparison file
    comparison_file = RAW_DIR / '小鱼易连视频终端对比及功能介绍.xlsx'
    if comparison_file.exists():
        print(f'Parsing {comparison_file.name}...')
        sheets = parse_xlsx(comparison_file)
        comparison_records = parse_comparison_sheets(sheets, comparison_file.name)
        
        with open(EXCEL_STORE / 'comparison' / 'records.json', 'w', encoding='utf-8') as f:
            json.dump(comparison_records, f, ensure_ascii=False, indent=2)
        
        with open(EXCEL_STORE / 'comparison' / 'indexes.json', 'w', encoding='utf-8') as f:
            json.dump(build_indexes(comparison_records, 'comparison'), f, ensure_ascii=False, indent=2)
        
        print(f'  -> {len(comparison_records)} comparison records')
    
    # Build manifest
    manifest = {
        'built_at': datetime.now().isoformat(),
        'data_types': ['pricing', 'proposal', 'comparison'],
        'pricing_count': len(pricing_records) if 'pricing_records' in dir() else 0,
        'proposal_count': len(proposal_records) if 'proposal_records' in dir() else 0,
        'comparison_count': len(comparison_records) if 'comparison_records' in dir() else 0
    }
    
    with open(EXCEL_STORE / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print('Build complete!')

if __name__ == '__main__':
    main()
