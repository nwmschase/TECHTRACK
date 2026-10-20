"""TechTrack page-finder (offline: no API calls; the only model is a small local embedding model on CPU).

Split design: the page-finder never reasons. It finds pages; the brain (an LLM, later) reads them and names the
next part to check, then asks fetch_by_part() for that part's pages.

    from search import search, fetch_by_part
    r = search(unit='water heater', brand='Suburban', model='SW6DE', complaint='gas clicks but never lights')
    r['entry']   -> the entry page(s): fault-code table for a code, troubleshooting / sequence chart for a symptom
    r['pages']   -> entry pages + the best other pages of the picked manual(s) (3-5 whole pages)
    f = fetch_by_part('on/off switch', r)   -> that part's test / replacement / component pages

1. Pick the manual: unit type -> brand -> model. A model matches a doc's model tags, or (next tier) a model printed
   in the manual's own page text (model lists, rating plates). Ties go to the doc that best matches the complaint.
   An RV maker's brand (e.g. Brinkley) also pins that maker's owner's manual.
2. Entry page: a code -> the fault-code table page(s) listing it (page flag is_fault_codes); a symptom -> the best
   pages flagged is_troubleshooting in the picked manual(s), ranked by meaning + words.
3. Ranking everywhere is hybrid: 0.5 x BM25 on whole words (normalised) + 0.5 x meaning similarity (bge-small
   passage vectors, best passage per page, normalised). No synonym lists, no boost words, no per-case rules.
4. fetch_by_part(part): searches the picked manual(s) first, then the same brand's other docs, then other makers'
   tech sheets / service manuals for the same unit type (later tiers weighted 0.85 / 0.7).
CLI: python3 search.py --unit "water heater" --brand Suburban --model SW6DE "gas clicks never lights" [--part "on/off switch"]
"""
import hashlib, sqlite3, re, math, json, os, sys, collections, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
# Index built from the app library by pagefinder/build_index.py (index.sqlite + passages.npy/json).
INDEX_DIR = os.environ.get('TT_PAGEFINDER_DIR', os.path.join(HERE, 'index'))
DB = os.path.join(INDEX_DIR, 'index.sqlite')
VEC = INDEX_DIR
# Embedding model (BAAI/bge-small-en-v1.5, quantized ONNX, ~65 MB). Not in the repo: read from this cache dir, and fetched
# once from Hugging Face into it when missing (hosted app). Offline tests point TT_MODEL_DIR at a pre-filled cache.
MODEL_NAME = 'BAAI/bge-small-en-v1.5'
MODEL_DIR = os.environ.get('TT_MODEL_DIR', os.path.join(os.path.expanduser('~'), '.cache', 'techtrack-models'))
APP_DB = os.environ.get('TT_APP_DB', '')   # the app library DB: its documents table overrides index metadata (single source of truth)


def _model_cached(cache_dir):
    root = os.path.join(cache_dir, 'models--Qdrant--bge-small-en-v1.5-onnx-Q', 'snapshots')
    return os.path.isdir(root) and any(os.path.exists(os.path.join(root, s, 'model_optimized.onnx')) for s in os.listdir(root))


def embedding_model(cache_dir=None, threads=None):
    """fastembed model; offline when the cache already holds it, else one download into the cache."""
    cache_dir = cache_dir or MODEL_DIR
    os.makedirs(cache_dir, exist_ok=True)
    if _model_cached(cache_dir):
        os.environ['HF_HUB_OFFLINE'] = '1'
    elif os.environ.get('TT_OFFLINE') == '1':
        raise RuntimeError(f'embedding model not in {cache_dir} and TT_OFFLINE=1')
    from fastembed import TextEmbedding
    return TextEmbedding(MODEL_NAME, cache_dir=cache_dir, threads=threads)

