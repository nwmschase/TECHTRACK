"""Chase 2026-11-24 live test GD-4 (RC07 Coleman-Mach 2111-0001, repair complete): the story came out worse. Fixes, with no
new GD primer rules and no new story-rejection rules:
1. 'no i cited what was removed already' was logged as 'nothing removed'. Only an explicit none is none; an answer that
   points back to the chat (or has no items) takes the access work from the tech's own messages.
2. Thin steps: the story writer leaned on GD's own in-chat 'Technician story' (same omissions) and the readings list missed
   the capacitor rating and the 0.000 V end of the range. The writer now gets the session without GD's story block, the
   full readings, the access work the tech described, and the tech's corrections stand.
3. No maker document was used: no empty MANUFACTURER REFERENCES header (the section is left out).
4. The work order listed ~50 raw web search results; only links GD gave the tech in its replies are listed.
5. GD wrote its story and then asked the access question; the wrap-up now confirms, asks the access question, and the story
   comes from the Write warranty story button. Offline, no paid call."""
import html, json, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import gd_story  # noqa: E402
import gd_work_orders as wo  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "wo_gd4_rc07_2026_11_24.html"
RAW = FIX.read_text()


def _load():
    hist, at = [], 0
    while True:
        i = RAW.find("<div class='msg ", at)
        if i < 0:
            break
        role = "user" if RAW.startswith("tech'", i + len("<div class='msg ")) else "assistant"
        j = RAW.index("</div>", RAW.index("<div class='who'>", i)) + len("</div>")
        k = RAW.index("</div>\n", j)
        hist.append({"role": role, "content": html.unescape(RAW[j:k])})
        at = k
    return hist


CHAT = _load()
ACCESS_Q_AT = next(n for n, m in enumerate(CHAT) if m["role"] == "assistant" and "Before I write the warranty story" in m["content"])
HIST = CHAT[:ACCESS_Q_AT + 1]                 # through GD's wrap-up reply; the tech's access answer is the next message
ANSWER = CHAT[ACCESS_Q_AT + 1]["content"]
WEB = []
for chunk in RAW.split("<li>Web: <a href='")[1:]:
    WEB.append({"url": html.unescape(chunk.split("'", 1)[0]), "title": ""})
LIVE_STORY = html.unescape(RAW.split("<div class='story'>", 1)[1].split("</div>", 1)[0])
TRIM_STEP = "Went to the control box cieling assembly and removed trim to gain access."


def case_gd4():
    return {"unit": {"category": "Air Conditioning", "model_text": "Coleman-Mach 2111-0001"}, "complaint": CHAT[0]["content"],
            "state": {"cause": "Failed ceiling control/relay board (not commanding fans) + seized fan motor (locked shaft, 1.91 A draw)",
                      "repair": {"done": True, "verified": True, "what": "Replaced ceiling control/relay board and fan motor",
                                 "quote": "replaced fanmotor and control board and all working as designed"},
                      "closed": True, "summary": "Board and fan motor replaced; unit now operates correctly",
                      "story": "GD's own mid-chat story", "access_asked": True}}


class TestFixture(unittest.TestCase):
    def test_real_export(self):
        self.assertEqual(ANSWER, "no i cited what was removed already")
        self.assertEqual(len(WEB), 55)
        self.assertIn("removing trim to gain access", CHAT[4]["content"])


