"""Build the page-finder index FROM THE APP LIBRARY (the app DB's documents table is the single source of truth).

    python -m pagefinder.build_index --app-db <rv_techtrack_v4.db> --sources <sources.json> --out pagefinder/index
        [--page-cache <pages.jsonl> --page-cache-manifest <manifest.csv>] [--no-embed]

- One index doc per app document (doc_id 'L<documents.id>'). Title, brand, category (= unit type), models and doc number
  come from the app library fields that the library cleanup curated. Nothing is guessed from a hardcoded brand or
  category list. Doc KIND (troubleshooting / service / tech sheet / owner's ...) is read from the title.
- Page text: the whole PDF sheet (PyMuPDF text layer, tesseract OCR for sheets without text). A page cache from an
  earlier extraction is reused when the PDF sha256 matches. Documents with no PDF fall back to the app's own
  doc_chunks text, merged per page.
- Page tags (contents / cover / safety / parts / fault-code table / troubleshooting / wiring), codes and printed page
  numbers: pagefinder.pagetext (same rules as the fresh-library build).
- Vectors: bge-small-en-v1.5 passages (120 words, step 90), float16, L2-normalised -> passages.npy + passages.json.
sources.json: {"<app doc id>": {"src": "<pdf path>", "sha": "<sha256>"}}.
No network (HF_HUB_OFFLINE=1), no API calls."""
import argparse, collections, csv, hashlib, json, os, re, sqlite3, sys, time
os.environ.setdefault('HF_HUB_OFFLINE', '1')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pagefinder import pagetext as PT
from pagefinder import doc_fixes as DF

SCHEMA = '''
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE docs(doc_id TEXT PRIMARY KEY, app_id INT, title TEXT, brand TEXT, product_line TEXT, models TEXT, title_models TEXT,
  unit_type TEXT, doc_type TEXT, doc_number TEXT, file_path TEXT, sha256 TEXT, n_pages INT, n_ocr_pages INT,
  page_offset INT, offset_conf TEXT, status TEXT, page_models TEXT, alt_titles TEXT, text_source TEXT,
  source_type TEXT DEFAULT 'oem', doc_note TEXT DEFAULT '', duplicate_of TEXT DEFAULT '', also_unit_types TEXT DEFAULT '',
  also_brands TEXT DEFAULT '', any_brand TEXT DEFAULT '', not_for TEXT DEFAULT '');
CREATE TABLE pages(doc_id TEXT, pdf_sheet INT, printed_page INT, printed_how TEXT, text TEXT, method TEXT, content_hash TEXT,
  chars INT, codes TEXT, models TEXT, is_toc INT, is_cover INT, is_safety INT, is_parts INT, is_fault_codes INT, is_troubleshooting INT, is_wiring INT,
  PRIMARY KEY(doc_id, pdf_sheet));
CREATE INDEX pages_doc ON pages(doc_id);
'''


def split_models(s):
    return [x.strip() for x in re.split(r'[;,]', s or '') if x.strip()]


MODEL_TAG_FIXES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_tag_fixes.tsv')


def model_tag_fixes(path=MODEL_TAG_FIXES):
    """{app doc id: {normalised model}}: model tags a doc must NOT carry even though its own page text shows them (a reviewed
    data file, e.g. an OEM cover that prints the sibling product's model). One row per fix, with the evidence. The model is
    dropped from the doc's model tags and from its page-text models (page_models), so neither tier matches it."""
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            if line.strip() and not line.startswith('#'):
                c = line.rstrip('\n').split('\t')
                if len(c) >= 2 and c[0].strip().isdigit(): out.setdefault(int(c[0]), set()).add(PT.norm_model(c[1].strip()))
    return out


