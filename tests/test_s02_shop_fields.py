"""S02 Coleman-Mach 2111-0001 uses the eight-field shop template."""
import unittest

import manual_figures as mf
from bay_procedure import compile_bay_procedure
from gd_library_coach import (
    COLEMAN_MOTOR_BOARD_AUTH_LINE,
    avoid_duplicate_reply,
    ensure_coleman_motor_board_auth,
    reply_authorizes_coleman_full_assembly,
    reply_fishes_coleman_more_tests,
    reply_names_coleman_motor_board_only,
)

TURNS = [
    "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead.",
    "122 VAC at the control box. Fan High is dead.",
    "Peacemaker bypass: compressor runs, fan does not rotate. About 1.91 A, shaft locked.",
    "Fan run capacitor 15 µF, rated 15 µF.",
]


def _how(text: str) -> str:
    for line in (text or "").splitlines():
        if line.startswith("HOW:"):
            return line.split(":", 1)[1].strip()
    return ""


class TestColemanShopFields(unittest.TestCase):
    def test_each_turn_uses_the_eight_fields(self):
        history = []
        replies = []
        for latest in TURNS:
            reply = avoid_duplicate_reply(
                "Check continuity of the windings.",
                history,
                latest,
                "Air Conditioning",
                "Coleman-Mach 2111-0001",
            )
            replies.append(reply)
            for name in mf.STEP_FIELDS:
                self.assertIn(f"{name}:", reply, name)
            self.assertNotIn("UNCONFIRMED", reply)
            self.assertLessEqual(mf._word_count(_how(reply)), 15, _how(reply))
            self.assertIn("Yes, go to the next step.", reply)
            self.assertIn("No, do this step again.", reply)
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
        self.assertIn("peacemaker", replies[0].lower())
        self.assertIn("authorization", replies[-1].lower())
        self.assertTrue(reply_names_coleman_motor_board_only(replies[-1]), replies[-1])
        self.assertFalse(reply_fishes_coleman_more_tests(replies[-1]), replies[-1])
        self.assertFalse(reply_authorizes_coleman_full_assembly(replies[-1]))
        self.assertIsNone(__import__("re").search(r"page\s+\d+", replies[-1], __import__("re").I))
        for left, right in zip(replies, replies[1:]):
            self.assertNotEqual(left.strip().lower(), right.strip().lower())

    def test_auth_card_keeps_the_manual_titles(self):
        self.assertIn("1976-536", COLEMAN_MOTOR_BOARD_AUTH_LINE)
        self.assertIn("1976-603", COLEMAN_MOTOR_BOARD_AUTH_LINE)
        self.assertIn("1976-695", COLEMAN_MOTOR_BOARD_AUTH_LINE)
        self.assertIn("Peacemaker", COLEMAN_MOTOR_BOARD_AUTH_LINE)
        self.assertIn("12VDC", COLEMAN_MOTOR_BOARD_AUTH_LINE)
        self.assertNotIn("continuity", COLEMAN_MOTOR_BOARD_AUTH_LINE.lower())

    def test_bay_order_uses_the_same_fields(self):
        proc = compile_bay_procedure(
            concern="Coleman-Mach 2111-0001 ran about 2 minutes then dead",
            brand="Coleman-Mach",
            model="2111-0001",
            category="Air Conditioning",
            chunks=[],
        )
        self.assertGreaterEqual(len(proc.bay_order), 4)
        blob = " ".join(proc.bay_order)
        for name in mf.STEP_FIELDS:
            self.assertIn(name + ":", blob)
        self.assertNotIn("UNCONFIRMED", blob)
        low = blob.lower()
        self.assertIn("pin 5", low)
        self.assertIn("pin 9", low)
        self.assertIn("peacemaker", low)
        self.assertIn("15", low)
        self.assertIn("fan motor", low)
        self.assertIn("control board", low)
        self.assertIn("do not replace the full 2111-0001", low)
        self.assertIn("confirmed correction", low)
        card = ensure_coleman_motor_board_auth(
            "Check continuity of the windings.",
            {
                "coleman_fan_high": "dead",
                "coleman_compressor": "ok",
                "coleman_fan_motor": "locked",
                "coleman_stall_amps": "reported",
                "coleman_cap": "ok",
            },
        )
        self.assertIn("WHERE:", card)
        self.assertNotIn("continuity", card.lower())
