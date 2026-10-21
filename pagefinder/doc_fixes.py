"""Reviewed library data fixes (pagefinder/doc_fixes.tsv): brand, title, doc type, source type, duplicates, extra model
tags, page notes and page model drops for single library docs, each row with its evidence.

The app library DB stays the source of truth for everything else. These fixes are applied on top of it, by
build_index.doc_record (so a rebuilt or in-place updated index carries them), by search.Library after it syncs with the
app DB (the app's own documents row would otherwise put the old value back), and by bay_procedure for the Bay PDF's
library excerpts. A row only applies when the doc's file name matches the `file` column, so a reused id or a test doc
with the same id is never touched.

source_type: oem (default) | shop_sheet (our own shop write-up) | maker_internal (a maker's unpublished internal flow).
A non-OEM doc can be shown, but is labeled everywhere and never counts as the OEM manual."""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DOC_FIXES = os.path.join(HERE, 'doc_fixes.tsv')

OEM = 'oem'
# label Grok sees in front of the title (GD prompt, page labels, source lines) / prefix on the Bay PDF citation
SOURCE_LABELS = {
    'shop_sheet': ('SHOP SHEET (not maker manual)', 'Shop sheet'),
    'maker_internal': ('MAKER INTERNAL FLOW, UNPUBLISHED (not maker manual)', 'Maker internal flow (unpublished, not a maker manual)'),
}
DOC_FIELDS = ('brand', 'product_line', 'title', 'doc_type', 'source_type', 'duplicate_of', 'models_add', 'doc_note')
PAGE_FIELDS = ('page_note', 'page_models_drop')

_CACHE = {}


def _norm_model(m):
    return re.sub(r'[^A-Z0-9]', '', (m or '').upper())


def split_list(v):
    return [x.strip() for x in re.split(r'[;,]', v or '') if x.strip()]


def load(path=DOC_FIXES):
    """{app id: {'file': basename, 'doc': {field: value}, 'pages': {sheet: {field: value}}, 'evidence': [..]}}"""
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return {}
    hit = _CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    out = {}
    for n, line in enumerate(open(path, encoding='utf-8'), 1):
        if not line.strip() or line.startswith('#'):
            continue
        c = line.rstrip('\n').split('\t')
        if len(c) < 6 or not c[0].strip().isdigit():
            raise ValueError(f'{path}:{n}: want 6 TAB columns: doc_id, file, sheet, field, value, evidence')
        app_id, fname, sheet, field, value, ev = int(c[0]), c[1].strip(), c[2].strip(), c[3].strip(), c[4].strip(), c[5].strip()
        if not ev:
            raise ValueError(f'{path}:{n}: every fix needs its evidence')
        e = out.setdefault(app_id, {'file': fname, 'doc': {}, 'pages': {}, 'evidence': []})
        if e['file'] != fname:
            raise ValueError(f'{path}:{n}: doc {app_id} rows name two files')
        if sheet:
            if field not in PAGE_FIELDS:
                raise ValueError(f'{path}:{n}: unknown page field {field!r}')
            e['pages'].setdefault(int(sheet), {})[field] = value
        else:
            if field not in DOC_FIELDS:
                raise ValueError(f'{path}:{n}: unknown doc field {field!r}')
            if field == 'source_type' and value != OEM and value not in SOURCE_LABELS:
                raise ValueError(f'{path}:{n}: unknown source_type {value!r}')
            e['doc'][field] = value
        e['evidence'].append(ev)
    _CACHE[path] = (mt, out)
    return out


def fix_for(app_id, file_path, path=DOC_FIXES):
    """The fixes of one doc, or None (unknown id, or the doc's file is not the one the fix was reviewed for)."""
    try:
        app_id = int(str(app_id).lstrip('L'))
    except (TypeError, ValueError):
        return None
    e = load(path).get(app_id)
    if not e or os.path.basename(file_path or '') != e['file']:
        return None
    return e


def apply(doc, pages=None, path=DOC_FIXES):
    """Apply the fixes to one page-finder doc dict in place (idempotent). Returns the fix entry or None.
    doc: {doc_id 'L<id>', file_path, title, brand, product_line, doc_type, models (JSON list), page_models (JSON list), status}.
    pages: the doc's page rows ({pdf_sheet, models JSON}); when given, page_models_drop is applied to them and to page_models."""
    import json
    e = fix_for(doc.get('doc_id') or doc.get('app_id'), doc.get('file_path'), path)
    doc.setdefault('source_type', OEM)
    if not e:
        return None
    f = e['doc']
    for k in ('brand', 'product_line', 'title', 'doc_type'):
        if k in f:
            doc[k] = f[k]
    doc['source_type'] = f.get('source_type', OEM)
    doc['doc_note'] = f.get('doc_note', '')
    if f.get('duplicate_of'):
        doc['status'] = 'duplicate'
        doc['duplicate_of'] = f['duplicate_of']
    if f.get('models_add'):
        mods = json.loads(doc.get('models') or '[]')
        have = {_norm_model(m) for m in mods}
        mods += [m for m in split_list(f['models_add']) if _norm_model(m) not in have and not have.add(_norm_model(m))]
        doc['models'] = json.dumps(mods)
    if pages is not None:   # a model printed only on a misprinted page is not a model of this doc
        drops = {sh: {_norm_model(m) for m in split_list(pf.get('page_models_drop'))} for sh, pf in e['pages'].items()}
        if any(drops.values()):
            union = set()
            for p in pages:
                pm = json.loads(p['models']) if isinstance(p.get('models'), str) else list(p.get('models') or [])
                d = drops.get(int(p['pdf_sheet']), set())
                if d:
                    pm = [m for m in pm if m not in d]
                    p['models'] = json.dumps(sorted(pm))
                union |= set(pm)
            doc['page_models'] = json.dumps(sorted(union))
    return e


def page_fix(doc_id, file_path, sheet, path=DOC_FIXES):
    e = fix_for(doc_id, file_path, path)
    return (e or {}).get('pages', {}).get(int(sheet), {}) if e else {}


def duplicates_into(target_doc_id, path=DOC_FIXES):
    """Titles of the docs marked duplicate_of target (they stay findable by title through the kept doc)."""
    return [e for e in load(path).values() if e['doc'].get('duplicate_of') == target_doc_id]


def source_label(source_type):
    return SOURCE_LABELS.get(source_type or OEM, ('', ''))[0]


def display_title(title, source_type):
    """The title as GD shows it: non-OEM docs carry their label in front, so no page of them reads as the maker's manual."""
    lab = source_label(source_type)
    return f'{lab}: {title}' if lab else title


def bay_title(title, source_type):
    """The Bay PDF citation: 'Shop sheet: ...' instead of a maker name for our own write-ups."""
    lab = SOURCE_LABELS.get(source_type or OEM, ('', ''))[1]
    if not lab:
        return title
    t = re.sub(r'\s*[—–-]+\s*shop\s*write-?\s*up\s*$', '', title or '', flags=re.I).strip()
    return f'{lab}: {t}'