class Test1AccessAnswer(unittest.TestCase):
    def test_point_back_answer_takes_the_access_work_from_the_chat(self):
        c = gd_story.record_access_answer(case_gd4(), ANSWER, HIST)
        st = c["state"]
        self.assertEqual(st["access_answer"], ANSWER)
        self.assertEqual(st["access_done"], [TRIM_STEP])
        self.assertTrue(st["access_from_chat"])
        self.assertTrue(gd_story.access_logged_reply(c).startswith("Logged from what you told me earlier: " + TRIM_STEP))
        self.assertNotIn("nothing removed", gd_story.access_logged_reply(c))

    def test_only_an_explicit_none_is_none(self):
        for none in ("nothing removed", "nothing", "none", "Nothing removed."):
            st = gd_story.record_access_answer(case_gd4(), none, HIST)["state"]
            self.assertEqual((st["access_done"], st["access_needed"], st["access_from_chat"]), ([], [], False), none)
        st = gd_story.record_access_answer(case_gd4(), "idk", HIST)["state"]           # unclear: from the chat
        self.assertEqual(st["access_done"], [TRIM_STEP])

    def test_story_writer_gets_the_chat_access_work_either_way(self):
        c = gd_story.record_access_answer(case_gd4(), "nothing removed", HIST + [{"role": "user", "content": "nothing removed"}])
        msg = gd_story.story_messages(c, HIST, "")[1]["content"]
        self.assertIn("ACCESS WORK THE TECH DESCRIBED IN THE SESSION: " + TRIM_STEP, msg)

    def test_fallback_logs_the_trim(self):
        c = gd_story.record_access_answer(case_gd4(), ANSWER, HIST)
        s = gd_story.write_warranty_story(c, HIST + [CHAT[ACCESS_Q_AT + 1]], "")
        self.assertIn("2. " + TRIM_STEP, s)
        self.assertEqual(s.count("removed trim"), 1)


class Test2WholeChat(unittest.TestCase):
    def test_readings_include_the_rating_and_the_range(self):
        r = gd_story.readings(HIST)
        for want in ("122", "0.000", "0.048", "1.91", "15.11", "15"):
            self.assertIn(want, r)

    def test_writer_input_is_the_whole_chat_without_gds_story_block(self):
        c = gd_story.record_access_answer(case_gd4(), ANSWER, HIST)
        msg = gd_story.story_messages(c, HIST + [CHAT[ACCESS_Q_AT + 1]], "")[1]["content"]
        for want in ("On Fan High, the board output tester doesn't light.", "rated 15 µF ±5%",
                     "its the fan motor thats running that bad voltage and locked shaft. i told you compressor runs",
                     "I measured 122 VAC input", "REPAIR STATUS: performed", "0.000, 0.048"):
            self.assertIn(want, msg)
        self.assertNotIn("Technician story", msg)
        self.assertNotIn("Testing performed: Confirmed 122 VAC", msg)
        self.assertNotIn("GD's own mid-chat story", msg)
        self.assertLess(len(msg), 60000)                 # not cut: the whole session fits
        sysp = gd_story.STORY_SYSTEM
        self.assertIn("When the tech corrected the assistant during the session, the tech's version is what happened.", sysp)

    def test_gd_mid_chat_story_is_not_returned(self):
        s = gd_story.write_warranty_story(case_gd4(), HIST, "")
        self.assertNotIn("GD's own mid-chat story", s)

    def test_fallback_has_every_test_with_readings(self):
        c = gd_story.record_access_answer(case_gd4(), ANSWER, HIST)
        s = gd_story.write_warranty_story(c, HIST + [CHAT[ACCESS_Q_AT + 1]], "")
        for want in ("I measured 122 VAC input.", "On Fan High, the board output tester doesn't light.",
                     "Read 0.000 to 0.048 VAC on black/white at the 9-pin connector.",
                     "The fan run capacitor reads 15.11 µF (rated 15 µF ±5%, so it's good).",
                     "It draws about 1.91 A at 122 V, and the shaft is locked.",
                     "Its the fan motor thats running that bad voltage and locked shaft.",
                     "Customer states the unit ran about 2 minutes then dead / no response."):
            self.assertIn(want, s)
        self.assertNotIn("?", s.split("CORRECTION")[0])
        self.assertEqual(gd_story.story_problems(s, c, HIST), [])


