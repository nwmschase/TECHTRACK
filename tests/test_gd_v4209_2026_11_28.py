"""v4.20.9 (Chase t1727u / t1729u, 2026-11-28; audit H1 H2 H3 M6 L1, M7 M10): New chat clears the job, the wrap-up and
the access question fire only at a real end of job, real error lines and logs, no silent fallbacks, the double-send guard
covers the whole turn, the dead code is deleted, one TT_STARTUP line, the code is the one source of the model.
No paid calls."""
import contextlib
import io
import json
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_errors  # noqa: E402
import gd_llm  # noqa: E402
import gd_sends  # noqa: E402
import gd_state  # noqa: E402
import gd_story  # noqa: E402
import gd_turn  # noqa: E402
from gd_fixtures import StubPageFinder  # noqa: E402
from gd_pages import Page  # noqa: E402
from test_fresh_core import FakeRespond, block  # noqa: E402

APP = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")


def _slice(src, start, end):
    a = src.index(start)
    return src[a:src.index(end, a + len(start))]


class _Session(dict):
    """A dict that also allows attribute access, like st.session_state."""
    __getattr__ = dict.get


FURNACE = [{"doc_id": "L9", "title": "Suburban NT Furnace Service Manual", "brand": "Suburban", "unit_type": "furnace",
            "doc_type": "service-manual"}]
FRIDGE = [{"doc_id": "L1", "title": "Norcold Fridge Service Manual", "brand": "Norcold", "unit_type": "refrigerator",
           "doc_type": "service-manual"}]


def _furnace_finder():
    return StubPageFinder(manuals=FURNACE, pages=[Page(doc_id="L9", title=FURNACE[0]["title"], page="12", sheet=12,
                                                      text="Sail switch test: 0.5 in. wc", kind="entry")])


def _fridge_finder():
    return StubPageFinder(manuals=FRIDGE, pages=[Page(doc_id="L1", title=FRIDGE[0]["title"], page="5", sheet=5,
                                                     text="Cooling unit check", kind="entry")])


def _app_reset(session):
    """Run the app's own New chat reset (reset_guided_diagnostics_session) on a fake session."""
    code = _slice(APP, "def clear_ask_source_state():", "\n# ---------------- GD OFFICIAL METHOD")
    ns = {"st": types.SimpleNamespace(session_state=session)}
    exec(compile(code, "rv_slice", "exec"), ns)
    ns["reset_guided_diagnostics_session"]()


class TestNewChatClearsTheJob(unittest.TestCase):
    def test_furnace_then_new_chat_then_fridge_carries_nothing_over(self):
        session = _Session()
        store = session.setdefault("gd_pin_store", {})
        furnace_reply = ("Sail switch failed. " + block(cause="failed sail switch (L9 p.12)", closed=True, order_part="sail switch",
                                                        cited=[{"doc_id": "L9", "page": "12"}], summary="furnace job"))
        gd_turn.run_turn("furnace no heat, blower runs", "Furnaces", "Suburban NT-20SEQT", [], finder=_furnace_finder(),
                         respond_fn=FakeRespond([[("read_pages", {"doc_id": "L9", "pages": ["12"]})], furnace_reply]),
                         store=store, log_path="", web_fetch=lambda u, w: [])
        case = store[gd_turn.STORE_KEY]
        case["state"].update(access_asked=True, access_answer="pulled the furnace", wrapup="repair")
        session.update(gd_case_chat_id=7, gd_access_prompt=True, gd_access_text="x", gd_last_cited=[{"doc_id": "L9"}],
                       gd_last_turn_pages=["p"], gd_last_drawn=[("L9", 12)], ask_chat=[{"role": "user", "content": "f"}])
        self.assertTrue(case["state"]["closed"])

        _app_reset(session)
        for k in gd_state.JOB_SESSION_KEYS:
            self.assertNotIn(k, session, k)

        chat = FakeRespond(["Check the cooling unit. " + block(summary="fridge job")])
        store2 = session.setdefault("gd_pin_store", {})
        gd_turn.run_turn("fridge not cooling on gas", "Refrigerators", "Norcold N8", [], finder=_fridge_finder(),
                         respond_fn=chat, store=store2, log_path="", web_fetch=lambda u, w: [])
        st2 = store2[gd_turn.STORE_KEY]["state"]
        self.assertEqual(st2.get("cause"), "")
        self.assertFalse(st2.get("closed"))
        self.assertNotIn("access_answer", st2)
        self.assertNotIn("access_asked", st2)
        self.assertEqual(st2.get("order_part"), "")
        self.assertEqual(store2[gd_turn.STORE_KEY]["complaint"], "fridge not cooling on gas")
        self.assertEqual(store2[gd_turn.STORE_KEY]["read"], {})
        sent = json.dumps(chat.seen[0][0], default=str)
        for leftover in ("sail switch", "Suburban", "pulled the furnace", "furnace job", "blower runs"):
            self.assertNotIn(leftover, sent, leftover)

    def test_open_saved_chat_clears_the_job_and_the_dead_flag_is_gone(self):
        body = _slice(APP, 'if cols[1].button("Open", key=f"open_ask_{ch.id}"):', 'st.session_state["ask_chat"] = hist')
        self.assertIn("_gs.clear_job_session(st.session_state)", body)
        reset = _slice(APP, "def reset_guided_diagnostics_session():", "\n# ---------------- GD OFFICIAL METHOD")
        self.assertIn("_gs.clear_job_session(st.session_state)", reset)
        # the old reset behind ask_clear_model never fired after v4.19.39: deleted, and it must not come back
        self.assertNotIn("ask_clear_model", APP)
        self.assertNotIn("ask_clear_cat", APP)
        for k in ("gd_pin_store", "gd_case_chat_id", "gd_access_prompt", "gd_access_text", "gd_last_cited",
                  "gd_last_turn_pages", "gd_last_drawn"):
            self.assertIn(k, gd_state.JOB_SESSION_KEYS)


