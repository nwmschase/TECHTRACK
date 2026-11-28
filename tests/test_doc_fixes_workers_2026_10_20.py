"""Library data fixes from the worker 1/2/3 page-reading flags of 2026-10-20 (runs/complaint-class/flags/worker{1,2,3}.tsv),
through pagefinder/doc_fixes.tsv: duplicates retired, non-RV docs excluded, brands/categories/models corrected, third-party
re-host pages excluded, wrong page marks cleared, misprints labeled as DOC DEFECT notes. No network, no API calls."""
import json, os, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pagefinder import doc_fixes as DF  # noqa: E402
import gd_pages, gd_prompt  # noqa: E402

INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))
APP_DB = os.environ.get("TT_TEST_APP_DB", "/workspace/techtrack-fresh/migration-test/fresh-start.db")
HAVE = os.path.exists(os.path.join(INDEX, "index.sqlite")) and os.path.exists(APP_DB)
RETIRED = {"L19": "L431", "L323": "L355", "L176": "L415", "L326": "L556", "L194": "L556", "L403": "L414",
           "L147": "L121", "L163": "L286", "L210": "L869"}


class TestNewFields(unittest.TestCase):
    def write(self, rows):
        f = tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False)
        f.write("\n".join("\t".join(r) for r in rows) + "\n"); f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_category_models_exclude_third_party(self):
        p = self.write([("7", "a.pdf", "", "category", "Leveling", "ev"), ("7", "a.pdf", "", "models_drop", "HTML5", "ev"),
                        ("7", "a.pdf", "", "models_add", "X100", "ev"), ("7", "a.pdf", "", "source_type", "third_party", "ev"),
                        ("7", "a.pdf", "3", "page_exclude", "ad insert", "ev"), ("7", "a.pdf", "2", "page_marks_off", "is_troubleshooting", "ev"),
                        ("8", "b.pdf", "", "exclude", "residential", "ev"), ("9", "c.pdf", "", "models_drop", "*", "ev")])
        d = dict(doc_id="L7", file_path="documents/a.pdf", unit_type="Slideouts", models='["HTML5", "Y2"]', page_models='["HTML5"]', status="active")
        DF.apply(d, path=p)
        self.assertEqual((d["unit_type"], json.loads(d["models"]), json.loads(d["page_models"]), d["source_type"]),
                         ("Leveling", ["Y2", "X100"], [], "third_party"))
        self.assertFalse(DF.page_kept("L7", "a.pdf", 3, path=p)); self.assertTrue(DF.page_kept("L7", "a.pdf", 2, path=p))
        row = DF.fix_page_row(dict(doc_id="L7", pdf_sheet=2, is_troubleshooting=1), "a.pdf", path=p)
        self.assertEqual(row["is_troubleshooting"], 0)
        e = dict(doc_id="L8", file_path="b.pdf", status="active"); DF.apply(e, path=p); self.assertEqual(e["status"], "excluded")
        g = dict(doc_id="L9", file_path="c.pdf", models='["R1", "R2"]'); DF.apply(g, path=p); self.assertEqual(json.loads(g["models"]), [])
        self.assertTrue(DF.display_title("T", "third_party").startswith("THIRD-PARTY DOC (not maker manual)"))

    def test_unknown_mark_rejected(self):
        with self.assertRaises(ValueError):
            DF.load(self.write([("7", "a.pdf", "2", "page_marks_off", "is_bogus", "ev")]))

    def test_every_row_has_evidence_and_known_file(self):
        db = sqlite3.connect(os.path.join(INDEX, "index.sqlite"))
        files = {r[0]: os.path.basename(r[1]) for r in db.execute("select doc_id, file_path from docs")}
        for app_id, e in DF.load().items():
            self.assertEqual(files.get(f"L{app_id}"), e["file"], app_id)
            self.assertTrue(all(ev.strip() for ev in e["evidence"]))


