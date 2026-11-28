"""Double-send guard. v4.20.5 (test7): turn 1 went to Grok twice. v4.20.6 (test7b, Chase go pt1664u): the guard moved to the
server (gd_sends) so a reload / second tab cannot start a second paid run, and the reply is put in the chat as soon as it lands."""
import ast, os, sys, threading, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SRC = open(os.path.join(ROOT, "rv_techtrack.py"), encoding="utf-8").read()
import gd_sends


def _fn(name):
    tree = ast.parse(SRC)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {}
    exec(compile(ast.Module([node], []), "rv_techtrack.py", "exec"), ns)
    return ns[name]


class TestSendKey(unittest.TestCase):
    def test_same_send_same_key(self):
        k = _fn("gd_send_key")
        self.assertEqual(k("user:3", 0, "Schwintek slide ", 0), k("user:3", 0, "Schwintek slide", 0))

    def test_next_turn_or_other_text_differs(self):
        k = _fn("gd_send_key")
        base = k("user:3", 2, "voltage good", 0)
        self.assertNotEqual(base, k("user:3", 4, "voltage good", 0))
        self.assertNotEqual(base, k("user:3", 2, "voltage low", 0))
        self.assertNotEqual(base, k("user:4", 2, "voltage good", 0))
        self.assertNotEqual(base, k("user:3", 2, "voltage good", 2048))


class TestSendStore(unittest.TestCase):
    def setUp(self):
        self.now = [1000.0]
        self.s = gd_sends.SendStore(ttl=600, clock=lambda: self.now[0])

    def test_first_asks_repeat_waits_then_reuses(self):
        self.assertEqual(self.s.claim(1, "k"), ("ask", None))
        self.assertEqual(self.s.claim(1, "k"), ("wait", None))     # second press / reload while Grok answers
        self.s.finish(1, "k", reply="R", flow=None)
        st, e = self.s.claim(1, "k")
        self.assertEqual((st, e["reply"]), ("reuse", "R"))

    def test_wait_returns_reply_landing_meanwhile(self):
        self.s.claim(1, "k")
        def sleep(x):
            self.now[0] += x
            if self.now[0] >= 1003:
                self.s.finish(1, "k", reply="first")
        self.assertEqual(self.s.wait(1, "k", sleep=sleep)["reply"], "first")

    def test_first_run_dies_then_repeat_asks(self):
        self.s.claim(1, "k")
        self.s.abandon(1, "k")
        self.assertIsNone(self.s.wait(1, "k", sleep=lambda x: None))
        self.assertEqual(self.s.claim(1, "k")[0], "ask")

    def test_ttl_ten_minutes_and_users_apart(self):
        self.s.claim(1, "k"); self.s.finish(1, "k", reply="R")
        self.assertEqual(self.s.claim(2, "k")[0], "ask")           # another tech never gets this reply
        self.now[0] += 601
        self.assertEqual(self.s.claim(1, "k")[0], "ask")
        self.assertEqual(gd_sends.TTL_SECONDS, gd_sends.WAIT_SECONDS + 600)   # v4.20.9: whole turn + 10 min kept

    def test_commit_once_and_unseen(self):
        self.s.claim(1, "k"); self.s.finish(1, "k", reply="R", turns=0)
        self.assertEqual([e["reply"] for e in self.s.unseen(1)], ["R"])
        self.assertTrue(self.s.take_commit(1, "k"))
        self.assertFalse(self.s.take_commit(1, "k"))
        self.s.mark_seen(1, "k")
        self.assertEqual(self.s.unseen(1), [])

    def test_failure_reply_not_reused(self):
        self.s.claim(1, "k"); self.s.finish(1, "k", reply="could not reach the AI")
        self.s.forget(1, "k")
        self.assertEqual(self.s.claim(1, "k")[0], "ask")
        i = SRC.index("_gd_commit_send(_done")
        self.assertIn("if _gd_reply_is_failure(reply):\n                                _sends.forget(_send_user, _send_key)",
                      SRC[i:i + 400])
        body = SRC[SRC.index("def _gd_reply_is_failure("):SRC.index("def _gd_case_copy(")]
        for name in ("gd_errors.is_error_line(reply)", "GD_OFFLINE_LINE", "index_fetch.LOADING_LINE", "index_fetch.UNAVAILABLE_LINE"):
            self.assertIn(name, body)

    def test_clear_user(self):
        self.s.claim(1, "k"); self.s.finish(1, "k", reply="R")
        self.s.clear_user(1)
        self.assertEqual(self.s.claim(1, "k")[0], "ask")

    def test_two_threads_only_one_asks(self):
        out, bar = [], threading.Barrier(8)
        def go():
            bar.wait()
            out.append(self.s.claim(1, "k")[0])
        ts = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(out.count("ask"), 1)

    def test_store_survives_module_reload(self):
        import importlib
        mod = importlib.import_module("gd_sends")
        a = mod.store()
        mod = importlib.reload(mod)
        self.assertIs(mod.store(), a)


