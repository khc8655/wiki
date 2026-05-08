#!/usr/bin/env python3
"""
Convert Excel rows (pricing/comparison/proposal) into structured cards,
compatible with the existing cards/sections format.
These cards then go through annotate_cards.py → build_embeddings.py
so Excel data participates in hybrid search alongside KB paragraphs.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CARDS_DIR = ROOT / 'cards' / 'sections'
DB_PATH = ROOT / 'db' / 'excel_store.db'


def _make_id(prefix: str, row_id: str) -> str:
    """Create a safe card ID from excel row id."""
    safe = re.sub(r'[^a-zA-Z0-9\-]', '_', row_id)
    return f"excel_{prefix}_{safe}"


def _extract_models(text: str) -> list:
    """Extract model numbers from any text field."""
    if not text:
        return []
    MODEL_RE = re.compile(
        r'(AE\d{3}[A-Z]?|XE\d{3}[A-Z]?|GE\d{3}[A-Z]?|PE\d{4}|'
        r'TP\d{3}(?:-[A-Z])?|MX\d{2}|AC\d{2}|NC\d{2}|NP\d{2}(?:V?\d+)?|'
        r'ME\d{3,4}|XM\d{4})', re.I
    )
    return sorted(set(m.upper() for m in MODEL_RE.findall(text)))


def _build_pricing_card(row: dict) -> dict:
    """Build a card from a pricing row."""
    product_name = row.get('product_name', '') or ''
    category = row.get('category', '') or ''
    pricing_type = row.get('pricing_type', '') or ''
    price_raw = row.get('price_raw', '') or ''
    description = row.get('description', '') or ''
    note = row.get('note', '') or ''
    source_file = row.get('source_file', '') or ''
    source_sheet = row.get('source_sheet', '') or ''
    source_row = row.get('source_row', 0)
    row_id = row.get('id', '')

    # Skip empty rows
    if not product_name.strip() and not price_raw.strip():
        return None

    # Build rich body text for embedding quality
    body_parts = []
    if product_name:
        body_parts.append(f"产品名称：{product_name}")
    if category:
        body_parts.append(f"分类：{category}")
    if pricing_type:
        body_parts.append(f"报价类型：{pricing_type}")
    if price_raw:
        body_parts.append(f"价格：{price_raw}")
    if description:
        body_parts.append(f"描述：{description}")
    if note:
        body_parts.append(f"备注：{note}")

    # Add AI association keywords for better hybrid search matching
    # When category contains AI-related terms, add explicit AI keywords to body
    ai_terms = ['AI', '智能', '语音转写', '人脸识别', '大模型', '接入授权']
    if any(k in (category + product_name + description) for k in ai_terms):
        body_parts.append("AI相关报价分类：AI语音转写、AI人脸识别、AI大模型、AI智能体、接入授权")

    body = '\n'.join(body_parts)

    # Title: product name or category
    title = product_name if product_name else category

    # Path for organization
    path = f"报价体系 > {source_sheet}"

    # Extract models from name/category/description
    models = _extract_models(f"{product_name} {category} {pricing_type} {description}")

    # Infer intent_tags from category
    intent_tags = []
    if any(k in (category + pricing_type) for k in ['AI', '智能']):
        intent_tags.append('AI智能')
    if any(k in category for k in ['私有云', '专有云', '公有云']):
        intent_tags.append('云平台')
    if models:
        intent_tags.append('报价价格')

    return {
        'id': _make_id('pricing', row_id),
        'doc_file': source_file,
        'title': title,
        'level': 3,
        'path': path,
        'line_start': source_row,
        'char_count': len(body),
        'body': body,
        'tags': [],
        'related_topics': [],
        'aliases': [],
        'sibling_sections': [],
        'source_weight': 3,
        'semantic': {
            'intent_tags': intent_tags,
            'concept_tags': [category, pricing_type] if pricing_type else [],
            'scenario_tags': [],
            'models': models,
            'keywords': _extract_keywords(body),
            'doc_hint': 'pricing',
        },
        '_excel_row': row_id,
        '_excel_source': f"{source_file}:{source_sheet}:row{source_row}",
    }


def _build_comparison_card(row: dict) -> dict:
    """Build a card from a comparison row."""
    model = row.get('model', '') or ''
    spec_name = row.get('spec_name', '') or ''
    spec_value = row.get('spec_value', '') or ''
    comparison_type = row.get('comparison_type', '') or ''
    source_file = row.get('source_file', '') or ''
    source_sheet = row.get('source_sheet', '') or ''
    source_row = row.get('source_row', 0)
    row_id = row.get('id', '')

    if not model or not spec_name:
        return None

    # Build body: spec_name : spec_value with full context
    body = f"{spec_name}：{spec_value}"

    # Title: model + spec
    title = f"{model} {spec_name}"

    # Path
    path = f"产品对比 > {source_sheet}"

    # Extract models
    models = _extract_models(model)
    if models:
        models = [models[0]]  # single model per row

    # Infer intent_tags from spec_name
    intent_tags = ['性能参数']
    if any(k in spec_name for k in ['输入', '输出', '接口', '接口类型']):
        intent_tags = ['接口硬件']
    elif any(k in spec_name for k in ['编解码', '分辨率', '处理能力', '帧率']):
        intent_tags = ['性能参数']
    elif any(k in spec_name for k in ['架构', '形态', '分体式', '一体式']):
        intent_tags = ['接口硬件']

    return {
        'id': _make_id('comparison', row_id),
        'doc_file': source_file or '硬件终端产品对比',
        'title': title,
        'level': 3,
        'path': path,
        'line_start': source_row,
        'char_count': len(body),
        'body': body,
        'tags': [],
        'related_topics': [],
        'aliases': [],
        'sibling_sections': [],
        'source_weight': 3,
        'semantic': {
            'intent_tags': intent_tags,
            'concept_tags': [comparison_type] if comparison_type else [],
            'scenario_tags': [],
            'models': models,
            'keywords': _extract_keywords(body),
            'doc_hint': 'comparison',
        },
        '_excel_row': row_id,
        '_excel_source': f"{source_file}:{source_sheet}:row{source_row}" if source_sheet else f"comparison:row{source_row}",
    }


def _build_proposal_card(row: dict) -> dict:
    """Build cards from a proposal row (one per non-empty phase)."""
    product_name = row.get('product_name', '') or ''
    product_model = row.get('product_model', '') or ''
    source_file = row.get('source_file', '') or ''
    source_sheet = row.get('source_sheet', '') or ''
    source_row = row.get('source_row', 0)
    row_id = row.get('id', '')

    if not product_name and not product_model:
        return []

    models = _extract_models(product_model)
    # Build title with model info: "一体化视频终端 GE600 招标参数"
    model_suffix = ' '.join(models) if models else ''
    title_base = f"{product_name} {model_suffix}".strip() if model_suffix else (product_name or product_model)
    path_base = f"招标参数 > {source_sheet}" if source_sheet else "招标参数"

    cards = []

    # Phase tender
    phase_tender = row.get('phase_tender', '') or ''
    if phase_tender.strip():
        cards.append({
            'id': _make_id('proposal_tender', row_id),
            'doc_file': source_file,
            'title': f"{title_base} 招标参数",
            'level': 3,
            'path': f"{path_base} > 招标参数",
            'line_start': source_row,
            'char_count': len(phase_tender),
            'body': phase_tender,
            'tags': [],
            'related_topics': [],
            'aliases': [],
            'sibling_sections': [],
            'source_weight': 3,
            'semantic': {
                'intent_tags': ['招标参数'],
                'concept_tags': [],
                'scenario_tags': [],
                'models': models,
                'keywords': _extract_keywords(phase_tender),
                'doc_hint': 'proposal',
            },
            '_excel_row': row_id,
            '_excel_source': f"{source_file}:{source_sheet}:row{source_row}",
        })

    # Phase proposal (可研)
    phase_proposal = row.get('phase_proposal', '') or ''
    if phase_proposal.strip():
        cards.append({
            'id': _make_id('proposal_proposal', row_id),
            'doc_file': source_file,
            'title': f"{title_base} 可研参数",
            'level': 3,
            'path': f"{path_base} > 可研参数",
            'line_start': source_row,
            'char_count': len(phase_proposal),
            'body': phase_proposal,
            'tags': [],
            'related_topics': [],
            'aliases': [],
            'sibling_sections': [],
            'source_weight': 3,
            'semantic': {
                'intent_tags': ['方案参数'],
                'concept_tags': [],
                'scenario_tags': [],
                'models': models,
                'keywords': _extract_keywords(phase_proposal),
                'doc_hint': 'proposal',
            },
            '_excel_row': row_id,
            '_excel_source': f"{source_file}:{source_sheet}:row{source_row}",
        })

    # Phase channel
    phase_channel = row.get('phase_channel', '') or ''
    if phase_channel.strip():
        cards.append({
            'id': _make_id('proposal_channel', row_id),
            'doc_file': source_file,
            'title': f"{title_base} 渠道参数",
            'level': 3,
            'path': f"{path_base} > 渠道参数",
            'line_start': source_row,
            'char_count': len(phase_channel),
            'body': phase_channel,
            'tags': [],
            'related_topics': [],
            'aliases': [],
            'sibling_sections': [],
            'source_weight': 3,
            'semantic': {
                'intent_tags': ['渠道参数'],
                'concept_tags': [],
                'scenario_tags': [],
                'models': models,
                'keywords': _extract_keywords(phase_channel),
                'doc_hint': 'proposal',
            },
            '_excel_row': row_id,
            '_excel_source': f"{source_file}:{source_sheet}:row{source_row}",
        })

    return cards


def _extract_keywords(text: str, max_kw: int = 10) -> list:
    """Extract meaningful keywords from text."""
    if not text:
        return []
    # Chinese keyword extraction: split on punctuation, filter short
    import re
    words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
    # Filter common stopwords
    stopwords = {'的', '和', '与', '为', '了', '在', '是', '不', '等', '具有', '支持',
                 '包括', '以及', '可以', '能够', '进行', '使用', '产品', '系统', '平台'}
    words = [w for w in words if w not in stopwords and len(w) >= 2]
    # Count frequency
    from collections import Counter
    freq = Counter(words)
    return [w for w, _ in freq.most_common(max_kw)]


def convert_all():
    """Convert all Excel rows to cards and write to cards/sections/."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    all_cards = []

    # 1. Pricing rows
    c.execute("""
        SELECT id, source_file, source_sheet, source_row, product_name,
               product_model, category, pricing_type, price_raw, description, note
        FROM pricing
    """)
    for row in c.fetchall():
        row_dict = {
            'id': row[0],
            'source_file': row[1],
            'source_sheet': row[2],
            'source_row': row[3],
            'product_name': row[4],
            'product_model': row[5],
            'category': row[6],
            'pricing_type': row[7],
            'price_raw': row[8],
            'description': row[9],
            'note': row[10],
        }
        card = _build_pricing_card(row_dict)
        if card:
            all_cards.append(card)

    # 2. Comparison rows
    c.execute("""
        SELECT id, source_file, source_sheet, source_row, model,
               spec_name, spec_value, comparison_type
        FROM comparison
    """)
    for row in c.fetchall():
        row_dict = {
            'id': row[0],
            'source_file': row[1],
            'source_sheet': row[2],
            'source_row': row[3],
            'model': row[4],
            'spec_name': row[5],
            'spec_value': row[6],
            'comparison_type': row[7],
        }
        card = _build_comparison_card(row_dict)
        if card:
            all_cards.append(card)

    # 3. Proposal rows
    c.execute("""
        SELECT id, source_file, source_sheet, source_row, seq,
               product_name, product_model,
               phase_channel, phase_proposal, phase_tender
        FROM proposal
    """)
    for row in c.fetchall():
        row_dict = {
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
        }
        cards = _build_proposal_card(row_dict)
        all_cards.extend(cards)

    conn.close()

    # Write cards
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for card in all_cards:
        card_id = card['id']
        safe_fname = re.sub(r'[^\w\-]', '_', card_id) + '.json'
        path = CARDS_DIR / safe_fname
        path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding='utf-8')
        written += 1

    print(f"[excel_to_cards] Wrote {written} cards to {CARDS_DIR}")
    return written


if __name__ == '__main__':
    count = convert_all()
    print(f"Done. Run next: annotate_cards.py → build_embeddings.py")
