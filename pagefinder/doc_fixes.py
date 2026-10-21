"""Reviewed library data fixes (pagefinder/doc_fixes.tsv): brand, title, doc type, source type, duplicates, extra model
tags, page notes and page model drops for single library docs, each row with its evidence.

The app library DB stays the source of truth for everything else. These fixes are applied on top of it, by
build_index.doc_record (so a rebuilt or in-place updated index carries them), by search.Library after it syncs with the
app DB (the app's own documents row would otherwise put the old value back), and by bay_procedure for the Bay PDF's
library excerpts. A row only applies when the doc's file name matches the `file` column, so a reused id or a test doc
with the same id is never touched.

source_type: oem (default) | shop_sheet (our own shop write-up) | maker_internal (a maker's unpublished internal flow) |
third_party (not the maker's: an aftermarket vendor's or tool maker's doc) | coach_builder (an RV builder's own pages,
e.g. a floorplan book or wiring standard) | dealer_doc (a dealer / distributor form or notice) | maker_web (the maker's own
published web FAQ / support page, captured verbatim: maker content, but not a service manual). A non-OEM doc can be shown, but is labeled
everywhere and never counts as the OEM manual.

Doc fields: brand, product_line, title, doc_type, category (the library category = unit type), also_category (comma list of
further library categories the doc's own pages cover, e.g. a control panel manual filed under Furnaces whose fault-code
pages are the water heater's: the doc is also a candidate for those unit types), source_type, duplicate_of
(a true duplicate: never returned, the kept copy is named), exclude (not an RV service doc, e.g. a residential product or
a seminar flyer: never returned, the reason is the value), models_add / models_drop (comma list), alt_titles ('; ' list of other names the manual is known by, e.g. the
combined manual it was split out of), also_brand (comma list of other maker names the product is sold or serviced under,
e.g. Atwood water heaters are now Dometic: a tech who names that maker still gets the doc), printed_pages (the
printed page number of each sheet in order, '1,2,3-12,26-32,40', for a PDF cut from a bigger book),
any_brand ('; ' list of scope phrases: the doc is a generic manual for every maker's unit of that kind, e.g. L47 Lippert
Electric Brakes fits any electric drum brake; when the job names a scope phrase the doc stays a candidate whatever brand
the job names, and it is always offered), not_for ('; ' list of phrases: the doc is never picked for a job that names one,
e.g. L47 not for hydraulic / disc / ABS brakes), doc_note (shown with the
doc; a misprint is a "DOC DEFECT: ..." note giving the correct value, the maker's text is never rewritten).
Page fields (sheet = PDF sheet): page_note (shown with the page), page_models_drop, page_exclude (the sheet is never
returned, e.g. a re-host site's ad insert or a marketing page; the reason is the value), page_marks_off (comma list of page
marks that are wrong for that sheet, e.g. is_troubleshooting), page_topics ('; ' list of page-topic labels, e.g.
'battery bank wiring: parallel batteries; DC busbars': shown to GD with the page and searched like page words)."""
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
    'third_party': ('THIRD-PARTY DOC (not maker manual)', 'Third-party doc'),
    'general_reference': ('GENERAL REFERENCE (not a product manual; applies to any brand)', 'General reference'),
    'coach_builder': ("COACH-BUILDER DOC (not the component maker's manual)", 'Coach-builder doc'),
    'dealer_doc': ('DEALER/DISTRIBUTOR DOC (not maker manual)', 'Dealer/distributor doc'),
    'maker_web': ("MAKER WEB FAQ (maker's published web page, not a service manual)", 'Maker web FAQ'),
}
DOC_FIELDS = ('brand', 'product_line', 'title', 'doc_type', 'category', 'also_category', 'source_type', 'duplicate_of', 'exclude',
              'models_add', 'models_drop', 'doc_note', 'alt_titles', 'also_brand', 'printed_pages', 'any_brand', 'not_for')
