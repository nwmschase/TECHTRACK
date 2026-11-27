"""v4.20.3 (Chase 2026-11-27, test3): find_documents filtered out every slide-out manual because Grok sent unit_type
"Slide-outs" and the library category is "Slideouts". Unit types now compare without spaces, dashes, case or a plural s
(as brands already did), and filters that leave nothing widen instead of returning an empty list. Offline, no paid call."""
import json
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_prompt  # noqa: E402
import gd_tools  # noqa: E402
from gd_pages import Page  # noqa: E402

DOCS = [
    {"doc_id": "L6", "title": "Lippert In-Wall Schwintek Slide-Out Troubleshooting and Service Manual", "brand": "Lippert",
     "unit_type": "Slideouts", "doc_number": "CCD-0001769"},
    {"doc_id": "L50", "title": "Lippert Ground Control Leveling Manual", "brand": "Lippert", "unit_type": "Leveling"},
    {"doc_id": "S1", "title": "Suburban SF Furnace Service Manual", "brand": "Suburban", "unit_type": "Furnaces"},
]
PAGES = [
    Page(doc_id="L6", title=DOCS[0]["title"], page="11", sheet=11, kind="entry",
         text="Schwintek In-Wall C2 controller error codes. Green 2 red 8: encoder not providing a signal."),
    Page(doc_id="L50", title=DOCS[1]["title"], page="4", sheet=4, text="Ground Control leveling jacks controller."),
    Page(doc_id="S1", title=DOCS[2]["title"], page="9", sheet=9, text="Furnace sail switch and limit switch."),
]


def tools():
    return gd_tools.LibraryTools(gd_tools.StubLibrary(DOCS, PAGES))


class TestUnitTypeVariants(unittest.TestCase):
    def test_variants_match_slideouts(self):
        t = tools()
        d = t.lib.docs["L6"]
        for u in ("Slide-outs", "Slide Outs", "slide-out", "Slideouts", "SLIDEOUT", "Slide-Out", "slide outs"):
            self.assertTrue(t._unit_ok(d, u), u)

    def test_other_unit_types_still_excluded(self):
        t = tools()
        self.assertFalse(t._unit_ok(t.lib.docs["L6"], "Furnaces"))
        self.assertFalse(t._unit_ok(t.lib.docs["L6"], "Leveling"))
        self.assertTrue(t._unit_ok(t.lib.docs["S1"], "furnace"))

    def test_test3_query_returns_l6(self):
        r = tools().find_documents(brand="Lippert", unit_type="Slide-outs", words="Schwintek In-Wall C2 controller", limit=10)
        self.assertEqual(r["documents"][0]["doc_id"], "L6")
        self.assertEqual(r["total"], 1)
        self.assertNotIn("filters_widened", r)


class TestEmptyFiltersWiden(unittest.TestCase):
    def test_unknown_unit_type_keeps_maker_and_scores_words(self):
        r = tools().find_documents(brand="Lippert", unit_type="Slide Rooms", words="Schwintek C2 controller")
        self.assertEqual(r["documents"][0]["doc_id"], "L6")
        self.assertTrue(all(d["doc_id"].startswith("L") for d in r["documents"]))
        self.assertIn("no document has unit type 'Slide Rooms'", r["filters_widened"])

    def test_unknown_maker_and_unit_type_go_library_wide(self):
        r = tools().find_documents(brand="Schwintek Inc", unit_type="Slide Rooms", words="Schwintek In-Wall C2 controller")
        self.assertEqual(r["documents"][0]["doc_id"], "L6")
        self.assertIn("listed across the whole library", r["filters_widened"])

    def test_never_empty_when_library_has_docs(self):
        r = tools().find_documents(brand="Nobody", unit_type="Nothing", words="zzz")
        self.assertGreater(r["total"], 0)

    def test_tool_output_is_json_with_note(self):
        out, pages, err = tools().call("find_documents", json.dumps({"brand": "Lippert", "unit_type": "Slide Rooms",
                                                                       "words": "Schwintek"}))
        self.assertEqual(err, "")
        self.assertIn("filters_widened", json.loads(out))


