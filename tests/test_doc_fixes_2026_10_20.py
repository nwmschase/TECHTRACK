"""Library data fixes of 2026-10-20 (runs/complaint-class/model_flags.tsv): pagefinder/doc_fixes.tsv + model_tag_fixes.tsv,
applied by build_index.doc_record, search.Library (after the app-DB sync) and the Bay PDF sources.
Pure tests run anywhere; real-library checks use the keyword half only and skip when the shipped index / app DB is not on
this box. No network, no API calls."""
import json, os, shutil, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pagefinder import doc_fixes as DF, build_index as B  # noqa: E402
import gd_pages, gd_prompt  # noqa: E402
from gd_pages import Page, Picked  # noqa: E402

INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))
APP_DB = os.environ.get("TT_TEST_APP_DB", "/workspace/techtrack-fresh/migration-test/fresh-start.db")
HAVE_INDEX = os.path.exists(os.path.join(INDEX, "index.sqlite"))
F218 = "documents/6_20260918222623_Level-Up-Advantage-807662-Manual-Mode-Flash-Home-Shop-Writeup.pdf"
F413 = "documents/6_20261010233040_TRUELINE-LEVELING-SYSTEM_ServiceManual_pg-valid-manual-air-level-install-servic.pdf"
F139 = "documents/1_20260728223145_Coleman AC Troubleshooting.pdf"


class TestFixFile(unittest.TestCase):
    def test_rows_load_with_evidence(self):
        fx = DF.load()
        for i in (1, 4, 38, 120, 124, 139, 218, 247, 262, 413, 804, 805, 867):
            self.assertIn(i, fx)
            self.assertTrue(all(len(e) > 30 for e in fx[i]["evidence"]))
        self.assertEqual(fx[413]["doc"]["brand"], "Valid")
        self.assertEqual(fx[218]["doc"]["source_type"], "shop_sheet")
        self.assertEqual(fx[1]["doc"]["source_type"], "maker_internal")
        self.assertEqual(fx[139]["doc"]["duplicate_of"], "L236")
        self.assertIn(9, fx[262]["pages"])
        self.assertIn(867, B.model_tag_fixes())

    def test_fix_only_for_the_reviewed_file(self):
        self.assertIsNotNone(DF.fix_for(413, F413))
        self.assertIsNotNone(DF.fix_for("L413", F413))
        self.assertIsNone(DF.fix_for(413, "documents/some_other_upload.pdf"))
        self.assertIsNone(DF.fix_for(4, ""))   # test stubs reuse small ids without a file

    def test_bad_rows_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as f:
            f.write("1\ta.pdf\t\tbrand\tX\t\n")
        try:
            with self.assertRaises(ValueError):
                DF.load(f.name)
        finally:
            os.unlink(f.name)

    def test_labels(self):
        self.assertEqual(DF.display_title("T", "oem"), "T")
        self.assertEqual(DF.display_title("T", "shop_sheet"), "SHOP SHEET (not maker manual): T")
        self.assertTrue(DF.display_title("T", "maker_internal").startswith("MAKER INTERNAL FLOW, UNPUBLISHED (not maker manual)"))
        self.assertEqual(DF.bay_title("Level Up Advantage 807662 Manual Mode Flash Home — Shop Writeup", "shop_sheet"),
                         "Shop sheet: Level Up Advantage 807662 Manual Mode Flash Home")


