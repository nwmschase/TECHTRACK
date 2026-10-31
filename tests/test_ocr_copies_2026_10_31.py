"""OCR copies in the page-finder build (Chase 2026-10-31 3:05 PM PT): build_index --ocr-copies reads the checked OCR copy
instead of a scanned original whose only text is a stamp. Offline; synthetic PDFs, no tesseract needed (the stamp sheet has
>= 20 characters, so pagetext never calls OCR on it)."""
import csv, json, os, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pymupdf  # noqa: E402
from pagefinder import ocr_copies as OC  # noqa: E402

STAMP = 'CCD-0000001  Rev. 1-17-2025'
BODY = 'Remove the burner cap and clean the igniter electrode with a dry cloth before relighting the hob.'


def pdf(path, extra=''):
    d = pymupdf.open(); pg = d.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), 0); pix.clear_with(200)
    pg.insert_image(pymupdf.Rect(50, 100, 550, 600), pixmap=pix)      # the 'scan'
    pg.insert_text((50, 760), STAMP, fontsize=8)                        # the only real text of the original
    if extra:
        pg.insert_text((50, 120), extra, fontsize=9, render_mode=3)     # invisible OCR layer, as ocrmypdf writes it
    d.save(path); d.close()


class TestOcrCopies(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); T = self.t.name
        self.orig = os.path.join(T, 'scan.pdf'); self.copy = os.path.join(T, 'scan.ocr.pdf'); self.other = os.path.join(T, 'other.pdf')
        pdf(self.orig); pdf(self.copy, BODY); pdf(self.other)
        self.osha, self.csha, self.xsha = OC.sha256_file(self.orig), OC.sha256_file(self.copy), OC.sha256_file(self.other)
        self.app = os.path.join(T, 'app.db'); c = sqlite3.connect(self.app)
        c.execute('create table categories(id integer primary key, name text)'); c.execute("insert into categories values(1,'Range & Cooktops')")
        c.execute('create table documents(id integer primary key, category_id int, title text, clean_title text, file_path text,'
                  ' content_sha256 text, brand text, product_line text, models text, doc_number text, revision_date text)')
        for i, p, s in ((9001, self.orig, self.osha), (9002, self.other, self.xsha)):
            c.execute('insert into documents values(?,?,?,?,?,?,?,?,?,?,?)', (i, 1, f'Test hob manual {i}', '', p, s, 'Testbrand', '', '', '', ''))
        c.commit(); c.close()
        self.sources = os.path.join(T, 'sources.json')
        json.dump({'9001': {'src': self.orig, 'sha': self.osha}, '9002': {'src': self.other, 'sha': self.xsha}}, open(self.sources, 'w'))
        self.man = os.path.join(T, 'manifest.csv')
        with open(self.man, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['original', 'original_sha256', 'copy', 'copy_sha256', 'method'])
            w.writerow([self.orig, self.osha, self.copy, self.csha, 'redo-ocr'])

    def tearDown(self):
        self.t.cleanup()

    def build(self, *extra):
        out = os.path.join(self.t.name, 'idx' + str(len(extra)))
        # its own process, as the build really runs (a Pool inside pytest would re-import whatever __main__ other tests set)
        p = subprocess.run([sys.executable, '-m', 'pagefinder.build_index', '--app-db', self.app, '--sources', self.sources, '--out', out,
                            '--no-embed', '--workers', '1', *extra], cwd=str(ROOT), capture_output=True, text=True)
        if p.returncode:
            raise OC.OcrCopyError(p.stderr[-2000:]) if 'OcrCopyError' in p.stderr else AssertionError(p.stderr[-2000:])
        db = sqlite3.connect(os.path.join(out, 'index.sqlite'))
        return {r[0]: r[1:] for r in db.execute('select d.doc_id, p.text, d.text_source, d.sha256 from docs d join pages p using(doc_id)')}, db

    def test_original_alone_is_stamp_only(self):
        rows, _ = self.build()
        self.assertIn('CCD-0000001', rows['L9001'][0])
        self.assertNotIn('igniter', rows['L9001'][0])

    def test_build_reads_the_ocr_copy(self):
        rows, db = self.build('--ocr-copies', self.man)
        text, how, sha = rows['L9001']
        self.assertIn('igniter electrode', text)
        self.assertIn('CCD-0000001', text)               # the PDF's own stamp text is still there
        self.assertIn('OCR copy, redo-ocr', how)
        self.assertEqual(sha, self.osha)                  # the doc keeps the app file's identity
        self.assertEqual(rows['L9002'][1], 'pdf')          # a doc without a copy is read as before
        self.assertIn('(1 used)', dict(db.execute('select key, value from meta'))['ocr_copies'])

    def test_changed_copy_stops_the_build(self):
        pdf(self.copy, BODY + ' edited')
        with self.assertRaises(OC.OcrCopyError):
            self.build('--ocr-copies', self.man)

    def test_missing_copy_stops_the_build(self):
        os.remove(self.copy)
        with self.assertRaises(OC.OcrCopyError):
            self.build('--ocr-copies', self.man)

    def test_manifest_rules(self):
        self.assertEqual(OC.load(self.man)[self.osha]['copy_sha256'], self.csha)
        self.assertEqual(OC.resolve('nope', OC.load(self.man)), (None, ''))
        bad = os.path.join(self.t.name, 'bad.csv')
        with open(bad, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['original_sha256', 'copy', 'copy_sha256']); w.writerow([self.osha, self.copy, ''])
        with self.assertRaises(OC.OcrCopyError):
            OC.load(bad)


if __name__ == '__main__':
    unittest.main()
