"""v4.20.13 (Chase t1741u answers, 2026-11-28): Repair complete after Diagnosis complete switches the record; the web gate
also opens on an empty search narrowed to the unit; the smart (meaning/embedding) search is deleted for good; a repair
sub-field Grok leaves out keeps its value. No paid calls."""
import ast
import json
import os
import pathlib
import re
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_state  # noqa: E402
import gd_story  # noqa: E402
import gd_tools  # noqa: E402
import gd_turn  # noqa: E402
from test_fresh_core import block  # noqa: E402
from test_gd_v4207_2026_11_28 import finder, turn, web_names  # noqa: E402


def case_with(wrapup, **state):
    st = gd_state.new_state()
    st.update(state)
    st["wrapup"] = wrapup
    return {"state": st}


class TestRepairCompleteSwitch(unittest.TestCase):
    def test_diag_logged_job_switches_on_button_verified_closed_or_plain_words(self):
        self.assertTrue(gd_story.repair_switch_due(case_with("diag"), "", close_action="repair"))
        self.assertTrue(gd_story.repair_switch_due(case_with("diag", repair={"done": True, "verified": True, "what": "", "quote": ""})))
        self.assertTrue(gd_story.repair_switch_due(case_with("diag", closed=True)))
        self.assertTrue(gd_story.repair_switch_due(case_with("diag"), "repair complete, furnace heating"))

    def test_nothing_else_switches(self):
        self.assertFalse(gd_story.repair_switch_due(case_with("diag"), "", close_action="diag"))
        self.assertFalse(gd_story.repair_switch_due(case_with("diag"), "fan still runs, what next"))
        self.assertFalse(gd_story.repair_switch_due(case_with("repair"), "", close_action="repair"))   # already repair
        self.assertFalse(gd_story.repair_switch_due(case_with("repair"), "diag complete", close_action="diag"))  # never downgraded
        self.assertFalse(gd_story.repair_switch_due(case_with(""), "", close_action="repair"))         # no diag record yet

    def test_the_line_names_the_switch_and_does_not_ask_again(self):
        self.assertIn("repair complete", gd_story.REPAIR_SWITCH_LINE)
        self.assertNotIn(gd_story.ACCESS_ASK, gd_story.REPAIR_SWITCH_LINE)
        self.assertNotIn("?", gd_story.REPAIR_SWITCH_LINE)


class TestRepairCompleteInTheApp(unittest.TestCase):
    def setUp(self):
        keys = ("XAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
        p = mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k not in keys}, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def _at(self):
        from test_gd_nav_and_send import APP
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(APP), default_timeout=60)
        at.run()
        at.text_input[0].set_value("manager")
        at.text_input[1].set_value("manager123")
        at.button[0].click().run()
        at.radio[0].set_value("💬 Guided Diagnostics").run()
        at.text_area(key="ask_input").set_value("Customer states furnace will not blow warm.")
        at.button(key="FormSubmitter:gd_send_form-Send").click().run()
        self.assertFalse(list(at.exception))
        return at

    def test_repair_button_after_diag_switches_the_record_with_one_line_and_no_second_question(self):
        at = self._at()
        at.button(key="gd_close_diag").click().run()
        self.assertFalse(list(at.exception))
        rec = at.session_state["gd_pin_store"]["gd_case"]["state"]
        self.assertEqual(rec["wrapup"], "diag")
        self.assertIn(gd_story.access_question("diag"), at.session_state["ask_chat"][-1]["content"])
        n = len(at.session_state["ask_chat"])
        at.button(key="gd_close_repair").click().run()
        self.assertFalse(list(at.exception))
        rec = at.session_state["gd_pin_store"]["gd_case"]["state"]
        self.assertEqual(rec["wrapup"], "repair")
        self.assertEqual(at.session_state["ask_chat"][-1]["content"], gd_story.REPAIR_SWITCH_LINE)
        self.assertNotIn(gd_story.ACCESS_ASK, at.session_state["ask_chat"][-1]["content"])
        self.assertEqual(len(at.session_state["ask_chat"]), n + 2)     # the tech's "Repair complete." and the one line
        # a second click does nothing more (already logged that way)
        at.button(key="gd_close_repair").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(len(at.session_state["ask_chat"]), n + 2)
        self.assertEqual(at.session_state["gd_pin_store"]["gd_case"]["state"]["wrapup"], "repair")

    def test_repair_button_with_no_diag_record_still_asks_the_access_question_once(self):
        at = self._at()
        at.button(key="gd_close_repair").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.session_state["gd_pin_store"]["gd_case"]["state"]["wrapup"], "repair")
        self.assertIn(gd_story.access_question("repair"), at.session_state["ask_chat"][-1]["content"])


