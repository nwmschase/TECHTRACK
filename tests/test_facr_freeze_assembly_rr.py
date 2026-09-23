"""FACR freeze + interior leak continues to rooftop assembly R&R after the three proves."""
import re
import unittest

from gd_library_coach import (
    FACR_ASSEMBLY_RR_SHOP_LINE,
    FACR_FREEZE_ASSEMBLY_LOCK,
    OPEN_LIBRARY_COACH_RULE,
    ensure_facr_freeze_assembly_rr,
    facr_freeze_proves_from_text,
    facr_proves_complete,
    facr_terminal_path_complete,
    facts_from_chat,
    reply_loops_drain_only,
    reply_names_rooftop_assembly_rr,
    reply_opens_fuse_12v_no_power,
    reply_stalls_searching_manuals,
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
        self.assertIn("rooftop assembly", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("CCD-0007990", FACR_FREEZE_ASSEMBLY_LOCK)
        self.assertIn("searching manuals", FACR_FREEZE_ASSEMBLY_LOCK.lower())

    def test_stall_and_drain_loop_continue_to_assembly_rr(self):
        facts = facr_freeze_proves_from_text(PROVES)
        self.assertTrue(reply_stalls_searching_manuals(STALL))
        self.assertTrue(reply_loops_drain_only(DRAIN_LOOP))
        for bad in (STALL, DRAIN_LOOP, "", "Error contacting AI: still searching manuals."):
            fixed = ensure_facr_freeze_assembly_rr(bad, facts)
            self.assertTrue(reply_names_rooftop_assembly_rr(fixed), fixed[:400])
            self.assertIn("CCD-0007990", fixed)
            self.assertIn("condensate", fixed.lower())
            self.assertIn("rooftop assembly", fixed.lower())
            self.assertIn("replace the rooftop assembly", fixed.lower())
            self.assertFalse(reply_stalls_searching_manuals(fixed), fixed[:300])
            self.assertFalse(reply_loops_drain_only(fixed), fixed[:300])
        self.assertIn(FACR_ASSEMBLY_RR_SHOP_LINE.split("\n")[0][:40], ensure_facr_freeze_assembly_rr(STALL, facts))

    def test_complete_reply_is_left_alone(self):
        facts = facr_freeze_proves_from_text(PROVES)
        self.assertTrue(reply_names_rooftop_assembly_rr(GOOD))
        self.assertEqual(ensure_facr_freeze_assembly_rr(GOOD, facts), GOOD)

    def test_searching_manuals_before_proves_does_not_stall(self):
        fixed = ensure_facr_freeze_assembly_rr("Searching manuals. I will look through the manuals.")
        self.assertFalse(reply_stalls_searching_manuals(fixed), fixed[:300])
        self.assertIn("CCD-0007990", fixed)
        self.assertIn("rooftop assembly", fixed.lower())
        self.assertNotIn("searching manuals.", fixed.lower())


def _chat(turns):
    """History is every turn but the last user line, matching a live GD send."""
    history = [{"role": role, "content": text} for role, text in turns[:-1]]
    latest = turns[-1][1]
    return history, latest


def _terminal_card(turns, model_reply):
    history, latest = _chat(turns)
    facts = facts_from_chat(history, latest)
    return facts, ensure_facr_freeze_assembly_rr(model_reply, facts)


class TestFacrTerminalCard(unittest.TestCase):
    def test_blank_final_card_after_good_path_is_assembly_rr(self):
        facts, card = _terminal_card(GOOD_PATH, "")
        self.assertTrue(facr_terminal_path_complete(facts), facts)
        self.assertFalse(facr_proves_complete(facts), facts)
        self.assertTrue(card.strip(), "final assistant card was blank")
        self.assertTrue(reply_names_rooftop_assembly_rr(card), card)
        self.assertIn("CCD-0007990", card)
        self.assertIn("rooftop assembly", card.lower())
        self.assertIn("refrigerant pressures", card.lower())
        self.assertFalse(reply_opens_fuse_12v_no_power(card), card)
        self.assertIsNone(re.search(r"page\s+\d+", card, re.I))
        for blank in ("   ", "\n", "Error contacting AI: 413 request too large"):
            _, again = _terminal_card(GOOD_PATH, blank)
            self.assertTrue(again.strip(), blank)
            self.assertTrue(reply_names_rooftop_assembly_rr(again), again[:400])

    def test_path_missing_pressure_stays_blank(self):
        short = GOOD_PATH[:-2]
        facts, card = _terminal_card(short, "")
        self.assertFalse(facr_terminal_path_complete(facts), facts)
        self.assertFalse(card.strip(), card)

    def test_suction_still_iced_does_not_climax(self):
        iced = []
        for role, text in GOOD_PATH:
            if text == "No.":
                iced.append((role, "Yes."))
            else:
                iced.append((role, text))
        facts, card = _terminal_card(iced, "")
        self.assertNotEqual(facts.get("facr_suction"), "clear")
        self.assertFalse(facr_terminal_path_complete(facts), facts)
        self.assertFalse(card.strip(), card)

    def test_readings_without_the_path_do_not_climax(self):
        turns = [
            ("user", COMPLAINT),
            (
                "user",
                "2 kΩ @ 25°C. Cool setpoint is 68°F. Open nozzles. "
                "72°F ambient. 68/235 psi.",
            ),
        ]
        facts, card = _terminal_card(turns, "")
        self.assertFalse(facr_terminal_path_complete(facts), facts)
        self.assertFalse(reply_names_rooftop_assembly_rr(card), card)
        self.assertFalse(card.strip(), card)

    def test_fuse_first_after_good_path_becomes_assembly_rr(self):
        fuse = (
            "Check the 15A fuse at the front vent cover, then meter the 12V inverter supply."
        )
        facts, card = _terminal_card(GOOD_PATH, fuse)
        self.assertTrue(facr_terminal_path_complete(facts))
        self.assertTrue(reply_names_rooftop_assembly_rr(card), card)
        self.assertFalse(reply_opens_fuse_12v_no_power(card), card)
        self.assertIn("CCD-0007990", card)


if __name__ == "__main__":
    unittest.main()