def doc_record(app, pgs, text_source):
    """app: dict of the app documents row (+category name). pgs: [{sheet, text, method, hf}] -> (doc row, page rows)."""
    title = (app.get('clean_title') or app.get('title') or '').strip()
    fn = os.path.basename(app.get('file_path') or '')
    fn_words = re.sub(r'^\d+_\d{14}_', '', fn)
    mods = []
    def add(m):
        if PT.norm_model(m) and PT.norm_model(m) not in {PT.norm_model(x) for x in mods}: mods.append(m)
    for m in split_models(app.get('models')): add(m)
    for m in PT.models_from(title, True) + PT.models_from(re.sub(r'[_]+', ' ', fn_words)): add(m)
    title_models = list(mods)
    first = '\n'.join(p['text'] for p in pgs[:2])[:4000]
    for m, _ in collections.Counter(PT.models_from(first[:2500])).most_common(12): add(m)
    drop = model_tag_fixes().get(app.get('id'), set())
    if drop: mods = [m for m in mods if PT.norm_model(m) not in drop]
    pn_map, off, oconf, _ = PT.page_numbers(pgs) if pgs else ({}, 0, 'none', '')
    plist = []
    for p in pgs:
        marks, codes = PT.page_marks(p, len(pgs))
        pp, how = pn_map.get(p['sheet'], (None, 'none'))
        plist.append(dict(pdf_sheet=p['sheet'], printed_page=pp, printed_how=how, text=p['text'], method=p.get('method', 'text'),
                          content_hash=hashlib.sha1(re.sub(r'\s+', ' ', p['text'].lower()).strip().encode()).hexdigest(),
                          chars=len(p['text']), codes=json.dumps(codes),
                          models=json.dumps(sorted({PT.norm_model(m) for m in PT.models_from(p['text'])} - drop)), **marks))
    norm = re.sub(r'\s+', ' ', ' '.join(p['text'] for p in pgs)).strip()
    status = 'active' if len(norm) >= 60 else 'no-text'
    doc = dict(doc_id=f"L{app['id']}", app_id=app['id'], title=title, brand=(app.get('brand') or '').strip(),
               product_line=(app.get('product_line') or '').strip(), models=json.dumps(mods), title_models=json.dumps(title_models),
               unit_type=(app.get('category') or '').strip(), doc_type=PT.infer_doctype(title, fn_words),
               doc_number=(app.get('doc_number') or '').strip(), file_path=app.get('file_path') or '', sha256=app.get('sha') or '',
               n_pages=len(pgs), n_ocr_pages=sum(1 for p in pgs if p.get('method') == 'ocr'), page_offset=off, offset_conf=oconf,
               status=status, page_models=json.dumps(sorted({m for p in plist for m in json.loads(p['models'])})), alt_titles='[]',
               text_source=text_source, source_type=DF.OEM, doc_note='', duplicate_of='', also_unit_types='', also_brands='', any_brand='', not_for='')
    DF.apply(doc, plist)   # reviewed data fixes (pagefinder/doc_fixes.tsv): brand, source type, duplicates, models, page fixes
    return doc, plist


def apply_fixes_in_place(index_db):
    """Re-apply the reviewed fixes (model_tag_fixes.tsv + doc_fixes.tsv) to a built index without re-extracting or
    re-embedding: page text and vectors do not change. Adds the source_type / doc_note / duplicate_of / also_unit_types columns to an older
    index. Returns {doc_id: [changed fields]}."""
    db = sqlite3.connect(index_db); db.row_factory = sqlite3.Row
    have = {r[1] for r in db.execute('pragma table_info(docs)')}
    for col, dflt in (('source_type', "'oem'"), ('doc_note', "''"), ('duplicate_of', "''"), ('also_unit_types', "''"), ('also_brands', "''"), ('any_brand', "''"), ('not_for', "''")):
        if col not in have: db.execute(f'ALTER TABLE docs ADD COLUMN {col} TEXT DEFAULT {dflt}')
    tag_drops = model_tag_fixes()
    docs = {r['doc_id']: dict(r) for r in db.execute('select * from docs')}
    changed = {}
    for k, d in docs.items():
        before = dict(d)
        pages = [dict(r) for r in db.execute('select pdf_sheet, models from pages where doc_id=? order by pdf_sheet', (k,))]
        drop = tag_drops.get(d['app_id'], set())
        if drop:
            d['models'] = json.dumps([m for m in json.loads(d['models'] or '[]') if PT.norm_model(m) not in drop])
            for p in pages: p['models'] = json.dumps([m for m in json.loads(p['models'] or '[]') if m not in drop])
            d['page_models'] = json.dumps(sorted({m for p in pages for m in json.loads(p['models'])}))
        fx = (DF.fix_for(k, d['file_path']) or {}).get('doc', {})
        if (d.get('status') == 'duplicate' and not fx.get('duplicate_of')) or (d.get('status') == 'excluded' and not fx.get('exclude')):
            d['status'] = 'active'; d['duplicate_of'] = ''   # the fix was taken back
        DF.apply(d, pages)
        for p in pages: db.execute('update pages set models=? where doc_id=? and pdf_sheet=?', (p['models'], k, p['pdf_sheet']))
        diff = [c for c in d if c in before and d[c] != before[c]]
        if diff:
            changed[k] = diff
            db.execute(f'update docs set {", ".join(f"{c}=?" for c in diff)} where doc_id=?', [d[c] for c in diff] + [k])
    db.commit(); db.close()
    return changed