class TestWiring(unittest.TestCase):
    def setUp(self):
        self.i0 = SRC.index("_send_key = gd_send_key(f\"user:{_send_user}\"")
        self.block = SRC[self.i0:SRC.index("st.rerun()", self.i0)]

    def test_claim_before_call_finish_and_commit_right_after(self):
        b = self.block
        i_claim = b.index("_sends.claim(_send_user, _send_key)")
        i_call = b.index("guided_diagnostics_reply(")
        i_finish = b.index("_sends.finish(", i_call)
        i_commit = b.index("_gd_commit_send(_done", i_finish)
        self.assertTrue(i_claim < i_call < i_finish < i_commit)
        # nothing is drawn between the reply landing and it going into the chat + database
        self.assertNotIn("st.", b[i_finish:i_commit].replace("st.session_state", ""))

    def test_commit_saves_to_db_without_drawing(self):
        body = SRC[SRC.index("def _gd_commit_send("):SRC.index("def _gd_show_unseen_replies(")]
        self.assertIn("persist_ask_turn(", body)
        for draw in ("st.image", "st.markdown", "st.caption", "st.spinner", "st.warning", "st.rerun"):
            self.assertNotIn(draw, body)

    def test_unseen_shown_before_history_and_new_chat_clears(self):
        i_unseen = SRC.index("_gd_show_unseen_replies(user[\"id\"])")
        i_hist = SRC.index('history = st.session_state.get("ask_chat") or []', i_unseen)
        self.assertLess(i_hist - i_unseen, 400)
        i_new = SRC.index("    if new_chat:")
        self.assertIn("gd_sends.store().clear_user(user[\"id\"])", SRC[i_new:i_new + 1400])


if __name__ == "__main__":
    unittest.main()


class _St:
    def __init__(self):
        self.session_state = {}


class TestCommitAndUnseen(unittest.TestCase):
    """A reply whose run was stopped before it reached the chat is shown (and saved once) by the next run, also after a reload."""

    def _ns(self, store):
        import types
        tree = ast.parse(SRC)
        names = {"_gd_commit_send", "_gd_show_unseen_replies", "_gd_restore_case", "_gd_mark_seen"}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        saved = []
        fake_sends = types.SimpleNamespace(store=lambda: store)
        ns = {"st": _St(), "saved": saved,
              "persist_ask_turn": lambda uid, cid, cat, model, um, rep: (saved.append((cid, um, rep)) or 77),
              "save_gd_work_order": lambda *a, **k: None, "_gd_record": lambda: {"state": {}},
              "_gd_cited_page_refs": lambda c: list(c or []), "_gd_turn_picture": lambda m, r, e: {"ref": {}},
              "_gd_reply_is_failure": lambda r: False}
        exec(compile(ast.Module(nodes, []), "rv_techtrack.py", "exec"), ns)
        sys.modules["gd_sends"], self._real = fake_sends, sys.modules.get("gd_sends")
        return ns

    def tearDown(self):
        sys.modules["gd_sends"] = self._real

    def _finished(self, store):
        store.claim(5, "k")
        return store.finish(5, "k", reply="Check the Motor 2 harness.", msg="slide moves crooked", turns=0, flow=None,
                            cited=[{"doc_id": "L6", "page": "11"}], case={"state": {"x": 1}}, chat_id=None)

    def test_stopped_run_reply_shown_on_reload_and_saved_once(self):
        store = gd_sends.SendStore()
        self._finished(store)                  # run A: Grok returned, then the run was stopped (no commit)
        ns = self._ns(store)                   # a fresh session (reload): empty chat
        ns["_gd_show_unseen_replies"](5)
        hist = ns["st"].session_state["ask_chat"]
        self.assertEqual([m["role"] for m in hist], ["user", "assistant"])
        self.assertEqual(hist[1]["content"], "Check the Motor 2 harness.")
        self.assertEqual(len(ns["saved"]), 1)
        self.assertEqual(ns["st"].session_state["ask_chat_id"], 77)
        self.assertEqual(ns["st"].session_state["gd_pin_store"]["gd_case"], {"state": {"x": 1}})
        ns["_gd_show_unseen_replies"](5)       # the next rerun: nothing doubled
        self.assertEqual(len(ns["st"].session_state["ask_chat"]), 2)
        ns["_gd_mark_seen"](5, hist)
        self.assertEqual(store.unseen(5), [])

    def test_reused_reply_already_saved_is_not_saved_again(self):
        store = gd_sends.SendStore()
        e = self._finished(store)
        self.assertTrue(store.take_commit(5, "k"))   # run A saved it
        ns = self._ns(store)
        ns["_gd_commit_send"](e, 5, persist=store.take_commit(5, "k"))
        self.assertEqual(ns["saved"], [])
        self.assertEqual(len(ns["st"].session_state["ask_chat"]), 2)

    def test_other_chat_turn_not_touched(self):
        store = gd_sends.SendStore()
        self._finished(store)
        ns = self._ns(store)
        ns["st"].session_state["ask_chat"] = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
        ns["_gd_show_unseen_replies"](5)       # this session is at another turn: the kept reply is not pushed in
        self.assertEqual(len(ns["st"].session_state["ask_chat"]), 2)
        self.assertEqual(ns["saved"], [])
