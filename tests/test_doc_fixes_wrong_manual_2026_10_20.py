"""Library data fixes from the wrong-manual test of 2026-10-20 (runs/complaint-class/WRONG-MANUAL-TEST-2026-10-20.md), through
pagefinder/doc_fixes.tsv: L846 (Truma CP plus panel) also filed under Water Heaters (new also_category field), L808 (MaxxAir
FAQ) labeled as the maker's web FAQ (new maker_web source type) instead of a shop sheet, and printed model / family lists for
the generic master manuals. No search ranking change. No network, no API calls."""
import json, os, re, sqlite3, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pagefinder import doc_fixes as DF, search as S  # noqa: E402
import gd_pages, gd_prompt  # noqa: E402

INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))
APP_DB = os.environ.get("TT_TEST_APP_DB", "/workspace/techtrack-fresh/migration-test/fresh-start.db")
HAVE = os.path.exists(os.path.join(INDEX, "index.sqlite")) and os.path.exists(APP_DB)
FILLED = (1, 3, 5, 8, 9, 24, 25, 150, 167, 209, 215, 217, 236, 241, 247, 250, 310, 315, 318, 351, 355, 366, 386, 399, 405,
          415, 430, 431, 432, 522, 540, 546, 749, 767, 787, 791, 794, 796, 797, 799, 800, 801, 881, 883)


class TestFields(unittest.TestCase):
    def write(self, rows):
        f = tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False)
        f.write("\n".join("\t".join(r) for r in rows) + "\n"); f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_also_category_and_maker_web(self):
        p = self.write([("7", "a.pdf", "", "category", "Furnaces", "ev"), ("7", "a.pdf", "", "also_category", "Water Heaters, Furnaces", "ev"),
                        ("8", "b.pdf", "", "source_type", "maker_web", "ev")])
        d = dict(doc_id="L7", file_path="documents/a.pdf", unit_type="Slideouts", models="[]")
        DF.apply(d, path=p)
        self.assertEqual((d["unit_type"], d["also_unit_types"]), ("Furnaces", "Water Heaters"))   # own category not repeated
        self.assertTrue(S.covers_unit(d, "Water Heaters")); self.assertTrue(S.covers_unit(d, "Furnaces"))
        self.assertFalse(S.covers_unit(d, "Air Conditioning"))
        e = dict(doc_id="L8", file_path="b.pdf"); DF.apply(e, path=p)
        self.assertEqual(e["source_type"], "maker_web")
        self.assertEqual(DF.display_title("T", "maker_web"), "MAKER WEB FAQ (maker's published web page, not a service manual): T")
        self.assertEqual(DF.bay_title("T", "maker_web"), "Maker web FAQ: T")
        self.assertIn("maker web FAQ", gd_prompt.SYSTEM)

    def test_doc_without_second_category(self):
        self.assertFalse(S.covers_unit(dict(unit_type="Furnaces"), "Water Heaters"))
        self.assertFalse(S.covers_unit(dict(unit_type="Furnaces", also_unit_types=None), "Water Heaters"))

    def test_rows(self):
        fx = DF.load()
        self.assertEqual(fx[846]["doc"]["also_category"], "Water Heaters")
        self.assertEqual(fx[846]["doc"]["category"], "Furnaces")
        self.assertEqual(fx[808]["doc"]["source_type"], "maker_web")
        for i in FILLED:
            self.assertTrue(fx[i]["doc"].get("models_add"), i)

    def test_added_models_are_printed_in_the_doc(self):
        """every model / family added by the fill is in the doc's own page text (two abbreviated series are printed as
        '6799-720 & -726' and '6700, 7000, 8000 & 9000 SERIES')"""
        db = sqlite3.connect(f"file:{os.path.join(INDEX, 'index.sqlite')}?mode=ro", uri=True)
        n = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        ok = {"6799726", "7000series"}
        for line in open(DF.DOC_FIXES, encoding="utf-8"):
            c = line.rstrip("\n").split("\t")
            if len(c) < 6 or c[3] != "models_add" or "2026-10-20 model-family fill" not in c[5]:
                continue
            text = n(" ".join(t for (t,) in db.execute("select text from pages where doc_id=?", (f"L{c[0]}",))))
            for m in DF.split_list(c[4]):
                self.assertTrue(n(m) in text or n(m) in ok, (c[0], m))


@unittest.skipUnless(HAVE, "index / app DB not on this box")
class TestLibrary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)
        cls.lib = cls.f.lib

    def ids(self, *a):
        p = self.f.pick_manual(*a)
        return [m["doc_id"] for m in p.manuals] + [x.doc_id for x in p.pages]

    def test_truma_aquago_finds_the_panel_doc(self):
        d = self.lib.docs["L846"]
        self.assertEqual((d["unit_type"], d["also_unit_types"]), ("Furnaces", "Water Heaters"))
        self.assertIn("L846", self.ids("Water Heaters", "Truma AquaGo comfort", "no hot water, E 2 W shown"))
        self.assertIn("L846", self.ids("Furnaces", "Truma VarioHeat", "furnace will not light"))

    def test_maxxair_faq_is_the_makers_web_faq(self):
        d = self.lib.docs["L808"]
        self.assertEqual(d["source_type"], "maker_web")
        self.assertTrue(self.f.doc_title("L808").startswith("MAKER WEB FAQ"))
        self.assertNotIn("SHOP SHEET", self.f.doc_title("L808"))

    def test_models_filled(self):
        # no longer searched since 2026-10-21 (models still filled in the index row): L150 duplicate of L215 (ae65201);
        # L787 L791 retired combined Master Owner's Manuals, L799 and L32 removed by Chase (exclude rows)
        gone = {150: "duplicate", 787: "excluded", 791: "excluded", 799: "excluded", 32: "excluded"}
        db = sqlite3.connect(f"file:{os.path.join(INDEX, 'index.sqlite')}?mode=ro", uri=True)
        row = lambda i: db.execute("select status, models from docs where doc_id=?", (f"L{i}",)).fetchone()
        for i in FILLED:
            if i in gone:
                self.assertNotIn(f"L{i}", self.lib.docs, i)
                self.assertEqual(row(i)[0], gone[i], i)
                self.assertTrue(json.loads(row(i)[1]), i)
            else:
                self.assertTrue(json.loads(self.lib.docs[f"L{i}"]["models"]), i)
        self.assertIn("Ground Control 3.0", json.loads(self.lib.docs["L1"]["models"]))
        self.assertIn("8330-735", json.loads(self.lib.docs["L236"]["models"]))
        # held back: multi-model docs whose exact tags would push a dedicated doc out (ranking tie-break is Chase's call)
        self.assertNotIn("140-1227", json.loads(row(799)[1]))
        self.assertEqual(json.loads(row(32)[1]), [])
        self.assertEqual([m["doc_id"] for m in self.f.pick_manual("Leveling", "Power Gear 140-1227", "not working").manuals][:2], ["L802", "L555"])


if __name__ == "__main__":
    unittest.main()
