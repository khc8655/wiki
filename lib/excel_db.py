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
            price_raw TEXT,
            is_pricing_record INTEGER,
            description TEXT,
            note TEXT,
            raw_data TEXT
        )
    ''')
    
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
            note TEXT,
            raw_data TEXT
        )
    ''')
    
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
            raw_data TEXT
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_model ON pricing(product_model)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pricing_name ON pricing(product_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_model ON proposal(product_model)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_name ON proposal(product_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparison_model ON comparison(model)')
    
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
            cursor.execute('''
                INSERT OR REPLACE INTO pricing VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                r.get('id', ''),
                r.get('source_file', ''),
                r.get('source_sheet', ''),
                r.get('source_row', 0),
                r.get('product_name', ''),
                r.get('product_model', ''),
                r.get('category', ''),
                r.get('price_raw', ''),
                1 if r.get('is_pricing_record') else 0,
                r.get('description', ''),
                r.get('note', ''),
                json.dumps(r, ensure_ascii=False)
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
            cursor.execute('''
                INSERT OR REPLACE INTO proposal VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                r.get('id', ''),
                r.get('source_file', ''),
                r.get('source_sheet', ''),
                r.get('source_row', 0),
                r.get('seq', ''),
                r.get('product_name', ''),
                r.get('product_model', ''),
                r.get('phase_channel', ''),
                r.get('phase_proposal', ''),
                r.get('phase_tender', ''),
                r.get('note', ''),
                json.dumps(r, ensure_ascii=False)
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
            cursor.execute('''
                INSERT OR REPLACE INTO comparison VALUES (?,?,?,?,?,?,?,?)
            ''', (
                r.get('id', ''),
                r.get('source_file', ''),
                r.get('source_sheet', ''),
                r.get('source_row', 0),
                r.get('model', ''),
                r.get('spec_name', ''),
                r.get('spec_value', ''),
                json.dumps(r, ensure_ascii=False)
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
    
    def search_proposal_by_model(self, model: str) -> List[Dict]:
        """按型号查招标参数"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 精确匹配
        cursor.execute('''
            SELECT * FROM proposal 
            WHERE product_model LIKE ? OR product_model LIKE ?
        ''', (f'%{model}%', f'%\n{model}%'))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
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
                'note': row[10],
                'raw_data': json.loads(row[11]) if row[11] else {}
            })
        
        return results
    
    def search_pricing_by_model(self, model: str) -> List[Dict]:
        """按型号查价格"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
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
                'price_raw': row[7],
                'is_pricing_record': bool(row[8]),
                'description': row[9],
                'note': row[10],
                'raw_data': json.loads(row[11]) if row[11] else {}
            })
        
        return results
    
    def search_comparison_by_model(self, model: str) -> List[Dict]:
        """按型号查对比参数"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
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
                'raw_data': json.loads(row[7]) if row[7] else {}
            })
        
        return results


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