class TestWrapupOnlyAtTheRealEnd(unittest.TestCase):
    NOT_THE_END = ("what do you recommend I check next?", "what do you recommend I check next",
                   "the fan is not working now", "fan is still not working now",
                   "do you recommend replacing the board or checking voltage first?",
                   "is the repair complete?", "should I recommend replacing the board?",
                   "no 12 v on that wire from thermostat", "it isn't working now", "what next")

    def test_everyday_wording_does_not_trigger(self):
        for msg in self.NOT_THE_END:
            self.assertEqual(gd_story.wrapup_due({"state": {}}, msg), "", msg)
            self.assertEqual(gd_story.tech_recommendation([{"role": "user", "content": msg}]), "", msg)

    def test_grok_saying_done_before_the_tech_verifies_does_not_trigger(self):
        self.assertEqual(gd_story.wrapup_due({"state": {"repair": {"done": True, "verified": False}}}, "ok"), "")
        self.assertEqual(gd_story.wrapup_due({"state": {"repair": {"done": True, "verified": True}}}, "ok"), "repair")
        self.assertEqual(gd_story.wrapup_due({"state": {"closed": True}}, "ok"), "repair")

    def test_plain_statements_and_the_close_buttons_trigger(self):
        self.assertEqual(gd_story.wrapup_due({"state": {}}, "diag complete"), "diag")
        self.assertEqual(gd_story.wrapup_due({"state": {}}, "I recommend replacing the control board."), "diag")
        self.assertEqual(gd_story.wrapup_due({"state": {}}, "repair complete, furnace heating"), "repair")
        self.assertEqual(gd_story.wrapup_due({"state": {}}, "", close_action="diag"), "diag")
        self.assertEqual(gd_story.wrapup_due({"state": {}}, "", close_action="repair"), "repair")
        self.assertEqual(gd_story.wrapup_due({"state": {"access_asked": True}}, "", close_action="repair"), "")
        self.assertIn('GD_CLOSE_DIAG_BUTTON = "✅ Diagnosis complete"', APP)
        self.assertIn('_gd_close_job(_close, user["id"], category_name, ask_model or "")', APP)

    def test_old_substring_triggers_are_deleted(self):
        for gone in ("_DONE_PHRASES", "_REPAIR_PHRASES"):
            self.assertFalse(hasattr(gd_story, gone), gone)
        self.assertNotIn("_DONE_PHRASES", (ROOT / "gd_story.py").read_text(encoding="utf-8"))


class TestAccessAnswerIsNotSwallowed(unittest.TestCase):
    ASKED = [{"role": "user", "content": "diag complete"}, {"role": "assistant", "content": gd_story.access_question("diag")}]

    def test_only_when_the_app_asked_and_the_reply_answers_it(self):
        self.assertTrue(gd_story.answers_access("pulled the fridge out and took the battery box covers off", self.ASKED))
        self.assertTrue(gd_story.answers_access("nothing removed", self.ASKED))
        self.assertTrue(gd_story.answers_access("I cited it already", self.ASKED))
        for msg in ("the fan is not working now", "what do you recommend I check next?", "fan still runs, what next"):
            self.assertFalse(gd_story.answers_access(msg, self.ASKED), msg)
        later = self.ASKED + [{"role": "user", "content": "q"}, {"role": "assistant", "content": "Check the fan."}]
        self.assertFalse(gd_story.answers_access("nothing removed", later))   # the last reply was not the access question

    def test_app_gate_uses_the_check(self):
        self.assertIn("_access_turn = _access_open and not photo_bytes and _story.answers_access(msg, history)", APP)
        self.assertIn("GD_ACCESS_NOT_ANSWER", APP)


