"""Live v4.19.16 Guided Diagnostics regressions.

The strings below are the ones that opened the live replies.
"""
import unittest

from gd_library_coach import (
    BAL_TONGUE_PROVE_SHOP_LINE,
    DIAL_OFF_RUN_SHOP_LINE,
    DOMETIC_NOCOOL_CONFIRM_FAN,
    DOMETIC_NOCOOL_OPEN,
    FACR_REPORTED_ASSEMBLY_RR_LINE,
    FACT12_E2_PROVE_LINE,
    FACT12_FREEZE_RESECURE_LINE,
    FURNACE_SAIL_PROVE_LINE,
    FURNACE_WALL_TSTAT_LINE,
    GIRARD_BLOWER_SUCTION_LINE,
    GIRARD_PETIT_ALIGN_LINE,
    GROUND_CONTROL_LEVEL_LINE,
    GROUND_CONTROL_PROVE_LINE,
    ICE_MOISTURE_SHOP_LINE,
    ensure_cooktop_tip_pan_check,
    ensure_facr_freeze_assembly_rr,
    ensure_fact12_freeze_resecure,
    ensure_furnace_wall_thermostat,
    ensure_girard_petit_align,
    facr_proves_from_chat,
    facr_reported_assembly_rr_line,
    facr_reported_path_supports_rr,
    facts_from_chat,
    furnace_rw_jumper_ran,
    is_fact12_freeze_code_context,
    reply_loops_furnace_12v,
    reply_names_rooftop_assembly_rr,
    strip_leaked_prompt,
)

FUSE_TREE = (
    "is not a fuse or 12V-continuity tree. Skip CCD-0008122 Fuse (p.19)"
)
FUSE_PATH = "Do not open the 15A fuse / 12V inverter path"

S04_HEARD = (
    "Heard: FCR10 dial OFF, compressor still running, overcooling.\n\n"
    "Leave the dial fully OFF."
)
S05_HEARD = (
    "Rear-wall icing halfway down the back is noted.\n\n"
    "Next: What is the temperature dial set to right now?"
)


class TestGuardEcho(unittest.TestCase):
    def test_exact_guard_strings_are_stripped_in_front_of_the_answer(self):
        dial = strip_leaked_prompt(f"{DIAL_OFF_RUN_SHOP_LINE}\n\n{S04_HEARD}")
        ice = strip_leaked_prompt(f"{ICE_MOISTURE_SHOP_LINE}\n\n{S05_HEARD}")
        for cleaned, kept in ((dial, S04_HEARD), (ice, S05_HEARD)):
            self.assertNotIn(FUSE_TREE, cleaned)
            self.assertNotIn(FUSE_PATH, cleaned)
            self.assertIn(kept.split("\n")[0], cleaned)
        self.assertNotIn("Skip CCD-0008122 Fuse (p.19)", dial)
        self.assertNotIn("Do not open the 15A fuse / 12V inverter path", ice)
        self.assertIn("Heard:", dial)
        self.assertIn("Rear-wall icing", ice)

    def test_a_guard_that_is_the_whole_reply_stays(self):
        dial = strip_leaked_prompt(DIAL_OFF_RUN_SHOP_LINE)
        ice = strip_leaked_prompt(ICE_MOISTURE_SHOP_LINE)
        self.assertNotIn(FUSE_TREE, dial)
        self.assertNotIn("skip ccd-0008122", dial.lower())
        self.assertIn("compressor stops", dial.lower())
        self.assertNotIn(FUSE_PATH, ice)
        self.assertIn("ice and moisture", ice.lower())
        self.assertTrue(
            strip_leaked_prompt("Do not swap a level sensor.").lower().startswith("do not")
        )