STOP = set('''a about above after again against all am an and any are aren't as at be because been before being below between both but by
can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have
haven't having he her here hers herself him himself his how i if in into is isn't it it's its itself just let's me more most mustn't my
myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she should shouldn't so some such than
that that's the their theirs them themselves then there there's these they this those through to too under until up very was wasn't we
were weren't what when where which while who whom why will with won't would wouldn't you your yours yourself yourselves also get gets
got getting one ones s t d ll m re ve y won wont dont doesnt didnt isnt cant'''.split())
TOKEN = re.compile(r"[a-z0-9]+")
def stem(w):
    if len(w) > 3 and w.endswith('ies'): return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')): return w[:-1]
    return w
def tokens(text): return [stem(w) for w in TOKEN.findall(text.lower()) if w not in STOP]
def nmodel(s): return re.sub(r'[^A-Z0-9]', '', s.upper())
def ncode(c):
    if not c: return ''
    m = re.search(r'(\d{1,2})\s*(?:flash|blink)|(?:flash|blink)\w*\s*(\d{1,2})', c, re.I)
    return f'FLASH{m.group(1) or m.group(2)}' if m else re.sub(r'[^A-Z0-9]', '', c.upper())
def codes_of(c): return [ncode(x) for x in re.split(r'\s*[/,;]\s*|\s+or\s+', c or '') if x.strip()]

