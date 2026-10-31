"""Readiness #26 (2026-10-31): the search word-list builder (pagefinder/build_terms.py) learns words ONLY from pages search
can return. Same rules as search.Library: index status 'active' with pages, then doc_fixes exclude (removed / set aside /
retired / not an RV doc) and duplicate_of on top, then page_exclude sheets (non-English, blank, ad inserts) dropped.
Offline: a tiny synthetic index + doc_fixes file, plus a parity check against search.Library on the shipped index."""
import os, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pagefinder import build_terms as BT  # noqa: E402

INDEX = ROOT / 'pagefinder' / 'index' / 'index.sqlite'

# doc_id, index status, n_pages, {sheet: text}; every doc has its own marker word so a leak is easy to see
DOCS = [
    ('L1', 'active', 2, {1: 'alphaword keeper page. Direct Spark Ignition (DSI) check', 2: 'alphaword second page Direct Spark Ignition (DSI)'}),
    ('L2', 'excluded', 1, {1: 'excludedword flat rate labor Hydraulic Power Unit (HPU) Hydraulic Power Unit (HPU)'}),
    ('L3', 'duplicate', 1, {1: 'duplicateword copy of another manual'}),
    ('L4', 'no-text', 1, {1: 'notextword'}),
    ('L5', 'active', 0, {1: 'zeropagesword'}),
    ('L6', 'active', 1, {1: 'retiredword combined master manual'}),        # doc_fixes exclude added after the index build
    ('L7', 'active', 1, {1: 'dupfixword second copy'}),                     # doc_fixes duplicate_of added after the build
    ('L8', 'active', 2, {1: 'betaword english page', 2: 'frenchword annulation acceptation'}),   # sheet 2 page_exclude
]
FIXES = [
    ('6', 'L6.pdf', '', 'exclude', 'retired 2026-10-21 (Chase): combined manual split', 'test'),
    ('7', 'L7.pdf', '', 'duplicate_of', 'L1', 'test'),
    ('8', 'L8.pdf', '2', 'page_exclude', 'non-English (French) page', 'test'),
    ('2', 'L2.pdf', '', 'exclude', 'SET ASIDE (labor guide), kept on file, not searchable', 'test'),
]


def make_index(d):
    p = os.path.join(d, 'index.sqlite')
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE docs(doc_id TEXT PRIMARY KEY, app_id INT, title TEXT, brand TEXT, product_line TEXT, models TEXT,"
               " file_path TEXT, n_pages INT, status TEXT, page_models TEXT, duplicate_of TEXT DEFAULT '')")
    db.execute('CREATE TABLE pages(doc_id TEXT, pdf_sheet INT, text TEXT, PRIMARY KEY(doc_id, pdf_sheet))')
    for k, st, n, pages in DOCS:
        db.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?,?,?)', (k, int(k[1:]), k, '', '', '[]', f'/x/{k}.pdf', n, st, '[]', ''))
        for s, t in pages.items():
            db.execute('INSERT INTO pages VALUES(?,?,?)', (k, s, t))
    db.commit(); db.close()
    fx = os.path.join(d, 'doc_fixes.tsv')
    with open(fx, 'w', encoding='utf-8') as f:
        f.write('# test fixes\n' + ''.join('\t'.join(r) + '\n' for r in FIXES))
    return p, fx


class TestSearchableOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.index, self.fixes = make_index(self.tmp.name)
        self.db = sqlite3.connect(self.index)

    def tearDown(self):
        self.db.close(); self.tmp.cleanup()

    def test_only_active_searchable_docs(self):
        self.assertEqual(sorted(BT.searchable_docs(self.db, self.fixes)), ['L1', 'L8'])

    def test_page_exclude_sheet_dropped(self):
        pages = [(d, s) for d, s, _ in BT.searchable_pages(self.db, self.fixes)]
        self.assertEqual(pages, [('L1', 1), ('L1', 2), ('L8', 1)])

    def test_no_words_from_removed_docs_or_pages(self):
        raw, bigrams, acr, ex = BT.library_words(self.db, self.fixes)
        for w in ('alphaword', 'betaword'):
            self.assertIn(w, raw)
        for w in ('excludedword', 'duplicateword', 'notextword', 'zeropagesword', 'retiredword', 'dupfixword',
                  'frenchword', 'annulation', 'acceptation'):
            self.assertNotIn(w, raw, w)
        self.assertIn('dsi', acr)          # defined twice on a searchable doc: learned
        self.assertNotIn('hpu', acr)       # defined only in a set-aside doc: not learned

    def test_main_end_to_end(self):
        out = os.path.join(self.tmp.name, 'terms')
        BT.main(['--index', self.index, '--out', out, '--doc-fixes', self.fixes])
        acr = open(os.path.join(out, 'acronyms.tsv'), encoding='utf-8').read()
        self.assertIn('dsi\tdirect spark ignition', acr)
        self.assertNotIn('hpu', acr)
        for f in ('word_forms.tsv', 'compounds.tsv'):
            text = open(os.path.join(out, f), encoding='utf-8').read()
            for w in ('annulation', 'acceptation', 'excludedword'):
                self.assertNotIn(w, text)

    def test_index_db_left_read_only_style(self):
        # the builder must not change the caller's connection (row_factory) or the index
        before = self.db.execute('select count(*) from pages').fetchone()
        list(BT.searchable_pages(self.db, self.fixes))
        self.assertIsNone(self.db.row_factory)
        self.assertEqual(self.db.execute('select count(*) from pages').fetchone(), before)


@unittest.skipUnless(INDEX.exists(), 'shipped index not on this box')
class TestParityWithSearch(unittest.TestCase):
    def test_same_pages_as_search_library(self):
        from pagefinder import search as S
        lib = S.Library(db=str(INDEX), app_db='')
        want = {(k, p['pdf_sheet']) for k in lib.docs for p in lib.pages(k)}
        db = sqlite3.connect(f'file:{INDEX}?mode=ro', uri=True)
        got = {(d, s) for d, s, _ in BT.searchable_pages(db)}
        db.close()
        self.assertEqual(got, want)
        self.assertTrue(got)

    def test_shipped_terms_have_no_junk_from_removed_docs(self):
        terms = ROOT / 'pagefinder' / 'terms'
        wf = {l.split('\t')[0] for l in open(terms / 'word_forms.tsv', encoding='utf-8') if not l.startswith('#')}
        cp = {l.split('\t')[0] for l in open(terms / 'compounds.tsv', encoding='utf-8') if not l.startswith('#')}
        # learned before 10/31 only from page_exclude French pages / set-aside flat-rate charts / OCR junk
        for w in ('annulation', 'acceptation', 'affectation', 'onionion', 'inted', 'naged'):
            self.assertNotIn(w, wf)
        for w in ('weekend', 'disengages', 'componenttag', 'leftrear'):
            self.assertNotIn(w, cp)
        # real terms kept
        for w in ('cooling', 'wiring', 'ignition', 'calibration'):
            self.assertIn(w, wf)
        for w in ('touchscreen', 'touchpad'):
            self.assertIn(w, cp)


if __name__ == '__main__':
    unittest.main()
