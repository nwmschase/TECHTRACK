"""TechTrack page-finder (offline: no API calls, no model: whole-word BM25 search).

The page-finder never reasons: Grok searches and reads the library with gd_tools, which calls this module's Library,
hybrid() ranking, model_score() and kind_weights(). v4.20.9: the old picker (search / pick_manual / fetch_by_part and
the CLI) is deleted; the numbered notes below describe the ranking rules those tools still share.

1. Pick the manual: unit type -> brand -> model. A model matches a doc's model tags, or (next tier) a model printed
   in the manual's own page text (model lists, rating plates). Ties go to the doc that best matches the complaint.
   An RV maker's brand (e.g. Brinkley) also pins that maker's owner's manual.
2. Entry page: a code -> the fault-code table page(s) listing it (page flag is_fault_codes); a symptom -> the best
   pages flagged is_troubleshooting in the picked manual(s), ranked by words.
3. Ranking everywhere is BM25 on whole words (normalised to 0..1; v4.20.13: the meaning/embedding half is deleted, there is no
   model and no passage vectors). Words are normalised the same way in pages and queries
   (cooling = cool, touchscreen = touch screen, temp = temperature) and the query gains the RV shop term families at half
   weight (freeze sensor | evaporator sensor | coil sensor; not cold | not cooling | too warm), from the data files in
   pagefinder/terms/ (terms.py). No boost words, no per-case rules.
4. fetch_by_part(part): searches the picked manual(s) first, then the same brand's other docs, then other makers'
   tech sheets / service manuals for the same unit type (later tiers weighted 0.85 / 0.7).
"""
import hashlib, sqlite3, re, math, json, os, sys, collections, threading
HERE = os.path.dirname(os.path.abspath(__file__))
# Index built from the app library by pagefinder/build_index.py (index.sqlite).
INDEX_DIR = os.environ.get('TT_PAGEFINDER_DIR', os.path.join(HERE, 'index'))
DB = os.path.join(INDEX_DIR, 'index.sqlite')
APP_DB = os.environ.get('TT_APP_DB', '')   # the app library DB: its documents table overrides index metadata (single source of truth)


# Process-wide lock: the hosted app runs every session in its own thread and re-executes its script on every click.
_LOCK = threading.RLock()

# Words: the same normalisation for pages and queries (plural, word forms, compounds, shop abbreviations), plus RV shop
# term families on the query side. All of it lives in reviewable data files under pagefinder/terms/ (see terms.py).
try:
    from pagefinder import terms as _terms
    from pagefinder import doc_fixes as _fixes
except ImportError:   # run as a script from inside pagefinder/
    import terms as _terms
    import doc_fixes as _fixes
STOP, TOKEN, stem = _terms.STOP, _terms.TOKEN, _terms.stem
def tokens(text): return _terms.vocab().tokens(text)
def query_terms(text, extra=()):
    """{token: weight} for BM25: the tech's own words 1.0, RV term-family words terms.FAMILY_WEIGHT"""
    return _terms.vocab().query_terms(text, extra)
def nmodel(s): return re.sub(r'[^A-Z0-9]', '', s.upper())