class Library:
    def __init__(self, db=None, vec_dir=None, app_db=None):
        db = db or DB
        self.db_path = db
        self.vec_dir = vec_dir or os.path.dirname(db)
        self.db = sqlite3.connect(f'file:{db}?mode=ro', uri=True, check_same_thread=False); self.db.row_factory = sqlite3.Row
        self.docs = {r['doc_id']: dict(r) for r in self.db.execute("select * from docs where status='active' and n_pages>0")}
        self._pages = {}; self._doc_tf = None; self._vec = None; self._model = None; self._extra_vec = {}
        self.sync_note = ''
        app_db = APP_DB if app_db is None else app_db
        self.app_db, self.app_sig = app_db, ''
        if app_db and os.path.exists(app_db):
            self.app_sig = app_signature(app_db)
            self.sync_with_app(app_db)
        self._prepare()

    def _prepare(self):
        for d in self.docs.values():
            d['brand'] = d.get('brand') or ''
            d['unit_type'] = d.get('unit_type') or ''
            d['models_n'] = [nmodel(m) for m in json.loads(d['models'] or '[]') if len(nmodel(m)) >= 3]
            d['page_models_n'] = set(json.loads(d.get('page_models') or '[]'))
        # vocabularies come from the library data itself (no hardcoded brand or category list)
        self.unit_types = sorted({d['unit_type'] for d in self.docs.values() if d['unit_type']})
        names = {}
        for d in self.docs.values():
            if d['brand']:
                names.setdefault(_phrase(d['brand']), d['brand'])
        lines = collections.defaultdict(set)   # a product line names its maker (e.g. 'Ground Control' -> Lippert), from the data
        for d in self.docs.values():
            pl = _phrase(d.get('product_line') or '')
            if d['brand'] and pl and len(pl) >= 4: lines[pl].add(d['brand'])
        # a product line that is just a unit-type word ('Leveling', 'Slide Out') names no maker, even if one maker uses it
        unit_words = {_phrase(u).replace(' ', '').rstrip('s') for u in self.unit_types}
        for pl, bs in lines.items():
            if len(bs) == 1 and pl not in names and pl.replace(' ', '').rstrip('s') not in unit_words:   # only lines that name one maker
                names[pl] = next(iter(bs))
        self.brand_names = sorted(names.items(), key=lambda kv: (-len(kv[0]), kv[0]))

    def sync_with_app(self, app_db):
        """The app library is the truth: app metadata (title, brand, category, models, doc number) replaces the index's;
        docs deleted in the app leave the finder; docs added since the index build are read from the app's doc_chunks
        (whole pages) and embedded on first use."""
        sys.path.insert(0, os.path.dirname(HERE))
        from pagefinder import build_index as B
        c = sqlite3.connect(f'file:{app_db}?mode=ro', uri=True)
        try:
            apps = {f"L{a['id']}": a for a in B.app_documents(c)}
            gone = [k for k in self.docs if k not in apps]
            for k in gone: self.docs.pop(k)
            added = []
            for k, a in apps.items():
                d = self.docs.get(k)
                if d is None:
                    pgs = B.pages_from_chunks(c, a['id'])
                    if not pgs: continue
                    a['sha'] = a.get('content_sha256') or ''
                    doc, plist = B.doc_record(a, pgs, 'app doc_chunks (added after index build)')
                    if doc['status'] != 'active': continue
                    self.docs[k] = doc
                    self._pages[k] = [self._page_row(dict(p, doc_id=k)) for p in plist]
                    added.append(k)
                    continue
                d['title'] = (a.get('clean_title') or a.get('title') or d['title']).strip()
                d['brand'] = (a.get('brand') or '').strip()
                d['product_line'] = (a.get('product_line') or '').strip()
                d['unit_type'] = (a.get('category') or '').strip()
                d['doc_number'] = (a.get('doc_number') or '').strip()
                have = {nmodel(m) for m in json.loads(d['models'] or '[]')}
                extra = [m for m in B.split_models(a.get('models')) if nmodel(m) not in have]
                if extra: d['models'] = json.dumps(json.loads(d['models'] or '[]') + extra)
            self.added_docs = added
            self.sync_note = f'app sync: {len(gone)} removed, {len(added)} added from app chunks'
        finally:
            c.close()

    @staticmethod
    def _page_row(r):
        r = dict(r)
        r['tf'] = collections.Counter(tokens(r['text'])); r['len'] = sum(r['tf'].values())
        r['codes'] = json.loads(r['codes']) if isinstance(r['codes'], str) else r['codes']
        return r
    def vectors(self):
        """passage vectors (float32) and {(doc_id, sheet): [row, ...]}"""
        if self._vec is None:
            import numpy as np
            V = np.load(os.path.join(self.vec_dir, 'passages.npy'))   # float16 kept as is (half the RAM); scored in float32 per query
            rows = collections.defaultdict(list)
            for i, (d, s) in enumerate(json.load(open(os.path.join(self.vec_dir, 'passages.json')))): rows[(d, s)].append(i)
            added = [k for k in getattr(self, 'added_docs', []) if k in self.docs]
            if added:   # docs added in the app after the index build: embed their pages once
                from pagefinder.build_index import passages
                keys, texts = [], []
                for k in added:
                    for p in self.pages(k):
                        for ps in passages(p['text']): keys.append((k, p['pdf_sheet'])); texts.append(ps)
                if texts:
                    E = np.asarray(list(self._embedder().embed(texts, batch_size=32)), dtype=np.float32)
                    E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9
                    base = len(V); V = np.concatenate([V, E.astype(V.dtype)])
                    for j, k in enumerate(keys): rows[k].append(base + j)
            self._vec = (V, rows)
        return self._vec
    def embed_query(self, text):
        import numpy as np
        v = np.asarray(next(iter(self._embedder().query_embed([text]))), dtype='float32')
        return v / (np.linalg.norm(v) + 1e-9)
    def _embedder(self):
        if self._model is None:
            self._model = embedding_model()
        return self._model
    def pages(self, doc_id):
        if doc_id not in self._pages:
            self._pages[doc_id] = [self._page_row(dict(r)) for r in self.db.execute('select * from pages where doc_id=? order by pdf_sheet', (doc_id,))]
        return self._pages[doc_id]
    def doc_tf(self):
        if self._doc_tf is None:
            self._doc_tf = {}
            for doc_id in self.docs:
                tf = collections.Counter()
                for p in self.pages(doc_id): tf.update(p['tf'])
                self._doc_tf[doc_id] = (tf, sum(tf.values()))
        return self._doc_tf