class TestDocRecord(unittest.TestCase):
    """build_index applies the fixes, so a rebuilt index carries them."""
    def pages(self, *texts):
        return [dict(sheet=i + 1, text=t, method="text", hf=[]) for i, t in enumerate(texts)]

    def test_brand_fix(self):
        app = dict(id=413, title="Valid TrueLine Leveling System Installation & Operation Guide VTL01K011", brand="Lippert",
                   category="Leveling", file_path=F413, models="", product_line="TrueLine")
        doc, _ = B.doc_record(app, self.pages("Valid TrueLine leveling system " * 5), "pdf")
        self.assertEqual(doc["brand"], "Valid")
        doc, _ = B.doc_record(dict(app, file_path="documents/other.pdf"), self.pages("Valid TrueLine leveling system " * 5), "pdf")
        self.assertEqual(doc["brand"], "Lippert")   # not the reviewed file: untouched

    def test_duplicate_and_shop_sheet(self):
        doc, _ = B.doc_record(dict(id=139, title="Coleman AC Troubleshooting", brand="Coleman-Mach", category="Air Conditioning",
                                   file_path=F139), self.pages("wall thermostat no compressor operation " * 5), "pdf")
        self.assertEqual((doc["status"], doc["duplicate_of"]), ("duplicate", "L236"))
        doc, _ = B.doc_record(dict(id=218, title="Level Up Advantage 807662 Manual Mode Flash Home — Shop Writeup", brand="Lippert",
                                   category="Leveling", file_path=F218), self.pages("Manual Mode flash home CAN " * 5), "pdf")
        self.assertEqual((doc["source_type"], doc["doc_type"], doc["status"]), ("shop_sheet", "shop-sheet", "active"))

    def test_page_model_drop(self):
        f262 = "documents/" + DF.load()[262]["file"]
        pg = ["Chill low profile FACR13LPSA2-PS troubleshooting"] * 8 + ["Not cool enough. Model Number FACR13SA-PS FACR14SA-PS R410A"]
        doc, plist = B.doc_record(dict(id=262, title="Chill Low Profile (R32)", brand="Furrion", category="Air Conditioning",
                                       file_path=f262, models="FACR13LPSA2-PS"), self.pages(*pg), "pdf")
        self.assertNotIn("FACR13SAPS", json.loads(doc["page_models"]))
        self.assertNotIn("FACR14SAPS", json.loads(plist[8]["models"]))
        self.assertIn("FACR13LPSA2PS", json.loads(doc["page_models"]))


