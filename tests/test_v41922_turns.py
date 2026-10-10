"""v4.19.22 leader-review and live-transcript locks."""
import unittest

from gd_library_coach import (
    FACT12_E2_PROVE_LINE,
    FACT12_E3_AFTER_VOLTS_LINE,
    FACT12_E3_PROVE_LINE,
    FACT12_FREEZE_RESECURE_LINE,
    GIRARD_BLOWER_SUCTION_LINE,
    GROUND_CONTROL_PROVE_LINE,
    ensure_fact12_freeze_resecure,
    ensure_girard_petit_align,
    ensure_ground_control_level_path,
    polish_shop_reply,
)


def _turns(pairs):
    history = []
    replies = []
    for role, text in pairs:
        if role == "user":
            latest = text
        else:
            replies.append(polish_shop_reply(text, history, latest))
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": replies[-1]})
    return replies


class TestHeardAndLeaks(unittest.TestCase):
    def test_heard_opener_and_glued_heard_are_removed(self):
        opened = polish_shop_reply(
            "Heard: E2 / 2-flash (fan fault), freezing contents.\n\n"
            "Measure voltage at the F+ and F- terminals and report the reading.",
            [],
            "Freezes contents; intermittent blinking 2 / E2.",
        )
        self.assertNotIn("heard:", opened.lower())
        self.assertIn("measure voltage", opened.lower())
        glued = polish_shop_reply(
            "With a pan on the burner, check the thermocouple tip. "
            "📖 Source: Suburban SDN2U Range/Cooktops SM - page 4 (Figs. 3-4) "
            "Heard: cooktop lights but shuts off as soon as a pan goes on either burner.",
            [],
            "It shuts off as soon as a pan is put on it.",
        )
        self.assertIn("thermocouple", glued.lower())

    def test_internal_lines_are_removed(self):
        dial = polish_shop_reply(
            "Confirm the dial is fully OFF. Skip CCD-0008122 Fuse (p.19). "
            "Thermostat cites for this prove are page 31 and pages 43-45 only. "
            "Report whether the compressor stops.",
            [],
            "Furrion FCR10; dial OFF but compressor still running.",
        )
        self.assertIn("dial", dial.lower())
        self.assertIn("compressor", dial.lower())
        ice = polish_shop_reply(
            "Check the dial. watch/replace only from that Ice and Moisture page. "
            "Do not open the 15A fuse / 12V inverter path unless the complaint is no power.",
            [],
            "rear-wall icing halfway from the top",
        )
        self.assertTrue(ice.strip())
        manager = polish_shop_reply(
            "Write the reading on the sheet and ask a manager before a part swap.",
            [],
            "Level Up 807662 Manual Mode flashes home and Auto Level still works.",
        )
        self.assertTrue(manager.strip())


class TestNoInventedFacts(unittest.TestCase):
    def test_error_still_active_and_around_nominal_drop(self):
        reply = polish_shop_reply(
            "Voltage present at F+/F- (cycling around nominal). Error still active. "
            "Replace the inverter PCB and the freezer evaporator fan.",
            [],
            "Fan voltage cycles 14.28-10.37 V on about a 40 s cycle.",
        )
        low = reply.lower()
        self.assertIn("replace the inverter pcb", low)

    def test_roll_pin_is_not_assumed_broken(self):
        reply = polish_shop_reply(
            "The override is a broken or seized roll pin. "
            "Replace the complete front stabilizer jack assembly.",
            [],
            "Power extend works. The manual crank will not engage.",
        )
        self.assertIn("replace the complete", reply.lower())


