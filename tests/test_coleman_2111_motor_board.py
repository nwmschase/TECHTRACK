"""Coleman-Mach 2111-0001 climax: fan motor + control board only."""
import re
import unittest

from gd_library_coach import (
    COLEMAN_MOTOR_BOARD_AUTH_LINE,
    COLEMAN_MOTOR_BOARD_LOCK,
    coleman_motor_board_evidence_complete,
    ensure_coleman_motor_board_auth,
    facts_from_chat,
    is_coleman_2111_context,
    reply_authorizes_coleman_full_assembly,
    reply_fishes_coleman_more_tests,
    reply_names_coleman_motor_board_only,
)

COMPLAINT = (
    "Coleman-Mach rooftop A/C model 2111-0001. "
    "Ran about 2 minutes then dead. No response."
)
PROVE = [
    ("user", COMPLAINT),
    (
        "assistant",
        "What does the board output tester show on Fan High, "
        "and what VAC is on black/white at the 9-pin?",
    ),
    ("user", "Tester dark. 0.02 VAC."),
    (
        "assistant",
        "Peacemaker bypass: does the compressor run, and does the fan rotate? "
        "What are the amps?",
    ),
    (
        "user",
        "Compressor runs. Fan no rotate high or low. 1.91 A at 122 V, shaft locked.",
    ),
    ("assistant", "What does the fan run capacitor measure?"),
    ("user", "15.11 µF. Rated 15 µF."),
]
FISHING = (
    "The fan is locked. Next, check fan motor winding continuity, "
    "then measure the start capacitor."
)
FULL_ASSEMBLY = "Replace the complete 2111-0001 rooftop assembly."


def _card(turns, model_reply):
    history = [{"role": role, "content": text} for role, text in turns[:-1]]
    latest = turns[-1][1]
    facts = facts_from_chat(history, latest)
    return facts, ensure_coleman_motor_board_auth(model_reply, facts)


class TestColemanMotorBoardClimax(unittest.TestCase):
    def test_context_is_2111_0001_only(self):
        self.assertTrue(
            is_coleman_2111_context(
                "Air Conditioning", "Coleman-Mach 2111-0001", "ran 2 minutes then dead"
            )
        )
        self.assertFalse(is_coleman_2111_context("", "2111-0041", "no cool"))
        self.assertFalse(
            is_coleman_2111_context(
                "",
                "Furrion FACR08HESA2-PS",
                "water leaking inside, frost on the evaporator",
            )
        )
        self.assertIn("control board", COLEMAN_MOTOR_BOARD_LOCK.lower())
        self.assertIn("1976-536", COLEMAN_MOTOR_BOARD_LOCK)
        self.assertIn("1976-695", COLEMAN_MOTOR_BOARD_LOCK)
        self.assertIn("peacemaker", COLEMAN_MOTOR_BOARD_LOCK.lower())
        self.assertNotIn("page 12", COLEMAN_MOTOR_BOARD_LOCK.lower())

    def test_evidence_complete_stops_fishing_with_motor_and_board_only(self):
        facts, card = _card(PROVE, FISHING)
        self.assertTrue(coleman_motor_board_evidence_complete(facts), facts)
        self.assertEqual(facts.get("coleman_fan_high"), "dead")
        self.assertEqual(facts.get("coleman_compressor"), "ok")
        self.assertEqual(facts.get("coleman_fan_motor"), "locked")
        self.assertEqual(facts.get("coleman_stall_amps"), "reported")
        self.assertEqual(facts.get("coleman_cap"), "ok")
        self.assertTrue(reply_fishes_coleman_more_tests(FISHING))
        self.assertTrue(reply_names_coleman_motor_board_only(card), card)
        self.assertFalse(reply_fishes_coleman_more_tests(card), card)
        self.assertFalse(reply_authorizes_coleman_full_assembly(card), card)
        self.assertIn("fan motor", card.lower())
        self.assertIn("control board", card.lower())
        self.assertIn("only", card.lower())
        self.assertIn("2111-0001", card)
        self.assertIn("not", card.lower())
        self.assertIn("1976-536", card)
        self.assertIn("1976-603", card)
        self.assertIn("1976-695", card)
        self.assertIn("Peacemaker", card)
        self.assertIn("12VDC", card)
        self.assertNotIn("continuity", card.lower())
        self.assertIsNone(re.search(r"page\s+\d+", card, re.I))
        self.assertIn("AUTHORIZATION", COLEMAN_MOTOR_BOARD_AUTH_LINE)

    def test_full_assembly_reply_becomes_motor_and_board_only(self):
        self.assertTrue(reply_authorizes_coleman_full_assembly(FULL_ASSEMBLY))
        facts, card = _card(PROVE, FULL_ASSEMBLY)
        self.assertTrue(coleman_motor_board_evidence_complete(facts))
        self.assertTrue(reply_names_coleman_motor_board_only(card), card)
        self.assertFalse(reply_authorizes_coleman_full_assembly(card), card)
        self.assertNotIn("complete 2111-0001 rooftop assembly", card.lower())

    def test_prose_evidence_from_the_live_retest_climaxes(self):
        turns = [
            ("user", COMPLAINT),
            (
                "user",
                "Board output tester no illuminate on Fan High. "
                "0.000-0.048 VAC on black/white at the 9-pin under Fan High.",
            ),
            (
                "user",
                "When you bypass the thermostat/board the compressor starts, "
                "but the fan never turns. The fan motor draws about 1.9 A at 122 V "
                "with the shaft locked.",
            ),
            (
                "user",
                "The fan-run capacitor measures correctly (≈15 µF).",
            ),
        ]
        facts, card = _card(turns, "Check the motor windings next.")
        self.assertTrue(coleman_motor_board_evidence_complete(facts), facts)
        self.assertTrue(reply_names_coleman_motor_board_only(card), card)
        self.assertFalse(reply_fishes_coleman_more_tests(card))

    def test_incomplete_evidence_does_not_force_the_card(self):
        partial = PROVE[:-2]
        facts, card = _card(partial, FISHING)
        self.assertFalse(coleman_motor_board_evidence_complete(facts), facts)
        self.assertEqual(card, FISHING)
        self.assertFalse(reply_names_coleman_motor_board_only(card))
        cap_bad = PROVE[:-1] + [("user", "Capacitor is open. 0 uF.")]
        facts, card = _card(cap_bad, FISHING)
        self.assertEqual(facts.get("coleman_cap"), "bad")
        self.assertFalse(coleman_motor_board_evidence_complete(facts))
        self.assertEqual(card, FISHING)
        fan_live = [
            ("user", COMPLAINT),
            ("assistant", "What VAC is on Fan High?"),
            ("user", "115 VAC on Fan High."),
            ("user", "Compressor runs. Fan no rotate. 1.9 A shaft locked. Cap 15 uF."),
        ]
        facts, card = _card(fan_live, FISHING)
        self.assertEqual(facts.get("coleman_fan_high"), "live")
        self.assertFalse(coleman_motor_board_evidence_complete(facts))
        self.assertEqual(card, FISHING)

    def test_blank_reply_when_evidence_is_complete_is_the_card(self):
        facts, card = _card(PROVE, "")
        self.assertTrue(coleman_motor_board_evidence_complete(facts))
        self.assertTrue(card.strip())
        self.assertTrue(reply_names_coleman_motor_board_only(card), card)
        self.assertFalse(reply_fishes_coleman_more_tests(card))


if __name__ == "__main__":
    unittest.main()
