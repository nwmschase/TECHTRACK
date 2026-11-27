"""v4.20.5 double-send guard (test7 2026-11-27: turn 1 went to Grok twice, 21:17:02 and 21:17:17 UTC, same message)."""
import ast, os, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "rv_techtrack.py"), encoding="utf-8").read()


def _fn(name):
    tree = ast.parse(SRC)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {"GD_SEND_WAIT_SECONDS": 240}
    exec(compile(ast.Module([node], []), "rv_techtrack.py", "exec"), ns)
    return ns[name]


class TestSendKey(unittest.TestCase):
    def test_same_send_same_key(self):
        k = _fn("gd_send_key")
        self.assertEqual(k(None, 0, "Schwintek slide ", 0), k(None, 0, "Schwintek slide", 0))

    def test_next_turn_or_other_text_differs(self):
        k = _fn("gd_send_key")
        base = k(12, 2, "voltage good", 0)
        self.assertNotEqual(base, k(12, 4, "voltage good", 0))
        self.assertNotEqual(base, k(12, 2, "voltage low", 0))
        self.assertNotEqual(base, k(13, 2, "voltage good", 0))
        self.assertNotEqual(base, k(12, 2, "voltage good", 2048))


class TestWaitForKept(unittest.TestCase):
    def setUp(self):
        self.wait = _fn("gd_wait_for_kept_reply")
        self.now = [1000.0]
        self.clock = lambda: self.now[0]

    def test_nothing_in_flight_asks_grok(self):
        self.assertIsNone(self.wait({}, "k", clock=self.clock, sleep=lambda s: None))

    def test_kept_reply_reused(self):
        st = {"gd_last_send": {"key": "k", "reply": "R", "flow": None}}
        self.assertEqual(self.wait(st, "k", clock=self.clock)["reply"], "R")

    def test_repeat_waits_for_the_first_runs_reply(self):
        st = {"gd_send_inflight": {"key": "k", "t": 1000.0}}
        def sleep(s):                       # the first run's reply lands while the repeat waits
            self.now[0] += s
            if self.now[0] >= 1003:
                st["gd_last_send"] = {"key": "k", "reply": "first", "flow": "f"}
        self.assertEqual(self.wait(st, "k", clock=self.clock, sleep=sleep)["reply"], "first")

    def test_first_run_dies_then_repeat_asks(self):
        st = {"gd_send_inflight": {"key": "k", "t": 1000.0}}
        def sleep(s):
            self.now[0] += s
            st.pop("gd_send_inflight", None)   # the first run ended without a reply (its finally cleared the mark)
        self.assertIsNone(self.wait(st, "k", clock=self.clock, sleep=sleep))

    def test_stale_or_other_send_does_not_wait(self):
        self.assertIsNone(self.wait({"gd_send_inflight": {"key": "k", "t": 0.0}}, "k", clock=self.clock))
        self.assertIsNone(self.wait({"gd_send_inflight": {"key": "other", "t": 1000.0}}, "k", clock=self.clock))


class TestWiring(unittest.TestCase):
    def test_reply_kept_and_reused(self):
        i_key = SRC.index("_send_key = gd_send_key(")
        i_reuse = SRC.index("_kept = gd_wait_for_kept_reply(st.session_state, _send_key)", i_key)
        i_mark = SRC.index('st.session_state["gd_send_inflight"] = {"key": _send_key', i_reuse)
        i_call = SRC.index("guided_diagnostics_reply(", i_mark)
        i_store = SRC.index('st.session_state["gd_last_send"] = {"key": _send_key', i_call)
        self.assertTrue(i_key < i_reuse < i_call < i_store)

    def test_new_chat_clears_it(self):
        i_new = SRC.index("    if new_chat:")
        self.assertIn('st.session_state.pop("gd_last_send", None)', SRC[i_new:i_new + 1400])
        self.assertIn('st.session_state.pop("gd_send_inflight", None)', SRC[i_new:i_new + 1400])


if __name__ == "__main__":
    unittest.main()