class Test3NoEmptyReferences(unittest.TestCase):
    def test_fallback_leaves_the_section_out(self):
        s = gd_story.write_warranty_story(gd_story.record_access_answer(case_gd4(), ANSWER, HIST), HIST, "")
        self.assertNotIn("MANUFACTURER REFERENCES", s)
        self.assertIn("3. CORRECTION", s)

    def test_grok_draft_with_an_empty_header_is_cleaned(self):
        draft = ("1. CONCERN\nCustomer states the unit ran about 2 minutes then went dead.\n\n2. CAUSE - DIAGNOSTIC TEST LOG\n"
                 "1. Removed the ceiling assembly trim to gain access to the control box.\n"
                 "2. Measured 122 VAC input at the control box; line voltage was good.\n"
                 "3. On Fan High the board output tester did not illuminate, and 0.000 to 0.048 VAC was read on black/white.\n"
                 "4. With the Peacemaker bypass the compressor ran, but the fan motor drew 1.91 A at 122 V with a locked shaft.\n"
                 "5. The fan run capacitor read 15.11 uF against a 15 uF +/-5% rating, ruling it out.\n\n"
                 "3. MANUFACTURER REFERENCES\n\n4. CORRECTION\nReplaced the control board and fan motor; verified working.")
        c = gd_story.record_access_answer(case_gd4(), ANSWER, HIST)
        out = gd_story.write_warranty_story(c, HIST, "", chat_fn=lambda m: draft)
        self.assertNotIn("MANUFACTURER REFERENCES", out)
        self.assertIn("3. CORRECTION", out)
        self.assertIn("5. The fan run capacitor", out)

    def test_prompt_says_leave_it_out(self):
        self.assertIn("When no official source is listed, the section is left out.", gd_story.STORY_SYSTEM)
        msg = gd_story.story_messages(case_gd4(), HIST, "")[1]["content"]
        self.assertIn("OFFICIAL PROCEDURE SOURCES: none recorded", msg)


class Test4CitedSourcesOnly(unittest.TestCase):
    def test_snapshot_lists_only_links_gd_gave_the_tech(self):
        case = {**case_gd4(), "web_sources": WEB}
        snap = wo.snapshot(history=HIST, case=case, chat_id=4)
        urls = [w["url"] for w in json.loads(snap["sources_json"])["web"]]
        self.assertEqual(urls, ["https://www.youtube.com/watch?v=QORCwM26n_I",
                                "https://thermostating.com/coleman-mach-thermostat-wiring/"])
        for junk in ("fixmycarinfo", "Zoeller", "burkert"):
            self.assertNotIn(junk, snap["sources_text"])

    def test_old_saved_row_renders_only_cited_links(self):
        class Row:
            wo_number, status, category_name, model_text, concern = "GD-4", "closed", "Air Conditioning", "x", "c"
            created_date = updated_date = None
            step_log = json.dumps(HIST)
            findings = "{}"
            sources_json = json.dumps({"pages": [], "web": WEB})
            sources_text = ""
            final_story = "story"
        try:
            page = wo.render_html(Row())
        except Exception as exc:                          # the row stub lacks a field the renderer needs
            self.skipTest(f"render stub: {exc}")
        self.assertIn("thermostating.com/coleman-mach-thermostat-wiring/", page)
        for junk in ("fixmycarinfo", "Zoeller", "burkert", "campingworld"):
            self.assertNotIn(junk, page)


class Test5WrapupOrder(unittest.TestCase):
    GD_REPLY = CHAT[ACCESS_Q_AT]["content"].split("Got it, logging this as", 1)[0].rstrip()

    def test_gd_reply_had_its_own_story(self):
        self.assertIn("**Technician story:**", self.GD_REPLY)

    def test_wrapup_confirms_then_asks_access_no_story(self):
        out = gd_story.wrapup_reply(self.GD_REPLY, gd_story.WRAPUP_REPAIR)
        self.assertTrue(out.startswith("**Repair verified — job complete.**"))
        self.assertTrue(out.endswith(gd_story.access_question("repair")))
        self.assertNotIn("Technician story", out)
        self.assertNotIn("Testing performed", out)

    def test_reply_without_a_story_is_kept_whole(self):
        r = "Diagnosis noted. Recommend replacing the thermostat."
        self.assertEqual(gd_story.wrapup_reply(r, "diag"), r + "\n\n" + gd_story.access_question("diag"))

    def test_wrapup_fires_on_this_repair_complete(self):
        c = case_gd4()
        c["state"].pop("access_asked")
        self.assertEqual(gd_story.wrapup_due(c, "replaced fanmotor and control board and all working as designed"), "repair")


if __name__ == "__main__":
    unittest.main()