def bm25(query, items, k1=1.2, b=0.75):
    """items: list of (key, Counter tf, length). Returns {key: score}. IDF from the items themselves."""
    N = len(items) or 1; avg = sum(l for _, _, l in items) / N or 1
    df = collections.Counter()
    for _, tf, _ in items:
        for q in set(query):
            if tf.get(q): df[q] += 1
    out = {}
    for key, tf, l in items:
        s = 0.0
        for q in set(query):
            f = tf.get(q, 0)
            if not f: continue
            idf = math.log(1 + (N - df[q] + 0.5) / (df[q] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * l / avg))
        out[key] = s
    return out

def meaning(lib, query, keys):
    """{(doc_id, sheet): best passage cosine} for the given pages"""
    import numpy as np
    V, rows = lib.vectors(); q = lib.embed_query(query)
    idx = [(k, rows.get(k, [])) for k in keys]
    flat = [i for _, r in idx for i in r]
    sims = dict(zip(flat, (V[flat].astype('float32') @ q).tolist())) if flat else {}
    return {k: max((sims[i] for i in r), default=0.0) for k, r in idx}

def hybrid(lib, query_text, pages, extra_tokens=()):
    """0.5 x normalised BM25 (whole words) + 0.5 x normalised meaning similarity. Returns {key: score in [0, 1]}."""
    key = lambda p: (p['doc_id'], p['pdf_sheet'])
    if not pages: return {}
    bm = bm25(tokens(query_text) + list(extra_tokens), [(key(p), p['tf'], p['len']) for p in pages])
    em = meaning(lib, query_text, [key(p) for p in pages])
    bmax = max(bm.values()) or 1.0
    lo, hi = min(em.values()), max(em.values())
    return {k: 0.5 * bm[k] / bmax + 0.5 * ((em[k] - lo) / (hi - lo) if hi > lo else 0.0) for k in bm}

def _phrase(text):
    """'Coleman-Mach' / 'coleman mach' -> 'coleman mach' (lowercase words joined by one space)."""
    return ' '.join(re.findall(r'[a-z0-9]+', (text or '').lower()))
def unit_type_of(text, lib=None):
    """The library category the tech picked (the app's own category list = the index unit types). Data-driven."""
    if not text: return ''
    lib = lib or _lib()
    t = _phrase(text)
    for u in lib.unit_types:
        if _phrase(u) == t or _phrase(u).rstrip('s') == t.rstrip('s'): return u
    return ''
def brand_of(text, lib=None):
    """A maker named in the tech's text: any brand (or product line) that the library's own docs carry. Data-driven.
    Whole words only: 'Coleman Mach' matches 'coleman mach' or 'colemanmach', never part of a longer word."""
    lib = lib or _lib()
    words = _phrase(text).split()
    t = ' ' + ' '.join(words) + ' '
    for name, brand in lib.brand_names:
        if f' {name} ' in t or (' ' in name and name.replace(' ', '') in words): return brand
    return ''

REFERENCE_KIND = r'reference|general|\bforms?\b|bulletin|recall|\btsb\b'   # categories named by document kind, not product
MW = re.compile(r'[a-z0-9]+(?:\.[0-9]+)?')
def mwords(text): return {w.replace('.', '') for w in MW.findall((text or '').lower()) if w not in STOP and len(w.replace('.', '')) >= 2}
def model_score(doc, qtokens, qwords):
    """(tag, title): tag = exact model tag 1000+len, else longest shared prefix (FCR10DCGTA-BG-PWH vs FCR10DCGTA = 10,
    vs FCR10 = 5), else 500+len when the model is printed in the manual's page text (e.g. L124 p.21 names SW6DE); title = how many of the tech's model words appear in the doc title (or a merged duplicate's title)."""
    tag = 0
    for q in qtokens:
        s = 0
        for m in doc['models_n']:
            if q == m: s = max(s, 1000 + len(m))
            elif min(len(q), len(m)) >= 4 and (q.startswith(m) or m.startswith(q)): s = max(s, min(len(q), len(m)))
        if not s and q in doc['page_models_n']: s = 500 + len(q)   # named in the manual's own page text
        tag += s
    tw = mwords(doc['title'] + ' ' + ' '.join(json.loads(doc.get('alt_titles') or '[]')))
    return tag, len(qwords & tw)