class TestNarrowedEmptySearchOpensTheGate(unittest.TestCase):
    NARROWED = [("brand", {"brand": "Acme"}), ("unit_type", {"unit_type": "refrigerator"}), ("doc_ids", {"doc_ids": ["L1"]})]

    def test_reason_for_each_narrowing(self):
        for name, extra in self.NARROWED:
            args = {"words": "zzqxv flurble", **extra}
            why = gd_turn.library_empty_reason("search_pages", args, json.dumps({"hits": [], "matching_pages": 0}))
            self.assertIn(gd_turn.WHY_NARROWED_EMPTY, why, name)
            self.assertIn(name, why)

    def test_whole_library_empty_keeps_its_own_reason_and_non_empty_gives_none(self):
        why = gd_turn.library_empty_reason("search_pages", {"words": "zzqxv"}, json.dumps({"hits": []}))
        self.assertTrue(why)
        self.assertNotIn(gd_turn.WHY_NARROWED_EMPTY, why)
        for _name, extra in self.NARROWED:
            self.assertEqual(gd_turn.library_empty_reason("search_pages", {"words": "E2", **extra},
                                                          json.dumps({"hits": [{"doc_id": "L1", "page": "25"}]})), "")

    def test_empty_narrowed_search_opens_the_gate_and_logs_a_tagged_line(self):
        for _name, extra in self.NARROWED:
            r, chat = turn([[("search_pages", {"words": "zzqxv flurble wompus", **extra})], "ok\n" + block(summary="s")])
            self.assertEqual(web_names(chat.seen[0][1]), [], "closed before the search")
            self.assertTrue(web_names(chat.seen[-1][1]), f"open after an empty search narrowed by {_name}")
            trig = [t for t in r["triggers"] if t["trigger"] == gd_turn.T_WEB_GATE_NARROWED]
            self.assertEqual(len(trig), 1, _name)
            self.assertIn(_name, json.dumps(trig[0]))
            self.assertIn(gd_turn.T_WEB_GATE_OPENED, [t["trigger"] for t in r["triggers"]])

    def test_non_empty_narrowed_search_does_not_open_it(self):
        for _name, extra in self.NARROWED:
            r, chat = turn([[("search_pages", {"words": "freezer fan", **extra})], "ok\n" + block(summary="s")])
            self.assertTrue(r["triggers"] is not None)
            self.assertEqual(web_names(chat.seen[-1][1]), [], f"a narrowed search with hits ({_name}) must not open the gate")
            self.assertNotIn(gd_turn.T_WEB_GATE_OPENED, [t["trigger"] for t in r["triggers"]])
            self.assertNotIn(gd_turn.T_WEB_GATE_NARROWED, [t["trigger"] for t in r["triggers"]])

    def test_whole_library_empty_opens_without_the_narrowed_tag(self):
        r, chat = turn([[("search_pages", {"words": "zzqxv flurble wompus"})], "ok\n" + block(summary="s")])
        self.assertTrue(web_names(chat.seen[-1][1]))
        names = [t["trigger"] for t in r["triggers"]]
        self.assertIn(gd_turn.T_WEB_GATE_OPENED, names)
        self.assertNotIn(gd_turn.T_WEB_GATE_NARROWED, names)

    def test_trigger_is_registered_and_the_turn_log_writes_it(self):
        self.assertIn(gd_turn.T_WEB_GATE_NARROWED, gd_turn.TRIGGERS)
        self.assertEqual(gd_turn.T_WEB_GATE_NARROWED, "WEB_GATE_OPENED_EMPTY_NARROWED")


class TestRepairFieldsKeepTheirValue(unittest.TestCase):
    FULL = {"done": True, "verified": True, "what": "replaced the fan motor", "quote": "fan runs"}

    def test_reply_with_only_what_keeps_verified_and_done(self):
        st = gd_state.merge(gd_state.new_state(), {"repair": dict(self.FULL)})
        clean, problems = gd_state.validate({"repair": {"what": "replaced the fan motor and the harness"}})
        self.assertFalse(problems)
        st2 = gd_state.merge(st, clean)
        self.assertTrue(st2["repair"]["verified"])
        self.assertTrue(st2["repair"]["done"])
        self.assertEqual(st2["repair"]["quote"], "fan runs")
        self.assertEqual(st2["repair"]["what"], "replaced the fan motor and the harness")

    def test_reply_that_leaves_repair_out_keeps_all_of_it(self):
        st = gd_state.merge(gd_state.new_state(), {"repair": dict(self.FULL)})
        clean, _ = gd_state.validate({"summary": "s"})
        self.assertEqual(gd_state.merge(st, clean)["repair"], self.FULL)

    def test_a_field_written_false_is_still_applied(self):
        st = gd_state.merge(gd_state.new_state(), {"repair": dict(self.FULL)})
        clean, _ = gd_state.validate({"repair": {"verified": False}})
        st2 = gd_state.merge(st, clean)
        self.assertFalse(st2["repair"]["verified"])
        self.assertTrue(st2["repair"]["done"])

    def test_through_the_parser(self):
        st = gd_state.merge(gd_state.new_state(), {"repair": dict(self.FULL)})
        _text, upd, _problems = gd_state.parse('ok <state>{"repair": {"quote": "still runs"}}</state>')
        self.assertTrue(gd_state.merge(st, upd)["repair"]["verified"])

    def test_a_non_dict_repair_is_still_refused(self):
        clean, problems = gd_state.validate({"repair": "yes"})
        self.assertNotIn("repair", clean)
        self.assertTrue(problems)


