"""FACR freeze + interior leak authorizes rooftop assembly R&R only after pressures."""
import re
import unittest

from gd_library_coach import (
    facr_freeze_proves_from_text,
    facr_proves_complete,
    facr_terminal_path_complete,
    reply_names_rooftop_assembly_rr,
)

# Live GD walk: coach names the check, tech answers short. The ohm / psi /
# temperature strings are the readings that were reported, not a new pass band.
COMPLAINT = (
    "Furrion FACR08HESA2-PS rooftop AC. Water leaking from the forward AC "
    "inside while running, not raining. Frost/ice on the evaporator."
)
GOOD_PATH = [
    ("user", COMPLAINT),
    ("assistant", "Inspect the condensate drain."),
    ("user", "Clear."),
    ("assistant", "Inspect the evaporator pan and the base-pan slope."),
    ("user", "Good."),
    ("assistant", "Check the filter and the fan."),
    ("user", "Good."),
    ("assistant", "Is the suction line iced?"),
    ("user", "No."),
    ("assistant", "Read the freeze sensor at 25°C."),
    ("user", "2 kΩ @ 25°C."),
    ("assistant", "What is the cool setpoint on the thermostat?"),
    ("user", "68°F."),
    ("assistant", "Are the nozzles open, and what is ambient?"),
    ("user", "Open nozzles. 72°F ambient."),
    ("assistant", "Read refrigerant pressures."),
    ("user", "68/235 psi. Frost and the interior leak are still there."),
]

PROVES = "Drain is clear. Fan-filter OK. Freeze sensor good. Interior leak is still there."
STALL = "Searching the manuals for a condensate procedure. Clear the drain again and retest."
DRAIN_LOOP = (
    "The drain is the whole job. Clear the drain, then check the drain, then clean the drain."
)
GOOD = (
    "Drain, fan/filter, and freeze sensor are already proved. "
    "Continue to rooftop assembly R&R on the CCD-0007990 condensate and assembly path. "
    "Replace the rooftop assembly.\n"
    "?? Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
)


class TestFacrAssemblyClimax(unittest.TestCase):
    def test_three_proves_are_recognized(self):
        facts = facr_freeze_proves_from_text(PROVES)
        self.assertTrue(facr_proves_complete(facts))
        self.assertEqual(facts.get("facr_drain"), "clear")
        self.assertEqual(facts.get("facr_fan_filter"), "ok")
        self.assertEqual(facts.get("facr_freeze_sensor"), "good")
        split = {}
        for line in (
            "condensate drain is clear",
            "fan and filter are good",
            "freeze sensor tests good",
        ):
            split.update(facr_freeze_proves_from_text(line))
        self.assertTrue(facr_proves_complete(split))


def _chat(turns):
    """History is every turn but the last user line, matching a live GD send."""
    history = [{"role": role, "content": text} for role, text in turns[:-1]]
    latest = turns[-1][1]
    return history, latest


if __name__ == "__main__":
    unittest.main()