PAGE_FIELDS = ('page_note', 'page_models_drop', 'page_exclude', 'page_marks_off', 'page_topics')
PAGE_MARKS = ('is_toc', 'is_cover', 'is_safety', 'is_parts', 'is_fault_codes', 'is_troubleshooting', 'is_wiring')

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
            if field == 'page_marks_off' and not set(split_list(value)) <= set(PAGE_MARKS):
                raise ValueError(f'{path}:{n}: unknown page mark in {value!r}')
            pf = e['pages'].setdefault(int(sheet), {})
            pf[field] = (pf[field] + ' ' + value) if field == 'page_note' and field in pf else value
        else:
            if field not in DOC_FIELDS:
                raise ValueError(f'{path}:{n}: unknown doc field {field!r}')
            if field == 'source_type' and value != OEM and value not in SOURCE_LABELS:
                raise ValueError(f'{path}:{n}: unknown source_type {value!r}')
            if field in e['doc'] and field in ('doc_note', 'models_add', 'models_drop'):
                value = e['doc'][field] + (' ' if field == 'doc_note' else ', ') + value   # several rows add up
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
    if 'category' in f:
        doc['unit_type'] = f['category']
    doc['also_unit_types'] = ', '.join(u for u in split_list(f.get('also_category')) if u != doc.get('unit_type'))
    doc['also_brands'] = ', '.join(b for b in split_list(f.get('also_brand')) if b.lower() != (doc.get('brand') or '').lower())
    doc['any_brand'] = '; '.join(split_list(f.get('any_brand')))   # generic manual: applies to every maker's unit of this kind
    doc['not_for'] = '; '.join(split_list(f.get('not_for')))       # ... but never to these kinds of the unit
    doc['source_type'] = f.get('source_type', OEM)
    doc['doc_note'] = f.get('doc_note', '')
    if f.get('alt_titles'):   # other names the manual is known by ('; ' list): the title tier also matches these words
        doc['alt_titles'] = json.dumps([t.strip() for t in f['alt_titles'].split(';') if t.strip()])
    if f.get('duplicate_of'):
        doc['status'] = 'duplicate'
        doc['duplicate_of'] = f['duplicate_of']
    elif f.get('exclude'):
        doc['status'] = 'excluded'
    drop_all = '*' in split_list(f.get('models_drop'))   # '*': every listed "model" is a part / document number
    doc_drop = {_norm_model(m) for m in split_list(f.get('models_drop')) if m != '*'}
    if drop_all:
        doc_drop |= {_norm_model(m) for m in json.loads(doc.get('models') or '[]')}
    if f.get('models_add') or doc_drop:
        mods = [m for m in json.loads(doc.get('models') or '[]') if _norm_model(m) not in doc_drop]
        have = {_norm_model(m) for m in mods}
        mods += [m for m in split_list(f.get('models_add')) if _norm_model(m) not in have and not have.add(_norm_model(m))]
        doc['models'] = json.dumps(mods)
    if doc_drop and doc.get('page_models'):   # a part / document number is no model on any page of the doc
        doc['page_models'] = json.dumps(sorted(m for m in json.loads(doc['page_models']) if m not in doc_drop))
    if pages is not None:   # a model printed only on a misprinted page is not a model of this doc
        drops = {sh: {_norm_model(m) for m in split_list(pf.get('page_models_drop'))} for sh, pf in e['pages'].items()}
        if doc_drop:
            drops = {int(p['pdf_sheet']): drops.get(int(p['pdf_sheet']), set()) | doc_drop for p in pages}
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


def page_kept(doc_id, file_path, sheet, path=DOC_FIXES):
    """False for a sheet marked page_exclude (a re-host ad insert, a marketing page)."""
    return not page_fix(doc_id, file_path, sheet, path).get('page_exclude')


def printed_page_map(doc_id, file_path, path=DOC_FIXES):
    """{sheet: printed page} from a doc's printed_pages fix: the printed page numbers of its sheets in order, as a comma
    list with ranges ('1,2,3-12,26-32,40'), for a PDF assembled from pages of a bigger book that keep their own numbers."""
    v = ((fix_for(doc_id, file_path, path) or {}).get('doc') or {}).get('printed_pages')
    if not v:
        return {}
    nums = []
    for part in split_list(v):
        a, _, b = part.partition('-')
        nums += list(range(int(a), int(b) + 1)) if b else [int(a)]
    return {i: n for i, n in enumerate(nums, 1)}


def fix_page_row(row, file_path, path=DOC_FIXES):
    """Clear the wrong page marks of one page row in place (page_marks_off); set the printed page of a sheet from the
    doc's printed_pages fix."""
    topics = page_fix(row['doc_id'], file_path, row['pdf_sheet'], path).get('page_topics')
    if topics:
        row['topics'] = topics.strip()   # '; ' list of labels, kept as written
    pp = printed_page_map(row['doc_id'], file_path, path).get(int(row['pdf_sheet']))
    if pp:
        row['printed_page'], row['printed_how'] = pp, 'printed (doc_fixes printed_pages)'
    for m in split_list(page_fix(row['doc_id'], file_path, row['pdf_sheet'], path).get('page_marks_off')):
        row[m] = 0
    return row


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