class TestSmartSearchIsGone(unittest.TestCase):
    """Guard: the meaning (embedding) search, its switch, its model, its vector files and its packages must not come back."""

    def _py_files(self):
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if rel.parts[0] in ("tests", ".git", "__pycache__") or "venv" in rel.parts[0]:
                continue
            yield p

    def test_no_import_or_name_of_the_old_path_in_the_code(self):
        banned_imports = ("fastembed", "onnxruntime")
        banned_names = ("meaning_flag_on", "MEANING_ON", "meaning_status", "announce_meaning_state", "embed_query", "embedding_model",
                        "shared_embedding_model", "shared_base_vectors", "T_MEANING_OFF", "TT_PAGEFINDER_MEANING", "_note_meaning_off",
                        "last_search_pages", "EMBED_BATCH", "passages.npy", "passages.json", "HF_HUB_OFFLINE")
        for p in self._py_files():
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for m in mods:
                    self.assertFalse(m.split(".")[0] in banned_imports, f"{p.name} imports {m}")
            for name in banned_names:
                code_lines = [ln for ln in src.splitlines() if name in ln and not ln.lstrip().startswith(("#", '"""', "- v4.", "v4."))]
                code_lines = [ln for ln in code_lines if "v4.20.13" not in ln and "deleted" not in ln and "removed" not in ln]
                if p.name == "rv_techtrack.py":
                    code_lines = [ln for ln in code_lines if not ln.startswith("- v4.")]
                self.assertEqual([], code_lines[:1], f"{p.name} still uses {name}")

    def test_search_module_has_no_embedding_surface(self):
        from pagefinder import search as pf
        for attr in ("meaning", "MEANING_ON", "meaning_flag_on", "embedding_model", "shared_embedding_model", "shared_base_vectors",
                     "announce_meaning_state", "meaning_status", "MODEL_NAME", "EMBED_BATCH"):
            self.assertFalse(hasattr(pf, attr), attr)
        lib = pf.Library(os.path.join(str(ROOT / "pagefinder" / "index"), "index.sqlite"), app_db="")
        for attr in ("vectors", "embed_query", "meaning_error"):
            self.assertFalse(hasattr(lib, attr), attr)

    def test_requirements_do_not_list_the_packages(self):
        req = (ROOT / "requirements.txt").read_text().lower()
        for pkg in ("fastembed", "onnxruntime"):
            self.assertIsNone(re.search(rf"^{pkg}\b", req, re.M), pkg)

    def test_no_vector_files_in_the_repo_and_the_finder_takes_no_meaning_switch(self):
        self.assertFalse((ROOT / "pagefinder" / "index" / "passages.npy").exists())
        self.assertFalse((ROOT / "pagefinder" / "index" / "passages.json").exists())
        import gd_pages
        import inspect
        self.assertNotIn("meaning", inspect.signature(gd_pages.LibraryPageFinder.__init__).parameters)

    def test_startup_line_says_removed(self):
        f = gd_turn.startup_fields("v4.20.13", "abc")
        self.assertTrue(f["smart_search"].startswith("removed"))

    def test_word_match_search_still_works(self):
        T = gd_tools.LibraryTools.for_finder(finder())
        self.assertTrue(T.search_pages("E2 freezer fan").get("hits"))

    def test_search_takes_no_meaning_term_when_scoring(self):
        from pagefinder import search as pf
        lib = pf.Library(os.path.join(str(ROOT / "pagefinder" / "index"), "index.sqlite"), app_db="")
        pages = [p for d in list(lib.docs)[:3] for p in lib.pages(d)][:8]
        out = pf.hybrid(lib, "error code hall signal", pages)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in out.values()))


if __name__ == "__main__":
    unittest.main()