@unittest.skipUnless(HAVE, "index / app DB not on this box")
class TestWorkerFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)
        cls.lib = cls.f.lib

    # v4.20.9: the old picker (pick_manual) is deleted; the same data is checked through the tools Grok uses.
    def tools(self):
        import gd_tools
        return gd_tools.LibraryTools.for_finder(self.f)

    def ids(self, unit_type, model, words):
        out = json.loads(self.tools().call("find_documents", {"model": model, "unit_type": unit_type, "words": words})[0])
        return [d["doc_id"] for d in out.get("documents", [])]

    def test_duplicates_and_excluded_never_returned(self):
        for k, keep in RETIRED.items():
            self.assertNotIn(k, self.lib.docs); self.assertIn(keep, self.lib.docs)
        for k in ("L393", "L398"):
            self.assertNotIn(k, self.lib.docs)
        self.assertNotIn("L403", self.ids("awnings", "Girard Vision", "awning will not extend"))
        self.assertEqual(self.ids("awnings", "Girard Vision", "awning will not extend")[:1], ["L414"])
        self.assertNotIn("L210", self.ids("Range & Cooktops", "Suburban SR3", "oven will not light"))
        self.assertNotIn("L393", self.ids("awnings", "Girard GG750 solar", "awning motor dead"))

    def test_brands(self):
        for k, b in (("L384", "Valid"), ("L381", "Valid"), ("L802", "Power Gear"), ("L735", "Power Gear"), ("L131", "Keystone"),
                     ("L132", "Keystone"), ("L137", "Keystone"), ("L304", "Everchill")):
            self.assertEqual(self.lib.docs[k]["brand"], b, k)
        self.assertEqual(self.lib.docs["L133"]["brand"], "Furrion")   # the one genuine Furrion form

    def test_categories(self):
        for k in ("L320", "L321", "L322", "L409"):   # Trans/Air bus/van HVAC: excluded 2026-10-21 (not RV, Chase)
            self.assertNotIn(k, self.lib.docs, k)
        want = {"Leveling": ("L704", "L705", "L706", "L707", "L708", "L709", "L710", "L711", "L20"),
                "Electrical": ("L406",), "axles-suspension-brakes": ("L45", "L46", "L47"), "Range & Cooktops": ("L869",),
                "Slideouts": ("L872", "L424", "L879"), "Plumbing / Toilets": ("L314",), "Furnaces": ("L846",)}
        for ut, ks in want.items():
            for k in ks:
                self.assertEqual(self.lib.docs[k]["unit_type"], ut, k)
        self.assertEqual({self.lib.docs[k]["brand"] for k in ("L424", "L879", "L872")}, {"Kwikee"})

    def test_junk_models_gone_real_models_added(self):
        junk = {"HTML5", "MC4", "RJ45", "120VAC", "120VAC", "N3T", "J24", "J26", "US131", "M35008", "205613", "052979", "052540",
                "03052019", "002445", "N8DCXN10DCX1", "SO530", "BAT1", "BAT2", "A080H584", "N30620", "CF21B", "GR5", "JAN12"}
        for k, d in self.lib.docs.items():
            self.assertFalse(junk & set(d["models_n"]), k)
        for k, m in (("L414", "VISION"), ("L815", "MIRAGE"), ("L341", "CFRV21B"), ("L338", "CFRV17BBD"), ("L143", "RM2652"),
                     ("L127", "HE0601"), ("L144", "N10DCX"), ("L836", "PD9145"), ("L31", "INVT100012VP2")):
            self.assertIn(m, self.lib.docs[k]["models_n"], k)
        self.assertEqual(self.ids("Range & Cooktops", "Furrion CF-RV21B", "burner will not light")[:1], ["L341"])
        self.assertIn("L143", self.ids("Refrigerators", "Dometic RM2652", "no cooling on gas")[:3])

    def test_third_party_and_shop_labels(self):
        for k in ("L189", "L190", "L246"):
            self.assertEqual(self.lib.docs[k]["source_type"], "shop_sheet", k)
            self.assertTrue(self.f.doc_title(k).startswith("SHOP SHEET (not maker manual): "))
        for k in ("L240", "L237"):
            self.assertTrue(self.f.doc_title(k).startswith("THIRD-PARTY DOC (not maker manual): "))
        self.assertIn("RVLock", self.lib.docs["L318"]["doc_note"])
        self.assertIn("Shurflo", self.lib.docs["L853"]["doc_note"])

    def test_rehost_pages_excluded_and_marks_cleared(self):
        # L803 (Suburban parts manual) removed 2026-10-21 (parts-ordering only); L224 (cut-off Atwood copy, its p50 was the
        # My RV Works insert) retired 2026-10-21 (ab43ae5), replaced by the clean split L892/L893/L894, which has no insert page
        self.assertNotIn("L224", self.lib.docs)
        for k, sh in (("L241", 27), ("L149", 61), ("L121", 112), ("L867", 24), ("L161", 62)):
            self.assertNotIn(sh, [p["pdf_sheet"] for p in self.lib.pages(k)], k)
            self.assertIn(sh - 1, [p["pdf_sheet"] for p in self.lib.pages(k)])
        self.assertIn("My RV Works", self.lib.docs["L149"]["doc_note"])
        for k, sh in (("L809", 4), ("L810", 4), ("L806", 7), ("L819", 7)):
            self.assertEqual([p["is_troubleshooting"] for p in self.lib.pages(k) if p["pdf_sheet"] == sh], [0], k)
        hits = json.loads(self.tools().call("search_pages", {"words": "no cooling", "brand": "Norcold",
                                                             "unit_type": "Refrigerators"})[0])["hits"]
        self.assertTrue(hits)
        self.assertNotIn("courtesy of My RV Works", json.dumps(hits))

    def test_misprints_are_doc_defect_notes_with_the_correct_value(self):
        for k, sh, want in (("L341", 6, "13.8"), ("L870", 39, "0.48 A"), ("L395", 3, "4 minutes"), ("L414", 18, "page 16"),
                            ("L47", 14, "page 13"), ("L287", 14, "page 13"), ("L296", 8, "10.7"), ("L827", 13, "1.12 in"),
                            ("L309", 8, "microwave"), ("L402", 3, "2 minutes")):
            note = DF.page_fix(k, self.lib.docs[k]["file_path"], sh).get("page_note", "")
            self.assertTrue(note.startswith("DOC DEFECT"), k); self.assertIn(want, note, k)
        db = sqlite3.connect(os.path.join(INDEX, "index.sqlite"))   # maker text is never rewritten
        self.assertIn("12.8", db.execute("select text from pages where doc_id='L341' and pdf_sheet=6").fetchone()[0])
        _out, p6, err = self.tools().call("read_pages", {"doc_id": "L341", "sheets": [6]})
        self.assertFalse(err)
        self.assertIn("PAGE NOTE (reviewed): DOC DEFECT", gd_prompt._pages_block("SELECTED PAGES", p6))
        self.assertIn("DOC DEFECT", gd_prompt.SYSTEM)       # the primer describes the page note
        self.assertIn("third-party document", gd_prompt.SYSTEM)

    def test_worker4_small_sheets(self):
        d = self.lib.docs
        for k in ("L677", "L584", "L688", "L702", "L703", "L713", "L463"):
            self.assertEqual(d[k]["unit_type"], "Leveling", k)
        self.assertNotIn("L877", d)   # Trans/Air truck/van A/C drawing: excluded 2026-10-21 (not RV, Chase)
        self.assertNotIn("L685", d)   # marine product
        for k in ("L517", "L528", "L529"):   # furniture / mattress covers: excluded 2026-10-21 (not RV service docs, Chase)
            self.assertNotIn(k, d, k)
        self.assertEqual((d["L852"]["brand"], d["L852"]["title"][:7]), ("Dometic", "Dometic"))
        self.assertIn("Tire Clearance", d["L871"]["title"])
        self.assertEqual(d["L488"]["product_line"], "Axles/Suspension"); self.assertNotEqual(d["L483"]["product_line"], "Tire Monitoring")
        for k, junk in (("L457", "C1036"), ("L461", "J673"), ("L463", "CABIN80AMINIBREAKERINSTALLATION"), ("L454", "1621HD"), ("L885", "EZE1")):
            self.assertNotIn(junk, d[k]["models_n"], k)
        for k in ("L244",):   # L877 excluded 2026-10-21 (Trans/Air, not RV)
            self.assertTrue(self.f.doc_title(k).startswith("SHOP SHEET (not maker manual): "), k)
        self.assertTrue(self.f.doc_title("L808").startswith("MAKER WEB FAQ"))   # maxxair.com FAQ: re-labeled 2026-10-20 (wrong-manual test)
        self.assertTrue(self.f.doc_title("L138").startswith("COACH-BUILDER DOC")); self.assertEqual(d["L138"]["brand"], "")
        self.assertTrue(self.f.doc_title("L142").startswith("COACH-BUILDER DOC"))
        self.assertTrue(self.f.doc_title("L868").startswith("THIRD-PARTY DOC"))
        for k in ("L136", "L542"):
            self.assertTrue(self.f.doc_title(k).startswith("DEALER/DISTRIBUTOR DOC"), k)
        for k in ("L78", "L229"):   # BAL parts guide PTS.LS.SS.001: removed 2026-10-21 (parts identification only, Chase)
            self.assertNotIn(k, d)
        for k in ("L536", "L538", "L543"):
            self.assertIn("NEEDS OCR", d[k]["doc_note"])
        self.assertIn("L724", self.ids("Leveling", "Bigfoot", "general maintenance lubrication"))


if __name__ == "__main__":
    unittest.main()
