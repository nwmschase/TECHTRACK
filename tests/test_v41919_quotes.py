"""v4.19.19: a printed quote is chunk text, and a shop reply does not invent facts."""
import re
import unittest

from bay_procedure import compile_bay_procedure, procedure_plain_text
from gd_library_coach import (
    BAL_TONGUE_PROVE_SHOP_LINE,
    COOKTOP_TIP_LOW_REPAIR,
    FACT12_FREEZE_RESECURE_LINE,
    avoid_duplicate_reply,
    category_conflicts_with_model,
    extract_bal_tongue_facts,
    facr_reported_assembly_rr_line,
    is_air_conditioning_context,
    is_water_heater_context,
    polish_shop_reply,
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower().rstrip(".")


class TestChunkQuotes(unittest.TestCase):
    def test_a_printed_quote_is_a_substring_of_its_chunk(self):
        chunks = [
            {
                "title": "Suburban Furnace Service and Training Manual",
                "page": 28,
                "excerpt": (
                    "The wall thermostat controls the operation of the dual stage furnace "
                    "by reacting to room temperature. Count the flashes and use the table below."
                ),
            },
            {
                "title": "Suburban Furnace Service and Training Manual",
                "page": 26,
                "excerpt": "Time line description. Start time.",
            },
        ]
        proc = compile_bay_procedure(
            "Will not blow warm; fan turns on then shuts off.",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
            chunks=chunks,
        )
        by_page = {}
        for chunk in chunks:
            by_page.setdefault(chunk["page"], []).append(chunk["excerpt"])
        printed = 0
        for src in proc.sources:
            quote = (src.get("excerpt") or "").strip()
            if not quote:
                continue
            printed += 1
            raws = by_page.get(src.get("page")) or []
            self.assertTrue(raws, quote)
            hay = " ".join(_collapse(raw) for raw in raws)
            self.assertIn(_collapse(quote), hay, quote)
            self.assertNotIn("table below", quote.lower())
        self.assertGreaterEqual(printed, 1)

    def test_a_locked_sentence_does_not_print_without_a_chunk(self):
        proc = compile_bay_procedure(
            "FACR08HESA2-PS freeze up interior leak condensate",
            "Furrion",
            "FACR08HESA2-PS",
            "Air Conditioning",
            chunks=[],
        )
        quotes = " ".join(src.get("excerpt") or "" for src in proc.sources)
        self.assertNotIn("freeze sensor sits on the evaporator", quotes.lower())
        self.assertNotIn("clean the drainage openings", quotes.lower())
        self.assertTrue(any(src.get("page") == 7 for src in proc.sources))
        self.assertTrue(any(src.get("page") == 10 for src in proc.sources))

    def test_expected_cites_stay_when_the_quote_is_blank(self):
        tongue = compile_bay_procedure(
            "BAL Soft-Touch SS 5.1 electric tongue jack dead. Other stabilizers and panel lights work.",
            "BAL",
            "Soft-Touch SS 5.1",
            "Leveling",
        )
        titles = " ".join(src.get("title") or "" for src in tongue.sources)
        self.assertIn("INS.STA.001", titles)
        self.assertTrue(any(src.get("page") for src in tongue.sources))

        e2 = compile_bay_procedure(
            "FCR10 E2 fan fault current on the freezer evaporator fan",
            "Furrion",
            "FCR10",
            "Refrigerators",
            chunks=[
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 29,
                    "excerpt": "Proceed to the next section.",
                }
            ],
        )
        self.assertIn("page 27", e2.primary_cite.lower())
        self.assertTrue(any(src.get("page") == 27 for src in e2.sources))
        self.assertNotIn("see doc", procedure_plain_text(e2).lower())

        ground = compile_bay_procedure(
            "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
            "tires off the ground even though the coach was nearly level.",
            "Lippert",
            "Ground Control 343633",
            "Leveling",
        )
        self.assertTrue(ground.sources)
        self.assertIn("page 1", ground.primary_cite.lower())
        self.assertNotIn("see doc", ground.primary_cite.lower())
        self.assertFalse(any((src.get("excerpt") or "").strip() for src in ground.sources))

        girard = compile_bay_procedure(
            "Girard GSWH-2 tankless water heater shows E8.",
            "Girard",
            "GSWH-2",
            "Water Heaters",
        )
        self.assertIn("page 23", girard.primary_cite.lower())
        self.assertIn("ccd-0009390", girard.primary_cite.lower())
        self.assertTrue(any(src.get("page") == 23 for src in girard.sources))
        self.assertNotIn("see doc", procedure_plain_text(girard).lower())

    def test_fact12_source_line_is_the_closest_reference(self):
        proc = compile_bay_procedure(
            "Furrion FACT12SA2 rooftop shows E3",
            "Furrion",
            "FACT12SA2",
            "Air Conditioning",
        )
        self.assertEqual(len(proc.sources), 2)
        pages = {src.get("page") for src in proc.sources}
        self.assertEqual(pages, {15, 18})
        self.assertTrue(all("CCD-0008666" in (src.get("title") or "") for src in proc.sources))
        self.assertFalse(any("closest reference" in (src.get("title") or "").lower() for src in proc.sources))
        self.assertFalse(any((src.get("excerpt") or "").strip() for src in proc.sources))
        plain = procedure_plain_text(proc).lower()
        self.assertIn("data line", plain)
        self.assertIn("page 15", plain)
        self.assertIn("page 18", plain)
        self.assertNotIn("closest reference", plain)
        self.assertNotIn("not in the library", plain)
        self.assertNotIn("see doc", plain)

    def test_dial_off_master_keeps_the_full_model(self):
        proc = compile_bay_procedure(
            "temperature dial OFF but compressor still running, freezer frozen solid",
            "Furrion",
            "FCR10",
            "Refrigerators",
        )
        self.assertIn("FCR10DCGTA-BL", proc.model_line)
        self.assertNotIn("see doc", procedure_plain_text(proc).lower())
        for src in proc.sources:
            if src.get("page") in (31, 43, 45):
                self.assertFalse((src.get("excerpt") or "").strip(), src)


