#!/usr/bin/env python3
"""
Excel数据源 SQLite 持久化层
迁移 excel_store/*/records.json → db/excel_store.db
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'db' / 'excel_store.db'


def init_db():
    """初始化数据库和表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # pricing 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pricing (
            id TEXT PRIMARY KEY,
            source_file TEXT,
            source_sheet TEXT,
            source_row INTEGER,
            product_name TEXT,
            product_model TEXT,
            category TEXT,
            pricing_type TEXT,
            price_raw TEXT,
            is_pricing_record INTEGER,
            description TEXT,
            note TEXT,
            raw_data TEXT
        )
    ''')
    cursor.execute('PRAGMA table_info(pricing)')
    existing_pricing_cols = [row[1] for row in cursor.fetchall()]
    if 'pricing_type' not in existing_pricing_cols:
        cursor.execute('ALTER TABLE pricing ADD COLUMN pricing_type TEXT DEFAULT ""')
    
    # proposal 表（招标参数）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proposal (
            id TEXT PRIMARY KEY,
            source_file TEXT,
            source_sheet TEXT,
            source_row INTEGER,
            seq TEXT,
            product_name TEXT,
            product_model TEXT,
            phase_channel TEXT,
            phase_proposal TEXT,
            phase_tender TEXT,
            phase_types TEXT,
            note TEXT,
            raw_data TEXT
        )
    ''')
    cursor.execute('PRAGMA table_info(proposal)')
    existing_proposal_cols = [row[1] for row in cursor.fetchall()]
    if 'phase_types' not in existing_proposal_cols:
        cursor.execute('ALTER TABLE proposal ADD COLUMN phase_types TEXT DEFAULT "[]"')
    
    # comparison 表（产品对比）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comparison (
            id TEXT PRIMARY KEY,
            source_file TEXT,
            source_sheet TEXT,
            source_row INTEGER,
            model TEXT,
            spec_name TEXT,
            spec_value TEXT,
            comparison_type TEXT,
            raw_data TEXT
        )
    ''')
    cursor.execute('PRAGMA table_info(comparison)')
    existing_comp_cols = [row[1] for row in cursor.fetchall()]
    if 'comparison_type' not in existing_comp_cols:
        cursor.execute('ALTER TABLE comparison ADD COLUMN comparison_type TEXT DEFAULT ""')
    
    # 创建/重建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_model ON pricing(product_model)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_name ON pricing(product_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_type ON pricing(pricing_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_model ON proposal(product_model)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_name ON proposal(product_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_phase_types ON proposal(phase_types)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparison_model ON comparison(model)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparison_type ON comparison(comparison_type)')
    
    conn.commit()
    conn.close()
    print(f"[ExcelDB] 数据库初始化完成: {DB_PATH}")


def migrate_json_to_sqlite():
    """从 JSON 迁移数据到 SQLite"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 清空现有数据
    cursor.execute('DELETE FROM pricing')
    cursor.execute('DELETE FROM proposal')
    cursor.execute('DELETE FROM comparison')
    
    excel_store = ROOT / 'excel_store'
    
    # 迁移 pricing
    pricing_file = excel_store / 'pricing' / 'records.json'
    if pricing_file.exists():
        records = json.loads(pricing_file.read_text(encoding='utf-8'))
        seen_ids = set()
        for r in records:
            rid = r.get('id', '')
            if not rid or rid in seen_ids:
                rid = f"pricing_{len(seen_ids)}"
            seen_ids.add(rid)
            # Reconstruct record from fields (not from 'row')
            rec = {
                'id': rid,
                'source_file': r.get('source_file', ''),
                'source_sheet': r.get('source_sheet', ''),
                'source_row': r.get('source_row', 0),
                'product_name': r.get('product_name', ''),
                'product_model': r.get('product_model', ''),
                'category': r.get('category', ''),
                'pricing_type': r.get('pricing_type', ''),
                'price_raw': r.get('price_raw', ''),
                'is_pricing_record': 1 if r.get('is_pricing_record') else 0,
                'description': r.get('description', ''),
                'note': r.get('note', ''),
            }
            raw_data_val = json.dumps(r, ensure_ascii=False)
            cursor.execute('''
                INSERT OR REPLACE INTO pricing VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                rec['id'], rec['source_file'], rec['source_sheet'], rec['source_row'],
                rec['product_name'], rec['product_model'], rec['category'],
                rec['pricing_type'], rec['price_raw'], rec['is_pricing_record'],
                rec['description'], rec['note'], raw_data_val
            ))
        print(f"[ExcelDB] 迁移 pricing: {len(records)} 条")
    
    # 迁移 proposal
    proposal_file = excel_store / 'proposal' / 'records.json'
    if proposal_file.exists():
        records = json.loads(proposal_file.read_text(encoding='utf-8'))
        seen_ids = set()
        for r in records:
            rid = r.get('id', '')
            if not rid or rid in seen_ids:
                rid = f"proposal_{len(seen_ids)}"
            seen_ids.add(rid)
            rec = {
                'id': rid,
                'source_file': r.get('source_file', ''),
                'source_sheet': r.get('source_sheet', ''),
                'source_row': r.get('source_row', 0),
                'seq': r.get('seq', ''),
                'product_name': r.get('product_name', ''),
                'product_model': r.get('product_model', ''),
                'phase_channel': r.get('phase_channel', ''),
                'phase_proposal': r.get('phase_proposal', ''),
                'phase_tender': r.get('phase_tender', ''),
                'phase_types': json.dumps(r.get('phase_types', []), ensure_ascii=False),
                'note': r.get('note', ''),
            }
            raw_data_val = json.dumps(r, ensure_ascii=False)
            cursor.execute('''
                INSERT OR REPLACE INTO proposal VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                rec['id'], rec['source_file'], rec['source_sheet'], rec['source_row'],
                rec['seq'], rec['product_name'], rec['product_model'],
                rec['phase_channel'], rec['phase_proposal'], rec['phase_tender'],
                rec['phase_types'], rec['note'], raw_data_val
            ))
        print(f"[ExcelDB] 迁移 proposal: {len(records)} 条")
    
    # 迁移 comparison
    comparison_file = excel_store / 'comparison' / 'records.json'
    if comparison_file.exists():
        records = json.loads(comparison_file.read_text(encoding='utf-8'))
        seen_ids = set()
        for r in records:
            rid = r.get('id', '')
            if not rid or rid in seen_ids:
                rid = f"comparison_{len(seen_ids)}"
            seen_ids.add(rid)
            rec = {
                'id': rid,
                'source_file': r.get('source_file', ''),
                'source_sheet': r.get('source_sheet', ''),
                'source_row': r.get('source_row', 0),
                'model': r.get('model', ''),
                'spec_name': r.get('feature', ''),
                'spec_value': r.get('value', ''),
                'comparison_type': r.get('comparison_type', ''),
            }
            raw_data_val = json.dumps(r, ensure_ascii=False)
            cursor.execute('''
                INSERT OR REPLACE INTO comparison VALUES (?,?,?,?,?,?,?,?,?)
            ''', (
                rec['id'], rec['source_file'], rec['source_sheet'], rec['source_row'],
                rec['model'], rec['spec_name'], rec['spec_value'],
                rec['comparison_type'], raw_data_val
            ))
        print(f"[ExcelDB] 迁移 comparison: {len(records)} 条")
    
    conn.commit()
    conn.close()
    print("[ExcelDB] 迁移完成")


class ExcelDB:
    """Excel 数据库查询类"""
    
    def __init__(self):
        self.db_path = DB_PATH
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
    
    def search_proposal_by_model(self, model: str, phase_filter: str = None) -> List[Dict]:
        """按型号查 proposal，可选 phase_filter 过滤（如 'tender'/'proposal'/'channel'）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if phase_filter:
            cursor.execute('''
                SELECT * FROM proposal
                WHERE (product_model LIKE ? OR product_model LIKE ?)
                AND phase_types LIKE ?
            ''', (f'%{model}%', f'%\n{model}%', f'%"{phase_filter}"%'))
        else:
            cursor.execute('''
                SELECT * FROM proposal 
                WHERE product_model LIKE ? OR product_model LIKE ?
            ''', (f'%{model}%', f'%\n{model}%'))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            phase_types = json.loads(row[10]) if row[10] else []
            results.append({
                'id': row[0],
                'source_file': row[1],
                'source_sheet': row[2],
                'source_row': row[3],
                'seq': row[4],
                'product_name': row[5],
                'product_model': row[6],
                'phase_channel': row[7],
                'phase_proposal': row[8],
                'phase_tender': row[9],
                'phase_types': phase_types,
                'note': row[11],
                'raw_data': json.loads(row[12]) if row[12] else {}
            })
        
        return results
    
    def search_pricing_by_model(self, model: str, pricing_type_filter: str = None) -> List[Dict]:
        """按型号查价格，可选 pricing_type 过滤"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if pricing_type_filter:
            cursor.execute('''
                SELECT * FROM pricing 
                WHERE (product_model LIKE ? OR product_name LIKE ?)
                AND pricing_type = ?
                ORDER BY is_pricing_record DESC
            ''', (f'%{model}%', f'%{model}%', pricing_type_filter))
        else:
            cursor.execute('''
                SELECT * FROM pricing 
                WHERE product_model LIKE ? OR product_name LIKE ?
                ORDER BY is_pricing_record DESC
            ''', (f'%{model}%', f'%{model}%'))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'source_file': row[1],
                'source_sheet': row[2],
                'source_row': row[3],
                'product_name': row[4],
                'product_model': row[5],
                'category': row[6],
                'pricing_type': row[7],
                'price_raw': row[8],
                'is_pricing_record': bool(row[9]),
                'description': row[10],
                'note': row[11],
                'raw_data': json.loads(row[12]) if row[12] else {}
            })
        
        return results
    
    def search_comparison_by_model(self, model: str, comparison_type_filter: str = None) -> List[Dict]:
        """按型号查对比参数，可选 comparison_type 过滤"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if comparison_type_filter:
            cursor.execute('''
                SELECT * FROM comparison 
                WHERE model LIKE ? AND comparison_type = ?
            ''', (f'%{model}%', comparison_type_filter))
        else:
            cursor.execute('''
                SELECT * FROM comparison 
                WHERE model LIKE ?
            ''', (f'%{model}%',))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'source_file': row[1],
                'source_sheet': row[2],
                'source_row': row[3],
                'model': row[4],
                'spec_name': row[5],
                'spec_value': row[6],
                'comparison_type': row[7],
                'raw_data': json.loads(row[8]) if row[8] else {}
            })
        
        return results

    def get_proposal_facets(self, model: str) -> Dict[str, int]:
        """返回某型号在各 phase_type 下的记录数"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT phase_types FROM proposal
            WHERE product_model LIKE ? OR product_model LIKE ?
        ''', (f'%{model}%', f'%\n{model}%'))
        rows = cursor.fetchall()
        conn.close()
        
        counts = {'channel': 0, 'proposal': 0, 'tender': 0}
        for row in rows:
            pts = json.loads(row[0]) if row[0] else []
            for pt in pts:
                if pt in counts:
                    counts[pt] += 1
        return counts

    def get_pricing_facets(self, model: str) -> Dict[str, int]:
        """返回某型号在各 pricing_type 下的记录数"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT pricing_type FROM pricing
            WHERE product_model LIKE ? OR product_name LIKE ?
        ''', (f'%{model}%', f'%{model}%'))
        rows = cursor.fetchall()
        conn.close()
        
        counts = {}
        for row in rows:
            pt = row[0] or '其他'
            counts[pt] = counts.get(pt, 0) + 1
        return counts

    def get_comparison_facets(self, model: str) -> Dict[str, int]:
        """返回某型号在各 comparison_type 下的记录数"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT comparison_type FROM comparison
            WHERE model LIKE ?
        ''', (f'%{model}%',))
        rows = cursor.fetchall()
        conn.close()
        
        counts = {}
        for row in rows:
            ct = row[0] or '其他'
            counts[ct] = counts.get(ct, 0) + 1
        return counts


# 全局实例
_db_instance: Optional[ExcelDB] = None


def get_excel_db() -> ExcelDB:
    """获取 ExcelDB 实例（单例）"""
    global _db_instance
    if _db_instance is None:
        _db_instance = ExcelDB()
    return _db_instance


if __name__ == '__main__':
    migrate_json_to_sqlite()