INDEX = ROOT / "pagefinder" / "index" / "index.sqlite"
APP_DB = os.environ.get("TT_LIVE_APP_DB_COPY", "")


@unittest.skipUnless(INDEX.exists() and APP_DB and os.path.exists(APP_DB), "real index + TT_LIVE_APP_DB_COPY (live DB copy) not on this box")
class TestRealIndex(unittest.TestCase):
    def test_test3_query_on_real_index(self):
        # Own process: building a Library synced to a live DB copy changes shared pagefinder state other tests rely on.
        import subprocess
        code = ("import sys, json; sys.path.insert(0, %r)\n"
                "from pagefinder import search as s\nimport gd_tools\n"
                "lib = s.Library(db=%r, app_db=%r)\n"
                "t = gd_tools.LibraryTools(lib, keywords=gd_tools._app_keywords(lib.app_db))\n"
                "r = t.find_documents(brand='Lippert', unit_type='Slide-outs', words='Schwintek In-Wall C2 controller', limit=10)\n"
                "print(json.dumps([r['documents'][0]['doc_id'], lib.docs['L6']['doc_number']]))\n") % (str(ROOT), str(INDEX), APP_DB)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1]), ["L6", "CCD-0001769"])


class TestStateReminder(unittest.TestCase):
    def test_reminder_every_turn_last_in_context(self):
        ctx = gd_prompt.context_block(category="", model_text="X", state={"summary": "s"})
        self.assertTrue(ctx.endswith(gd_prompt.STATE_REMINDER))
        self.assertIn("<state>", gd_prompt.STATE_REMINDER)
        msgs = gd_prompt.build_messages(user_msg="hi", history=[], category="", model_text="")
        self.assertIn(gd_prompt.STATE_REMINDER, msgs[1]["content"])

    def test_primer_line9_test_or_measurement(self):
        # Fix 3 (Chase "yes", 2026-11-27): wording only; what the tech sees is a lead to the next test.
        self.assertNotIn("until a test shows the fault", gd_prompt.PRIMER)
        self.assertIn("until a test or measurement shows the fault; what the tech sees points to the next test. "
                      "Each reply ends on the next check.", gd_prompt.PRIMER)


class TestTurnLogCarriesText(unittest.TestCase):
    """Fix 4 (Chase "yes", 2026-11-27): the published turn log carries the tech's message and Grok's reply."""

    def setUp(self):
        import test_gd_wording_2026_11_27b as w
        self.fn, self.puts = w._ns_publish()

    def _run(self, **kw):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.fn({"turn": 3, "tool_calls": []}, **kw)
        return json.loads(buf.getvalue()[len("GD_TURN "):]), json.loads(self.puts[-1][0])

    def test_message_and_reply_in_both_outputs(self):
        printed, stored = self._run(user_msg="I think I see a pinched wire", reply="Check continuity end to end.")
        for rec in (printed, stored):
            self.assertEqual(rec["tech_message"], "I think I see a pinched wire")
            self.assertEqual(rec["reply"], "Check continuity end to end.")
            self.assertEqual(rec["turn"], 3)

    def test_long_reply_cut_near_8kb_with_marker(self):
        long = "x" * 20000
        printed, _ = self._run(user_msg="hi", reply=long)
        self.assertLess(len(printed["reply"].encode("utf-8")), 8192 + 100)
        self.assertIn("[...cut here: 8192 of 20000 characters kept]", printed["reply"])
        self.assertEqual(printed["tech_message"], "hi")

    def test_multibyte_cut_is_valid_text(self):
        printed, _ = self._run(user_msg="°" * 6000, reply="ok")
        self.assertIn("cut here", printed["tech_message"])
        self.assertTrue(printed["tech_message"].startswith("°"))

    def test_log_dict_not_mutated(self):
        import io
        from contextlib import redirect_stdout
        rec = {"turn": 1}
        with redirect_stdout(io.StringIO()):
            self.fn(rec, user_msg="a", reply="b")
        self.assertEqual(rec, {"turn": 1})


if __name__ == "__main__":
    unittest.main()