def pick_manual(lib, unit=None, brand=None, model=None, complaint='', code=None, max_docs=3):
    ms = {}
    why = []
    cand = list(lib.docs.values())
    ut = unit_type_of(unit or '', lib)
    if ut:
        c2 = [d for d in cand if d['unit_type'] == ut]
        if c2: cand = c2; why.append(f'unit type {ut}: {len(c2)} docs')
    b = brand or brand_of(model or '', lib)   # the maker comes from what the tech typed, never from the category name
    coach = []
    if b:
        c2 = [d for d in cand if d['brand'].lower() == b.lower()]
        if c2: cand = c2; why.append(f'brand {b}: {len(c2)} docs')
        else:
            # R4 brand lock: never another maker's manual for this unit. The one exception is a whole-unit maker (an RV
            # builder): its owner's manuals are filed under a reference-kind category and cover every system of the unit.
            coach = [d for d in lib.docs.values() if d['brand'].lower() == b.lower() and d['doc_type'] == 'owners-manual'
                     and re.search(REFERENCE_KIND, d['unit_type'] or '', re.I)]
            if not coach:
                why.append(f'brand {b}: no {ut or ""} manuals of this maker in the library (brand lock): none picked')
                return [], why, ''
            cand = list(coach)
            why.append(f'brand {b}: no {ut or ""} docs; its whole-unit owner\'s manuals {[d["doc_id"] for d in coach]}')
    brand_pool = list(cand)
    q_models = []
    for t in re.findall(r'[A-Za-z0-9][A-Za-z0-9\-/\.]*', f'{model or ""} {unit or ""}'):
        n = nmodel(t)
        if len(n) >= 3 and re.search(r'\d', n): q_models.append(n)
    q_models = list(dict.fromkeys(q_models))
    qwords = mwords(model)
    family = []
    ms = {d['doc_id']: model_score(d, q_models, qwords) for d in cand}
    top = max([v[0] for v in ms.values()] or [0]); ttop = max([v[1] for v in ms.values()] or [0])
    if top > 0:
        cand = [d for d in cand if ms[d['doc_id']][0] == top]; why.append(f'model tags {q_models}: {len(cand)} docs at match score {top}')
    elif ttop > 0:
        floor = ttop
        family = [d for d in cand if ms[d['doc_id']][1] >= ttop - 1] if ttop >= 2 else []
        cand = [d for d in cand if ms[d['doc_id']][1] == ttop]; why.append(f'model words {sorted(qwords)} in title (best {ttop}, kept >= {floor}): {len(cand)} docs')
    else: why.append(f'model {q_models or "-"}: no model match, ranked by complaint text')
    top_tag = top
    q = tokens(complaint or '')
    dtf = lib.doc_tf()
    has_code = lambda d, c: any(c in p['codes'] for p in lib.pages(d['doc_id']))
    cc = ''
    if code:  # "E2 / 2 flashes": use the first form the brand's manuals actually index
        alts = codes_of(code)
        cc = next((c for c in alts if any(has_code(d, c) for d in cand)), '') or next((c for c in alts if any(has_code(d, c) for d in brand_pool)), alts[0] if alts else '')
        q = q + [cc.lower()]
    ds = bm25(q, [(d['doc_id'], dtf[d['doc_id']][0], dtf[d['doc_id']][1]) for d in cand], b=0.3)  # mild length norm: a whole manual should not lose to a 1-page sheet
    code_extra = []
    if cc:
        has = [d for d in cand if has_code(d, cc)]
        if has and len(has) < len(cand): cand = has; why.append(f'code {cc} appears in {len(has)} of them')
        if not has:  # the code is explained in another doc of this brand + unit (e.g. the thermostat manual for an A/C code)
            wider = [d for d in brand_pool if d not in cand and has_code(d, cc)]
            if wider:
                wtf = bm25(q, [(d['doc_id'], dtf[d['doc_id']][0], dtf[d['doc_id']][1]) for d in wider], b=0.3)
                code_extra = sorted(wider, key=lambda d: -wtf.get(d['doc_id'], 0))[:2]
                why.append(f'code {cc} not in the model manual; added {[d["doc_id"] for d in code_extra]} (same brand + unit docs that list it)')
    cand.sort(key=lambda d: (-ds.get(d['doc_id'], 0), d['doc_id']))
    pinned = cand[:max_docs]
    if pinned and ds.get(pinned[0]['doc_id'], 0) > 0:  # drop docs far behind the best complaint match
        best = ds[pinned[0]['doc_id']]
        pinned = [d for d in pinned if ds.get(d['doc_id'], 0) >= 0.5 * best]
    if code_extra: pinned = pinned[:max(1, max_docs - 1 - len(code_extra))] + code_extra
    # diagnosis needs a troubleshooting / service manual: if the model-matched docs are only owner, install, spec
    # or form docs, add the best such manual of the same brand + unit (by complaint text)
    DIAG = ('troubleshooting', 'service-manual')
    if pinned and not any(d['doc_type'] in DIAG for d in pinned):
        pool2 = [d for d in brand_pool if d['doc_type'] in DIAG and d not in pinned]
        near = [d for d in pool2 if ms.get(d['doc_id'], (0, 0)) != (0, 0)] or pool2
        if near:
            ns = bm25(q, [(d['doc_id'], dtf[d['doc_id']][0], dtf[d['doc_id']][1]) for d in near], b=0.3)
            best = max(near, key=lambda d: (ns.get(d['doc_id'], 0), d['doc_id']))
            if ns.get(best['doc_id'], 0) > 0:
                pinned = pinned[:max_docs] + [best]
                why.append(f'model docs are {sorted({d["doc_type"] for d in pinned[:-1]})} only; added {best["doc_type"]} {best["doc_id"]}')
    # best title match is only a 1-2 page sheet: also search the product family (titles missing one model word)
    if ttop and not top_tag and sum(d['n_pages'] for d in pinned) < 3 and family:
        more = [d for d in family if d not in pinned]
        fs = bm25(q, [(d['doc_id'], dtf[d['doc_id']][0], dtf[d['doc_id']][1]) for d in more], b=0.3)
        add = sorted(more, key=lambda d: -fs.get(d['doc_id'], 0))[:max_docs - len(pinned)]
        if add: pinned += add; why.append(f'best match has < 3 pages; added family docs {[d["doc_id"] for d in add]}')
    if coach:
        cs = bm25(q, [(d['doc_id'], dtf[d['doc_id']][0], dtf[d['doc_id']][1]) for d in coach], b=0.3)
        msc = {d['doc_id']: model_score(d, q_models, qwords) for d in coach}
        best = max(coach, key=lambda d: (msc[d['doc_id']], cs.get(d['doc_id'], 0), d['doc_id']))
        if best not in pinned: pinned = [best] + pinned; why.append(f'{b} owner\'s manual covers the unit: added {best["doc_id"]}')
    return pinned, why, cc