class TestRealErrors(unittest.TestCase):
    def _run(self, exc):
        code = _slice(APP, "def _gd_official_reply(", "\ndef gd_send_key(")
        published = []

        def respond(items, tools, tool_choice=None):
            raise exc

        stub = _fridge_finder()
        ns = {"st": types.SimpleNamespace(session_state={}), "_gd_official_respond": respond, "_gd_official_chat": None,
              "_gd_page_finder": lambda: stub, "_gd_page_image_fn": lambda: None, "GD_USAGE_LOG": "",
              "record_cited_pages": lambda line: None, "gd_llm": gd_llm, "_secret": lambda k: None,
              "_gd_secret_values": lambda: ["SECRETKEY123"], "_gd_fb": lambda *a, **k: None,
              "_gd_publish_turn_log": lambda log, *a: published.append(log)}
        exec(compile(code, "rv_slice", "exec"), ns)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            reply = ns["_gd_official_reply"]("fridge warm", "Refrigerators", "Norcold N8", [], {})
        return reply, published, out.getvalue()

    def test_timeout(self):
        reply, pub, out = self._run(gd_llm.LLMProviderError("xAI: timed out after 240s.", kind="timeout"))
        self.assertTrue(reply.startswith(gd_errors.ERROR_PREFIX))
        self.assertIn("took too long", reply)
        self.assertEqual(pub[-1]["error"]["type"], "timeout")
        self.assertIn("GD_ERROR ", out)

    def test_xai_error_with_status(self):
        reply, pub, out = self._run(gd_llm.LLMProviderError("xAI: 429 rate limit", kind="xai_error", status=429))
        self.assertIn("xAI error 429", reply)
        self.assertEqual(pub[-1]["event"], "turn_failed")
        self.assertEqual(pub[-1]["error"]["status"], 429)

    def test_app_bug_is_named_logged_with_a_traceback_and_keys_are_masked(self):
        reply, pub, out = self._run(KeyError("SECRETKEY123 missing"))
        self.assertIn("a bug in the app (KeyError)", reply)
        rec = pub[-1]["error"]
        self.assertEqual(rec["type"], "app_bug")
        self.assertTrue(rec["traceback"])
        self.assertNotIn("SECRETKEY123", out + json.dumps(pub))

    def test_generic_line_is_gone_and_failures_are_never_reused(self):
        self.assertNotIn("GD_UNAVAILABLE_LINE", APP)
        self.assertNotIn("could not reach the AI right now", APP)
        self.assertTrue(gd_errors.is_error_line(gd_errors.tech_line("timeout")))
        self.assertIn("if gd_errors.is_error_line(reply):", APP)

    def test_respond_tags_its_errors(self):
        with self.assertRaises(gd_llm.LLMProviderError) as cm:
            gd_llm.respond([], [], secret_fn=lambda k: "")
        self.assertEqual(cm.exception.kind, "no_key")


