"""TechTrack page-finder (offline: no API calls; the only model is a small local embedding model on CPU).

The page-finder never reasons: Grok searches and reads the library with gd_tools, which calls this module's Library,
hybrid() ranking, model_score() and kind_weights(). v4.20.9: the old picker (search / pick_manual / fetch_by_part and
the CLI) is deleted; the numbered notes below describe the ranking rules those tools still share.

1. Pick the manual: unit type -> brand -> model. A model matches a doc's model tags, or (next tier) a model printed
   in the manual's own page text (model lists, rating plates). Ties go to the doc that best matches the complaint.
   An RV maker's brand (e.g. Brinkley) also pins that maker's owner's manual.
2. Entry page: a code -> the fault-code table page(s) listing it (page flag is_fault_codes); a symptom -> the best
   pages flagged is_troubleshooting in the picked manual(s), ranked by meaning + words.
3. Ranking everywhere is hybrid: 0.5 x BM25 on whole words (normalised) + 0.5 x meaning similarity (bge-small
   passage vectors, best passage per page, normalised). Words are normalised the same way in pages and queries
   (cooling = cool, touchscreen = touch screen, temp = temperature) and the query gains the RV shop term families at half
   weight (freeze sensor | evaporator sensor | coil sensor; not cold | not cooling | too warm), from the data files in
   pagefinder/terms/ (terms.py). No boost words, no per-case rules.
4. fetch_by_part(part): searches the picked manual(s) first, then the same brand's other docs, then other makers'
   tech sheets / service manuals for the same unit type (later tiers weighted 0.85 / 0.7).
"""
import hashlib, sqlite3, re, math, json, os, sys, collections, threading, time, logging
HERE = os.path.dirname(os.path.abspath(__file__))
# Index built from the app library by pagefinder/build_index.py (index.sqlite + passages.npy/json).
INDEX_DIR = os.environ.get('TT_PAGEFINDER_DIR', os.path.join(HERE, 'index'))
DB = os.path.join(INDEX_DIR, 'index.sqlite')
# Embedding model (BAAI/bge-small-en-v1.5, quantized ONNX, ~65 MB). v4.20.8: off by default, so this is never loaded
# unless TT_PAGEFINDER_MEANING=on. Not in the repo: when on, read from this cache dir, and fetched once from Hugging Face
# into it when missing. Offline tests point TT_MODEL_DIR at a pre-filled cache.
MODEL_NAME = 'BAAI/bge-small-en-v1.5'
MODEL_DIR = os.environ.get('TT_MODEL_DIR', os.path.join(os.path.expanduser('~'), '.cache', 'techtrack-models'))
APP_DB = os.environ.get('TT_APP_DB', '')   # the app library DB: its documents table overrides index metadata (single source of truth)


def _model_cached(cache_dir):
    root = os.path.join(cache_dir, 'models--Qdrant--bge-small-en-v1.5-onnx-Q', 'snapshots')
    return os.path.isdir(root) and any(os.path.exists(os.path.join(root, s, 'model_optimized.onnx')) for s in os.listdir(root))


# Process-wide caches. The hosted app runs every session in its own thread and re-executes its script on every click;
# the embedding model (~65 MB file, ~400 MB in RAM) and the shipped passage vectors do not depend on the app library,
# so they are loaded ONCE per process and shared, never once per Library / per rerun (that churned RAM to 1.2 GB).
_LOCK = threading.RLock()
_MODELS = {}      # cache_dir -> TextEmbedding
_BASE_VEC = {}    # vec_dir -> (V, {(doc_id, sheet): [row, ...]})


_MODEL_FAIL = {}  # cache_dir -> (time, error): a failed load (e.g. no network for the first download) is retried after
MODEL_RETRY_SEC = 600   # this long, not on every click
# Pages of docs added after the index build are embedded in the app. onnxruntime keeps the peak working memory of the
# biggest batch: 32 passages held ~+230 MB RSS for good, 4 passages ~+45 MB (measured 10/20) at a small speed cost.
EMBED_BATCH = 4
_log = logging.getLogger("techtrack.pagefinder")


def shared_embedding_model(cache_dir=None):
    cache_dir = cache_dir or MODEL_DIR
    with _LOCK:
        if cache_dir in _MODELS:
            return _MODELS[cache_dir]
        failed = _MODEL_FAIL.get(cache_dir)
        if failed and time.time() - failed[0] < MODEL_RETRY_SEC:
            raise RuntimeError(f'embedding model unavailable (retry later): {failed[1]}')
        try:
            m = embedding_model(cache_dir)
        except Exception as e:
            _MODEL_FAIL[cache_dir] = (time.time(), f'{type(e).__name__}: {e}'[:300])
            _log.error('embedding model could not load; page-finder runs on whole-word (BM25) scores only: %s', e)
            raise
        _MODEL_FAIL.pop(cache_dir, None)
        _MODELS[cache_dir] = m
        return m


