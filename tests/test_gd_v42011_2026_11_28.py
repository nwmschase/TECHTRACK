"""v4.20.11 (Chase t1741u, 2026-11-28 "double triple check"): audit fixes with no product change. Calls Grok asked for on the
last (tools off) round are not run; the app's picture-page crash and a library tool crash are tagged GD_FALLBACK lines; the
app's own failed-turn line is not sent back to Grok as Grok's words; the turn log is
published after the reply-findings / cited-ledger steps; the never-filled notes_next field is gone; the state format says
what the code does with `summary` and `cited`. No paid calls."""
import contextlib
import io
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import importlib  # noqa: E402

import gd_prompt  # noqa: E402
import gd_turn  # noqa: E402
from gd_fixtures import StubPageFinder  # noqa: E402
from gd_pages import Page  # noqa: E402
from test_fresh_core import FakeRespond, block  # noqa: E402

APP = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
FRIDGE = [{"doc_id": "L1", "title": "Norcold Fridge Service Manual", "brand": "Norcold", "unit_type": "refrigerator",
           "doc_type": "service-manual"}]


def _finder():
    return StubPageFinder(manuals=FRIDGE, pages=[Page(doc_id="L1", title=FRIDGE[0]["title"], page=str(n), sheet=n,
                                                      text=f"Cooling unit check step {n}", kind="entry") for n in range(1, 9)])


def _errors_modules():
    import gd_tools
    return list({id(m): m for m in (gd_turn.gd_errors, gd_tools.gd_errors, importlib.import_module("gd_errors"))}.values())


class TestLastRoundCallsNotRun(unittest.TestCase):
    def test_calls_on_the_tools_off_round_are_not_run_or_cited(self):
        n = gd_turn.SAFETY_CEILING_CALLS
        script = [[("read_pages", {"doc_id": "L1", "sheets": [i + 1]})] for i in range(n)]
        store = {}
        with contextlib.redirect_stdout(io.StringIO()):
            r = gd_turn.run_turn("fridge warm", "Refrigerators", "Norcold N8", [], finder=_finder(),
                                 respond_fn=FakeRespond(script), store=store, log_path="", web_fetch=lambda u, w: [])
        reads = [t for t in r["tool_calls"] if t.get("tool") == "read_pages"]
        self.assertEqual(len(reads), n - 1)                       # the last round's read_pages never ran
        self.assertNotIn(f"L1#{n}", store[gd_turn.STORE_KEY]["read_order"])
        self.assertTrue(any("not run: read_pages" in p for p in r["problems"]))
        self.assertIn(gd_turn.T_SAFETY_CEILING, [t["trigger"] for t in r["triggers"]])
        self.assertEqual(r["reply"], gd_turn.CEILING_REPLY)


class TestNoSilentCrash(unittest.TestCase):
    def test_tool_crash_is_a_tagged_fallback(self):
        import gd_tools
        lib = gd_tools.LibraryTools.for_finder(_finder())
        lib.search_pages = lambda **k: 1 / 0
        for m in _errors_modules():
            m.take_fallbacks()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            text, pages, err = lib.call("search_pages", {"words": "fan"})
        self.assertIn("ZeroDivisionError", json.loads(text)["error"])
        self.assertTrue(err)
        self.assertIn("GD_FALLBACK", out.getvalue())
        self.assertIn("tool_crash", [f["where"] for m in _errors_modules() for f in m.take_fallbacks()])

    def test_picture_page_crash_is_a_tagged_fallback(self):
        src = (ROOT / "gd_turn.py").read_text(encoding="utf-8")
        a = src.index("app_page = app_open_picture_page(case, library, user_msg)")
        self.assertIn('gd_errors.fallback("picture_page"', src[a:a + 500])


class TestFailedTurnLines(unittest.TestCase):
    def test_app_error_line_is_not_sent_to_grok(self):
        ge = importlib.import_module("gd_errors")
        line = ge.tech_line(ge.KIND_TIMEOUT)
        hist = [{"role": "user", "content": "fridge warm"}, {"role": "assistant", "content": line},
                {"role": "user", "content": "fridge warm"}, {"role": "assistant", "content": "Check the fan."}]
        kept = gd_prompt.recent_history(hist)
        self.assertNotIn(line, [m["content"] for m in kept])
        self.assertEqual([m["content"] for m in kept], ["fridge warm", "fridge warm", "Check the fan."])

    def test_turn_log_published_after_findings_and_ledger(self):
        a = APP.index("def _gd_official_reply(")
        body = APP[a:APP.index("\ndef gd_send_key(", a)]
        pub = body.index('_gd_publish_turn_log(result.get("log")')
        self.assertGreater(pub, body.index("record_reply_findings"))
        self.assertGreater(pub, body.index('gd_errors.fallback("cited_ledger"'))
        self.assertEqual(body.count('_gd_publish_turn_log(result.get("log")'), 1)


class TestDeadFieldsGone(unittest.TestCase):
    def test_notes_next_is_gone(self):
        self.assertNotIn('"notes_next": []', (ROOT / "gd_turn.py").read_text(encoding="utf-8"))
        self.assertNotIn("notes_next", gd_turn.new_case("", "", ""))
        store = {gd_turn.STORE_KEY: {**gd_turn.new_case("Refrigerators", "Norcold N8", "x"), "notes_next": ["old"]}}
        with contextlib.redirect_stdout(io.StringIO()):
            gd_turn.run_turn("fridge warm", "Refrigerators", "Norcold N8", [], finder=_finder(),
                             respond_fn=FakeRespond(["ok " + block()]), store=store, log_path="", web_fetch=lambda u, w: [])
        self.assertNotIn("notes_next", store[gd_turn.STORE_KEY])

    def test_state_format_matches_merge(self):
        self.assertNotIn("`summary` and `cited` are stored fresh each turn", gd_prompt.STATE_FORMAT)
        self.assertIn("except `cited`, which holds this turn's citations", gd_prompt.STATE_FORMAT)


if __name__ == "__main__":
    unittest.main()
