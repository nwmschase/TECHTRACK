"""2026-11-24 live M1066 (FCR16DCASA-SS, evaporator fan): a photo was attached to the opening message, the photo did not
count, and history_user_text replaced the typed complaint with "The file did not count." The saved chat, its title and the
warranty story's CUSTOMER COMPLAINT all read that note. Offline only."""
import html, json, pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gd_story  # noqa: E402
from gd_step_photo import history_user_text  # noqa: E402

COMPLAINT = "CUSTOMER STATES THAT THE REFER IS NOT GETTING COLD."


class TestOpeningMessageKeepsTheComplaint(unittest.TestCase):
    def test_opening_message_with_unconfirmed_photo_keeps_typed_text(self):
        for review in ({"verdict": "unclear", "sees": ""}, {"verdict": "mismatch", "sees": "A data plate."}):
            out = history_user_text(COMPLAINT, True, review, asked="")
            self.assertTrue(out.startswith(COMPLAINT))
            self.assertIn("did not count as a finding", out)

    def test_step_answer_contradicted_by_photo_is_still_dropped(self):
        out = history_user_text("Supply connection is tight. Yes.", True, {"verdict": "mismatch", "sees": "Water at the fitting."},
                                asked="Check the supply connection.")
        self.assertEqual(out, "The file did not count.")
        self.assertEqual(history_user_text("tight", True, {"verdict": "mismatch", "sees": "x"}), "The file did not count.")

    def test_send_path_passes_what_was_asked(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        # v4.20.6: the send is kept with what was asked (gd_sends entry) and the chat line is built from it
        self.assertIn('_entry = {"key": None, "msg": msg, "photo": bool(photo_bytes), "photo_review": photo_review, "asked": asked,', src)
        self.assertIn('msg, bool(entry.get("photo")), entry.get("photo_review"), asked=entry.get("asked") or "")', src)


def load_work_order(path):
    """The chat and complaint from a TechTrack work-order export (the real live M1066 download)."""
    t = path.read_text(encoding="utf-8")
    msgs = re.findall(r"<div class='msg (tech|gd)'><div class='who'>[^<]*</div>(.*?)</div>\n", t, re.S)
    hist = [{"role": "user" if r == "tech" else "assistant", "content": html.unescape(c)} for r, c in msgs]
    complaint = html.unescape(re.search(r"<h2>Complaint</h2>\s*<p>(.*?)</p>", t, re.S).group(1))
    return hist, complaint


M1066, M1066_COMPLAINT = load_work_order(ROOT / "tests" / "fixtures" / "m1066_work_order_2026_11_24.html")
# The live record as saved: stale part / pending test, no cause, no repair (what the export shows).
M1066_CASE = {"unit": {"category": "", "model_text": "FCR16DCASA-SS"}, "complaint": M1066_COMPLAINT,
              "state": {"part_working": "sealed system / thermistors",
                        "pending_test": "evaporator temp/frost, freezer temp, evaporator fan", "cause": "",
                        "repair": {"done": False, "verified": False, "what": "", "quote": ""}}}
REAL_COMPLAINT = "Customer states refrigerator does not maintain proper cooling temperatures and will not cool below 42F"
READINGS = ["13.34", "12.07", "11.73", "1.27", "6.81", "12.26", "7.28", "12.50", "13.48", "12.64", "12.30", "0.84", "11.21",
            "48", "5", "60"]

GROK_OK = """CONCERN
Customer states refrigerator does not maintain proper cooling temperatures and will not cool below 42F. Technician verified the concern; the fresh-food compartment would not cool below 42F.

CAUSE
The technician removed the refrigerator and performed electrical, mechanical and visual diagnostic inspections following Furrion warranty troubleshooting procedures. Compressor and condenser fan operation, interior lighting and control panel operation were verified; settings were correct, the unit was not in low power mode and the door seals were good. The main control board, wiring and refrigerant connections were inspected with no control board damage found; discoloration was observed around the refrigerant fittings and filter-drier, with no refrigerant leak confirmed. On battery power only, the technician measured battery voltage 13.34V DC, refrigerator terminal voltage 12.07V DC and compressor controller voltage 11.73V DC, a supply voltage drop of 1.27V DC; initial compressor starting amperage was 6.81A DC with 12.26V DC at the controller at startup, and operating amperage was 7.28-12.50A DC. With shore power connected, battery voltage was 13.48V DC, terminal voltage 12.64V DC and controller voltage 12.30V DC, a drop of 0.84V DC, with compressor operating amperage of 11.21A DC. The supply voltage drop is above the maker's limit and is a noted finding, not the cause. During cooling testing the freezer pulled down from approximately 48F to 5F while the fresh-food compartment only went from 60F to 48F, showing insufficient cold-air circulation into the fresh-food side. The technician removed the freezer upper air duct assembly and found the evaporator circulation fan not operating, and fan activation testing per the Furrion CCD-0009616 troubleshooting manual showed the fan failed to start. The evaporator circulation fan assembly has failed, so cold air from the freezer evaporator is not distributed into the fresh-food compartment while the compressor and sealed system operate normally.

CORRECTION
Recommend replacing the evaporator fan assembly, then re-test airflow and compartment temperatures to verify repair."""


def numbered(section):
    return [l for l in section.split("\n") if re.match(r"\s*\d+[.)]\s", l)]


def terse_label_lines(lines):
    """Bare 'Label: value' lines (the rejected 11/24 sample): short, a colon, no verb sentence."""
    return [l for l in lines if re.match(r"\s*\d+[.)]\s+[A-Za-z /-]{2,40}:\s+[^.]{1,60}\.?$", l)]


class TestRealM1066Story(unittest.TestCase):
    """The real live M1066 chat through the story path, no Grok call (chat_fn=None = Grok not available)."""

    def setUp(self):
        self.s = gd_story.write_warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS", chat_fn=None)
        self.sec = gd_story.parse_story(self.s)

    def test_complaint_is_the_real_complaint(self):
        self.assertIn(REAL_COMPLAINT, self.sec["CONCERN"])
        self.assertNotIn("did not count", self.s)
        self.assertNotIn("Label/photo", self.s)

    def test_cause_names_the_evaporator_fan_failure(self):
        low = self.sec["CAUSE"].lower()
        self.assertIn("evaporator circulation fan", low)
        self.assertIn("failure", low)
        self.assertNotIn("not determined", low)

    def test_correction_is_a_recommendation(self):
        self.assertTrue(self.sec["CORRECTION"].startswith("I recommend replacing the evaporator fan assembly"), self.sec["CORRECTION"])
        for bad in ("OPEN", "no correction recorded", "not yet performed"):
            self.assertNotIn(bad, self.s)

    def test_all_tech_work_is_carried(self):
        for want in ("I first removed the refrigerator", "electrical, mechanical and visual", "discoloration around refrigerant fittings and filter-drier",
                     "no refrigerant leak was confirmed", "I removed the freezer upper air duct assembly", "fan activation testing",
                     "The fan failed to start", "48F to 5F", "60F to 48F"):
            self.assertIn(want, self.s)
        self.assertIn("I also noted that the voltage drop exceeded the manual limit", self.s)
        self.assertNotIn("page", self.sec.get("REFERENCES", "").lower())


class TestStoryGuard(unittest.TestCase):
    """Chase 10/23 story spec, 11/25 "A STORY IS A WELL WRITTEN CONCERN CAUSE AND CORRECTION": paragraphs (no numbered or
    bulleted log) carrying every reading the tech reported, full sentences, never terse label lines. Both the fallback and the Grok path (via its check) are held to it."""

    def assert_guard(self, story):
        sec = gd_story.parse_story(story)
        for s in ("CONCERN", "CAUSE", "CORRECTION"):
            self.assertTrue(sec.get(s), f"no {s}")
        self.assertEqual(numbered(sec["CAUSE"]), [], "a story is paragraphs, not a numbered list (Chase 11/25)")
        self.assertFalse([l for l in sec["CAUSE"].split("\n") if l.strip().startswith(("- ", "* ", "• "))])
        self.assertGreaterEqual(len(gd_story._sentences(sec["CAUSE"])), 5)
        self.assertEqual(terse_label_lines(sec["CAUSE"].split("\n")), [], "terse label lines in the Cause")
        for r in READINGS:
            self.assertIn(r, story, f"reading {r} missing")

    def test_reading_extractor_finds_every_reported_reading(self):
        self.assertEqual(gd_story.readings(M1066), READINGS)

    def test_fallback_meets_the_guard(self):
        self.assert_guard(gd_story.warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS"))

    def test_grok_story_meeting_the_spec_is_used(self):
        self.assertEqual(gd_story.story_problems(GROK_OK, M1066_CASE, M1066), [])
        out = gd_story.write_warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS", chat_fn=lambda m: GROK_OK)
        self.assertEqual(out, GROK_OK)
        self.assert_guard(out)

    def test_grok_story_dropping_a_reading_is_retried_then_falls_back(self):
        short = GROK_OK.replace("with compressor operating amperage of 11.21A DC", "with the compressor running normally")
        self.assertIn("missing readings: 11.21", gd_story.story_problems(short, M1066_CASE, M1066))
        seen = []
        out = gd_story.write_warranty_story(M1066_CASE, M1066, "", chat_fn=lambda m: seen.append(m) or short)
        self.assertEqual(len(seen), 2)
        self.assertIn("The last draft needs these fixed: missing readings: 11.21", seen[1][1]["content"])
        self.assertEqual(out, gd_story.warranty_story(M1066_CASE, M1066, ""))
        fixed = []
        out2 = gd_story.write_warranty_story(M1066_CASE, M1066, "", chat_fn=lambda m: (fixed.append(1), short if len(fixed) == 1 else GROK_OK)[1])
        self.assertEqual(out2, GROK_OK)

    def test_terse_label_story_is_rejected(self):
        terse = ("COMPLAINT:\n" + REAL_COMPLAINT + "\n\nCAUSE:\nSupply voltage drop: 1.27V DC.\nCompressor amps: 11.21A DC.\n\n"
                 "CORRECTION:\nRecommend replacing the evaporator fan assembly.")
        self.assertTrue(any(p.startswith("missing readings") for p in gd_story.story_problems(terse, M1066_CASE, M1066)))
        self.assertNotEqual(gd_story.write_warranty_story(M1066_CASE, M1066, "", chat_fn=lambda m: terse), terse)

    def test_other_bad_grok_text_falls_back(self):
        fb = gd_story.warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS")
        for bad in ("Just replace the fan.",
                    GROK_OK.replace("Recommend replacing", "Replaced"),
                    GROK_OK.replace("fan assembly, then", "fan assembly (Furrion PN 2025064999), then")):
            self.assertEqual(gd_story.write_warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS", chat_fn=lambda m, b=bad: b), fb)
        self.assertEqual(gd_story.write_warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS", chat_fn=lambda m: 1 / 0), fb)

    def test_open_tag_is_scrubbed_not_over_stripped(self):
        txt = GROK_OK.replace("Recommend replacing", "OPEN - Recommend replacing")
        out = gd_story.write_warranty_story(M1066_CASE, M1066, "", chat_fn=lambda m: txt)
        self.assertNotIn("OPEN", out)
        self.assertEqual(out, GROK_OK)


class TestStoryPrompt(unittest.TestCase):
    def test_prompt_carries_the_spec(self):
        p = gd_story.STORY_SYSTEM
        for want in ("\nCONCERN\n", "\nCAUSE\n", "\nCORRECTION\n", "no bullet points or numbered lists",
                     "well-written Concern, Cause and Correction", "reasonably draw",
                     "every test, inspection and action", "with its units", "no page numbers", "noted finding",
                     "I recommend replacing the wall thermostat, then re-test the full heating sequence to verify repair.", "first person",
                     "same story goes on customer-pay work"):
            self.assertIn(want, p)

    def test_messages_carry_complaint_status_readings_refs(self):
        seen = []
        gd_story.write_warranty_story(M1066_CASE, M1066, "", chat_fn=lambda m: seen.append(m) or GROK_OK, references=["Furrion CCD-0009616: Troubleshooting"])
        user = seen[0][1]["content"]
        self.assertIn("CUSTOMER COMPLAINT (job start): " + REAL_COMPLAINT, user)
        self.assertIn("REPAIR STATUS: not performed", user)
        self.assertIn("13.34, 12.07", user)
        self.assertIn("OFFICIAL PROCEDURE SOURCES: Furrion CCD-0009616: Troubleshooting", user)
        self.assertIn("TECH'S STATED RECOMMENDATION: Replace the evaporator fan assembly", user)
        self.assertNotIn("did not count", user)

    def test_repair_done(self):
        case = json.loads(json.dumps(M1066_CASE))
        case["state"]["repair"] = {"done": True, "verified": True, "what": "Replaced the evaporator fan assembly; fresh food reached 38F",
                                   "quote": "new fan in"}
        seen = []
        gd_story.write_warranty_story(case, M1066, "", chat_fn=lambda m: seen.append(m) or GROK_OK)
        self.assertIn("REPAIR STATUS: performed", seen[0][1]["content"])
        fb = gd_story.warranty_story(case, M1066, "FCR16DCASA-SS")
        self.assertIn("I replaced the evaporator fan assembly; fresh food reached 38F. After the repair, I operated the unit "
                      "and verified it was working properly.", fb)
        self.assertNotIn("recommend replacing", fb.lower())

    def test_gd_mid_chat_story_is_not_the_story(self):
        # GD-4 (11/24): the story is written by the Write warranty story button from the whole chat; a story GD put in its
        # state block mid-chat is not returned
        case = json.loads(json.dumps(M1066_CASE))
        case["state"]["story"] = "Fan bad. Replaced."
        self.assertEqual(gd_story.write_warranty_story(case, M1066, "", chat_fn=lambda m: GROK_OK), GROK_OK)
        self.assertNotIn("Fan bad. Replaced.", gd_story.write_warranty_story(case, M1066, ""))


class TestRecordCapture(unittest.TestCase):
    def test_reply_that_confirms_cause_fills_the_record(self):
        case = json.loads(json.dumps(M1066_CASE))
        gd_story.record_reply_findings(case, M1066[-1]["content"])
        st = case["state"]
        self.assertTrue(st["cause"].startswith("Evaporator circulation fan assembly failure"))
        self.assertTrue(st["recommendation"].startswith("Replace the evaporator fan assembly"))
        import gd_work_orders as wo
        snap = wo.snapshot(history=M1066, case=case, chat_id=7)
        f = json.loads(snap["findings"])
        self.assertIn("Evaporator circulation fan", f["cause"])
        self.assertIn("evaporator fan assembly", f["recommendation"])

    def test_record_cause_from_state_block_is_kept(self):
        case = {"state": {"cause": "Grok's own cause"}}
        gd_story.record_reply_findings(case, "**Cause confirmed:** something else")
        self.assertEqual(case["state"]["cause"], "Grok's own cause")

    def test_app_wires_capture_and_story_writer(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn("gd_story.record_reply_findings(pin_store.get(gd_turn.STORE_KEY)", src)
        self.assertIn("gd_story.write_warranty_story(_case, history, model_text, chat_fn=_chat, references=_refs)", src)


if __name__ == "__main__":
    unittest.main()