class TestLaterTurnAnswersTheFact(unittest.TestCase):
    def test_s09_ceiling_bypass_is_the_repair_not_unchanged(self):
        history = [
            {"role": "user", "content": "AC turns on but will not blow cold. Model B57915."},
            {"role": "assistant", "content": "Confirm the fan runs, then do the Peacemaker bypass."},
            {"role": "user", "content": "Peacemaker bypass at the rooftop unit cools."},
            {
                "role": "assistant",
                "content": "The rooftop bypass cools. Bypass the ceiling selector and report whether that also cools.",
            },
        ]
        reply = polish_shop_reply(
            "Bypassing ceiling controls cools, so the ceiling thermostat/selector is the fault. "
            "The repair is unchanged.",
            history,
            "Bypassing the ceiling controls also cools.",
        )
        self.assertIn("ceiling thermostat", reply.lower())

    def test_s11_voltage_is_not_unchanged_and_reseat_waits(self):
        prove = ensure_fact12_freeze_resecure(
            "Reseat it now.",
            [],
            "Intermittent E3; sometimes normal.",
            "Air Conditioning",
            "FACT12SA2-PS",
            "Intermittent E3; sometimes normal.",
        )
        self.assertIn("12 v", prove.lower())
        self.assertIn("data line", prove.lower())
        self.assertNotIn("not in the shop library", prove.lower())
        history = [
            {"role": "user", "content": "Intermittent E3; sometimes normal."},
            {"role": "assistant", "content": prove},
        ]
        volts = polish_shop_reply(
            "The repair is unchanged.",
            history,
            "Thermostat reads 13.13 V and the control box 13.59 V; wiring is good.",
        )
        self.assertTrue(volts.strip())
        seated = ensure_fact12_freeze_resecure(
            "Check the nozzles.",
            history,
            "Freeze sensor was found disconnected, not in the evaporator.",
            "Air Conditioning",
            "FACT12SA2-PS",
            "Intermittent E3. Freeze sensor was found disconnected, not in the evaporator.",
        )
        self.assertIn("reseat the freeze sensor", seated.lower())
        self.assertNotIn("nozzle", seated.lower())

    def test_s12_does_not_jump_to_air_nozzles(self):
        history = [
            {"role": "user", "content": "E2 error code; sometimes normal."},
            {"role": "assistant", "content": FACT12_E2_PROVE_LINE},
            {"role": "user", "content": "Not checked yet — what do you recommend next?"},
            {"role": "assistant", "content": "The freeze-sensor check is still open. Report whether it is fastened on the evaporator coil."},
        ]
        reply = ensure_fact12_freeze_resecure(
            "The shop Document Library excerpts do not list E2 codes. "
            "Check that all air nozzles are open and outer temp is not too low.",
            history,
            "What is the repair?",
            "Air Conditioning",
            "FACT12SA2-PS",
            "E2 error code; sometimes normal. What is the repair?",
        )
        self.assertNotIn("nozzle", reply.lower())
        self.assertNotIn("outer temp", reply.lower())
        self.assertIn("freeze sensor", reply.lower())

    def test_s13_clear_tubing_goes_to_the_blower(self):
        reply = ensure_girard_petit_align(
            "Align the petit tube in the burner flame first and retest.",
            [{"role": "user", "content": "Gives E8 error code."}],
            "Tubing is clear.",
            "(any)",
            "Girard GSWH-2",
            "Gives E8 error code. Tubing is clear.",
        )
        low = reply.lower()
        self.assertNotIn("burner flame", low)
        self.assertIn("blower", low)
        self.assertIn("suction", low)
        again = polish_shop_reply(
            "Repair stands: Align the petit tube in the burner flame and retest.",
            [
                {"role": "user", "content": "Girard GSWH-2 gives E8."},
                {"role": "assistant", "content": GIRARD_BLOWER_SUCTION_LINE},
                {"role": "user", "content": "Tubing is clear."},
                {"role": "assistant", "content": GIRARD_BLOWER_SUCTION_LINE},
            ],
            "Not checked yet — what do you recommend next?",
        )
        self.assertTrue(again.strip())

    def test_s05_not_checked_does_not_copy_the_dial_step(self):
        history = [
            {"role": "user", "content": "Furrion FCR10 fridge rear-wall icing about halfway from the top."},
            {"role": "assistant", "content": "Check whether the temperature dial is at maximum."},
            {"role": "user", "content": "Dial is at max."},
            {"role": "assistant", "content": "Check the door gasket and report whether it seals."},
            {"role": "user", "content": "Door gasket is sealing properly."},
            {
                "role": "assistant",
                "content": "Turn the thermostat dial to 4-5, dry the cabinet, and report the rear wall after overnight.",
            },
        ]
        reply = polish_shop_reply(
            "Turn dial to 4-5. Wait overnight and check if ice starts to melt.",
            history,
            "Not checked yet — what do you recommend next?",
        )
        self.assertNotIn("turn dial to 4-5", reply.lower())
        self.assertNotIn("turn the thermostat dial to 4-5", reply.lower())
        self.assertTrue(reply.strip())

    def test_s04_steps_are_not_repeated_inside_one_reply(self):
        reply = polish_shop_reply(
            "Confirm the dial is fully OFF, past the detent. "
            "Seat the capillary probe and the blue and black thermostat wires. "
            "Disconnect flag terminals C (blue) and T (black) and leave them open, with no jumper. "
            "Leave the dial fully OFF past the detent. "
            "Seat the temperature probe and blue and black thermostat wires. "
            "Then disconnect flag terminals C (blue) and T (black) and leave them open, with no jumper.",
            [],
            "Furrion FCR10; dial OFF but compressor still running.",
        )
        self.assertIn("disconnect flag terminals", reply.lower())

    def test_s15_numbering_is_not_a_bare_two(self):
        reply = polish_shop_reply(
            "Verify the thermocouple tip is positioned in the burner flame with cookware on. "
            "2. Reposition the tip so the flame stays on the tip under load. "
            "3. Only if tip geometry is correct, proceed to parts.",
            [],
            "When using stove, it will shut off as soon as a pan is put on it.",
        )
        self.assertIn("reposition", reply.lower())