@unittest.skipUnless(HAVE_INDEX, "index not on this box")
class TestShippedIndex(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(os.path.join(INDEX, "index.sqlite"))

    def row(self, k):
        cur = self.db.execute("select * from docs where doc_id=?", (k,))
        return dict(zip([c[0] for c in cur.description], cur.fetchone()))

    def test_fixes_in_shipped_index(self):
        self.assertEqual(self.row("L413")["brand"], "Valid")
        self.assertEqual(self.row("L218")["source_type"], "shop_sheet")
        self.assertEqual(self.row("L1")["source_type"], "maker_internal")
        for k, t in (("L139", "L236"), ("L38", "L287"), ("L4", "L58")):
            self.assertEqual((self.row(k)["status"], self.row(k)["duplicate_of"]), ("duplicate", t))
        self.assertIn("NT-20SEQ", json.loads(self.row("L120")["models"]))
        self.assertIn("SW6DE", json.loads(self.row("L124")["models"]))
        m867 = json.loads(self.row("L867")["models"])
        self.assertNotIn("120VAC", m867); self.assertIn("SW6DE", m867)
        self.assertNotIn("FACR13SAPS", json.loads(self.row("L262")["page_models"]))
        self.assertTrue(self.row("L247")["title"].startswith("Thetford Permanent RV Toilet Owner's Manual 42088"))
        self.assertIn("no repair procedure", self.row("L804")["doc_note"])

    def test_in_place_update_is_idempotent(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "index.sqlite"); shutil.copy(os.path.join(INDEX, "index.sqlite"), p)
            self.assertEqual(B.apply_fixes_in_place(p), {})
        finally:
            shutil.rmtree(d)


@unittest.skipUnless(HAVE_INDEX and os.path.exists(APP_DB), "index / app DB not on this box")
class TestRealLibrary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)
        cls.lib = cls.f.lib

    def test_app_db_still_has_old_values_but_fixes_win(self):
        c = sqlite3.connect(f"file:{APP_DB}?mode=ro", uri=True)
        self.assertEqual(c.execute("select brand from documents where id=413").fetchone()[0], "Lippert")
        self.assertEqual(self.lib.docs["L413"]["brand"], "Valid")
        self.assertEqual(self.lib.docs["L218"]["source_type"], "shop_sheet")
        self.assertEqual(self.lib.docs["L1"]["source_type"], "maker_internal")

    def test_duplicates_never_returned(self):
        for k in ("L139", "L38", "L4"):
            self.assertNotIn(k, self.lib.docs)
        for model, complaint in (("Coleman-Mach 2111-0001", "Ran about 2 minutes then dead / no response."),
                                 ("Coleman AC", "no compressor operation"), ("Coleman Mach wall thermostat", "fan will not run"),
                                 ("Coleman-Mach", "Coleman AC Troubleshooting")):
            p = self.f.pick_manual("Air Conditioning", model, complaint)
            ids = [m["doc_id"] for m in p.manuals] + [x.doc_id for x in p.pages]
            ids += [x.doc_id for x in self.f.fetch_part("thermostat", p)]
            self.assertNotIn("L139", ids)
        p = self.f.pick_manual("Water Heaters", "Furrion FWH09A-AM", "E5")
        self.assertEqual([m["doc_id"] for m in p.manuals][:1], ["L287"])

    def test_l413_is_valid_not_lippert(self):
        p = self.f.pick_manual("Leveling", "Valid TrueLine", "system will not auto level")
        self.assertEqual([m["doc_id"] for m in p.manuals][:1], ["L413"])
        self.assertEqual({m["brand"] for m in p.manuals}, {"Valid"})   # L384/L381 are Valid TrueLine too (worker 1 flags)
        for model in ("Lippert Level Up Advantage 807662", "Lippert Ground Control 3.0", "Lippert leveling"):
            p = self.f.pick_manual("Leveling", model, "manual mode not working")
            self.assertNotIn("L413", [m["doc_id"] for m in p.manuals])

    def test_shop_sheet_labeled_and_never_the_oem_manual(self):
        p = self.f.pick_manual("Leveling", "Lippert Level Up Advantage 807662", "manual mode flashes and goes home")
        ids = [m["doc_id"] for m in p.manuals]
        self.assertIn("L218", ids)
        self.assertNotEqual(ids[0], "L218")   # the maker's manual leads; the shop sheet is listed after it
        m = next(m for m in p.manuals if m["doc_id"] == "L218")
        self.assertTrue(m["title"].startswith("SHOP SHEET (not maker manual): "))
        self.assertEqual(m["source_type"], "shop_sheet")
        shop_pages = [x for x in p.pages if x.doc_id == "L218"]
        self.assertTrue(shop_pages)
        self.assertTrue(all(x.label().startswith("SHOP SHEET (not maker manual): ") for x in shop_pages))
        ctx = gd_prompt.context_block(category="Leveling", model_text="Level Up 807662", picked=p, toc=[], pages=p.pages,
                                      not_shown=[], state={})
        self.assertIn("SHOP SHEET (not maker manual): Level Up Advantage 807662", ctx)
        self.assertTrue(self.f.doc_title("L218").startswith("SHOP SHEET (not maker manual)"))
        self.assertTrue(self.f.doc_title("L1").startswith("MAKER INTERNAL FLOW, UNPUBLISHED"))
        self.assertEqual(self.f.doc_title("L236"), self.lib.docs["L236"]["title"])   # OEM docs: unchanged

    def test_shop_sheet_not_offered_as_other_makers_tech_sheet(self):
        from pagefinder import search as S
        res = S.fetch_by_part("touch pad harness", {"manuals": [{"doc_id": "L413", "unit_type": "Leveling", "brand": "Valid"}]},
                              k=10000, lib=self.lib)
        self.assertFalse([x for x in res if x["doc_id"] in ("L218", "L1") and "other maker" in x["reason"]])

    def test_misprinted_page_note(self):
        p = self.f.pick_manual("Air Conditioning", "Furrion FACR13LPSA2-PS", "not cool enough")
        p9 = [x for x in p.pages if x.doc_id == "L262" and x.sheet == 9]
        self.assertTrue(p9)
        self.assertIn("MISPRINTED PAGE", p9[0].note)
        block = gd_prompt._pages_block("SELECTED PAGES", p9)
        self.assertIn("PAGE NOTE (reviewed): MISPRINTED PAGE", block)
        p = self.f.pick_manual("Air Conditioning", "Furrion FACR14SA-PS", "not cool enough")
        self.assertNotIn("L262", [m["doc_id"] for m in p.manuals])

    def test_model_tags(self):
        p = self.f.pick_manual("Water Heaters", "Suburban SW6DE", "gas clicks but never lights")
        self.assertIn("L124", [m["doc_id"] for m in p.manuals])
        self.assertIn("SW6DE", self.lib.docs["L124"]["models_n"])
        self.assertNotIn("120VAC", self.lib.docs["L867"]["models_n"])
        p = self.f.pick_manual("Furnaces", "Suburban NT-20SEQT", "won't blow warm air")
        self.assertEqual([m["doc_id"] for m in p.manuals], ["L120"])
        self.assertTrue(any("model tags" in w for w in p.why))
        p = self.f.pick_manual("Plumbing / Toilets", "Thetford Aqua-Magic Style II", "leaks at the base")
        self.assertIn("L247", [m["doc_id"] for m in p.manuals])

    def test_doc_note_reaches_prompt(self):
        p = Picked(manuals=[{"doc_id": "L804", "title": "Brinkley Model Z", "note": self.lib.docs["L804"]["doc_note"]}])
        ctx = gd_prompt.context_block(category="ID & Reference", model_text="Brinkley Z", picked=p, toc=[], pages=[],
                                      not_shown=[], state={})
        self.assertIn("[note: Owner's manual (care, operation, safety). It has no repair procedure", ctx)

    def test_fault_codes_stay_brand_locked(self):
        """E3 / E5 mean different things per maker (Furrion E5 = air pressure/exhaust, Girard E5 = blower): code search
        never crosses the brand lock."""
        for unit, model, code, brand in (("Water Heaters", "Furrion FWH09A", "E5", "Furrion"),
                                         ("Water Heaters", "Girard GSWH-2", "E5", "Girard"),
                                         ("Air Conditioning", "Furrion multi zone thermostat", "E3", "Furrion")):
            p = self.f.pick_manual(unit, model, "error code", code)
            self.assertTrue(p.manuals)
            self.assertEqual({m["brand"] for m in p.manuals}, {brand})
            self.assertEqual({self.lib.docs[x.doc_id]["brand"] for x in self.f.fetch_part("blower", p)} - {brand}, set())


