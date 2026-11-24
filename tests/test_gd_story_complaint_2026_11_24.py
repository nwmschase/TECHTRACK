"""2026-11-24 live M1066 (FCR16DCASA-SS, evaporator fan): a photo was attached to the opening message, the photo did not
count, and history_user_text replaced the typed complaint with "The file did not count." The saved chat, its title and the
warranty story's CUSTOMER COMPLAINT all read that note. Offline only."""
import json, pathlib, sys, unittest
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
        self.assertIn("history_user_text(msg, bool(photo_bytes), photo_review, asked=asked)", src)


M1066 = json.loads((ROOT / "tests" / "fixtures" / "m1066_chat_2026_11_24.json").read_text(encoding="utf-8"))
M1066_CASE = {"unit": {"category": "Refrigerators", "model_text": "FCR16DCASA-SS"},
              "complaint": M1066[0]["content"].split("\n")[0],
              "state": {"facts": [{"item": "Supply voltage drop", "value": "1.27 V DC on battery, 0.84 V DC on shore power"},
                                  {"item": "Freezer / fresh-food pull-down", "value": "freezer 48F to 5F; fresh food 60F to 48F"},
                                  {"item": "Evaporator circulation fan", "value": "not operating; failed to start on activation test"}],
                        "cause": "Evaporator circulation fan assembly failure",
                        "order_part": "evaporator fan assembly",
                        "repair": {"done": False, "verified": False, "what": "", "quote": ""}}}
GROK_OK = """**COMPLAINT:**
Customer states the refrigerator is not getting cold; in 40 degree weather it would not go below 42 degrees.

**CAUSE:**
Verified customer concern. Checked power, settings, low power mode and door seals - all good.
Measured 12.07 V DC at the refrigerator terminals on battery (1.27 V DC drop) and 0.84 V DC drop on shore power.
Freezer pulled down from 48F to 5F while the fresh-food compartment only reached 48F.
Removed the freezer upper air duct assembly and found the evaporator circulation fan not operating; fan failed activation testing.

**CORRECTION:**
Recommend replacing the evaporator fan assembly and verifying proper cooling operation."""


class TestStoryComplaintAndRecommendation(unittest.TestCase):
    def test_story_skips_the_photo_note_as_complaint(self):
        hist = [{"role": "user", "content": "The file did not count."}, {"role": "assistant", "content": "x"},
                {"role": "user", "content": "fan not running"}]
        s = gd_story.warranty_story({"complaint": COMPLAINT, "state": {"cause": "Evaporator fan failed"}}, hist, "FCR16DCASA-SS")
        self.assertNotIn("did not count", s)
        self.assertIn("COMPLAINT:\n" + COMPLAINT + "\n", s)
        s0 = gd_story.warranty_story({"state": {"cause": "c"}}, hist, "M")
        self.assertIn("COMPLAINT:\nNot recorded.", s0)      # never the tech's later findings
        s2 = gd_story.warranty_story({"state": {"cause": "c"}},
                                     [{"role": "user", "content": COMPLAINT + "\n(The file did not count as a finding.)"}], "M")
        self.assertIn("COMPLAINT:\n" + COMPLAINT + "\n", s2)
        self.assertNotIn("did not count", s2)

    def test_template_diagnosis_only_is_a_recommendation(self):
        s = gd_story.warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS")
        self.assertIn("CORRECTION:\nRecommend replacing the evaporator fan assembly and verifying proper operation.", s)
        self.assertIn("Evaporator circulation fan: not operating", s)
        for bad in ("OPEN", "not yet performed", "did not count", "state", "session"):
            self.assertNotIn(bad, s)
        self.assertTrue(s.startswith("COMPLAINT:\nCUSTOMER STATES THAT THE REFER IS NOT GETTING COLD."))

    def test_template_repair_done(self):
        case = json.loads(json.dumps(M1066_CASE))
        case["state"]["repair"] = {"done": True, "verified": True, "what": "Replaced the evaporator fan assembly; fresh food reached 38F",
                                   "quote": "new fan in"}
        s = gd_story.warranty_story(case, M1066, "FCR16DCASA-SS")
        self.assertIn("CORRECTION:\nReplaced the evaporator fan assembly; fresh food reached 38F. Repair verified working.", s)
        self.assertNotIn("Recommend replacing", s)


class TestGrokWrittenStory(unittest.TestCase):
    def test_grok_story_is_used_and_cleaned(self):
        seen = []
        out = gd_story.write_warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS", chat_fn=lambda m: seen.append(m) or GROK_OK)
        self.assertTrue(out.startswith("COMPLAINT:\nCustomer states"))
        self.assertIn("CORRECTION:\nRecommend replacing the evaporator fan assembly and verifying proper cooling operation.", out)
        self.assertNotIn("**", out)
        user = seen[0][1]["content"]
        self.assertIn("REPAIR STATUS: not performed", user)
        self.assertIn("CUSTOMER COMPLAINT (job start): CUSTOMER STATES THAT THE REFER IS NOT GETTING COLD", user)
        self.assertNotIn("did not count", user)
        self.assertIn("Recommend", seen[0][0]["content"])

    def test_open_tag_and_parenthetical_are_scrubbed(self):
        txt = GROK_OK.replace("Recommend replacing", "OPEN - Recommend replacing").replace("operation.", "operation (not yet performed).")
        out = gd_story.write_warranty_story(M1066_CASE, M1066, "", chat_fn=lambda m: txt)
        self.assertNotIn("OPEN", out)
        self.assertNotIn("not yet performed", out)
        self.assertIn("Recommend replacing", out)

    def test_bad_grok_text_falls_back_to_template(self):
        for bad in ("Just replace the fan.",                                             # no sections
                    GROK_OK.replace("Recommend replacing", "Replaced"),                  # claims a repair not done
                    GROK_OK.replace("assembly and", "assembly (Furrion PN 2025064999) and")):  # invented part number
            out = gd_story.write_warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS", chat_fn=lambda m, b=bad: b)
            self.assertEqual(out, gd_story.warranty_story(M1066_CASE, M1066, "FCR16DCASA-SS"))
        boom = gd_story.write_warranty_story(M1066_CASE, M1066, "", chat_fn=lambda m: 1 / 0)
        self.assertIn("Recommend replacing the evaporator fan assembly", boom)

    def test_repair_done_story_status(self):
        case = json.loads(json.dumps(M1066_CASE)); case["state"]["repair"]["done"] = True
        seen = []
        gd_story.write_warranty_story(case, M1066, "", chat_fn=lambda m: seen.append(m) or GROK_OK)
        self.assertIn("REPAIR STATUS: performed", seen[0][1]["content"])

    def test_app_button_uses_the_story_writer(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn("gd_story.write_warranty_story(_case, history, model_text, chat_fn=_chat)", src)


if __name__ == "__main__":
    unittest.main()
