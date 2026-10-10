"""v4.19.27: a firm repair stays firm, and an answered check is not asked again."""
import unittest

from gd_library_coach import (
    FURNACE_WALL_TSTAT_LINE,
    avoid_duplicate_reply,
    ensure_furnace_wall_thermostat,
    polish_shop_reply,
)


class TestFirmRepairStays(unittest.TestCase):
    def test_s04_restates_the_spark_free_thermostat(self):
        history = [
            {
                "role": "user",
                "content": (
                    "Furrion FCR10; dial OFF but compressor still running; "
                    "fridge ice-cold / overcooling after weeks parked plugged in."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Replace the Spark-Free Thermostat, part G 2021128850 "
                    "(retail C-FCR10DCGTA-007). Follow the steps on pages 43–45: "
                    "remove housing, seat probe straight, align clocking pin, "
                    "tighten lock nut, reconnect wires.\n"
                    "📖 Source: CCD-0008122 - pages 31, 43, 45"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Opened C (blue) and T (black) at the thermostat, no jumper, "
                    "left apart: compressor stopped."
                ),
            },
        ]
        reply = polish_shop_reply(
            "Check the reading on this unit and write it down.",
            history,
            "What is the repair?",
            "Refrigerators",
            "Furrion FCR10",
        )
        low = reply.lower()
        self.assertIn("the repair is to replace the spark-free thermostat", low)
        self.assertNotIn("the repair is to follow", low)
        self.assertNotIn("check the reading on this unit", low)

    def test_s06_does_not_reask_the_can_unplug(self):
        history = [
            {
                "role": "user",
                "content": (
                    "Level Up Advantage 807662 Manual Mode flashes then dumps back to home. "
                    "Auto Level still works."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Leave the rubber-boot terminator in, unplug only the Firefly cable, "
                    "and report whether Manual Mode holds."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Unplugged the wired Firefly coach CAN cable, rubber-boot terminator "
                    "left in: Manual Mode stays."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Real fix is Firefly USB firmware update: read GUI + CCM from Settings, "
                    "call Firefly 574-825-4600, use USB stick 4 GB or smaller."
                ),
            },
        ]
        reply = avoid_duplicate_reply(
            "Leave the rubber-boot terminator in. Unplug only the Firefly cable, try Manual Mode again, and report whether it holds. If Manual Mode holds, call Firefly at 574-825-4600 and update the firmware with a USB stick of 4 GB or smaller.",
            history,
            "What is the repair?",
            "Leveling",
            "Lippert Level Up Advantage 807662",
        )
        low = reply.lower()
        self.assertIn("the repair is to update the firefly firmware", low)
        self.assertNotIn("unplug only", low)
        self.assertNotIn("report whether it holds", low)
        self.assertIn("📖", reply)

    def test_s08_continuity_ok_is_the_thermostat(self):
        history = [
            {"role": "user", "content": "Will not blow warm; fan turns on then shuts off."},
            {
                "role": "user",
                "content": "Thermostat bypassed at the furnace: the furnace operates.",
            },
            {
                "role": "assistant",
                "content": (
                    "Prove the sail switch with the blower running. "
                    "Report power in and power out before any thermostat replacement."
                ),
            },
        ]
        conditional = (
            "With the blower running, measure power in and power out at the sail switch. "
            "If power is present in and out, replace the wall thermostat."
        )
        opened = ensure_furnace_wall_thermostat(
            conditional,
            history,
            "Sail switch continuity OK",
            "Furnaces",
            "Suburban NT-20SEQT",
        )
        self.assertEqual(opened, FURNACE_WALL_TSTAT_LINE)
        reply = avoid_duplicate_reply(
            opened,
            history,
            "Sail switch continuity OK",
            "Furnaces",
            "Suburban NT-20SEQT",
        )
        self.assertIn("replace the wall thermostat", reply.lower())
        self.assertNotIn("measure power", reply.lower())

    def test_s09_both_bypasses_replace_the_ceiling_selector(self):
        history = [
            {"role": "user", "content": "AC turns on but will not blow cold."},
            {"role": "user", "content": "Peacemaker bypass at the rooftop unit cools."},
            {
                "role": "assistant",
                "content": (
                    "Bypass the ceiling selector and report whether it cools. "
                    "If both bypasses cool, replace the ceiling thermostat/selector.\n"
                    "📖 Source: Dometic Brisk II, page 23"
                ),
            },
        ]
        reply = polish_shop_reply(
            "Check the reading on this unit and write it down.",
            history,
            "Bypassing the ceiling controls also cools.",
            "Air Conditioning",
            "B57915E711J0EMX",
        )
        low = reply.lower()
        self.assertIn("replace the ceiling thermostat", low)
        self.assertNotIn("check the reading on this unit", low)
        self.assertNotIn("bypass the ceiling selector and report", low)
        history = history + [
            {"role": "user", "content": "Bypassing the ceiling controls also cools."},
            {"role": "assistant", "content": reply},
        ]
        again = polish_shop_reply(
            history[2]["content"],
            history,
            "What is the repair?",
            "Air Conditioning",
            "B57915E711J0EMX",
        )
        self.assertIn("the repair is to replace the ceiling thermostat", again.lower())
        self.assertNotEqual(again.strip(), history[2]["content"].strip())
        self.assertNotIn("check the reading on this unit", again.lower())


if __name__ == "__main__":
    unittest.main()