class TestShopReplyPolish(unittest.TestCase):
    def test_the_model_instruction_never_reaches_the_tech(self):
        history = [
            {"role": "assistant", "content": BAL_TONGUE_PROVE_SHOP_LINE},
        ]
        latest = "I measured 0 V at the soft-touch panel tongue channel while commanding extend."
        facts = extract_bal_tongue_facts(latest)
        self.assertEqual(facts.get("tongue_channel_volts"), "missing")
        reply = avoid_duplicate_reply(
            "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel.",
            history,
            latest,
        )
        low = reply.lower()
        self.assertNotIn("that check was already asked", low)
        self.assertNotIn("use the facts already reported", low)
        self.assertIn("20300427", reply)
        self.assertNotIn("noted:", low)

    def test_fallback_questions_are_not_noted_as_facts(self):
        history = [
            {"role": "user", "content": "FACT12SA2-PS shows E3."},
            {"role": "assistant", "content": FACT12_FREEZE_RESECURE_LINE},
        ]
        reply = avoid_duplicate_reply(FACT12_FREEZE_RESECURE_LINE, history, "What is the repair?")
        self.assertNotIn("Noted: What is the repair", reply)
        self.assertNotIn("what is the repair", reply.lower())
        self.assertNotEqual(reply.strip(), FACT12_FREEZE_RESECURE_LINE.strip())

    def test_unreported_claims_are_removed(self):
        user = "Drain is clear. Filter is clean. Fan spins. Freeze sensor reads 2 kΩ."
        card = facr_reported_assembly_rr_line()
        self.assertNotIn("nozzle", card.lower())
        with_nozzles = facr_reported_assembly_rr_line({"facr_nozzle": "open"})
        self.assertIn("nozzles", with_nozzles.lower())
        scrubbed = polish_shop_reply(
            "Nozzles are reported good. Dial turned down. Error remains. The tip sits low. "
            "No sticky Low Voltage. E2 returned after reset.",
            [{"role": "user", "content": user}, {"role": "assistant", "content": "Next check."}],
            "The code returned after the thaw.",
        )
        low = scrubbed.lower()
        self.assertNotIn("nozzles are reported good", low)
        self.assertNotIn("dial turned down", low)
        self.assertNotIn("error remains", low)
        self.assertNotIn("sits low", low)
        self.assertNotIn("no sticky", low)
        self.assertNotIn("after reset", low)
        self.assertIn("thaw", low)
        self.assertNotIn("unchanged", low)

    def test_cooktop_repair_does_not_invent_tip_height_or_ask_to_pivot(self):
        self.assertNotIn("sits low", COOKTOP_TIP_LOW_REPAIR.lower())
        reply = polish_shop_reply(
            COOKTOP_TIP_LOW_REPAIR
            + " Does the coach have any other symptoms, or do you want to pivot to a different check?",
            [],
            "It will shut off as soon as a pan is put on it.",
        )
        self.assertNotIn("pivot", reply.lower())
        self.assertNotIn("any other symptoms", reply.lower())
        self.assertIn("reposition", reply.lower())

    def test_the_same_check_is_not_said_twice_in_one_reply(self):
        reply = polish_shop_reply(
            "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel. "
            "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel.",
            [],
            "Tongue jack only is dead.",
        )
        self.assertEqual(reply.lower().count("check for 12v"), 1)

    def test_library_gap_is_one_line_of_shop_advice(self):
        self.assertNotIn("not in the shop library", FACT12_FREEZE_RESECURE_LINE.lower())
        self.assertNotIn("closest reference", FACT12_FREEZE_RESECURE_LINE.lower())
        self.assertNotIn("do not replace the control board first", FACT12_FREEZE_RESECURE_LINE.lower())
        self.assertIn("reseat", FACT12_FREEZE_RESECURE_LINE.lower())
        self.assertIn("page 5", FACT12_FREEZE_RESECURE_LINE.lower())

    def test_category_does_not_override_a_named_model(self):
        self.assertFalse(
            is_air_conditioning_context("Air Conditioning", "Girard GSWH-2", "E8 code")
        )
        self.assertTrue(
            is_water_heater_context("Air Conditioning", "Girard GSWH-2", "E8 code")
        )
        self.assertTrue(category_conflicts_with_model("Air Conditioning", "Girard GSWH-2", "E8"))
        self.assertTrue(
            is_air_conditioning_context("Air Conditioning", "Furrion FACT12SA2", "E2")
        )

    def test_noted_claims_have_to_be_in_the_tech_message(self):
        history = [{"role": "assistant", "content": "Bypass the wall thermostat at the furnace."}]
        sail = polish_shop_reply(
            "The sail switch, limits, ignition, and gas valve is good. "
            "Prove the sail switch with the blower running.",
            history,
            "Bypass operates the furnace.",
        )
        self.assertNotIn("gas valve", sail.lower())
        self.assertIn("sail switch", sail.lower())
        reported = polish_shop_reply(
            "The petit tube alignment was reported. Align the petit tube in the burner flame.",
            history,
            "Tubing is clear.",
        )
        self.assertNotIn("was reported", reported.lower())
        self.assertIn("align the petit tube", reported.lower())
        pin = polish_shop_reply(
            "The roll pin or override coupler is broken or seized. "
            "Replace the complete front stabilizer jack assembly.",
            history,
            "Power works. Manual crank will not operate.",
        )
        self.assertNotIn("is broken", pin.lower())
        self.assertIn("replace the complete", pin.lower())
        flame = polish_shop_reply(
            "Heard: the burner lights but goes out when the pan is placed. "
            "Reposition the thermocouple tip in the burner flame with the pan on.",
            history,
            "It shuts off as soon as a pan is put on it.",
        )
        self.assertNotIn("goes out", flame.lower())
        self.assertNotIn("heard:", flame.lower())
        self.assertIn("reposition", flame.lower())

    def test_a_reply_is_not_only_a_source_line_or_a_bare_repair_label(self):
        source_only = polish_shop_reply(
            "📖 Source: Girard tankless water heater service manual",
            [{"role": "user", "content": "Girard GSWH-2 E8. Tubing is clear."},
             {"role": "assistant", "content": "Check the vent."}],
            "Tubing is clear.",
        )
        self.assertIn("suction", source_only.lower())
        self.assertIn("blower", source_only.lower())
        self.assertNotIn("burner flame", source_only.lower())
        bare = polish_shop_reply(
            "That is the repair.",
            [
                {"role": "user", "content": "FACT12SA2-PS shows E3 and the freeze sensor is off the coil."},
                {"role": "assistant", "content": FACT12_FREEZE_RESECURE_LINE},
            ],
            "The sensor was disconnected.",
        )
        self.assertNotEqual(bare.strip().lower(), "that is the repair.")
        self.assertTrue(re.search(r"\b(?:confirm|reseat|resecure|write|fasten)\b", bare, re.I))

    def test_a_long_tech_message_is_not_echoed(self):
        history = [{"role": "assistant", "content": "Bypass the wall thermostat at the furnace."}]
        latest = "I jumped red and white at the furnace and the burner lights and the blower runs."
        reply = polish_shop_reply(
            "Replace the wall thermostat. That is the repair.",
            history,
            latest,
        )
        self.assertNotIn("jumped red and white", reply.lower())
        self.assertIn("sail switch", reply.lower())
        self.assertIn("if ", reply.lower())
        self.assertIn("replace the wall thermostat", reply.lower())

    def test_the_dial_instruction_and_the_cooktop_guard_do_not_repeat(self):
        history = [
            {"role": "assistant", "content": "Turn the thermostat dial to 4-5 and recheck the rear wall."},
        ]
        reply = polish_shop_reply(
            "Set the thermostat dial to 4 to 5 and look at the rear wall again.",
            history,
            "Rear wall ice is still there.",
        )
        self.assertNotIn("4 to 5", reply.lower())
        self.assertNotIn("4-5", reply.lower())
        self.assertNotIn("unchanged", reply.lower())
        self.assertTrue(re.search(r"\b(?:dry|month|replace|gasket|frost)\b", reply, re.I))
        guard = polish_shop_reply(
            "Before condemning the thermocouple, confirm the flame is present with the pan on. "
            "1. Confirm the flame is present with the pan on. "
            "2. Remove the pan and watch the flame. "
            "3. Check the thermocouple position against the manual. "
            "Does the unit have a thermocouple or flame sensor, and is the tip in the flame with the pan on? "
            "Reposition the thermocouple tip in the burner flame with the pan on. Figs. That is the repair.",
            [],
            "It shuts off as soon as a pan is put on it.",
        )
        self.assertNotIn("before condemning", guard.lower())
        self.assertNotIn("does the unit have", guard.lower())
        self.assertNotRegex(guard, r"\bFigs\.(?!\s*\d)")
        self.assertIn("reposition", guard.lower())