class TestBayPdfSources(unittest.TestCase):
    def chunks(self):
        return [{"document_id": 218, "file_path": F218, "title": "Level Up Advantage 807662 Manual Mode Flash Home — Shop Writeup",
                 "brand": "Lippert", "page": 1,
                 "excerpt": "Unplugged wired CAN only. Manual Mode stays and works after the CAN harness is unplugged at the controller."},
                {"document_id": 139, "file_path": F139, "title": "Coleman AC Troubleshooting", "page": 2, "excerpt": "x" * 60},
                {"document_id": 413, "file_path": F413, "title": "Valid TrueLine Leveling System", "brand": "Lippert", "page": 3,
                 "excerpt": "y" * 60},
                {"document_id": 4, "title": "Thetford Water Valve Kit 42109", "page": 1, "excerpt": "Pull the pedal."}]

    def test_fixes_on_chunks(self):
        import bay_procedure as bp
        out = bp.apply_library_doc_fixes(self.chunks())
        self.assertEqual([c["document_id"] for c in out], [218, 413, 4])   # the L139 duplicate is dropped
        self.assertEqual(out[0]["title"], "Shop sheet: Level Up Advantage 807662 Manual Mode Flash Home")
        self.assertEqual(out[1]["brand"], "Valid")
        self.assertEqual(out[2]["title"], "Thetford Water Valve Kit 42109")   # a test doc with a reused id: untouched

    def test_bay_citation_says_shop_sheet(self):
        import bay_procedure as bp
        proc = bp.compile_bay_procedure("Manual mode flashes and goes home", brand="Lippert", model="Level Up Advantage 807662",
                                        category="Leveling", chunks=self.chunks()[:1])
        self.assertTrue(proc.primary_cite.startswith("Shop sheet: "), proc.primary_cite)
        self.assertNotIn("Lippert", proc.primary_cite)
        self.assertTrue(all(s["title"].startswith("Shop sheet: ") for s in proc.sources))


class TestPrompt(unittest.TestCase):
    def test_rule_names_the_labels(self):
        self.assertIn('"SHOP SHEET (not maker manual)"', gd_prompt.SYSTEM)
        self.assertIn("PAGE NOTE", gd_prompt.SYSTEM)

    def test_page_without_note_unchanged(self):
        block = gd_prompt._pages_block("SELECTED PAGES", [Page("L9", "Acme", "3", 3, "text", "entry", "r")])
        self.assertEqual(block, "=== SELECTED PAGES ===\n--- [Acme (L9), p.3] (entry; r) ---\ntext")


if __name__ == "__main__":
    unittest.main()
