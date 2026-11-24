"""Chase 2026-11-24 (WO 156231 live test): the warranty story's correction follows the tech's own stated recommendation;
MANUFACTURER REFERENCES name the official document AND the procedure / flowchart the tests came from (read from the cited
pages' own text, no page numbers, no library codes); and at diag complete / repair complete GD asks what had to come off for
access and what the repair will need removed, and the story uses the tech's answer (CAUSE steps / CORRECTION list).
State-driven; the 'no rules' primer is unchanged. Offline: no paid call."""
import html, json, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import gd_story  # noqa: E402
import gd_work_orders  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def _between(text, start, end, at=0):
    i = text.index(start, at) + len(start)
    return text[i:text.index(end, i)], text.index(end, i)


def load_156231():
    t = (FIX / "wo_156231_2026_11_24.html").read_text()
    hist, at = [], 0
    while True:
        i = t.find("<div class='msg ", at)
        if i < 0:
            break
        role = "user" if t.startswith("tech'", i + len("<div class='msg ")) else "assistant"
        body, at = _between(t, "</div>", "</div>\n", t.index("<div class='who'>", i))
        hist.append({"role": role, "content": html.unescape(body)})
    complaint, _ = _between(t, "<h2>Complaint</h2>\n<p>", "</p>") if "<h2>Complaint</h2>\n<p>" in t else _between(t, "<h2>Complaint</h2><p>", "</p>")
    return t, hist, html.unescape(complaint)


PAGES = json.loads((FIX / "wo_156231_l120_pages.json").read_text())


def lookup(ref, page):
    d = PAGES["doc"]
    if str(ref) not in (d["doc_id"], d["title"]) or str(page) not in PAGES["pages"]:
        return None
    return {**d, "text": PAGES["pages"][str(page)], "page": str(page), "source": "library"}


HTML, HIST, COMPLAINT = load_156231()


def case_156231(**state):
    st = {"part_working": "thermostat circuit", "cause": "wall thermostat or its wiring not closing the call-for-heat circuit",
          "repair": {"done": False, "verified": False, "what": "inspect/clean/replace thermostat and wiring", "quote": ""},
          "help_mode": "walkthrough"}
    st.update(state)
    return {"unit": {"category": "", "model_text": "NT-20SEQT"}, "complaint": COMPLAINT, "state": st}


CITED = [{"title": "Suburban Furnace Service and Training Manual", "page": p} for p in ("30", "31", "4")]


class Test156231(unittest.TestCase):
    def test_fixture_is_the_real_export(self):
        users = [m["content"] for m in HIST if m["role"] == "user"]
        self.assertIn("Ok diagnostic complete then I will recommend a new thermostat", users[-1])
        self.assertIn("bypassed thermostat and it works", users)

    def test_tech_recommendation_is_captured(self):
        self.assertEqual(gd_story.tech_recommendation(HIST), "Replace the thermostat")
        case = case_156231()
        gd_story.record_tech_findings(case, HIST[-2]["content"] if HIST[-1]["role"] == "assistant" else HIST[-1]["content"])
        self.assertEqual(case["state"]["tech_recommendation"], "Replace the thermostat")

    def test_references_name_the_procedure_no_codes_no_pages(self):
        refs = gd_story.procedure_references(case_156231(), HIST, CITED, page_lookup=lookup)
        self.assertEqual(len(refs), 1)
        r = refs[0]
        self.assertTrue(r.startswith("Suburban Furnace Service and Training Manual: "))
        self.assertIn("Trouble Shooting Guide - Suburban RV Furnaces with Fan Control Module Boards - 12 VDC Heating Section", r)
        self.assertIn("General Service Information - Gas Supply Pressure Requirements", r)
        self.assertNotIn("L120", r)
        for bad in ("page", " p.", " pp", " 30", " 31", " 4;"):
            self.assertNotIn(bad, r.replace("Suburban", ""))

    def test_fallback_story(self):
        refs = gd_story.procedure_references(case_156231(), HIST, CITED, page_lookup=lookup)
        s = gd_story.write_warranty_story(case_156231(), HIST, "NT-20SEQT", references=refs)
        corr = s.split("CORRECTION", 1)[1]
        self.assertIn("Recommend replacing the thermostat, then re-test the full sequence without the jumper", corr)
        self.assertNotIn("L120", s)
        self.assertNotIn("page", s.lower())
        self.assertIn("1. Blower will start immediately but doesnt ignite at all.", s)
        self.assertIn("3. Bypassed thermostat and it works.", s)
        self.assertNotIn("recommend a new thermostat", s.split("CORRECTION", 1)[0])
        self.assertEqual(gd_story.story_problems(s, case_156231(), HIST), [])

    def test_live_story_that_ignored_the_recommendation_is_flagged(self):
        live, _ = _between(HTML, "<div class='story'>", "</div>")
        probs = gd_story.story_problems(html.unescape(live), case_156231(), HIST)
        self.assertTrue(any("tech's recommendation" in p for p in probs))

    def test_grok_draft_with_codes_and_pages_is_retried_then_fallback(self):
        bad = ("1. CONCERN\nx\n\n2. CAUSE - DIAGNOSTIC TEST LOG\n1. a.\n2. b.\n\n3. MANUFACTURER REFERENCES\n- L120 page 31\n\n"
               "4. CORRECTION\nRecommend replacing the thermostat.")
        seen = []
        out = gd_story.write_warranty_story(case_156231(), HIST, "", chat_fn=lambda m: seen.append(m) or bad)
        self.assertEqual(len(seen), 2)
        self.assertIn("library codes", seen[1][1]["content"])
        self.assertNotIn("L120", out)