def remark_covers_in_place(index_db):
    """Re-mark is_cover on a built index with the current rule (pagetext.is_cover_page) from the stored page text, without
    re-extracting or re-embedding. Only sheet 1 can change. Returns {doc_id: (old, new)} for the changed sheets."""
    db = sqlite3.connect(index_db); db.row_factory = sqlite3.Row
    n_pages = {r['doc_id']: r['n_pages'] for r in db.execute('select doc_id, n_pages from docs')}
    changed = {}
    for r in db.execute('select * from pages where pdf_sheet=1').fetchall():
        new = int(PT.is_cover_page(r['text'] or '', 1, n_pages.get(r['doc_id'], 0), dict(r)))
        if new != (r['is_cover'] or 0):
            changed[r['doc_id']] = (r['is_cover'], new)
            db.execute('update pages set is_cover=? where doc_id=? and pdf_sheet=1', (new, r['doc_id']))
    db.commit(); db.close()
    return changed


def pages_from_chunks(conn, app_id):
    """Fallback page text: the app's own doc_chunks merged per page (overlaps removed)."""
    by = collections.defaultdict(list)
    for page, t in conn.execute('select page, chunk_text from doc_chunks where document_id=? order by page, id', (app_id,)):
        by[page or 1].append(t)
    out = []
    for s in sorted(by):
        text = PT.merge_chunks(by[s]); ls = [l for l in text.splitlines() if l.strip()]
        out.append(dict(sheet=s, text=text, method='app-chunks', hf=PT.hf_candidates(ls[:2], ls[-2:])))
    return out


def app_documents(conn):
    conn.row_factory = sqlite3.Row
    rows = conn.execute('select d.*, c.name as category from documents d left join categories c on c.id=d.category_id order by d.id').fetchall()
    conn.row_factory = None
    return [dict(r) for r in rows]


def passages(text, n=120, step=90):
    ws = text.split()
    return [' '.join(ws[i:i + n]) for i in range(0, max(1, len(ws) - (n - step)), step)] if ws else []


