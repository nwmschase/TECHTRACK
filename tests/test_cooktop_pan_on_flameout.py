"""Suburban / gas cooktop pan-on flame-out: tip position with pan before parts R&R."""
import unittest

from gd_library_coach import (
    is_cooktop_pan_on_flameout_context,
    is_cooktop_range_context,
    is_fcr_e2_fan_fault_context,
    is_water_heater_context,
)

WO_MODEL = "Suburban cooktop"
WO_COMPLAINT = (
    "Burner lights, then goes out when a pan is placed (either burner)"
)

SUBURBAN_RANGE = {
    "title": "Suburban Range/Cooktops SM",
    "category": "Range & Cooktops",
    "page": 12,
    "excerpt": (
        "Suburban range / cooktop burner. Thermocouple / flame sensor at the burner head. "
        "Tip position in the flame with cookware on."
    ),
}
FURNACE_SAIL = {
    "title": "Suburban Furnace Service Manual",
    "category": "Furnaces",
    "page": 8,
    "excerpt": "Sail switch IN/OUT. Blower running. Draft and igniter path. No cooktop.",
}
IGNITER_FIRST = {
    "title": "Generic LP igniter notes",
    "category": "Furnaces",
    "page": 3,
    "excerpt": "Check igniter, draft, regulator, orifice. Replace safety valve.",
}
THERMOCOUPLE_RR = {
    "title": "Suburban Range/Cooktops SM",
    "category": "Range & Cooktops",
    "page": 20,
    "excerpt": "Replace the thermocouple. Safety valve R&R. No tip or pan check on this page.",
}

LIBRARY = [FURNACE_SAIL, IGNITER_FIRST, THERMOCOUPLE_RR, SUBURBAN_RANGE]


class TestCooktopDetect(unittest.TestCase):
    def test_pan_on_shutoff_is_cooktop_not_furnace_marker(self):
        self.assertTrue(is_cooktop_range_context("", WO_MODEL, WO_COMPLAINT))
        self.assertTrue(
            is_cooktop_pan_on_flameout_context("", WO_MODEL, WO_COMPLAINT)
        )
        self.assertTrue(
            is_cooktop_pan_on_flameout_context(
                "Range & Cooktops", WO_MODEL, WO_COMPLAINT
            )
        )

    def test_suburban_furnace_is_not_cooktop(self):
        self.assertFalse(
            is_cooktop_pan_on_flameout_context(
                "Furnaces", "Suburban SF-42", "furnace won't light sail switch"
            )
        )
        self.assertFalse(
            is_cooktop_range_context("Furnaces", "Suburban SF-42", "no heat blower runs")
        )

    def test_cooktop_wont_spark_without_pan_is_not_flameout_path(self):
        self.assertTrue(is_cooktop_range_context("", "Suburban cooktop", "won't spark"))
        self.assertFalse(
            is_cooktop_pan_on_flameout_context("", "Suburban cooktop", "won't spark")
        )

    def test_fridge_and_water_heater_lose(self):
        self.assertFalse(
            is_cooktop_pan_on_flameout_context(
                "Refrigerators", "Furrion FCR10", "not cooling"
            )
        )
        self.assertFalse(is_fcr_e2_fan_fault_context("", WO_MODEL, WO_COMPLAINT))
        self.assertFalse(is_water_heater_context("", WO_MODEL, WO_COMPLAINT))


if __name__ == "__main__":
    unittest.main()
