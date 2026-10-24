"""v4.19.26: proved repairs, answered checks, and no copied turn."""
import unittest

from gd_library_coach import (
    FURNACE_WALL_TSTAT_LINE,
    _conditional_lines,
    avoid_duplicate_reply,
    polish_shop_reply,
)


class TestRepairStatement(unittest.TestCase):
    def test_s01_does_not_restate_a_clean_filter_as_the_repair(self):
        history = [
            {
                "role": "user",
                "content": (
                    "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC "
                    "inside while running, not raining."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Check the return air filter for dirt or blockage. "
                    "Clean it if dirty, or replace if it won't come clean."
                ),
            },
            {"role": "user", "content": "Filter is clean."},
            {
                "role": "assistant",
                "content": "Check the evaporator blower for free rotation.",
            },
            {"role": "user", "content": "Evaporator fan spins freely with good airflow."},
            {"role": "user", "content": "Freeze sensor reads 2 kΩ at 25°C."},
        ]
        reply = polish_shop_reply(
            "The repair is clean it if dirty, or replace if it won't come clean.",
            history,
            "What is the repair?",
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        low = reply.lower()
        self.assertNotIn("clean it if dirty", low)
        self.assertNotIn("won't come clean", low)
        self.assertNotRegex(low, r"the repair is (?!to\b)\w")
        self.assertIn("rooftop", low)

    def test_s11_repair_statement_uses_to_plus_verb(self):
        history = [
            {"role": "user", "content": "Intermittent E3; sometimes normal."},
            {
                "role": "assistant",
                "content": (
                    "The freeze sensor is off the coil. "
                    "Reseat it on the evaporator coil and retest."
                ),
            },
            {
                "role": "user",
                "content": "Freeze sensor was found disconnected, not in the evaporator.",
            },
        ]
        reply = polish_shop_reply(
            "The repair is reseat it on the evaporator coil and retest.",
            history,
            "What is the repair?",
            "Air Conditioning",
            "FACT12SA2-PS",
        )
        low = reply.lower()
        self.assertIn("the repair is to reseat it", low)
        self.assertNotIn("the repair is reseat", low)


class TestProvedRepair(unittest.TestCase):

    def test_s05_does_not_ask_the_dial_again(self):
        history = [
            {
                "role": "user",
                "content": "Furrion FCR10 fridge; rear-wall icing about halfway from the top.",
            },
            {
                "role": "assistant",
                "content": "Check whether the temperature dial is at maximum and report the setting.",
            },
            {"role": "user", "content": "Dial is at max."},
            {"role": "assistant", "content": "Check the door gasket and report whether it seals."},
            {"role": "user", "content": "Door gasket is sealing properly."},
        ]
        reply = polish_shop_reply(
            "Check whether the temperature dial is at maximum. Report the setting.",
            history,
            "Fridge is still cooling.",
            "Refrigerators",
            "FCR10DCGTA-BL",
        )
        low = reply.lower()
        self.assertNotIn("at maximum", low)
        self.assertNotIn("report the setting", low)
        self.assertTrue(reply.strip())

    def test_s11_voltage_is_not_asked_again(self):
        history = [
            {"role": "user", "content": "Intermittent E3; sometimes normal."},
            {
                "role": "assistant",
                "content": (
                    "Measure 12 V and the data line at the connector, and check whether "
                    "the freeze sensor is fastened on the evaporator coil."
                ),
            },
        ]
        reply = polish_shop_reply(
            "Measure 12 V and the data line at the connector again.",
            history,
            "Thermostat reads 13.13 V and the control box 13.59 V; wiring is good.",
            "Air Conditioning",
            "FACT12SA2-PS",
        )
        low = reply.lower()
        self.assertNotIn("measure 12 v", low)
        self.assertNotIn("data line", low)
        self.assertIn("freeze sensor", low)


class TestNoCopiedTurn(unittest.TestCase):
    def test_s10_keeps_rear_five_times_on_every_line(self):
        lines = _conditional_lines(
            [],
            "Auto-level lifts driver-side tires though nearly level.",
            "Leveling",
            "Lippert Ground Control 343633",
        )
        self.assertGreaterEqual(len(lines), 3)
        for line in lines:
            self.assertIn("front five times", line.lower())
            self.assertIn("rear five times", line.lower())
            self.assertIn("enter", line.lower())

    def test_a_ground_turn_is_not_copied(self):
        previous = (
            "If the plugs are seated and one side still lifts, press FRONT five times, "
            "then REAR five times, then ENTER. If the coach sits level after that, "
            "the zero-point calibration is the repair."
        )
        history = [
            {"role": "user", "content": "Auto-level lifts driver-side tires though nearly level."},
            {"role": "assistant", "content": previous},
        ]
        reply = avoid_duplicate_reply(
            previous,
            history,
            "Not checked yet — what do you recommend next?",
            "Leveling",
            "Lippert Ground Control 343633",
        )
        self.assertNotEqual(reply.strip().lower(), previous.strip().lower())
        self.assertIn("rear five times", reply.lower())


if __name__ == "__main__":
    unittest.main()