class TestFurnaceBypassRepair(unittest.TestCase):
    def test_bypassed_furnace_that_operates_stops_the_12v_loop(self):
        history = [
            {"role": "user", "content": "Will not blow warm; fan turns on then shuts off."},
            {
                "role": "assistant",
                "content": (
                    "Bypass the wall thermostat at the furnace first. "
                    "Jumper the thermostat terminals on the furnace."
                ),
            },
            {
                "role": "user",
                "content": "Thermostat bypassed at the furnace: the furnace operates.",
            },
            {
                "role": "assistant",
                "content": (
                    "Next: Check for 12 VDC at the furnace thermostat terminals "
                    "while the wall thermostat is calling for heat."
                ),
            },
        ]
        blob = " ".join(m["content"] for m in history if m["role"] == "user")
        self.assertTrue(furnace_rw_jumper_ran(blob))
        loop = (
            "With wall thermostat calling for heat, check 12 VDC at the "
            "furnace thermostat terminals. Report the reading."
        )
        self.assertTrue(reply_loops_furnace_12v(loop))
        for latest in (
            "Not checked yet — what do you recommend next?",
            "What is the repair?",
        ):
            fixed = ensure_furnace_wall_thermostat(
                loop, history, latest, "Furnaces", "Suburban NT-20SEQT"
            )
            self.assertEqual(fixed, FURNACE_SAIL_PROVE_LINE)
            self.assertIn("sail switch", fixed.lower())
            self.assertNotIn("replace the wall thermostat", fixed.lower())
            self.assertNotIn("12 vdc", fixed.lower())
            self.assertFalse(reply_loops_furnace_12v(fixed))


class TestGirardAlignment(unittest.TestCase):
    def _history(self):
        return [
            {
                "role": "user",
                "content": (
                    "Customer states water heater stopped working. Was working "
                    "but no longer heats. Gives E8 error code."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Look through the exhaust vent for any blockage. "
                    "Confirm the plastic (petit) tube is connected."
                ),
            },
            {"role": "user", "content": "Tubing is clear."},
        ]

    def test_clear_tubing_and_a_next_ask_aligns_the_petit_tube(self):
        loop = (
            "Look through the exhaust vent for blockage, and confirm the "
            "petit tube faces away from the blower wheel."
        )
        fixed = ensure_girard_petit_align(
            loop,
            self._history(),
            "Not checked yet — what do you recommend next?",
            "(any)",
            "Girard GSWH-2",
            "Gives E8 error code.",
        )
        self.assertEqual(fixed, GIRARD_BLOWER_SUCTION_LINE)
        self.assertIn("suction", fixed.lower())
        self.assertIn("blower", fixed.lower())
        self.assertNotIn("burner flame", fixed.lower())
        self.assertNotIn("exhaust vent", fixed.lower())
        self.assertNotIn("blower wheel", fixed.lower())

    def test_aps_ok_is_the_alignment_fix(self):
        history = self._history() + [
            {
                "role": "assistant",
                "content": "Look through the exhaust vent for blockage.",
            }
        ]
        loop = (
            "Exhaust vent blockage and petit tube orientation still need checking. "
            "Look through the exhaust for blockage and confirm the petit tube "
            "faces away from the blower wheel."
        )
        fixed = ensure_girard_petit_align(
            loop,
            history,
            "APS and harness continuity are OK.",
            "(any)",
            "Girard GSWH-2",
            "Gives E8 error code.",
        )
        self.assertEqual(fixed, GIRARD_BLOWER_SUCTION_LINE)
        self.assertNotIn("burner flame", fixed.lower())


class TestFacrReportedPath(unittest.TestCase):
    def test_live_walk_authorizes_rr_instead_of_another_pressure_ask(self):
        turns = [
            (
                "user",
                "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward "
                "AC inside while running, not raining; frost/ice on evaporator.",
            ),
            ("assistant", "Check the condensation drain openings."),
            ("user", "Drain is clear, pan is clean and draining, base-pan slope is fine."),
            ("assistant", "Pull and inspect the return-air filter."),
            ("user", "Filter is clean."),
            ("assistant", "Verify the evaporator fan is running."),
            ("user", "Evaporator fan spins freely with good airflow."),
            ("assistant", "Confirm the nozzles are open."),
            ("user", "Nozzles are open."),
            ("assistant", "Measure the freeze sensor."),
            ("user", "Freeze sensor reads 2 kΩ at 25°C."),
        ]
        history = [{"role": role, "content": text} for role, text in turns[:-1]]
        latest = turns[-1][1]
        facts = facts_from_chat(history, latest)
        self.assertTrue(facr_reported_path_supports_rr(facts), facts)
        pressure = (
            "Next: check refrigerant pressures (high and low side) while the "
            "unit is running and icing."
        )
        card = ensure_facr_freeze_assembly_rr(pressure, facts)
        self.assertIn("refrigerant pressures", card.lower())
        self.assertFalse(reply_names_rooftop_assembly_rr(card), card)
        self.assertNotIn("replace the rooftop assembly", card.lower())
        self.assertEqual(facr_proves_from_chat(history, latest).get("facr_drain"), "clear")


