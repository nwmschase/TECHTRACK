"""Level Up Advantage / 807662 library retrieval: prefer Level-Up/OCTP/TI over Unity."""
import unittest

from gd_library_coach import (
    figure_render_honesty_note,
    is_ground_control_manual,
    is_level_up_advantage_context,
    is_level_up_library_title,
    is_unity_board_manual,
)

CHASE_MODEL = (
    "Lippert Level Up Advantage Leveling Controller w/ Slide Output, label 807662 / 25499"
)
CHASE_CONCERN = (
    "Manual Mode flashes then returns to home/first screen. "
    "Connectors: Touch Pad, Remote Sensor, Pump, CAN, Slide Output, Power."
)
CHASE_QUERY = f"{CHASE_MODEL} {CHASE_CONCERN} LCD wiring"

UNITY = {
    "title": "Lippert OneControl M Series Unity Board SM",
    "category": "Electrical",
    "excerpt": (
        "OneControl Unity M-Series reversing output for awning and slide. "
        "BAT1 BAT2 X270 hold EXTEND RETRACT polarity reverse."
    ),
    "page": 4,
}
TI005 = {
    "title": "TI-005 Electronic Leveling Troubleshooting Guide",
    "category": "Leveling",
    "excerpt": (
        "Level-Up hydraulic leveling controller Manual Mode. "
        "Touch pad LCD returns to home screen. Pump and slide output."
    ),
    "page": 2,
}
QR092 = {
    "title": "QR-092 Level-Up OCTP wiring",
    "category": "Leveling",
    "excerpt": "Level-Up OCTP touch pad LCD wiring diagram. Controller harness.",
    "page": 1,
}
QR059 = {
    "title": "QR-059 ID guide",
    "category": "ID & Reference",
    "excerpt": "Identify Level-Up leveling controller 807662 vs other Lippert boards.",
    "page": 1,
}
TI170 = {
    "title": "TI-170",
    "category": "Leveling",
    "excerpt": "Level-Up leveling notes and controller identification.",
    "page": 1,
}
GROUND = {
    "title": "Ground Control LCD SM",
    "category": "Leveling",
    "excerpt": "Ground Control electric leveling LCD. Not hydraulic Level Up 807662.",
    "page": 3,
}

LIBRARY = [UNITY, TI005, QR092, QR059, TI170, GROUND]


class TestLevelUpDetect(unittest.TestCase):

    def test_part_numbers_and_octp(self):
        self.assertTrue(is_level_up_advantage_context("", "807662", "won't dump"))
        self.assertTrue(is_level_up_advantage_context("", "25499", "Manual Mode"))
        self.assertTrue(is_level_up_advantage_context("Leveling", "", "OCTP wiring"))

    def test_ground_control_alone_is_not_level_up_advantage(self):
        self.assertFalse(
            is_level_up_advantage_context("Leveling", "Ground Control LCD", "no display")
        )
        self.assertTrue(is_ground_control_manual("Ground Control LCD SM"))

    def test_fridge_is_not_level_up(self):
        self.assertFalse(
            is_level_up_advantage_context("Refrigerators", "Furrion FCR10", "not cooling")
        )


class TestLevelUpRanking(unittest.TestCase):


    def test_title_helpers(self):
        self.assertTrue(is_level_up_library_title(TI005["title"]))
        self.assertTrue(is_level_up_library_title(QR092["title"]))
        self.assertFalse(is_level_up_library_title(UNITY["title"]))
        self.assertFalse(is_level_up_library_title(GROUND["title"]))
        self.assertTrue(is_unity_board_manual(UNITY["title"]))


class TestLevelUpHonesty(unittest.TestCase):


    def test_figure_render_fail_names_level_up_not_missing_library(self):
        note = figure_render_honesty_note(TI005["title"], True)
        self.assertIn("TI-005", note)
        self.assertIn("could not render", note.lower())
        self.assertNotIn("lacks the procedure", note.lower())
        unity_note = figure_render_honesty_note(UNITY["title"], True)
        self.assertIn("wrong book", unity_note.lower())
        self.assertIn("level-up", unity_note.lower())


if __name__ == "__main__":
    unittest.main()