DOWN = ('is_toc', 'is_cover', 'is_safety', 'is_parts')
def code_pattern(cc):
    if cc.startswith('FLASH'): return re.compile(r'(?<![\d.])' + cc[5:] + r'\s*(?:flash|blink)\w*', re.I)
    return re.compile(r'(?<![A-Za-z0-9])' + r'\s?-?\s?'.join(re.findall(r'[A-Z]+|\d+', cc)) + r'(?![0-9])', re.I)

def _marks(p): return [m[3:] for m in ('is_toc', 'is_cover', 'is_safety', 'is_parts', 'is_fault_codes', 'is_troubleshooting', 'is_wiring') if p[m]]
def _out(lib, p, score, reason):
    d = lib.docs[p['doc_id']]
    return dict(doc_id=p['doc_id'], title=d['title'], pdf_sheet=p['pdf_sheet'], printed_page=p['printed_page'], marks=_marks(p),
                score=round(score, 3), reason=reason, codes=sorted(p['codes']), chars=len(p['text']), text=p['text'])

def search(unit=None, brand=None, model=None, complaint='', code=None, k_min=3, k_max=5, n_entry=2, lib=None):
    """Pick the manual(s), the entry page(s) and the best supporting pages. No reasoning: the brain reads them."""
    lib = lib or _lib()
    pinned, why, cc = pick_manual(lib, unit, brand, model, complaint, code)
    if not pinned: return dict(manuals=[], entry=[], pages=[], why=why + ['no manual found'], chars=0, code=cc)
    pages = [p for d in pinned for p in lib.pages(d['doc_id']) if p['len']]
    key = lambda p: (p['doc_id'], p['pdf_sheet'])
    query = (complaint or '') + (f' {cc}' if cc else '')
    entry, reasons = [], {}
    if cc:   # fault code: the code-table page(s) listing it
        withc = [p for p in pages if cc in p['codes']]
        fc = sorted([p for p in withc if p['is_fault_codes']], key=lambda p: -len(p['codes']))
        for p in (fc or withc)[:n_entry]: entry.append(p); reasons[key(p)] = f'fault-code page listing {cc}'
        if not withc: why.append(f'code {cc} not found in the pinned manual(s); entry by symptom')
    if not entry:   # symptom: troubleshooting / sequence-chart pages, ranked by meaning + words
        ts = [p for p in pages if p['is_troubleshooting']] or pages
        hs = hybrid(lib, query, ts)
        for p in sorted(ts, key=lambda p: -hs[key(p)])[:n_entry]:
            entry.append(p); reasons[key(p)] = f'entry: troubleshooting page (hybrid {hs[key(p)]:.2f})' if p['is_troubleshooting'] else f'entry: no troubleshooting pages flagged; best page (hybrid {hs[key(p)]:.2f})'
    # supporting pages: hybrid rank over all pinned pages; contents/cover/safety/parts pages count less
    hs = hybrid(lib, query, pages)
    sc = {key(p): hs[key(p)] * (0.3 if any(p[m] for m in DOWN) and not (p['is_troubleshooting'] or p['is_fault_codes']) else 1.0) for p in pages}
    chosen = list(entry)
    ranked = sorted(pages, key=lambda p: -sc[key(p)])
    top = sc[key(ranked[0])] if ranked else 0
    for p in ranked:
        if len(chosen) >= k_max: break
        if p in chosen: continue
        if len(chosen) >= k_min and sc[key(p)] < 0.6 * top: break
        chosen.append(p); reasons[key(p)] = f'hybrid {sc[key(p)]:.2f}'
    out = [_out(lib, p, sc.get(key(p), 0), reasons[key(p)]) for p in chosen]
    return dict(manuals=[dict(doc_id=d['doc_id'], title=d['title'], brand=d['brand'], unit_type=d['unit_type'], doc_type=d['doc_type']) for d in pinned],
                entry=out[:len(entry)], pages=out, why=why, chars=sum(p['chars'] for p in out), code=cc)