def embed_texts(texts, model_dir, threads=None):
    import numpy as np
    from pagefinder.search import embedding_model
    m = embedding_model(model_dir, threads=threads)
    out = []
    t0 = time.time()
    for i, v in enumerate(m.embed(texts, batch_size=64)):
        out.append(v)
        if i and i % 5000 == 0: print(i, f'{time.time() - t0:.0f}s', flush=True)
    V = np.asarray(out, dtype=np.float32).reshape(-1, 384)
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
    return V.astype(np.float16)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--app-db', required=True); ap.add_argument('--sources'); ap.add_argument('--out', required=True)
    ap.add_argument('--page-cache'); ap.add_argument('--page-cache-manifest'); ap.add_argument('--no-embed', action='store_true')
    ap.add_argument('--model-dir'); ap.add_argument('--workers', type=int, default=6)
    if argv is None: argv = sys.argv[1:]
    if argv[:1] == ['--apply-fixes']:   # python -m pagefinder.build_index --apply-fixes pagefinder/index/index.sqlite
        for k, v in sorted(apply_fixes_in_place(argv[1]).items()): print(k, v)
        return
    if argv[:1] == ['--remark-covers']:   # python -m pagefinder.build_index --remark-covers pagefinder/index/index.sqlite
        ch = remark_covers_in_place(argv[1])
        for k, v in sorted(ch.items()): print(k, 'is_cover', v[0], '->', v[1])
        print(len(ch), 'sheets changed')
        return
    a = ap.parse_args(argv)
    conn = sqlite3.connect(f'file:{a.app_db}?mode=ro', uri=True)
    apps = app_documents(conn)
    src = {int(k): v for k, v in json.load(open(a.sources)).items()} if a.sources else {}
    cache_by_sha = {}
    if a.page_cache and a.page_cache_manifest:
        id2sha = {r['doc_id']: r['sha256'] for r in csv.DictReader(open(a.page_cache_manifest)) if r.get('sha256')}
        tmp = collections.defaultdict(list)
        for l in open(a.page_cache):
            r = json.loads(l)
            if r.get('sheet') and r['doc_id'] in id2sha: tmp[r['doc_id']].append(r)
        for d, pgs in tmp.items():
            cache_by_sha.setdefault(id2sha[d], sorted(pgs, key=lambda r: r['sheet']))
    todo, got = [], {}
    for app in apps:
        s = src.get(app['id']) or {}
        app['sha'] = s.get('sha') or app.get('content_sha256') or ''
        if app['sha'] in cache_by_sha: got[app['id']] = (cache_by_sha[app['sha']], 'pdf (cached extraction)')
        elif s.get('src') and os.path.exists(s['src']): todo.append((app['id'], s['src']))
    print(f'{len(apps)} app docs: {len(got)} from page cache, {len(todo)} to extract', flush=True)
    if todo:
        from multiprocessing import Pool
        with Pool(a.workers) as pool:
            for app_id, pgs in pool.imap_unordered(_extract, todo):
                if pgs: got[app_id] = (pgs, 'pdf')
    os.makedirs(a.out, exist_ok=True)
    out_db = os.path.join(a.out, 'index.sqlite')
    if os.path.exists(out_db): os.remove(out_db)
    db = sqlite3.connect(out_db); db.executescript(SCHEMA)
    counts = collections.Counter()
    for app in apps:
        pgs, how = got.get(app['id']) or (pages_from_chunks(conn, app['id']), 'app doc_chunks (no PDF)')
        pgs = [p for p in pgs if p.get('sheet')]
        doc, plist = doc_record(app, pgs, how)
        counts[how] += 1; counts[doc['status']] += 1
        cols = list(doc)
        db.execute(f'INSERT INTO docs({",".join(cols)}) VALUES({",".join("?" * len(cols))})', [doc[c] for c in cols])
        for p in plist:
            db.execute('INSERT INTO pages VALUES(:doc_id,:pdf_sheet,:printed_page,:printed_how,:text,:method,:content_hash,:chars,:codes,:models,'
                       ':is_toc,:is_cover,:is_safety,:is_parts,:is_fault_codes,:is_troubleshooting,:is_wiring)', dict(doc_id=doc['doc_id'], **p))
    fp = hashlib.sha256(''.join(f"{a_['id']}:{a_['sha']}" for a_ in apps).encode()).hexdigest()
    db.executemany('INSERT INTO meta VALUES(?,?)', [('built_from', os.path.abspath(a.app_db)), ('built_at', time.strftime('%Y-%m-%d %H:%M:%S %Z')),
                                                   ('library_fingerprint', fp), ('n_docs', str(len(apps)))])
    db.commit()
    print(dict(counts), 'pages', db.execute('select count(*) from pages').fetchone()[0], flush=True)
    if not a.no_embed:
        import numpy as np
        rows = db.execute("select p.doc_id, p.pdf_sheet, p.text from pages p join docs d using(doc_id) where d.status='active' order by 1,2").fetchall()
        keys, texts = [], []
        for d, s, t in rows:
            for ps in passages(t): keys.append([d, s]); texts.append(ps)
        print(len(rows), 'pages ->', len(texts), 'passages', flush=True)
        V = embed_texts(texts, a.model_dir)
        np.save(os.path.join(a.out, 'passages.npy'), V); json.dump(keys, open(os.path.join(a.out, 'passages.json'), 'w'))
        print('vectors', V.shape, flush=True)


def _extract(item):
    app_id, path = item
    try:
        pgs = PT.do_pdf_path(f'L{app_id}', path)
        return app_id, [p for p in pgs if p.get('sheet')]
    except Exception as e:
        print('extract failed', app_id, repr(e), flush=True)
        return app_id, []


if __name__ == '__main__':
    main()
