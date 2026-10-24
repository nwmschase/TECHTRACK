"""Coleman-Mach 2111-0001 climax: fan motor + control board only."""
import re
import unittest

from gd_library_coach import (
    is_coleman_2111_context,
    reply_authorizes_coleman_full_assembly,
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


if __name__ == "__main__":
    unittest.main()