class TestFact12E2(unittest.TestCase):
    def test_model_fact12_e2_reseats_the_freeze_sensor(self):
        complaint = "E2 error code; sometimes normal."
        self.assertTrue(
            is_fact12_freeze_code_context(
                "Air Conditioning", "FACT12SA2-PS", complaint
            )
        )
        self.assertNotIn("fact", complaint.lower())
        gap = (
            "The shop Document Library excerpts for the Furrion FACT12SA2-PS "
            "(CCD-0008666) do not list or define an E2 code.\n\n"
            "Check 115V supply voltage at the unit."
        )
        fixed = ensure_fact12_freeze_resecure(
            gap,
            [],
            complaint,
            "Air Conditioning",
            "FACT12SA2-PS",
            complaint,
        )
        self.assertEqual(fixed, FACT12_E2_PROVE_LINE)
        self.assertIn("before any repair", fixed.lower())
        self.assertNotIn("reseat", fixed.lower())
        self.assertIn("CCD-0008666", fixed)
        self.assertNotIn("do not list or define", fixed.lower())
        self.assertNotIn("115v", fixed.lower())
        again = ensure_fact12_freeze_resecure(
            gap,
            [{"role": "user", "content": complaint}],
            "What is the repair?",
            "Air Conditioning",
            "FACT12SA2-PS",
            complaint,
        )
        self.assertIn("freeze sensor", again.lower())
        self.assertNotIn("do not list or define", again.lower())


class TestCooktopPage4(unittest.TestCase):
    def test_tip_repair_cites_sdn2u_page_4_and_drops_the_contradiction(self):
        complaint = (
            "When using stove, it will shut off as soon as a pan is put on it — either burner."
        )
        reply = (
            "Before condemning the thermocouple, safety valve, orifice, regulator, "
            "or igniter: verify the thermocouple / flame-sensor tip is positioned "
            "in the burner flame WITH COOKWARE ON. Reposition the tip so the flame "
            "stays on the tip under load.\n"
            "📖 Source: Suburban Range/Cooktops SM\n\n"
            "The shop Document Library excerpts (Suburban Range and Cooktops "
            "Service & Owner's Manual pages 2, 4, 9) do not cover thermocouple "
            "or flame-sensor tip position.\n\n"
            "Do you have other pages from that manual?"
        )
        fixed = ensure_cooktop_tip_pan_check(
            reply,
            complaint,
            history=[],
        )
        low = fixed.lower()
        self.assertIn("page 4", low)
        self.assertIn("figs. 3-4", low)
        self.assertIn("sdn2u", low)
        self.assertNotIn("do not cover", low)
        self.assertNotIn("does not cover", low)
        self.assertNotIn("do you have other pages", low)
        self.assertIn("tip", low)


class TestTurnOneSteps(unittest.TestCase):
    def test_s03_s09_and_s10_open_as_short_steps(self):
        self.assertIn("\n1. ", BAL_TONGUE_PROVE_SHOP_LINE)
        self.assertIn("20300427", BAL_TONGUE_PROVE_SHOP_LINE)
        self.assertIn("confirm the fan runs", DOMETIC_NOCOOL_CONFIRM_FAN.lower())
        self.assertIn("peacemaker", DOMETIC_NOCOOL_OPEN.lower())
        self.assertIn("\n1. ", GROUND_CONTROL_LEVEL_LINE)
        self.assertIn("front five", GROUND_CONTROL_LEVEL_LINE.lower())
        self.assertIn("plugs are seated", GROUND_CONTROL_PROVE_LINE.lower())
        self.assertIn("3311071", DOMETIC_NOCOOL_CONFIRM_FAN)
        self.assertIn("ins.sta.001", BAL_TONGUE_PROVE_SHOP_LINE.lower())
        self.assertIn("rear five", GROUND_CONTROL_LEVEL_LINE.lower())
        self.assertNotIn("swap a level sensor.", GROUND_CONTROL_LEVEL_LINE.lower())


if __name__ == "__main__":
    unittest.main()