DIAG_TYPES = ('tech-sheet', 'service-manual', 'troubleshooting', 'install-manual', 'recall-bulletin')
def fetch_by_part(part, result=None, brand=None, unit=None, k=3, lib=None):
    """Pages that test / replace / describe one part, for the brain's next step.
    Tier 1: the manual(s) search() picked. Tier 2: the same brand's other docs in that category.
    Tier 3: other makers' tech sheets / service / troubleshooting / install docs for the same unit type.
    One hybrid score over all candidate pages, x1.0 / x0.85 / x0.7 by tier; contents and cover pages x0.3."""
    lib = lib or _lib()
    pinned = [m['doc_id'] for m in (result or {}).get('manuals', [])]
    units = {m['unit_type'] for m in (result or {}).get('manuals', []) if m['unit_type']} or ({unit_type_of(unit, lib)} if unit else set())
    brands = {m['brand'].lower() for m in (result or {}).get('manuals', [])} | ({brand.lower()} if brand else set())
    tier = {d: 1.0 for d in pinned}
    for d in lib.docs.values():
        if d['doc_id'] in tier: continue
        if d['brand'].lower() in brands and d['unit_type'] in units: tier[d['doc_id']] = 0.85
        elif d['unit_type'] in units and d['doc_type'] in DIAG_TYPES: tier[d['doc_id']] = 0.7
    pages = [p for d in tier for p in lib.pages(d) if p['len']]
    hs = hybrid(lib, part, pages)
    key = lambda p: (p['doc_id'], p['pdf_sheet'])
    sc = {key(p): hs[key(p)] * tier[p['doc_id']] * (0.3 if p['is_toc'] or p['is_cover'] else 1.0) for p in pages}
    best = sorted(pages, key=lambda p: -sc[key(p)])[:k]
    names = {1.0: 'picked manual', 0.85: 'same brand', 0.7: 'other maker, same unit type'}
    return [_out(lib, p, sc[key(p)], f'{names[tier[p["doc_id"]]]} (hybrid {hs[key(p)]:.2f})') for p in best]