def _turns(pairs):
    """Polish each coach reply with the chat so far. Return the coach lines."""
    history = []
    out = []
    for user, coach in pairs:
        reply = polish_shop_reply(coach, history, user)
        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": reply})
        out.append(reply)
    return out


class TestLiveTranscripts(unittest.TestCase):
    def test_s02_does_not_open_with_a_truncated_noted_line(self):
        replies = _turns([
            (
                "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead / no response.",
                "Coleman-Mach 2111-0001 ran 2 min then dead. Check 12 VDC at the low-voltage terminal strip first.",
            ),
            (
                "122 VAC at the control box. Board output tester no illuminate on Fan High. "
                "0.000-0.048 VAC on black/white at the 9-pin under Fan High.",
                "Noted: 122 VAC at the control. Fan High dead confirmed (tester dark, ~0 VAC on 9-pin black/white). "
                "Next: Run a Peacemaker bypass of the thermostat/control box.",
            ),
            (
                "Peacemaker bypass: compressor runs, fan does not rotate on high or low. About 1.91 A at 122 V, shaft locked.",
                "Noted: 122 V. Check the fan run capacitor value against its rating.",
            ),
            (
                "Fan run capacitor 15.11 µF FAN-C, rated 15 µF ±5%.",
                "Authorization card: Fan motor and control board only. Do not replace the full 2111-0001 assembly.",
            ),
        ])
        joined = "\n".join(replies).lower()
        self.assertNotIn("noted:", joined)
        self.assertIn("peacemaker", replies[1].lower())
        self.assertIn("capacitor", replies[2].lower())
        self.assertIn("fan motor", replies[3].lower())
        self.assertIn("control board", replies[3].lower())
        self.assertNotIn("do not replace the full 2111-0001 assembly", replies[3].lower())

    def test_s03_drops_the_echo_and_the_second_panel_sentence(self):
        replies = _turns([
            (
                "BAL Soft-Touch SS 5.1 electric tongue jack dead only; other stabilizers and panel lights work.",
                "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel. "
                "No 12V on the tongue output wire means replace the soft-touch user panel 20300427. "
                "Do not lead with the coupler, the shear pin, the 30A fuse, or the remote stabilizer harness.",
            ),
            (
                "I measured 0 V at the soft-touch panel tongue channel while commanding extend; "
                "other stabilizers and panel lights still work.",
                "Noted: 0 V at the soft. Replace the soft-touch user panel 20300427. "
                "Do not replace the coupler or the shear pin, and do not open the 30A fuse or the remote stabilizer harness. "
                "You measured 0 V on the tongue output wire at the panel while commanding extend. "
                "Replace the soft-touch user panel, part 20300427.",
            ),
        ])
        second = replies[1].lower()
        self.assertNotIn("noted:", second)
        self.assertNotIn("you measured", second)
        self.assertEqual(second.count("20300427"), 1)
        self.assertIn("do not replace the coupler", second)

    def test_s05_does_not_invent_a_dial_adjustment(self):
        replies = _turns([
            (
                "Furrion FCR10DCGTA-BL fridge; rear-wall icing about halfway from the top down.",
                "Is the temperature dial set to maximum? If ice or moisture persists after drying and waiting 1 month, replace the unit.",
            ),
            (
                "Dial is at max.",
                "Check the door gasket seal.",
            ),
            (
                "Door gasket is sealing properly.",
                "Noted: Door gasket is sealing properly. Turn the dial down to 4-5. Wait overnight. Dry any moisture with a towel.",
            ),
            (
                "Not checked yet — what do you recommend next?",
                "Wait overnight, dry any moisture with a towel, then check if the unit is cooling properly.",
            ),
            (
                "Fridge is still cooling.",
                "Noted: fridge is still cooling after dial adjustment. Dry up any moisture and wait 1 month. If the issue persists, replace the unit.",
            ),
        ])
        self.assertNotIn("noted:", "\n".join(replies).lower())
        self.assertNotIn("dial adjustment", replies[4].lower())
        self.assertNotIn("unchanged", replies[4].lower())
        self.assertIn("frost", replies[4].lower())
        self.assertNotEqual(_collapse(replies[2]), _collapse(replies[3]))

    def test_s07_does_not_call_a_voltage_cycle_near_nominal(self):
        reply = polish_shop_reply(
            "The 14.28-10.37 V cycle is near nominal. Replace the inverter PCB and the freezer evaporator fan.",
            [{"role": "user", "content": "FCR10 E2 fan fault."}],
            "fan V 14.28-10.37 V; fan amps 0.383-0.442 A; E2 returned after thaw",
        )
        self.assertNotIn("near nominal", reply.lower())
        self.assertIn("inverter pcb", reply.lower())

    def test_s08_does_not_declare_untested_parts_good(self):
        replies = _turns([
            (
                "Will not blow warm; fan turns on then shuts off.",
                "Bypass the wall thermostat at the furnace first.",
            ),
            (
                "Thermostat bypassed at the furnace: the furnace operates.",
                "Bypass worked, so the furnace module, sail switch, limits, and ignition path are good. "
                "Next: Check the wall thermostat and the wire run from thermostat to furnace.",
            ),
            (
                "Not checked yet — what do you recommend next?",
                "Replace the wall thermostat. If voltage is missing, check the wire run.",
            ),
        ])
        self.assertNotIn("are good", replies[1].lower())
        self.assertIn("sail switch", replies[1].lower())
        self.assertIn("if ", replies[1].lower())
        self.assertNotIn("module board", replies[1].lower())
        self.assertNotIn("voltage is missing", replies[2].lower())
        self.assertIn("if ", replies[2].lower())
        self.assertNotIn("unchanged", replies[2].lower())
        self.assertNotEqual(_collapse(replies[1]), _collapse(replies[2]))

    def test_s11_states_the_repair_once_then_does_not_repeat_the_sentence(self):
        replies = _turns([
            (
                "Intermittent E3; sometimes normal.",
                FACT12_FREEZE_RESECURE_LINE,
            ),
            (
                "Not checked yet — what do you recommend next?",
                "Reseat the freeze sensor on the coil and retest before any board swap.",
            ),
            (
                "Thermostat reads 13.13 V and the control box 13.59 V; wiring is good.",
                "Noted: 13.13 V and the control. Reseat the freeze sensor on the coil and retest before any board swap.",
            ),
            (
                "Freeze sensor was found disconnected, not in the evaporator.",
                "Seat the freeze sensor on the evaporator coil. That is the repair.",
            ),
        ])
        joined = "\n".join(replies).lower()
        self.assertNotIn("noted:", joined)
        self.assertNotIn("that is the repair", replies[3].lower())
        self.assertNotIn("repair stands", joined)
        self.assertNotIn("unchanged", joined)
        self.assertNotIn("not in the shop library", replies[0].lower())
        self.assertIn("before any repair", replies[0].lower())
        self.assertNotIn("measure 12 v", replies[2].lower())
        self.assertNotIn("data line", replies[2].lower())
        self.assertIn("freeze sensor", replies[2].lower())
        self.assertIn("reseat", replies[3].lower())
        self.assertNotEqual(_collapse(replies[1]), _collapse(replies[2]))
        self.assertNotEqual(_collapse(replies[2]), _collapse(replies[3]))

    def test_s13_does_not_claim_the_alignment_was_reported(self):
        replies = _turns([
            (
                "Customer states water heater stopped working. Gives E8 error code.",
                "Look through the exhaust vent and confirm the petit tube is connected.",
            ),
            (
                "Tubing is clear.",
                "Noted: Tubing is clear. Align the petit tube in the burner flame first and retest. "
                "Do not replace the control board before the petit tube is aligned.",
            ),
            (
                "Not checked yet — what do you recommend next?",
                "Align the petit tube in the burner flame first and retest. That is the repair.",
            ),
        ])
        self.assertNotIn("noted:", "\n".join(replies).lower())
        self.assertNotIn("was reported", replies[1].lower())
        self.assertIn("blower", replies[1].lower())
        self.assertIn("suction", replies[1].lower())
        self.assertNotIn("burner flame", replies[1].lower())
        self.assertNotIn("repair stands", replies[2].lower())
        self.assertNotIn("unchanged", replies[2].lower())
        self.assertNotIn("that is the repair", replies[2].lower())
        self.assertNotEqual(_collapse(replies[1]), _collapse(replies[2]))


if __name__ == "__main__":
    unittest.main()
