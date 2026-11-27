"""v4.20.2 wording + turn log (Chase 2026-11-27 10:11 AM PT, test2: web-first and 'not even close to a guided diagnostic
feel'). Offline: no network, no paid call. No new rules: no library-first line."""
import ast
import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gd_prompt  # noqa: E402
import gd_turn  # noqa: E402

SRC = (ROOT / "rv_techtrack.py").read_text()


class TestPrimerWording(unittest.TestCase):
    def setUp(self):
        self.p = gd_prompt.PRIMER

    def test_internet_any_point_removed(self):
        self.assertNotIn("the internet is open at any point", self.p)
        self.assertIn("The search can run again at any point.", self.p)

    def test_web_address_sentence_removed_library_kept(self):
        self.assertNotIn("a cited web address opens the whole document", self.p)
        self.assertIn("A cited library page shows the tech that exact page.", self.p)

    def test_built_on_not_led_by(self):
        self.assertNotIn("is led by that manual's pages", self.p)
        self.assertIn("a good answer is built on that manual's pages", self.p)

    def test_code_table_line(self):
        self.assertIn("A fault code table is for reference and for help planning the diagnostic steps; the checks themselves "
                      "come from the manual's test pages for that part.", self.p)

    def test_library_first_line_v4_20_4(self):
        # v4.20.2 kept the library-first rule out; Chase approved it for v4.20.4 (test6, 2026-11-27 t1647u).
        self.assertIn("Each job starts in the library: a document or page search for the unit comes before any web search; "
                      "the web is for what the library does not have.", self.p)
        self.assertIn("then, when the library has nothing that fits, goes to the internet, until it has an answer.", self.p)
        self.assertNotIn("other filters, then goes to the internet", self.p)
        self.assertEqual(self.p.count("before any web search"), 1)

    def test_walkthrough_line(self):
        line = gd_turn.HELP_MODE_LINES[gd_turn.HELP_WALKTHROUGH]
        self.assertTrue(line.endswith("one step at a time: the check to make, the reading to expect, and what each result means."))


def _ns_publish():
    tree = ast.parse(SRC)
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in ("_gd_publish_turn_log", "_gd_log_text"))
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "GD_TURN_LOG_TEXT_CAP" for t in n.targets))]
    puts = []

    class St:
        session_state = {"ask_chat_id": 7}
    ns = {"json": json, "time": __import__("time"), "st": St,
          "r2_put_bytes": lambda body, key, ct: puts.append((body, key, ct)) or True}
    exec(compile(ast.Module(body=keep, type_ignores=[]), "x", "exec"), ns)
    return ns["_gd_publish_turn_log"], puts


class TestTurnLogPublished(unittest.TestCase):
    def test_prints_and_puts_to_r2(self):
        fn, puts = _ns_publish()
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn({"turn": 1, "tool_calls": [{"name": "search_pages"}]})
        out = buf.getvalue()
        self.assertTrue(out.startswith("GD_TURN "))
        self.assertEqual(json.loads(out[len("GD_TURN "):])["turn"], 1)
        self.assertEqual(len(puts), 1)
        body, key, ct = puts[0]
        self.assertEqual(json.loads(body)["tool_calls"][0]["name"], "search_pages")
        self.assertRegex(key, r"^gd-turn-logs/\d{4}-\d{2}-\d{2}/\d{8}T\d{6}Z-\d{3}-7\.json$")
        self.assertEqual(ct, "application/json")

    def test_r2_failure_never_raises(self):
        fn, _ = _ns_publish()
        import types
        fn.__globals__["r2_put_bytes"] = lambda *a: (_ for _ in ()).throw(RuntimeError("down"))
        with redirect_stdout(io.StringIO()):
            fn({"turn": 2})

    def test_empty_log_does_nothing(self):
        fn, puts = _ns_publish()
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(None)
        self.assertEqual(buf.getvalue(), "")
        self.assertEqual(puts, [])

    def test_wired_after_run_turn_and_guarded(self):
        body = SRC.split("def _gd_official_reply(", 1)[1].split("\ndef ", 1)[0]
        call = '_gd_publish_turn_log(result.get("log"), user_msg, result.get("reply"))'
        self.assertLess(body.index("gd_turn.run_turn("), body.index(call))
        seg = body[body.index(call) - 40:]
        self.assertIn("try:", seg[:60])

    def test_no_secret_names_in_publisher(self):
        fn_src = SRC.split("def _gd_log_text(", 1)[1].split("\ndef _gd_official_reply", 1)[0]
        for s in ("XAI_API_KEY", "R2_SECRET", "R2_RW_", "st.secrets"):
            self.assertNotIn(s, fn_src)


if __name__ == "__main__":
    unittest.main()