def app_signature(app_db):
    """Cheap fingerprint of the app library (document metadata + page-chunk count). It changes on every upload, edit,
    delete, bulk import or DB restore, so the finder re-reads the app library instead of serving stale titles/docs."""
    try:
        c = sqlite3.connect(f'file:{app_db}?mode=ro', uri=True)
        try:
            h = hashlib.sha1()
            for r in c.execute("select id, coalesce(clean_title,''), coalesce(title,''), coalesce(brand,''), coalesce(product_line,''),"
                               " coalesce(category_id,0), coalesce(models,''), coalesce(doc_number,'') from documents order by id"):
                h.update(repr(r).encode())
            h.update(repr(c.execute('select count(*), coalesce(max(id),0) from doc_chunks').fetchone()).encode())
            return h.hexdigest()
        finally:
            c.close()
    except sqlite3.Error:
        return ''


_L = None
def _lib():
    global _L
    if _L is None:
        _L = Library()
    elif _L.app_db and os.path.exists(_L.app_db) and app_signature(_L.app_db) != _L.app_sig:
        _L = Library(_L.db_path, _L.vec_dir, _L.app_db)   # the app library changed: re-read it
    return _L

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('complaint', nargs='*'); ap.add_argument('--unit'); ap.add_argument('--brand')
    ap.add_argument('--model'); ap.add_argument('--code'); ap.add_argument('--part'); ap.add_argument('--full', action='store_true')
    a = ap.parse_args()
    r = search(a.unit, a.brand, a.model, ' '.join(a.complaint), a.code)
    print('why:', '; '.join(r['why']))
    for m in r['manuals']: print('manual:', m['doc_id'], m['title'])
    show = [('page', p) for p in r['pages']] + ([('part', p) for p in fetch_by_part(a.part, r)] if a.part else [])
    for kind, p in show:
        print(f"-- [{kind}] {p['doc_id']} sheet {p['pdf_sheet']} (printed p.{p['printed_page']}) {p['marks']} {p['reason']} {p['chars']} chars")
        print(p['text'] if a.full else p['text'][:300].replace('\n', ' '))
    print('total chars', r['chars'])