class TestWrapupTrigger(unittest.TestCase):
    def test_diag_complete(self):
        c = {"state": {"repair": {"done": False}}}
        self.assertEqual(gd_story.wrapup_due(c, "Ok diagnostic complete then I will recommend a new thermostat"), "diag")
        self.assertEqual(gd_story.wrapup_due(c, "I want to recommend a replacement of the evaporator fan assembly"), "diag")
        self.assertEqual(gd_story.wrapup_due(c, "no 12 v on that wire from thermostat"), "")

    def test_repair_complete(self):
        self.assertEqual(gd_story.wrapup_due({"state": {"repair": {"done": True}}}, "replaced it, heats now"), "repair")
        self.assertEqual(gd_story.wrapup_due({"state": {"closed": True}}, "ok"), "repair")
        self.assertEqual(gd_story.wrapup_due({"state": {}}, "repair complete, furnace heating"), "repair")

    def test_asked_once(self):
        self.assertEqual(gd_story.wrapup_due({"state": {"access_asked": True}}, "diagnosis complete"), "")
        self.assertEqual(gd_story.wrapup_due({"state": {"access_answer": "nothing removed"}}, "repair complete"), "")

    def test_question_text(self):
        q = gd_story.access_question("diag")
        self.assertTrue(q.startswith("Got it, logging this as diag complete for now. Before I write the warranty story:"))
        self.assertIn("nothing removed", q)
        self.assertTrue(gd_story.access_question("repair").startswith("Got it, logging this as repair complete."))


