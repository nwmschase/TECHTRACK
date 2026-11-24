"""Chase 2026-11-24 12:50 PM: GD asks the tech up front whether he wants the manual pages pulled up or a full walkthrough.
With just the pages, it still steps in to help when he asks or gets stuck. The choice is stored in the job state and told to
Grok as one line of session context; the 'no rules' primer is unchanged. Offline: scripted fake Grok, no paid call."""
import pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import gd_prompt  # noqa: E402
import gd_story  # noqa: E402
import gd_turn  # noqa: E402
from test_fresh_core import FakeRespond, block, finder  # noqa: E402


def context(seen_items):
    return seen_items[1]["content"]          # [system primer, system context, ...conversation]


class TestHelpModeReachesGrok(unittest.TestCase):
    def turn(self, msg, store, history=(), mode=None):
        chat = FakeRespond(["Here are the pages. " + block(summary="s")])
        r = gd_turn.run_turn(msg, "Refrigerators", "Acme X1", list(history), finder=finder(), respond_fn=chat, store=store,
                             log_path="", help_mode=mode)
        return r, context(chat.seen[0][0])

    def test_pages_mode_is_stored_and_told_each_turn(self):
        store = {}
        r, ctx = self.turn("not cooling", store, mode=gd_turn.HELP_PAGES)
        self.assertIn(gd_turn.HELP_MODE_LINES["pages"], ctx)
        self.assertEqual(store[gd_turn.STORE_KEY]["state"]["help_mode"], "pages")
        hist = [{"role": "user", "content": "not cooling"}, {"role": "assistant", "content": r["reply"]}]
        r2, ctx2 = self.turn("I'm stuck on the fan test, help", store, hist)            # no new choice: still pages, kept
        self.assertIn(gd_turn.HELP_MODE_LINES["pages"], ctx2)
        self.assertIn("whenever he asks for help or says he is stuck", ctx2)

    def test_walk_me_through_it_switches_and_keeps_the_job(self):
        store = {}
        r, _ = self.turn("not cooling", store, mode="pages")
        hist = [{"role": "user", "content": "not cooling"}, {"role": "assistant", "content": r["reply"]}]
        chat = FakeRespond(["Step 1. " + block(summary="s2")])
        gd_turn.run_turn("I'm stuck. Walk me through it from here.", "Refrigerators", "Acme X1", hist, finder=finder(),
                         respond_fn=chat, store=store, log_path="", help_mode="walkthrough")
        items = chat.seen[0][0]
        self.assertIn(gd_turn.HELP_MODE_LINES["walkthrough"], context(items))
        self.assertNotIn(gd_turn.HELP_MODE_LINES["pages"], context(items))
        self.assertEqual([m["content"] for m in items[2:4]], ["not cooling", r["reply"]])     # whole job carried
        self.assertEqual(store[gd_turn.STORE_KEY]["state"]["help_mode"], "walkthrough")

    def test_no_choice_is_the_old_behavior(self):
        store = {}
        _, ctx = self.turn("not cooling", store)
        self.assertNotIn("HOW THE TECH WANTS HELP", ctx)

    def test_grok_cannot_overwrite_the_choice(self):
        store = {}
        chat = FakeRespond(["ok " + block(help_mode="walkthrough", summary="s")])
        gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=finder(), respond_fn=chat, store=store, log_path="",
                         help_mode="pages")
        self.assertEqual(store[gd_turn.STORE_KEY]["state"]["help_mode"], "pages")

    def test_primer_untouched_and_mode_lines_are_context(self):
        for line in gd_turn.HELP_MODE_LINES.values():
            self.assertNotIn(line, gd_prompt.PRIMER)
            self.assertNotIn(line, gd_prompt.SYSTEM)


class TestStoryWorksInBothModes(unittest.TestCase):
    def test_story_in_pages_mode(self):
        hist = [{"role": "user", "content": "Customer states furnace will not light"},
                {"role": "assistant", "content": "Pages: the ignition troubleshooting chart. **Cause confirmed:** Failed igniter."},
                {"role": "user", "content": "Removed the access door. Measured 12.6V DC at the board. Igniter measured open, 0 ohm continuity failed."}]
        for mode in ("pages", "walkthrough"):
            case = {"unit": {"model_text": "DFMD35"}, "complaint": "", "state": {"help_mode": mode, "repair": {"done": False}}}
            s = gd_story.write_warranty_story(case, hist, "DFMD35")
            sec = gd_story.parse_story(s)
            self.assertIn("furnace will not light", sec["CONCERN"])
            self.assertIn("12.6", s)
            self.assertIn("Failed igniter", sec["CAUSE"])
            self.assertTrue(sec["CORRECTION"].startswith("Recommend"))


class TestAppChoice(unittest.TestCase):
    def test_buttons_and_wiring(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        for want in ('GD_HELP_QUESTION = "How do you want help on this job?"',
                     '"📖 Pull up the manual pages": "pages"', '"🧭 Walk me through the repair": "walkthrough"',
                     'GD_WALK_ME_BUTTON = "🧭 Walk me through it"',
                     'st.radio(GD_HELP_QUESTION, list(GD_HELP_OPTIONS), index=None, key="gd_help_choice", horizontal=True)',
                     'help_mode=st.session_state.get("gd_help_mode") or None', "help_mode=help_mode,",
                     'st.session_state["gd_help_mode"] = None       # the next job asks again'):
            self.assertIn(want, src)


if __name__ == "__main__":
    unittest.main()


class TestAppWalk(unittest.TestCase):
    """The tech's view, AppTest in offline mode (no model keys): the question shows before the first message, the pick is
    kept, and in pages mode the 'Walk me through it' button sits under the chat."""

    def setUp(self):
        import os
        from unittest import mock
        keys = ("XAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
        p = mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k not in keys}, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def test_choice_then_walk_me_button(self):
        from test_gd_nav_and_send import APP
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(APP), default_timeout=60)
        at.run()
        at.text_input[0].set_value("manager")
        at.text_input[1].set_value("manager123")
        at.button[0].click().run()
        at.radio[0].set_value("💬 Guided Diagnostics").run()
        choice = at.radio(key="gd_help_choice")
        self.assertEqual(choice.label, "How do you want help on this job?")
        self.assertEqual(list(choice.options), ["📖 Pull up the manual pages", "🧭 Walk me through the repair"])
        self.assertIsNone(choice.value)
        choice.set_value("📖 Pull up the manual pages").run()
        self.assertEqual(at.session_state["gd_help_mode"], "pages")
        at.text_area(key="ask_input").set_value("Customer states refrigerator will not cool below 42F.")
        at.button(key="FormSubmitter:gd_send_form-Send").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(at.session_state["ask_chat"])
        self.assertEqual(at.session_state["gd_help_mode"], "pages")
        walk = at.button(key="gd_walk_me")
        self.assertEqual(walk.label, "🧭 Walk me through it")
        walk.click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.session_state["gd_help_mode"], "walkthrough")
        users = [m["content"] for m in at.session_state["ask_chat"] if m["role"] == "user"]
        self.assertEqual(users[-1], "I'm stuck. Walk me through it from here.")
