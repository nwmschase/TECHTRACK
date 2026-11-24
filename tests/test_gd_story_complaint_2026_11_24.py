"""2026-11-24 live M1066 (FCR16DCASA-SS, evaporator fan): a photo was attached to the opening message, the photo did not
count, and history_user_text replaced the typed complaint with "The file did not count." The saved chat, its title and the
warranty story's CUSTOMER COMPLAINT all read that note. Offline only."""
import pathlib, sys, unittest
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


class TestStoryComplaintAndRecommendation(unittest.TestCase):
    def test_story_skips_the_photo_note_as_complaint(self):
        hist = [{"role": "user", "content": "The file did not count."}, {"role": "assistant", "content": "x"},
                {"role": "user", "content": "fan not running"}]
        s = gd_story.warranty_story({"complaint": COMPLAINT, "state": {"cause": "Evaporator fan failed"}}, hist, "FCR16DCASA-SS")
        self.assertNotIn("The file did not count", s)
        self.assertIn("1. CUSTOMER COMPLAINT\n" + COMPLAINT + "\n", s)
        s0 = gd_story.warranty_story({"state": {"cause": "c"}}, hist, "M")
        self.assertIn("1. CUSTOMER COMPLAINT\nNot recorded.", s0)      # never the tech's later findings
        s2 = gd_story.warranty_story({"state": {"cause": "c"}},
                                     [{"role": "user", "content": COMPLAINT + "\n(The file did not count as a finding.)"}], "M")
        self.assertIn("1. CUSTOMER COMPLAINT\n" + COMPLAINT + "\n", s2)
        self.assertNotIn("did not count", s2)

    def test_open_job_with_part_to_order_shows_the_recommendation(self):
        s = gd_story.warranty_story({"state": {"cause": "Evaporator fan assembly failure",
                                               "order_part": "evaporator fan assembly"}}, [{"role": "user", "content": COMPLAINT}], "M")
        self.assertIn("OPEN - recommended: replace evaporator fan assembly (not yet performed).", s)


if __name__ == "__main__":
    unittest.main()