class TestNoSilentFallbacks(unittest.TestCase):
    def test_fallback_prints_and_queues_for_the_turn_log(self):
        gd_errors.take_fallbacks()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            gd_errors.fallback("photo_read", "x", exc=ValueError("bad KEY999X"), secrets=["KEY999X"])
        self.assertIn("GD_FALLBACK ", out.getvalue())
        self.assertNotIn("KEY999X", out.getvalue())
        got = gd_errors.take_fallbacks()
        self.assertEqual(got[0]["where"], "photo_read")
        self.assertEqual(gd_errors.take_fallbacks(), [])

    def test_publish_puts_fallbacks_in_the_turn_log(self):
        self.assertIn('log["fallbacks"] = fb', APP)

    def test_state_block_problems_and_photo_failures_are_logged(self):
        gd_errors.take_fallbacks()
        with contextlib.redirect_stdout(io.StringIO()):
            gd_turn.run_turn("fridge warm", "Refrigerators", "Norcold N8", [], finder=_fridge_finder(),
                             respond_fn=FakeRespond(["no block here"]), store={}, log_path="", web_fetch=lambda u, w: [])
            import gd_step_photo
            r = gd_step_photo.review_step_photo(b"\xff\xd8\xff", "image/jpeg", "", "", complete_fn=lambda m: 1 / 0)
        self.assertEqual(r["verdict"], "unclear")
        wheres = [f["where"] for f in gd_errors.take_fallbacks()]
        self.assertIn("state_block", wheres)
        self.assertIn("photo_read", wheres)

    def test_meaning_status_failure_is_not_reported_as_off_by_setting(self):
        broken = types.SimpleNamespace(s=types.SimpleNamespace(meaning_status=lambda lib: 1 / 0), lib=None)
        with contextlib.redirect_stdout(io.StringIO()):
            state, err = gd_turn.meaning_status(broken)
        self.assertEqual(state, "failed")
        gd_errors.take_fallbacks()

    def test_gd_path_has_no_quiet_except_left(self):
        """Every except in the GD path either logs (gd_errors / _gd_fb / emit), re-raises, reports the error back, or is
        one of the listed parse / lookup helpers whose default IS the answer (bad JSON -> no hits, no secret -> '')."""
        import ast
        allowed = {
            ("gd_llm.py", "_record_usage"), ("gd_llm.py", "default_secret"), ("gd_llm.py", "_lookup"),
            ("gd_llm.py", "_sdk_installed"), ("gd_llm.py", "_client_timeout"), ("gd_llm.py", "runner"),
            ("gd_llm.py", "_dump"), ("gd_step_photo.py", "vision_model_ids"), ("gd_page_links.py", "sheet_for"), ("gd_page_links.py", "page_refs"),
            ("gd_pages.py", "host"), ("gd_state.py", "parse"), ("gd_step_photo.py", "xai_vision_model_candidates"),
            ("gd_tools.py", "_models"), ("gd_tools.py", "call"), ("gd_tools.py", "open_web_document"),
            ("gd_turn.py", "library_empty_reason"), ("gd_turn.py", "_found_doc_ids"), ("gd_turn.py", "_empty"),
            ("gd_turn.py", "_args"), ("gd_work_orders.py", "_loads"), ("gd_official.py", "host_of"),
            ("gd_errors.py", "emit"),
        }
        found = []
        for f in sorted(ROOT.glob("gd_*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            owners = {}   # handler -> every function it sits in (a nested helper counts as its outer function too)
            for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for h in [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]:
                    owners.setdefault(h, []).append(fn.name)
            for h in [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]:
                self.assertIsNotNone(h.type, f"bare except in {f.name}:{h.lineno}")
                src = ast.unparse(h)
                logs = any(w in src for w in ("gd_errors.", "_gd_fb(", "raise", "emit(", "print(", "problems.append(",
                                              "missing.append("))
                names = owners.get(h, ["<module>"])
                if not logs and not any((f.name, n) in allowed for n in names):
                    found.append(f"{f.name}:{h.lineno} in {names[-1]}")
        self.assertEqual(sorted(set(found)), [])


class TestSendGuardCoversTheWholeTurn(unittest.TestCase):
    def test_wait_and_ttl_are_longer_than_the_longest_turn(self):
        longest = gd_turn.SAFETY_CEILING_CALLS * (gd_llm.TOOL_REQUEST_TIMEOUT_SEC + gd_llm.DEADLINE_SLACK_SEC)
        self.assertGreater(gd_sends.WAIT_SECONDS, longest)
        self.assertGreater(gd_sends.TTL_SECONDS, longest)
        self.assertGreaterEqual(longest, 6 * 240)

    def test_a_second_press_after_5_and_20_minutes_still_waits(self):
        now = [1000.0]
        s = gd_sends.SendStore(ttl=gd_sends.TTL_SECONDS, clock=lambda: now[0])
        self.assertEqual(s.claim(1, "k"), ("ask", None))
        for minutes in (5, 20, 26):
            now[0] = 1000.0 + minutes * 60
            self.assertEqual(s.claim(1, "k"), ("wait", None), minutes)
        s.finish(1, "k", reply="R")
        self.assertEqual(s.claim(1, "k")[0], "reuse")

    def test_in_flight_send_is_never_pruned_while_its_turn_can_run(self):
        now = [0.0]
        s = gd_sends.SendStore(ttl=600, clock=lambda: now[0])
        s.claim(1, "k")
        now[0] = gd_sends.WAIT_SECONDS - 1
        s._prune(now[0])
        self.assertIn((1, "k"), s.entries)

    def test_paid_photo_read_runs_after_the_guard(self):
        send = _slice(APP, 'if send or st.session_state.pop("ask_force_send", False):', "\n    if write_story and history")
        claim = send.index("_sends.claim(_send_user, _send_key)")
        photo = send.index("_photos.review_step_photo(photo_bytes, photo_mime, asked, msg)")
        self.assertLess(claim, photo)
        self.assertEqual(send.count("review_step_photo("), 1)


class TestDeadCodeStaysDeleted(unittest.TestCase):
    def test_files_are_gone(self):
        for f in ("legacy_selector.py", "rv_techtrackpr4", "scripts/picker_sweep.py"):
            self.assertFalse((ROOT / f).exists(), f)

    def test_names_are_gone_from_live_code(self):
        """Read from the code itself (names, attributes, defs, imports), so a changelog line naming what was deleted is fine."""
        import ast
        live = list(ROOT.glob("*.py")) + list((ROOT / "pagefinder").glob("*.py")) + list((ROOT / "scripts").glob("*.py"))
        used = set()
        for p in live:
            for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Name):
                    used.add(n.id)
                elif isinstance(n, ast.Attribute):
                    used.add(n.attr)
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    used.add(n.name)
                elif isinstance(n, ast.alias):
                    used.update(n.name.split("."))
                elif isinstance(n, ast.arg):
                    used.add(n.arg)
                elif isinstance(n, ast.keyword) and n.arg:
                    used.add(n.arg)
        for name in ("legacy_selector", "pick_manual", "fetch_by_part", "fetch_part", "entry_pages", "toc_pages",
                     "PROCEDURE_TREES", "PROCEDURE_FURRION_FCR_CCD_0008122", "get_procedure_node", "make_web_fn",
                     "xai_search", "http_search", "HARD_TREE_EXCLUSIVE_CHAT", "HARD_TREE", "Picked", "apply_budget",
                     "StubPageFinder", "T_STORY", "unity_gate", "ask_flow", "GD_UNAVAILABLE_LINE", "_DONE_PHRASES",
                     "_REPAIR_PHRASES", "ask_clear_model", "stage_zip_bytes", "present_photo_review"):
            self.assertNotIn(name, used, name)

    def test_story_field_is_gone(self):
        self.assertNotIn("story", gd_state.SCHEMA)
        self.assertNotIn("story", gd_state.new_state())
        prompt = (ROOT / "gd_prompt.py").read_text(encoding="utf-8")
        primer = (ROOT / "gd_primer.md").read_text(encoding="utf-8")
        self.assertNotIn('"story"', prompt)
        self.assertNotIn("`story` field", primer)
        self.assertNotIn("Grok writes the technician story", primer)
        _p, upd, probs = gd_state.parse('ok <state>{"story": "old"}</state>')
        self.assertNotIn("story", upd)


class TestStartupLineAndModel(unittest.TestCase):
    def test_startup_fields_come_from_the_code(self):
        f = gd_turn.startup_fields("v4.20.9", "abc123")
        self.assertEqual(f["model"], gd_llm.DEFAULT_XAI_MODEL)
        self.assertEqual(f["model"], "grok-4.3")                    # the model that runs is unchanged
        self.assertEqual(f["gd_temperature"], gd_llm.GD_RESPOND_TEMPERATURE)
        self.assertEqual(f["round_limit"], gd_turn.SAFETY_CEILING_CALLS)
        self.assertIn(f["smart_search"], ("on", "off"))
        self.assertEqual(f["web_gate"], "on")
        for k in ("version", "commit", "reasoning_effort"):
            self.assertIn(k, f)
        self.assertIn("_print_startup_line()", APP)
        self.assertIn("gd_errors.TAG_STARTUP", APP)

    def test_xai_model_secret_is_not_read(self):
        seen = []

        def secret(k):
            seen.append(k)
            return {"XAI_API_KEY": "k", "XAI_MODEL": "grok-other"}.get(k, "")

        class C:
            class responses:
                @staticmethod
                def create(**kw):
                    seen.append(("model", kw["model"]))
                    return {"output": [], "usage": {}}

        gd_llm.respond([], [], secret_fn=secret, client_factory=lambda *a, **k: C())
        self.assertIn(("model", "grok-4.3"), seen)
        self.assertNotIn("XAI_MODEL", seen)
        for f in ("gd_llm.py", "gd_step_photo.py", "rv_techtrack.py"):
            src = (ROOT / f).read_text(encoding="utf-8")
            self.assertNotIn('_lookup("XAI_MODEL"', src, f)
            self.assertNotIn('_secret("XAI_MODEL")', src, f)

    def test_docs_match_the_code(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("grok-4.6", readme)
        self.assertIn("grok-4.3", readme)
        self.assertIn("Each round waits at most 240 seconds", readme)
        self.assertIn("no Groq fallback on the GD path", readme)
        self.assertNotIn("The default model stays", readme)


if __name__ == "__main__":
    unittest.main()