def shared_base_vectors(vec_dir):
    """passages.npy + passages.json of the shipped index, loaded once per process (read-only; never mutate)."""
    with _LOCK:
        if vec_dir not in _BASE_VEC:
            import numpy as np
            # float16 kept as is (half the RAM); scored in float32 per query. Memory-mapped (TT_PAGEFINDER_MMAP, default on):
            # the rows live in the OS file cache (clean, reclaimable) instead of private heap memory.
            mm = 'r' if os.environ.get('TT_PAGEFINDER_MMAP', 'on').strip().lower() not in ('0', 'off', 'false', 'no') else None
            V = np.load(os.path.join(vec_dir, 'passages.npy'), mmap_mode=mm)
            V.setflags(write=False)
            rows = collections.defaultdict(list)
            for i, (d, s) in enumerate(json.load(open(os.path.join(vec_dir, 'passages.json')))): rows[(d, s)].append(i)
            _BASE_VEC[vec_dir] = (V, dict(rows))
        return _BASE_VEC[vec_dir]


def embedding_model(cache_dir=None, threads=None):
    """fastembed model; offline when the cache already holds it, else one download into the cache."""
    cache_dir = cache_dir or MODEL_DIR
    os.makedirs(cache_dir, exist_ok=True)
    if _model_cached(cache_dir):
        os.environ['HF_HUB_OFFLINE'] = '1'
    elif os.environ.get('TT_OFFLINE') == '1':
        raise RuntimeError(f'embedding model not in {cache_dir} and TT_OFFLINE=1')
    else:
        # v4.20.6: not cached, so the one download has to be allowed (a leftover HF_HUB_OFFLINE=1 blocked it on the live app).
        os.environ.pop('HF_HUB_OFFLINE', None)
    from fastembed import TextEmbedding
    return TextEmbedding(MODEL_NAME, cache_dir=cache_dir, threads=threads)

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
    def __init__(self, db=None, vec_dir=None, app_db=None):
        db = db or DB
        self.db_path = db
        self.vec_dir = vec_dir or os.path.dirname(db)
        self.db = sqlite3.connect(f'file:{db}?mode=ro', uri=True, check_same_thread=False); self.db.row_factory = sqlite3.Row
        self.docs = {r['doc_id']: dict(r) for r in self.db.execute("select * from docs where status='active' and n_pages>0")}
        self._pages = {}; self._doc_tf = None; self._vec = None; self._model = None; self._extra_vec = {}
        self.sync_note = ''; self.meaning_error = ''
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
    def vectors(self):
        """passage vectors (float32) and {(doc_id, sheet): [row, ...]}"""
        with _LOCK:
            return self._vectors_locked()
    def _vectors_locked(self):
        if self._vec is None:
            import numpy as np
            V, base_rows = shared_base_vectors(self.vec_dir)
            rows = collections.defaultdict(list, base_rows)   # new dict; shared lists are replaced, never appended to
            added = [k for k in getattr(self, 'added_docs', []) if k in self.docs]
            if added:   # docs added in the app after the index build: embed their pages once
                from pagefinder.build_index import passages
                keys, texts = [], []
                for k in added:
                    for p in self.pages(k):
                        for ps in passages(p['text']): keys.append((k, p['pdf_sheet'])); texts.append(ps)
                if texts:
                    E = np.asarray(list(self._embedder().embed(texts, batch_size=EMBED_BATCH)), dtype=np.float32)
                    E /= np.linalg.norm(E, axis=1, keepdims=True) + 1e-9
                    base = len(V); V = np.concatenate([V, E.astype(V.dtype)])
                    for j, k in enumerate(keys): rows[k] = rows[k] + [base + j]
            self._vec = (V, rows)
        return self._vec
    def embed_query(self, text):
        import numpy as np
        v = np.asarray(next(iter(self._embedder().query_embed([text]))), dtype='float32')
        return v / (np.linalg.norm(v) + 1e-9)
    def _embedder(self):
        if self._model is None:
            self._model = shared_embedding_model()
        return self._model
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

# Meaning half on/off for this process. v4.20.8 default is OFF: whole-word (BM25) scores only; the embedding model
# (~260 MB RSS) and the passage vectors (~64 MB) are never imported or loaded. TT_PAGEFINDER_MEANING=on turns it back
# on (env only; not a Streamlit secret). Offline 10/20 + 11/28: which manual is picked is the same either way; when
# on, only the order of pages inside the picked manual changes, and a 11/28 answer-key run found no net gain.
MEANING_BLOCK = 16384   # passages scored per block in meaning()


def meaning_flag_on(value=None):
    """True only for an explicit on (1/on/true/yes). Default, unset, empty or any other value is off."""
    raw = os.environ.get('TT_PAGEFINDER_MEANING', 'off') if value is None else value
    return str(raw or 'off').strip().lower() in ('1', 'on', 'true', 'yes')


