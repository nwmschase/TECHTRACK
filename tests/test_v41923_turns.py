"""Live v4.19.22 transcripts: a later turn reaches a conditional repair and never goes blank."""
import re
import unittest

from gd_library_coach import avoid_duplicate_reply


def _replay(user_turns, drafts):
    history = []
    replies = []
    for latest, draft in zip(user_turns, drafts):
        reply = avoid_duplicate_reply(draft, history, latest)
        replies.append(reply)
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": reply})
    return replies


def _assert_walk(test, replies):
    seen = set()
    for reply in replies:
        text = (reply or "").strip()
        test.assertTrue(text)
        test.assertNotIn("report the result of that check", text.lower())
        key = re.sub(r"\s+", " ", text.lower())
        test.assertNotIn(key, seen)
        seen.add(key)
    last = replies[-1].lower()
    test.assertTrue(
        re.search(r"\bif\b.+\b(replace|reseat|repair)\b", last, re.S)
        or "replace the" in last
    )


class TestTranscriptReplay(unittest.TestCase):
    def test_s01_reaches_a_rooftop_conditional_without_a_freeze_reseat(self):
        replies = _replay(
            [
                "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside while running.",
                "Drain is clear, pan is clean and draining, base-pan slope is fine.",
                "Filter is clean.",
                "Evaporator fan spins freely with good airflow.",
                "Freeze sensor reads 2 kΩ at 25°C.",
                "What is the repair?",
            ],
            ["", "", "Report the result of that check.", "Reseat the freeze sensor on the coil and retest before any board swap.", "", "Report the result of that check."],
        )
        for reply in replies:
            self.assertTrue((reply or "").strip())
        blob = " ".join(replies).lower()
        self.assertNotIn("reseat the freeze sensor", blob)
        self.assertNotIn("wall thermostat", blob)
        self.assertNotIn("replace the rooftop assembly", blob)
        self.assertIn("pressure", blob)

    def test_s02_does_not_replace_a_wall_thermostat_on_a_coleman(self):
        replies = _replay(
            [
                "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead.",
                "122 VAC at the control box. Fan High is dead.",
                "Peacemaker bypass: compressor runs, fan does not rotate. About 1.91 A, shaft locked.",
                "What is the repair?",
                "Not checked yet — what do you recommend next?",
            ],
            [
                "",
                "The compressor starts and runs while the fan stays locked. Measure stall current.",
                "Replace the wall thermostat. If voltage is missing, check the wire run.",
                "",
                "Report the result of that check.",
            ],
        )
        _assert_walk(self, replies)
        blob = " ".join(replies).lower()
        self.assertNotIn("wall thermostat", blob)
        self.assertIn("control board", replies[-1].lower())

    def test_s05_does_not_invent_a_rear_drain_after_the_gasket(self):
        replies = _replay(
            [
                "Furrion FCR10DCGTA-BL fridge; rear-wall icing about halfway from the top down.",
                "Dial is at max.",
                "Door gasket is sealing properly.",
                "Not checked yet — what do you recommend next?",
                "Fridge is still cooling.",
                "What is the repair?",
            ],
            ["", "", "", "", "", "Dry the cabinet, clear the rear drain, and check the door gasket."],
        )
        _assert_walk(self, replies)
        blob = " ".join(replies).lower()
        self.assertNotIn("rear drain", blob)
        self.assertIn("cooling unit", replies[-1].lower())

    def test_s08_conditional_names_the_thermostat_not_a_module_board(self):
        replies = _replay(
            [
                "Suburban furnace. Will not blow warm; fan turns on then shuts off.",
                "Thermostat bypassed at the furnace: the furnace operates.",
                "Not checked yet — what do you recommend next?",
                "What is the repair?",
            ],
            ["", "", "", "Prove the sail switch with the blower running before the module board."],
        )
        _assert_walk(self, replies)
        blob = " ".join(replies).lower()
        self.assertNotIn("module board", blob)
        self.assertIn("wall thermostat", replies[-1].lower())
        self.assertIn("sail", replies[-1].lower())

    def test_s10_never_goes_blank_and_reaches_zero_point(self):
        replies = _replay(
            [
                "Lippert Ground Control 343633. Auto-level lifts driver-side tires though nearly level.",
                "Not checked yet — what do you recommend next?",
                "What is the repair?",
                "What is the repair?",
            ],
            ["", "Report the result of that check.", "", ""],
        )
        _assert_walk(self, replies)
        self.assertIn("front", replies[-1].lower())

    def test_s12_answers_what_is_the_repair(self):
        replies = _replay(
            [
                "FACT12 E2 error code; sometimes normal.",
                "Not checked yet — what do you recommend next?",
                "What is the repair?",
            ],
            ["", "", ""],
        )
        _assert_walk(self, replies)
        self.assertIn("freeze sensor", replies[-1].lower())
        self.assertIn("replace", replies[-1].lower())

    def test_s13_seats_the_tube_at_the_blower(self):
        replies = _replay(
            [
                "Girard GSWH-2 gives E8 error code.",
                "Tubing is clear.",
                "Not checked yet — what do you recommend next?",
                "What is the repair?",
            ],
            ["", "", "", ""],
        )
        _assert_walk(self, replies)
        blob = " ".join(replies).lower()
        self.assertNotIn("burner flame", blob)
        self.assertIn("blower", replies[-1].lower())
        self.assertIn("seat", replies[-1].lower())

    def test_s14_front_jack_does_not_cite_the_rear_stabilizer(self):
        replies = _replay(
            [
                "Front stabilizer jack. Power works. The manual crank will not operate.",
                "Not checked yet — what do you recommend next?",
                "What is the repair?",
            ],
            ["", "", ""],
        )
        _assert_walk(self, replies)
        blob = " ".join(replies).lower()
        self.assertNotIn("rear stabilizer", blob)
        self.assertIn("front stabilizer jack", replies[-1].lower())

    def test_s03_drops_a_malformed_source_header(self):
        reply = avoid_duplicate_reply(
            "Source: | Page: 1\nManual: BAL Soft-Touch | Page: 1\n"
            "Press tongue extend and check for 12V on the tongue output wire.",
            [],
            "BAL Soft-Touch SS 5.1 electric tongue jack is dead.",
        )
        self.assertNotIn("source: |", reply.lower())
        self.assertNotIn("manual:", reply.lower())
        self.assertTrue(reply.strip())


if __name__ == "__main__":
    unittest.main()