class Library:
    def __init__(self, db=None, app_db=None):
        db = db or DB
        self.db_path = db
        self.db = sqlite3.connect(f'file:{db}?mode=ro', uri=True, check_same_thread=False); self.db.row_factory = sqlite3.Row
        self.docs = {r['doc_id']: dict(r) for r in self.db.execute("select * from docs where status='active' and n_pages>0")}
        self._pages = {}; self._doc_tf = None
        self.sync_note = ''
        app_db = APP_DB if app_db is None else app_db
        self.app_db, self.app_sig = app_db, ''
        if app_db and os.path.exists(app_db):
            self.app_sig = app_signature(app_db)
            self.sync_with_app(app_db)
        self.apply_doc_fixes()
        self._prepare()

    def apply_doc_fixes(self):
        """Reviewed data fixes (pagefinder/doc_fixes.tsv) win over the app DB's documents row, which the sync just copied
        in: e.g. L413 is Valid, not Lippert; a duplicate (L139 = L236) leaves the finder; shop sheets keep their label."""
        for k in list(self.docs):
            _fixes.apply(self.docs[k])
            if self.docs[k].get('status', 'active') != 'active':
                self.docs.pop(k)

    def _prepare(self):
        for d in self.docs.values():
            d['brand'] = d.get('brand') or ''
            d['unit_type'] = d.get('unit_type') or ''
            d['also_brands_l'] = {b.lower() for b in _fixes.split_list(d.get('also_brands'))}   # doc_fixes also_brand (Atwood = Dometic)
            d['any_brand_p'] = [w for w in (mwords(x) for x in _fixes.split_list(d.get('any_brand'))) if w]   # doc_fixes any_brand scope
            d['not_for_p'] = [w for w in (mwords(x) for x in _fixes.split_list(d.get('not_for'))) if w]
            d['models_n'] = [nmodel(m) for m in json.loads(d['models'] or '[]') if len(nmodel(m)) >= 3]
            d['page_models_n'] = set(json.loads(d.get('page_models') or '[]'))
        # vocabularies come from the library data itself (no hardcoded brand or category list)
        self.unit_types = sorted({d['unit_type'] for d in self.docs.values() if d['unit_type']})
        # docs filed under a document-kind category: which product unit types does the title itself name (see covers_unit)
        products = [(u, mwords(u)) for u in self.unit_types if not re.search(REFERENCE_KIND, u, re.I)]
        for d in self.docs.values():
            if re.search(REFERENCE_KIND, d['unit_type'], re.I):
                tw = mwords(d['title'])
                d['title_units'] = {u for u, need in products if need and need <= tw}
        names = {}
        for d in self.docs.values():
            if d['brand']:
                names.setdefault(_phrase(d['brand']), d['brand'])
            for ab in _fixes.split_list(d.get('also_brands')):
                names.setdefault(_phrase(ab), ab)
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
        (whole pages)."""
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
                    self._pages[k] = [self._page_row(_fixes.fix_page_row(dict(p, doc_id=k), doc['file_path'])) for p in plist
                                      if _fixes.page_kept(k, doc['file_path'], p['pdf_sheet'])]
                    added.append(k)
                    continue
                d['title'] = (a.get('clean_title') or a.get('title') or d['title']).strip()
                d['brand'] = (a.get('brand') or '').strip()
                d['product_line'] = (a.get('product_line') or '').strip()
                d['unit_type'] = (a.get('category') or '').strip()
                d['doc_number'] = (a.get('doc_number') or '').strip()
                d['revision_date'] = (a.get('revision_date') or '').strip()
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
        # + reviewed page topics. Word keys are interned: every page used to hold its own copy of each word string
        # (3.3M keys at 36k pages); interned, all pages share one copy per distinct word. Same counts, same scores.
        r['tf'] = collections.Counter(map(sys.intern, tokens(r['text'] + ('\n' + r['topics'] if r.get('topics') else ''))))
        r['len'] = sum(r['tf'].values())
        r['codes'] = json.loads(r['codes']) if isinstance(r['codes'], str) else r['codes']
        return r
    def pages(self, doc_id):
        if doc_id not in self._pages:
            fp = (self.docs.get(doc_id) or {}).get('file_path')   # reviewed page fixes: excluded sheets, wrong marks
            self._pages[doc_id] = [self._page_row(_fixes.fix_page_row(dict(r), fp)) for r in self.db.execute('select * from pages where doc_id=? order by pdf_sheet', (doc_id,))
                                   if _fixes.page_kept(doc_id, fp, r['pdf_sheet'])]
        return self._pages[doc_id]
    def doc_tf(self):
        # Built whole, then published: a second turn running at the same time used to see the half-filled dict and
        # fail with KeyError (test7 2026-11-27, 'L166'). The lock makes the other thread wait for the finished one.
        d = self._doc_tf
        if d is not None:
            return d
        with _LOCK:
            if self._doc_tf is None:
                built = {}
                for doc_id in list(self.docs):
                    tf = collections.Counter()
                    for p in self.pages(doc_id): tf.update(p['tf'])
                    built[doc_id] = (tf, sum(tf.values()))
                self._doc_tf = built
            return self._doc_tf

def bm25(query, items, k1=1.2, b=0.75):
    """query: tokens (weight 1 each) or {token or phrase tuple: weight}. items: list of (key, Counter tf, length).
    Returns {key: score}.
    IDF from the items themselves."""
    qw = dict(query) if isinstance(query, dict) else {q: 1.0 for q in query}
    N = len(items) or 1; avg = sum(l for _, _, l in items) / N or 1
    # a tuple key is a phrase of a term family: present only when all its words are, with the count of its rarest word
    freq = lambda tf, q: min(tf.get(t, 0) for t in q) if isinstance(q, tuple) else tf.get(q, 0)
    df = collections.Counter()
    for _, tf, _ in items:
        for q in qw:
            if freq(tf, q): df[q] += 1
    out = {}
    for key, tf, l in items:
        s = 0.0
        for q, w in qw.items():
            f = freq(tf, q)
            if not f: continue
            idf = math.log(1 + (N - df[q] + 0.5) / (df[q] + 0.5))
            s += w * idf * f * (k1 + 1) / (f + k1 * (1 - b + b * l / avg))
        out[key] = s
    return out

def hybrid(lib, query_text, pages, extra_tokens=()):
    """Normalised BM25 (whole words + RV term families) in [0, 1]: word-match only. Pages with none of the words score 0,
    so a search whose words no page holds comes back empty. (`lib` is kept for the callers' signature.)"""
    key = lambda p: (p['doc_id'], p['pdf_sheet'])
    if not pages: return {}
    bm = bm25(query_terms(query_text, extra_tokens), [(key(p), p['tf'], p['len']) for p in pages])
    bmax = max(bm.values()) or 1.0
    return {k: bm[k] / bmax for k in bm}

def _phrase(text):
    """'Coleman-Mach' / 'coleman mach' -> 'coleman mach' (lowercase words joined by one space)."""
    return ' '.join(re.findall(r'[a-z0-9]+', (text or '').lower()))


REFERENCE_KIND = r'reference|general|\bforms?\b|bulletin|recall|\btsb\b'   # categories named by document kind, not product


MW = re.compile(r'[a-z0-9]+(?:\.[0-9]+)?')
def mwords(text):
    """title / model-text words; plain words get the page-finder's normalisation (touchscreen = touch screen)"""
    out = set()
    for w in MW.findall((text or '').lower()):
        w = w.replace('.', '')
        if w in STOP or len(w) < 2: continue
        out.update(t for t in (_terms.vocab().word(w) if w.isalpha() else [w]) if t not in STOP)
    return out
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


# v4.20.0 (2026-11-03): with the full Lippert/Furrion load, a maker's user, install and spec sheets for the same unit
# outscored its troubleshooting / service manual on symptom words (they repeat the product's own vocabulary). For a
# symptom or diagnostic search, a doc's score is weighted by its kind, but only when the docs being ranked include a
# diagnosis doc, so a unit whose only manual is an owner's manual ranks exactly as before.
DIAG_KINDS = ('troubleshooting', 'service-manual')
KIND_WEIGHT = {'troubleshooting': 1.0, 'service-manual': 1.0, 'tech-sheet': 1.0, 'wiring-diagram': 1.0, 'recall-bulletin': 1.0,
               'shop-sheet': 1.0, 'owners-manual': float(os.environ.get('TT_KW_OWNER', '0.5')),
               'install-manual': float(os.environ.get('TT_KW_INSTALL', '0.5')), 'reference': float(os.environ.get('TT_KW_REF', '0.5')),
               'parts-list': float(os.environ.get('TT_KW_REF', '0.5')), 'other': float(os.environ.get('TT_KW_OTHER', '0.85')),
               'warranty-form': float(os.environ.get('TT_KW_REF', '0.5'))}


def kind_weights(docs):
    """doc_id -> weight for a diagnostic ranking of these docs (all 1.0 when none of them is a diagnosis doc)."""
    docs = list(docs)
    if not any(d.get('doc_type') in DIAG_KINDS for d in docs):
        return {d['doc_id']: 1.0 for d in docs}
    out = {d['doc_id']: KIND_WEIGHT.get(d.get('doc_type') or '', 1.0) for d in docs}
    # a whole-line diagnosis doc (a maker's "master training handout": no model list, or more than GENERIC_MODELS models)
    # counts less than a diagnosis manual written for the unit, when such a manual is among the docs
    specific = [d for d in docs if d.get('doc_type') in DIAG_KINDS and 0 < len(d.get('models_n') or ()) <= GENERIC_MODELS]
    if specific:
        for d in docs:
            if d.get('doc_type') in DIAG_KINDS and d not in specific: out[d['doc_id']] = GENERIC_WEIGHT
    return out


GENERIC_MODELS = 8
GENERIC_WEIGHT = float(os.environ.get('TT_KW_GENERIC', '0.7'))




def shown_title(d):
    """The doc title as GD shows it: a shop sheet / unpublished internal flow carries its label in front, so no page of
    it ever reads as the maker's manual (pagefinder/doc_fixes.py)."""
    return _fixes.display_title(d['title'], d.get('source_type'))


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
    except sqlite3.Error as e:   # v4.20.9: logged (no app-DB signature means the library is rebuilt as if it changed)
        print(f"GD_FALLBACK app_signature {type(e).__name__}: {e}", flush=True)
        return ''


_L = None
def _lib():
    global _L
    with _LOCK:
        if _L is None:
            _L = Library()
        elif _L.app_db and os.path.exists(_L.app_db) and app_signature(_L.app_db) != _L.app_sig:
            # the app library changed: re-read it. The old Library (all page word counts, ~300 MB at 36k pages) is let go
            # BEFORE the new one is built, so the two are not held at the same time.
            args = (_L.db_path, _L.app_db); _L = None; import gc; gc.collect()
            _L = Library(*args)
        return _L


def use_library(db, app_db):
    """The process-wide Library for this index + app DB: kept when it already matches (the app re-runs its script on
    every click), rebuilt only for a different index/app DB; app-library edits are picked up by _lib()."""
    global _L
    with _LOCK:
        if _L is None or (_L.db_path, _L.app_db) != (db, app_db):
            _L = None; import gc; gc.collect()   # let the old one go first (see _lib)
            _L = Library(db, app_db=app_db)
        return _L
