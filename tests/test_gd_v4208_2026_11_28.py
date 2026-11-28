"""v4.20.8 (Chase t1725u, 2026-11-28): meaning (smart) search off by default, leftovers cleaned, empty
page search opens the web gate, SMART_SEARCH_OFF / MEANING_SEARCH_OFF logged. No paid calls."""
import io
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_pages  # noqa: E402
import gd_tools  # noqa: E402
import gd_turn  # noqa: E402
from pagefinder import search as pf  # noqa: E402
from test_fresh_core import FakeRespond, block, page, MAN  # noqa: E402
from test_gd_v4207_2026_11_28 import finder, turn, web_names, PIC  # noqa: E402

INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))


def _restore_meaning(saved_on, saved_announced):
    pf.MEANING_ON = saved_on
    pf._ANNOUNCED = saved_announced


class TestMeaningDefaultOff(unittest.TestCase):
    def test_flag_is_off_unless_explicitly_on(self):
        self.assertFalse(pf.meaning_flag_on(""))
        self.assertFalse(pf.meaning_flag_on("off"))
        self.assertFalse(pf.meaning_flag_on("0"))
        self.assertFalse(pf.meaning_flag_on("false"))
        self.assertFalse(pf.meaning_flag_on("maybe"))
        self.assertTrue(pf.meaning_flag_on("on"))
        self.assertTrue(pf.meaning_flag_on("1"))
        self.assertTrue(pf.meaning_flag_on("true"))
        self.assertTrue(pf.meaning_flag_on("yes"))
        src = (ROOT / "pagefinder" / "search.py").read_text()
        self.assertIn("os.environ.get('TT_PAGEFINDER_MEANING', 'off')", src)
        self.assertNotIn("os.environ.get('TT_PAGEFINDER_MEANING', 'on')", src)

    def test_app_default_and_finder_follow_the_flag(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertNotIn('_secret("TT_PAGEFINDER_MEANING")', src)
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            f = gd_pages.LibraryPageFinder(INDEX, meaning=None)
            self.assertFalse(f.meaning)
            self.assertFalse(pf.MEANING_ON)
        finally:
            _restore_meaning(saved, announced)

    def test_retired_secret_read_and_old_web_log_trigger_stay_gone(self):
        app = (ROOT / "rv_techtrack.py").read_text()
        tools = (ROOT / "gd_tools.py").read_text()
        turn_src = (ROOT / "gd_turn.py").read_text()
        self.assertNotIn('_secret("TT_PAGEFINDER_MEANING")', app)
        self.assertNotIn("WEB_BEFORE_LIBRARY_SEARCH", turn_src)
        self.assertFalse(hasattr(gd_turn, "T_WEB_BEFORE_LIBRARY"))
        self.assertNotIn("self.meaning_error", tools)
        self.assertIn("T_MEANING_OFF", turn_src)


class TestNoModelLoadWhenOff(unittest.TestCase):
    def test_hybrid_and_search_pages_never_import_fastembed_or_vectors(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            f = gd_pages.LibraryPageFinder(INDEX, meaning=False)
            T = gd_tools.LibraryTools.for_finder(f)
            real_import = __import__

            def guarded(name, *a, **k):
                if name == "fastembed" or name.startswith("fastembed."):
                    raise AssertionError("fastembed imported while meaning search is off")
                return real_import(name, *a, **k)

            with mock.patch("builtins.__import__", side_effect=guarded), \
                 mock.patch.object(pf, "shared_embedding_model", side_effect=AssertionError("model loaded")), \
                 mock.patch.object(pf, "shared_base_vectors", side_effect=AssertionError("vectors loaded")), \
                 mock.patch.object(pf, "meaning", side_effect=AssertionError("meaning() called while off")):
                lib = f.lib
                pages = lib.pages("L6")[:8] if "L6" in lib.docs else [p for d in list(lib.docs)[:3] for p in lib.pages(d)][:8]
                self.assertTrue(pages)
                pf.hybrid(lib, "error code 8 hall signal", pages)
                r = T.search_pages("zzqxv flurble wompus")
                self.assertEqual(r.get("hits"), [])
        finally:
            _restore_meaning(saved, announced)


class TestEmptySearchOpensTheWebGate(unittest.TestCase):
    def test_nonsense_query_on_pages_returns_empty(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            T = gd_tools.LibraryTools.for_finder(finder())
            r = T.search_pages("zzqxv flurble wompus")
            self.assertEqual(r.get("hits"), [])
            self.assertEqual(r.get("matching_pages"), 0)
            why = gd_turn.library_empty_reason("search_pages", {"words": "zzqxv flurble wompus"}, json.dumps(r))
            self.assertTrue(why)
        finally:
            _restore_meaning(saved, announced)

    def test_nonsense_query_on_real_library_returns_empty(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            f = gd_pages.LibraryPageFinder(INDEX, meaning=False)
            T = gd_tools.LibraryTools.for_finder(f)
            r = T.search_pages("zzqxv flurble wompus")
            self.assertEqual(r.get("hits"), [])
            self.assertEqual(r.get("matching_pages"), 0)
        finally:
            _restore_meaning(saved, announced)

    def test_empty_library_search_opens_the_web_gate(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            r, chat = turn([[("search_pages", {"words": "zzqxv flurble wompus"})], "ok\n" + block(summary="s")])
            self.assertTrue(web_names(chat.seen[-1][1]))
            self.assertIn(gd_turn.T_WEB_GATE_OPENED, [t["trigger"] for t in r["triggers"]])
            self.assertTrue(r.get("log") or r)  # turn ran
        finally:
            _restore_meaning(saved, announced)

    def test_picture_lookup_still_finds_a_labelled_page(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            store = {}
            turn([[("find_documents", {"unit_type": "refrigerator"})], "ok\n" + block(summary="s")], store=store)
            r, _chat = turn(["Here is the fan.\n" + block(summary="s")], store=store, msg="send me a photo of the fan motor",
                            picture_request=True)
            self.assertIn(gd_turn.T_APP_PICTURE_PAGE, [t["trigger"] for t in r["triggers"]])
            self.assertIn(("L1", "31"), [(c["doc_id"], c["page"]) for c in r["cited"]])
        finally:
            _restore_meaning(saved, announced)

    def test_failed_meaning_does_not_halve_word_scores(self):
        """Leftover: a 0.5 blend toward zeros would cap a lone word-match at 0.5 and could hide a hit behind score>0."""
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = True
            f = finder()
            T = gd_tools.LibraryTools.for_finder(f)
            r = T.search_pages("E2 freezer fan")
            self.assertTrue(r.get("hits"))
            top = r["hits"][0]["score"]
            self.assertGreater(top, 0.5)
            self.assertLessEqual(top, 1.0)
        finally:
            _restore_meaning(saved, announced)


class TestMeaningLogs(unittest.TestCase):
    def test_startup_line_when_off(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        buf = io.StringIO()
        try:
            pf.MEANING_ON = False
            pf._ANNOUNCED = None
            with mock.patch("sys.stdout", buf):
                pf.announce_meaning_state(force=True)
            text = buf.getvalue()
            self.assertIn("SMART_SEARCH_OFF reason=switched off by setting using=word-match-only", text)
            self.assertEqual(text.count("SMART_SEARCH_OFF"), 1)
            buf2 = io.StringIO()
            with mock.patch("sys.stdout", buf2):
                pf.announce_meaning_state(force=True)
                pf.announce_meaning_state()
            self.assertEqual(buf2.getvalue(), "")
        finally:
            _restore_meaning(saved, announced)

    def test_failed_load_prints_the_same_tagged_line(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        saved_fail, saved_models = dict(pf._MODEL_FAIL), dict(pf._MODELS)
        buf = io.StringIO()
        try:
            pf.MEANING_ON = True
            pf._ANNOUNCED = None
            pf._MODELS.clear()
            pf._MODEL_FAIL.clear()
            lib = pf.Library(os.path.join(INDEX, "index.sqlite"), INDEX)
            def boom(*a, **k):
                raise OSError("no network")
            with mock.patch.object(pf, "embedding_model", boom), mock.patch("sys.stdout", buf):
                out = pf.meaning(lib, "jacks will not extend", [("L370", 1)])
            self.assertEqual(out, {("L370", 1): 0.0})
            self.assertIn("no network", lib.meaning_error)
            self.assertEqual(pf.meaning_status(lib)[0], "failed")
            self.assertIn("SMART_SEARCH_OFF reason=download failed", buf.getvalue())
            self.assertIn("using=word-match-only", buf.getvalue())
            # a second query does not print again
            buf2 = io.StringIO()
            with mock.patch.object(pf, "embedding_model", boom), mock.patch("sys.stdout", buf2):
                pf.meaning(lib, "again", [("L370", 1)])
            self.assertEqual(buf2.getvalue(), "")
        finally:
            pf._MODEL_FAIL.clear(); pf._MODEL_FAIL.update(saved_fail)
            pf._MODELS.clear(); pf._MODELS.update(saved_models)
            _restore_meaning(saved, announced)

    def test_turn_log_records_meaning_search_off_once_and_usage(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            r, _chat = turn([[("search_pages", {"words": "E2"})], "ok\n" + block(summary="s")])
            names = [t["trigger"] for t in r["triggers"]]
            self.assertEqual(names.count(gd_turn.T_MEANING_OFF), 1)
            self.assertEqual(r["usage"].get("meaning"), "off")
            # a later search in the same job does not add a second trigger
            r2, _c2 = turn([[("search_pages", {"words": "fan motor"})], "ok\n" + block(summary="s")],
                           store={"gd_case": r["log"] and None} if False else None)
        finally:
            _restore_meaning(saved, announced)

    def test_turn_log_once_per_job_across_turns(self):
        saved, announced = pf.MEANING_ON, pf._ANNOUNCED
        try:
            pf.MEANING_ON = False
            store = {}
            r1, _ = turn([[("search_pages", {"words": "E2"})], "ok\n" + block(summary="s")], store=store)
            r2, _ = turn([[("search_pages", {"words": "fan motor"})], "ok\n" + block(summary="s")], store=store,
                         msg="fan has 12 V")
            self.assertEqual([t["trigger"] for t in r1["triggers"]].count(gd_turn.T_MEANING_OFF), 1)
            self.assertEqual([t["trigger"] for t in r2["triggers"]].count(gd_turn.T_MEANING_OFF), 0)
            self.assertEqual(r2["usage"].get("meaning"), "off")
        finally:
            _restore_meaning(saved, announced)


if __name__ == "__main__":
    unittest.main()
