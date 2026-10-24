"""Water Heaters / Girard GSWH-2 library retrieval: prefer CCD-0009390 over Unity."""
import re
import unittest
from pathlib import Path

from gd_library_coach import (
    figure_render_honesty_note,
    is_air_conditioning_context,
    is_fcr_e2_fan_fault_context,
    is_unity_board_manual,
    is_water_heater_context,
    is_water_heater_library_title,
)

ROOT = Path(__file__).resolve().parents[1]

CHASE_MODEL = "Girard GSWH-2"
CHASE_CONCERN = "water heater stopped working… E8"
CHASE_QUERY = f"{CHASE_MODEL} {CHASE_CONCERN}"

UNITY = {
    "title": "Lippert OneControl M Series Unity Board SM",
    "category": "Electrical",
    "excerpt": (
        "OneControl Unity M-Series reversing output for awning and slide. "
        "BAT1 BAT2 X270 hold EXTEND RETRACT polarity reverse."
    ),
    "page": 4,
}
GSWH = {
    "title": "Girard GSWH-2 Troubleshooting Manual CCD-0009390",
    "category": "Water Heaters",
    "excerpt": (
        "Girard GSWH-2 tankless water heater. E8 air pressure switch. "
        "Petit Tube restriction / air pressure switch path."
    ),
    "page": 12,
}
FRIDGE = {
    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
    "category": "Refrigerators",
    "excerpt": "E2 Fan Fault Current. Freezer evaporator fan F+ F-.",
    "page": 27,
}
FACT = {
    "title": "Furrion FACT12SA2 Rooftop Air Conditioner SM",
    "category": "Air Conditioning",
    "excerpt": "Furrion FACT rooftop air conditioner. E2 freeze sensor.",
    "page": 8,
}

LIBRARY = [UNITY, GSWH, FRIDGE, FACT]


class TestWaterHeaterDetect(unittest.TestCase):

    def test_gswh2_e8_without_category(self):
        self.assertTrue(is_water_heater_context("", "GSWH-2", "E8"))
        self.assertTrue(is_water_heater_context("", "", "GSWH-2 E8"))

    def test_petit_tube_and_air_pressure(self):
        self.assertTrue(is_water_heater_context("", "", "Petit Tube restriction"))
        self.assertTrue(
            is_water_heater_context("Water Heaters", "Girard", "E8 air pressure switch")
        )


    def test_rooftop_ac_e2_is_not_water_heater(self):
        self.assertFalse(is_water_heater_context("Air Conditioning", "Furrion FACT12SA2", "E2"))
        self.assertTrue(is_air_conditioning_context("Air Conditioning", "Furrion FACT12SA2", "E2"))

    def test_bare_e8_is_not_enough(self):
        self.assertFalse(is_water_heater_context("", "", "E8"))


class TestWaterHeaterRanking(unittest.TestCase):


    def test_title_helpers(self):
        self.assertTrue(is_water_heater_library_title(GSWH["title"]))
        self.assertFalse(is_water_heater_library_title(UNITY["title"]))
        self.assertFalse(is_water_heater_library_title(FRIDGE["title"]))
        self.assertFalse(is_water_heater_library_title(FACT["title"]))
        self.assertTrue(is_unity_board_manual(UNITY["title"]))


class TestWaterHeaterHonesty(unittest.TestCase):


    def test_figure_render_fail_names_gswh_not_missing_library(self):
        note = figure_render_honesty_note(GSWH["title"], True)
        self.assertIn("CCD-0009390", note)
        self.assertIn("could not render", note.lower())
        self.assertNotIn("lacks the procedure", note.lower())
        unity_note = figure_render_honesty_note(UNITY["title"], True)
        self.assertIn("wrong book", unity_note.lower())
        self.assertIn("gswh", unity_note.lower())


if __name__ == "__main__":
    unittest.main()
