"""RV shop vocabulary in the page-finder's word half (pagefinder/terms.py + pagefinder/terms/*.tsv), fresh-core 18/19.
Pure-table tests run anywhere; the real-library checks use the keyword half only (no model download) and skip when
the shipped index / app DB is not on this box."""
import collections, filecmp, json, os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pagefinder import terms as T, search as S  # noqa: E402

V = T.vocab()


class TestNormalise(unittest.TestCase):
    def test_word_forms_and_spellings(self):
        self.assertEqual(V.tokens("cooling"), V.tokens("cool"))
        self.assertEqual(V.tokens("cools"), V.tokens("cool"))
        self.assertEqual(V.tokens("temp sensor"), ["temperature", "sensor"])
        self.assertEqual(V.tokens("evap fan"), ["evaporator", "fan"])
        self.assertEqual(V.tokens("fridge"), ["refrigerator"])
        self.assertEqual(V.tokens("ignitor"), V.tokens("igniter"))

    def test_compounds_split(self):
        self.assertEqual(V.tokens("touchscreen"), V.tokens("touch screen"))
        self.assertEqual(V.tokens("touchpad"), V.tokens("touch pad"))

    def test_keep_words_untouched(self):
        for w in ("fitting", "housing", "bearing", "ceiling", "troubleshooting"):
            self.assertEqual(V.tokens(w), [w])

    def test_stop_words_dropped(self):
        self.assertEqual(V.tokens("the fan is not working"), ["fan", "work"])
        self.assertIs(S.STOP, T.STOP)


class TestFamilies(unittest.TestCase):
    def test_exact_words_full_weight_family_half(self):
        q = V.query_terms("will not blow cold")
        self.assertEqual(q["cold"], 1.0)
        self.assertEqual(q["cool"], T.FAMILY_WEIGHT)

    def test_phrase_member_is_one_unit(self):
        q = V.query_terms("evaporator temperature sensor")
        self.assertEqual(q[("freeze", "sensor")], T.FAMILY_WEIGHT)
        self.assertNotIn("freeze", q)          # 'freeze' alone must not score: only with 'sensor' on the page
        q = V.query_terms("control board")
        self.assertEqual(q["pcb"], T.FAMILY_WEIGHT)
        self.assertNotIn("circuit", q)

    def test_negation_any_form_but_not_across_clauses(self):
        self.assertIn(("cool", "insufficient"), V.query_terms("unit won't cool"))
        self.assertIn("warm", V.query_terms("fridge doesn't get cold"))
        # 'not getting cold' is one clause, 'freezer operating' another: no 'not operate' style cross-clause match
        q = V.query_terms("not getting cold; freezer operating properly")
        self.assertIn("warm", q)
        self.assertNotIn("lockout", q)

    def test_bm25_exact_outranks_family(self):
        q = V.query_terms("not cold")
        items = [("exact", collections.Counter(V.tokens("cold air not cold")), 4),
                 ("family", collections.Counter(V.tokens("cool air not cool")), 4),
                 ("none", collections.Counter(V.tokens("door seal hinge")), 4)]
        s = S.bm25(q, items)
        self.assertGreater(s["exact"], s["family"])
        self.assertGreater(s["family"], s["none"])

    def test_bm25_phrase_needs_all_words(self):
        q = {("freeze", "sensor"): 0.5}
        items = [("both", collections.Counter(["freeze", "sensor"]), 2), ("one", collections.Counter(["freeze", "door"]), 2)]
        s = S.bm25(q, items)
        self.assertGreater(s.get("both", 0), 0)
        self.assertEqual(s.get("one", 0), 0)

    def test_family_table_well_formed(self):
        rows = T._rows("rv_term_families.tsv")
        self.assertTrue(rows)
        for r in rows:
            self.assertIn(r[0], ("same", "family", "keep"), r)
            self.assertGreaterEqual(len(r), 3, f"row without evidence: {r}")
            if r[0] != "keep":
                self.assertGreaterEqual(len(r[1].split(" | ")), 2, r)


INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))
APP_DB = os.environ.get("TT_TEST_APP_DB", "/workspace/techtrack-fresh/migration-test/fresh-start.db")
HAVE_INDEX = os.path.exists(os.path.join(INDEX, "index.sqlite"))


@unittest.skipUnless(HAVE_INDEX, "index not on this box")
class TestGeneratedTablesReproducible(unittest.TestCase):
    def test_build_terms_matches_committed(self):
        from pagefinder import build_terms
        with tempfile.TemporaryDirectory() as d:
            build_terms.main(["--index", os.path.join(INDEX, "index.sqlite"), "--out", d])
            for name in ("word_forms.tsv", "compounds.tsv", "acronyms.tsv"):
                self.assertTrue(filecmp.cmp(os.path.join(d, name), os.path.join(T.TERMS_DIR, name), shallow=False), name)


@unittest.skipUnless(HAVE_INDEX and os.path.exists(APP_DB), "index / app DB not on this box")
class TestRealLibraryVocabulary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gd_pages
        cls.f = gd_pages.LibraryPageFinder(INDEX, app_db=APP_DB)

    # v4.20.9: the old picker (pick_manual / fetch_part) is deleted; the vocabulary is checked through the tools Grok uses.
    def _call(self, name, **args):
        import gd_tools
        return json.loads(gd_tools.LibraryTools.for_finder(self.f).call(name, args)[0])

    def test_rc04_touchpad_finds_touch_screen_form(self):
        docs = self._call("find_documents", model="BAL touchscreen leveling system", unit_type="Leveling",
                          words="touchpad occasionally unresponsive during operation; auto-level doesn't consistently complete")
        self.assertIn("Touch Screen", docs["documents"][0]["title"])

    def test_rc16_coil_temp_sensor_is_freeze_sensor(self):
        hits = self._call("search_pages", words="coil temp sensor", brand="Furrion", unit_type="Air Conditioning")["hits"]
        self.assertTrue(hits)
        self.assertRegex((hits[0]["snippet"] + " " + hits[0].get("topics", "")).lower(),
                         r"freeze sensor|evaporator (temperature )?sensor")

    def test_doc_336_tag_fix(self):
        from pagefinder import build_index
        fixes = build_index.model_tag_fixes()
        self.assertIn(336, fixes)
        docs = self._call("find_documents", brand="Furrion", model="BC1715A",
                          unit_type=self.f.lib.docs["L336"]["unit_type"], words="not working")["documents"]
        self.assertNotIn("L336", [d["doc_id"] for d in docs])

if __name__ == "__main__":
    unittest.main()