MEANING_ON = meaning_flag_on()
_ANNOUNCED = None       # last SMART_SEARCH_* state printed (process-wide; never per query)
_ANNOUNCE_LOCK = threading.Lock()


def meaning_status(lib=None):
    """('on' | 'off_by_setting' | 'failed', error-or-empty). Reads lib.meaning_error and the process-wide fail cache."""
    if not MEANING_ON:
        return 'off_by_setting', ''
    err = (getattr(lib, 'meaning_error', None) or '') if lib is not None else ''
    if not err:
        with _LOCK:
            failed = next(iter(_MODEL_FAIL.values()), None)
        if failed:
            err = failed[1]
    if err:
        return 'failed', err
    return 'on', ''


def announce_meaning_state(lib=None, force=False):
    """One tagged SMART_SEARCH_OFF (or _ON) line on stdout, only on a state change or force=True at startup.

    force=True at app start prints the off-by-setting line; if the setting is on, it waits for a real load or failure.
    """
    global _ANNOUNCED
    state, err = meaning_status(lib)
    with _ANNOUNCE_LOCK:
        if force and state == 'on':
            return state, err
        if _ANNOUNCED == state:
            return state, err
        _ANNOUNCED = state
        if state == 'off_by_setting':
            line = 'SMART_SEARCH_OFF reason=switched off by setting using=word-match-only'
        elif state == 'failed':
            detail = (err or 'model could not load').replace('\n', ' ').replace('\r', ' ')[:300]
            line = f'SMART_SEARCH_OFF reason=download failed detail={detail} using=word-match-only'
        else:
            line = 'SMART_SEARCH_ON'
        print(line, flush=True)
        try:
            sys.stdout.flush()
        except Exception:
            pass
    return state, err


def meaning(lib, query, keys):
    """{(doc_id, sheet): best passage cosine} for the given pages"""
    import numpy as np
    if not MEANING_ON:
        return {k: 0.0 for k in keys}
    try:
        V, rows = lib.vectors(); q = lib.embed_query(query)
    except Exception as e:
        # The model is a download on first start when meaning is on. If it cannot load, scores stay on whole words.
        lib.meaning_error = f'{type(e).__name__}: {e}'[:300]
        announce_meaning_state(lib)
        return {k: 0.0 for k in keys}
    lib.meaning_error = ''
    announce_meaning_state(lib)
    idx = [(k, rows.get(k, [])) for k in keys]
    flat = [i for _, r in idx for i in r]
    # Scored in blocks: V[flat].astype('float32') over every passage of the library made two full temporary copies
    # (float16 + float32, ~240 MB at 105k passages) on each all-docs search; a block holds ~25 MB at most.
    sims = {}
    for b in range(0, len(flat), MEANING_BLOCK):
        part = flat[b:b + MEANING_BLOCK]
        sims.update(zip(part, (V[part].astype('float32') @ q).tolist()))
    return {k: max((sims[i] for i in r), default=0.0) for k, r in idx}

def hybrid(lib, query_text, pages, extra_tokens=()):
    """Normalised BM25 (whole words + RV term families) in [0, 1]. When meaning search is on and the model loaded,
    0.5 x BM25 + 0.5 x normalised meaning. When meaning is off or the model failed, word-match only — never a 0.5
    blend toward zeros, and the model and passage vectors are not loaded."""
    key = lambda p: (p['doc_id'], p['pdf_sheet'])
    if not pages: return {}
    bm = bm25(query_terms(query_text, extra_tokens), [(key(p), p['tf'], p['len']) for p in pages])
    bmax = max(bm.values()) or 1.0
    words = {k: bm[k] / bmax for k in bm}
    if not MEANING_ON:
        return words
    em = meaning(lib, query_text, [key(p) for p in pages])
    if getattr(lib, 'meaning_error', ''):
        return words
    lo, hi = min(em.values()), max(em.values())
    if hi <= lo:
        return words
    return {k: 0.5 * words[k] + 0.5 * ((em[k] - lo) / (hi - lo)) for k in words}

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
            args = (_L.db_path, _L.vec_dir, _L.app_db); _L = None; import gc; gc.collect()
            _L = Library(*args)
        return _L


def use_library(db, vec_dir, app_db):
    """The process-wide Library for this index + app DB: kept when it already matches (the app re-runs its script on
    every click), rebuilt only for a different index/app DB; app-library edits are picked up by _lib()."""
    global _L
    with _LOCK:
        if _L is None or (_L.db_path, _L.vec_dir, _L.app_db) != (db, vec_dir, app_db):
            _L = None; import gc; gc.collect()   # let the old one go first (see _lib)
            _L = Library(db, vec_dir, app_db=app_db)
        return _L