class TestAccessAnswer(unittest.TestCase):
    def test_run_on_split_done_vs_needed(self):
        a = gd_story.parse_access_answer(
            "had to pull the fridge out and take the battery box covers off and remove the furnace access panel, for the "
            "repair it will need the furnace pulled and the return duct off")
        self.assertEqual(a["done"], ["Pulled the fridge out", "Took the battery box covers off", "Removed the furnace access panel"])
        self.assertEqual(a["needed"], ["furnace", "return duct"])

    def test_bare_item_takes_the_verb_before_it(self):
        a = gd_story.parse_access_answer("removed 2 panels under the dinette and the water heater door")
        self.assertEqual(a["done"], ["Removed 2 panels under the dinette", "Removed the water heater door"])
        self.assertEqual(a["needed"], [])

    def test_nothing_removed(self):
        a = gd_story.parse_access_answer("nothing removed")
        self.assertTrue(a["nothing"])
        c = gd_story.record_access_answer({"state": {}}, "nothing removed")
        self.assertEqual((c["state"]["access_done"], c["state"]["access_needed"]), ([], []))

    def test_slide_floor(self):
        c = {"state": {"repair": {"done": False}}}
        gd_story.record_access_answer(c, "slide floor is rotted, had to pull the fridge out, for the repair will need the "
                                         "fridge, the stove, the counters and all the drawers removed to replace the floor")
        self.assertEqual(c["state"]["access_done"], ["Pulled the fridge out"])
        self.assertEqual(c["state"]["access_needed"], ["fridge", "stove", "counters", "drawers"])
        h = [{"role": "user", "content": "slide floor soft by the fridge"}, {"role": "assistant", "content": "Check the floor."},
             {"role": "user", "content": "floor is rotted under the fridge, plywood delaminated"},
             {"role": "assistant", "content": "ok"},
             {"role": "user", "content": "diagnosis complete, recommend replacing the slide floor"}]
        gd_story.record_tech_findings(c, h[-1]["content"])
        s = gd_story.warranty_story(c, h, "")
        cause, corr = s.split("CORRECTION", 1)
        self.assertIn("1. Pulled the fridge out.", cause)
        self.assertIn("Recommend replacing the slide floor", corr)
        for n, item in enumerate(("fridge", "stove", "counters", "drawers"), 1):
            self.assertIn(f"{n}. Remove and reinstall the {item}.", corr)
        self.assertNotIn("Remove and reinstall the floor", corr)

    def test_grok_story_missing_an_access_item_is_flagged(self):
        c = case_156231()
        gd_story.record_access_answer(c, "had to pull the furnace out, the repair will need the wall panel removed")
        s = gd_story.warranty_story(c, HIST, "")
        self.assertEqual(gd_story.story_problems(s, c, HIST), [])
        self.assertTrue(gd_story.story_problems(s.replace("Remove and reinstall the wall panel.", ""), c, HIST))

    def test_work_order_shows_access_and_recommendation(self):
        c = case_156231(tech_recommendation="Replace the thermostat", wrapup="diag")
        gd_story.record_access_answer(c, "had to pull the furnace out")
        snap = gd_work_orders.snapshot(history=HIST, case=c, chat_id=1)
        f = json.loads(snap["findings"])
        self.assertEqual(f["tech_recommendation"], "Replace the thermostat")
        self.assertEqual(f["access_done"], ["Pulled the furnace out"])


class TestAppWrapup(unittest.TestCase):
    """The tech's view, AppTest offline: the Write warranty story button asks the access question first when it was not
    answered; 'Nothing removed' writes the story."""

    def setUp(self):
        import os
        from unittest import mock
        keys = ("XAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
        p = mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k not in keys}, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def test_send_then_write_story_asks_access_first(self):
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
        at.text_area(key="ask_input").set_value("Ok diagnostic complete then I will recommend a new thermostat")
        at.button(key="FormSubmitter:gd_send_form-Send").click().run()
        self.assertFalse(list(at.exception))
        last = at.session_state["ask_chat"][-1]["content"]
        self.assertIn(gd_story.access_question("diag"), last)
        rec = at.session_state["gd_pin_store"]["gd_case"]["state"]
        self.assertTrue(rec["access_asked"])
        self.assertEqual(rec["tech_recommendation"], "Replace the thermostat")
        at.text_area(key="ask_input").set_value("had to pull the furnace out, the repair will need the wall panel removed")
        at.button(key="FormSubmitter:gd_send_form-Send").click().run()
        self.assertFalse(list(at.exception))
        rec = at.session_state["gd_pin_store"]["gd_case"]["state"]
        self.assertEqual(rec["access_done"], ["Pulled the furnace out"])
        self.assertEqual(rec["access_needed"], ["wall panel"])
        self.assertIn("Logged", at.session_state["ask_chat"][-1]["content"])

    def test_write_story_without_answer_shows_the_question(self):
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
        write = next(b for b in at.button if "warranty story" in (b.label or "").lower())
        write.click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(at.session_state["gd_access_prompt"])
        at.button(key="gd_access_none").click().run()
        self.assertFalse(list(at.exception))
        self.assertNotIn("gd_access_prompt", at.session_state)
        self.assertEqual(at.session_state["gd_pin_store"]["gd_case"]["state"]["access_answer"], "nothing removed")


if __name__ == "__main__":
    unittest.main()