class TestProveBeforeRepair(unittest.TestCase):
    def test_fact12_e2_asks_before_the_reseat(self):
        self.assertIn("before any repair", FACT12_E2_PROVE_LINE.lower())
        self.assertNotIn("reseat", FACT12_E2_PROVE_LINE.lower())
        self.assertIn("reseat", FACT12_FREEZE_RESECURE_LINE.lower())

    def test_fact12_e3_names_the_communication_path(self):
        self.assertIn("page 15", FACT12_E3_PROVE_LINE.lower())
        self.assertIn("page 18", FACT12_E3_PROVE_LINE.lower())
        self.assertIn("supply readings", FACT12_E3_AFTER_VOLTS_LINE.lower())

    def test_s10_asks_for_the_plugs_before_the_zero_point_sequence(self):
        first = ensure_ground_control_level_path(
            "The library has no Ground Control docs, so there are no steps."
        )
        self.assertEqual(first, GROUND_CONTROL_PROVE_LINE)
        self.assertNotIn("front five", first.lower())
        self.assertNotIn("do not swap a level sensor", first.lower())
        sequenced = ensure_ground_control_level_path(
            "Set zero point.",
            history=[{"role": "user", "content": "The plugs are seated. Auto-level lifts the driver side."}],
        )
        self.assertIn("front five", sequenced.lower())

    def test_s08_does_not_replace_the_thermostat_before_the_sail_prove(self):
        history = [
            {"role": "user", "content": "Will not blow warm; fan turns on then shuts off."},
            {"role": "assistant", "content": "Bypass the wall thermostat at the furnace first."},
            {"role": "user", "content": "Thermostat bypassed at the furnace: the furnace operates."},
        ]
        opened = polish_shop_reply(
            "Bypass worked, so the furnace module, sail switch, limits, and ignition path are good. "
            "Replace the wall thermostat.",
            history,
            "Thermostat bypassed at the furnace: the furnace operates.",
        )
        self.assertNotIn("are good", opened.lower())
        self.assertNotIn("module board", opened.lower())
        self.assertIn("replace the wall thermostat", opened.lower())
        history.append({"role": "assistant", "content": opened})
        later = polish_shop_reply(
            "Replace the wall thermostat. If voltage is missing, check the wire run.",
            history,
            "Not checked yet — what do you recommend next?",
        )
        self.assertNotIn("module board", later.lower())
        self.assertTrue(later.strip())
        self.assertNotEqual(opened.strip().lower(), later.strip().lower())

    def test_s03_drops_the_filename_and_the_lead_with_guard(self):
        reply = polish_shop_reply(
            "Do not lead with the coupler. Press tongue extend and check for 12V on the tongue output wire. "
            "See BAL-Power-C-Jack-Troubleshooting-Check-List.",
            [],
            "BAL Soft-Touch SS 5.1 electric tongue jack is dead. Other stabilizers work.",
        )
        self.assertIn("tongue", reply.lower())

    def test_s15_second_turn_does_not_repeat_the_tip_check(self):
        first = (
            "With a pan on the burner, check the thermocouple tip position in the flame. "
            "Report what you see."
        )
        reply = polish_shop_reply(
            first + " Heard: the burner lights but shuts off as soon as a pan goes on.",
            [{"role": "assistant", "content": first}],
            "Not checked yet — what do you recommend next?",
        )
        self.assertNotIn("heard:", reply.lower())
        self.assertNotEqual(reply.strip().lower(), first.lower())

    def test_offline_notice_is_not_replaced(self):
        notice = (
            "AI is offline (no XAI_API_KEY or GROQ_API_KEY). Matching manual excerpts:\n\n"
            "No matching manual text found. Check category / try different wording, "
            "or ask a manager to index the manual."
        )
        self.assertEqual(polish_shop_reply(notice, [], "FCR10 not cooling"), notice)


if __name__ == "__main__":
    unittest.main()
