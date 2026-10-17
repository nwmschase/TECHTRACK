"""ROOT RULE condition (1) + terminal escalation (Leader 3:30 AM 2026-10-17, PR #92 @854ef47).

(1) Condemning part B requires one of: (i) B's own decisive FAILING result; (ii) a cited manual elimination path; (iii) an OEM
authorization path. A normal/OK answer to test A rules A OUT; it is never a basis that condemns B. This holds whether or not a pending
scope exists. Ownership is structural: a result belongs to the component at the head of its sentence (cut at the first location
preposition) or the object of its test verb, never to a part named only as the place it was read ('yellow at the board').
(2) A session that ends with pending tests and no fix produces the ESCALATION SUMMARY (pending tests named + shop/OEM step).
Sessions below are verbatim from the 854ef47 sweep (RC22 T1-T9, RC20 T1-T14); the manual pages are verbatim library text
(Suburban p.17, Furrion p.27). GD code never sees a case id, brand or doc id."""
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go  # noqa: E402
from tests.test_selector_root_fix import Lib  # noqa: E402
from tests.test_scope_root_rule import DOCS, CATS  # noqa: E402

RC22_854_HIST = [('Customer says they ran gas and electric together, got gurgling/steam and water out the PRV; electric never worked after that, gas clicks but never lights, and now it only tries for a shorter time.', 'Safety first: chock the wheels, keep everyone clear of jacks/slides, and disconnect power before touching wiring.\nUsing: Suburban Water Heater Master Service and Training Manual - read section, pages 2-43.\nConfirm no gas odor around the heater or at floor level before operating; if odor is present stop. Report odor yes or no. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nOpen a hot faucet until water flows steady with no air sputter, then close it to confirm the tank is full. Report tank full yes or no. [Library: Suburban Water Heater Master Service and Training Manual p.10]\nWith 120 VAC on, turn the electric element switch (lower left in the control housing) ON, wait 10 minutes, then check tank/hot-faucet temperature. Report whether electric heat is present. [Library: Suburban Water Heater Master Service and Training Manual p.18]\nTurn the electric switch OFF. With LP on and 12 VDC present, turn the DSI ON/OFF switch ON. Watch the reset light, listen for clicks/spark, see if the burner lights, and time how long it tries before lockout (light stays on). Report what you see/hear and the times. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nReport those results.\n'), ('No gas odor around the heater or floor. Tank looks full/OK. Electric heat is present (element ~90 VAC, electric works). With DSI on, it clicks/tries but the burner never lights and the try is shorter than before.', 'Unplug and reseat the DSI module-board connector, the ON/OFF switch/lamp plug, and the gas-valve brown-wire connector until they click fully home. Report if any pin was loose, burned, or not seated. [Library: Suburban Water Heater Master Service and Training Manual p.21]\nSet meter to DC volts. With DSI switch ON, probe the two terminals of the ON/OFF switch (power in vs switched out). Report voltage (need 10.5–13.5 VDC). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf voltage is good, leave switch ON and probe the red wire at the module board vs chassis ground. Report voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nReport those three results.\n'), ('Connectors reseated; pins look seated/OK, nothing loose or burned. Idle supply is ~14.2 VDC (collapses to ~5–10 V during a try: 10.1, 8.3, ~5.5–9.5); orange/ground jumper made no change. Same collapse seen on the board supply path vs chassis.', 'Set meter to DC volts. Unplug the brown wire at the gas valve so the valve is out of circuit. Turn DSI switch ON and watch red-wire (board supply) vs chassis during the click/try. Report whether voltage still collapses and the numbers. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nSet meter to ohms. With power off and brown unplugged, measure across the gas-valve solenoid terminals. Report ohms (spec 30–50). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf ohms are in spec, reconnect brown. Hook a manometer at the valve inlet, LP on, DSI OFF. Report static WC (need 11–14"). [Library: Suburban Water Heater Master Service and Training Manual p.10]\n'), ('Gas valve coil is ~32 Ohm. Brown unplugged and static WC at the inlet aren’t in the notes; those look OK. Voltage still collapses on the recorded supply path during a try (~14.2 V idle to ~5–10 V).', 'Unplug the module-board connector completely. Turn DSI switch ON. Set meter to DC volts; probe the red (board supply) wire vs chassis. Report voltage (should stay near idle, no try/collapse). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nPower off. Set meter to ohms. Check electrode high-voltage wire and electrode body to chassis for a short (should be open). Report ohms. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nInspect electrode porcelain for cracks/carbon, tip gap 1/8", and that the spark wire cannot pinch on the door. Report what you see. [Library: Suburban Water Heater Master Service and Training Manual p.17]\n'), ('Board connector unplugged and electrode short/gap/porcelain aren’t in the notes; those look normal/OK. Spark cable unplugged made no change to the collapse. Supply still ~14.2 V idle and drops to ~5–10 V on a try with the board in circuit.', 'Unplug the module-board connector completely so the board is out of circuit. Turn the DSI ON/OFF switch ON. Set meter to DC volts; probe the red board-supply wire vs chassis ground. Report the voltage and whether it stays near idle or still drops (there should be no try/collapse with the board unplugged). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nReport that reading.\n'), ('Board connector fully unplugged isn’t in the notes; that supply reading looks normal/OK. Recorded path is still ~14.2 V idle collapsing to ~5–10 V on a try with the board in circuit.', 'Set meter to DC volts. Leave the board plugged in. Probe the brown wire at the gas valve vs chassis during a DSI try. Report the voltage while it is clicking. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nHook a manometer at the valve inlet. LP on, DSI ON. Report WC during the try (need 11–14"). [Library: Suburban Water Heater Master Service and Training Manual p.10]\nReport those two readings.\n'), ('Brown at the valve during try and WC on a try aren’t in the notes; those look normal/OK. Supply still ~14.2 V idle collapsing to ~5–10 V on a try; yellow at the board is 0 V idle / ~-1.2 V during try.', 'Watch the electrode tip during a DSI try (door open, stay clear of spark). Report whether a spark jumps the 1/8" gap at the tip. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nPull the burner tube and look through the orifice and mixer for spider webs, rust, or debris. Report what you find. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nReport those two results.\n')]
RC22_854_T8_TECH = 'Spark at the electrode tip and burner-tube/orifice inspection aren’t in the notes; those look normal/OK. Spark cable unplugged made no change to the voltage collapse.'
RC22_854_T8_GD = 'Replace the DSI module board (SW6DE part 520814). Keep the original spark cable and connectors; seat the new board plug fully. [Library: Suburban Water Heater Master Service and Training Manual p.31]\nAfter install: LP on, tank full, DSI switch ON. Confirm burner lights and stays on through heat-up (reset light off after TFI). [Library: Suburban Water Heater Master Service and Training Manual p.16]\nSet meter DC volts on red board supply vs chassis during the try. Report idle and try voltages (need 10.5–13.5 VDC, no collapse to 5–10 V). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nVERIFY: run the function again (full cycle, 2-3 times) and confirm it completes and the complaint is gone. [General trade knowledge]\n'
RC22_854_T9_TECH = 'Before I replace that - anything else to check?'
RC22_854_T9_GD = 'Nothing else on this unit. Collapse only with the board in circuit, spark/valve/orifice/electrode/connectors already OK — replace the DSI module board (520814). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nAfter install: LP on, tank full, DSI ON. Confirm burner lights and stays on (reset light off after TFI). [Library: Suburban Water Heater Master Service and Training Manual p.16]\nVERIFY: run gas heat 2–3 full cycles and confirm it completes and the complaint is gone. [General trade knowledge]\n'
SUBURBAN_P17 = 'OF OPeratiOn & trOubleSHOOting cHart\n• Confirm power present at ON/OFF Switch .......................................................\n(10.5 volt DC min - 13.5 volt DC max)\n• Confirm that thermostat and ECO are closed, and that power is present at .....\nthermostat\n• Confirm power is present on red wire to module board, and on blue wire to ....\nreset light, confirm that ground connections are secured, test reset light bulb\nConfirm and correct power supply.\nReset ECO if open, confirm that water \nin tank is cold, replace thermostat if \nfound to be defective.\nRepair or replace wiring if defective, \nreplace module board or switch/lamp \nassembly if found to be defective.\n• Inspect burner and orifice for debris, confirm gas and spark are ......................\npresent, inspec electrode for proper gap (1/8”), test module board with field \ntester\n• Inspect electrode and wire connections, test modu lectrode for proper gap (1/8”), test module board with field \ntester\n• Inspect electrode and wire connections, test module board with field tester ....\n• Check for proper voltage (10.5 min - 13.5 max) on brown wire at ....................\ngas valve (during TFI), confirm proper gas pressure available (11” WC - 14” \nWC), measure resistance through solenoids (30-50 OHM’s), inspect brown \nwire for open or short\n• Inspect electrode for: proper gap, damaged porcelain insulator, ......................\ncarbon build up on tip, loose or corroded wire connections, confirm proper \nflame impingement at electrode, inspect burner and orifice for debris, confirm \nthat gas pressure is correct, test module board with field tester\n• Inspect electrode for crack in porcelain, proper gap (1/8”), ..............................\nor carbon build up on tip, ensure that spark is present at electrode tip, inspect \nb 8”), ..............................\nor carbon build up on tip, ensure that spark is present at electrode tip, inspect \nburner for debris, inspect electrode wire for short (including against the back \nside fo the appliance door when in closed position)\n• Follow previously described trouble shooting procedures ................................\nClean or replace burner, correct \nelectrode gap, replace module board if \nfound to be defective.\nCorrect electrode gap, clean or correct \nelectrode wire connections, replace \nmodule board if found to be defective.\nCorrect voltage supply, correct gas \npressure, replace gas valve if found to \nbe defective, repair or replace wire if \ndefective.\nReplace electrode, module board, \ngas valve, or electrode wire if found \ndefective.  Clean or replace burner \ntube, correct gas pressure.\nReplace electrode or wire if defective, \nclean electrode tips with Emory cl replace burner \ntube, correct gas pressure.\nReplace electrode or wire if defective, \nclean electrode tips with Emory cloth,  \nadjust electrode if sparking incorrectly, \nclean or replace burner tube.\nTo reset the appliance from LOCKOUT \nmode, turn the power switch off for \n5-10 seconds and then turn the switch \nback on.\nteSt PrOceDureS cOrrective actiOn\n• Inspect by-pass valve for proper position, confirm that all plumbing system ....\nmixing valves are closed (including outside shower valves), confirm that \nthermostat is operating correctly, confirm that diffuser tubes are properly \ninstalled\n• Inspect that thermostat is secure to tank and opening at correct temberature .\n130 degrees F, plus or minus 5 degrees F\n• Install air pocket in tank, confirm water temperature is within operating range \n130 degrees F, plus or minus 5 degrees F, inspect relief valve for signs of \ncontamination at s within operating range \n130 degrees F, plus or minus 5 degrees F, inspect relief valve for signs of \ncontamination at seal\n• Check for proper gas pressure (11”WC-14” WC), inspect burner .....................\nflue tube, and vent for debris\nSet by-pass valves to correct position, \nclose open mixing valves, replace \nthermostat if defective, replace diffuser \ntube (‘s).\nReplace or secure thermostat\nReplace thermostat or relief valve \nif found to be defective, install \naccumulator tank to plumbing system \nper manufacturers installation \ninstructions.\nSet to correct gas pressure, replace \nvalve if found to be defective, clean or \nreplace burner tube, clean flue tube \nand vent assembly.17'
FURRION_P27 = 'Rev: 03.30.26 Page 27 CCD-0008122\nError Code - Fan Fault Diagnostics\nConnect power to the Connect power to the \nappliance and locate appliance and locate \nthe inverter PCB.the inverter PCB.\nIs the nominal \nvoltage 12V?\nMeasure and record \nvoltage using a \nmultimeter (Fig. 21) at \nthe F+ and F– terminals \non the inverter PCB.\nYes\nNo\nCheck connections: Check connections: \n• • Fan connection into inverter PCB Fan connection into inverter PCB \nF+/F– terminalsF+/F– terminals.\n• Fan quick connection to harness.\nReplace the inverter PCB.\nProceed to Compressor Inverter \nPCB Replacement in Repair \nSection 2 for further information.\nDid the error \ncode go away \nafter resetting \npower?\nYes\nNo\nReplace the inverter PCB and fan.\nProceed to Compressor Inverter PCB \nReplacement and Fan Replacement \nin Repair Section 2 for further \ninformation.\nIssue resolved.\nNo further action required.\nFig. 21 '
RC20_854_TECH = ['Customer says front jacks drift/move on their own when other circuits pressurize, including slides; started after the front-left jack was replaced (old one clanked, internal failure).', 'Front jacks still drift on their own when other circuits (incl. slides) pressurize, same as the complaint. LCD, Firefly Jacks/Warnings, and the power/LCD/pump connectors look normal/OK.', 'Battery posts at rest, controller power connector (Red–Green and Yellow–Green), and Manual Mode on the LCD all look normal/OK.', 'Front jacks still drift when another circuit pressurizes (same as on arrival; still after the loose front-left cartridge was snugged, bled, and resynced). Plumbing check at the front-left jack hoses is pending. VERIFY: complaint is still present.', 'Marked rams and ran another circuit: front jacks still drift on their own after the pump stops, same as on arrival (still after snug/bleed/resync). Plumbing check at the front-left hoses is pending.', 'Front jacks still drift on their own when another circuit pressurizes (same as on arrival after snug/bleed/resync). Case notes don’t record left vs right, direction, or distance. Plumbing check at the front-left hoses is still pending; no parts replaced.', 'Can’t give left vs right, direction, or distance — notes only say both front jacks still drift after snug/bleed/resync. Plumbing check at the front-left hoses is still pending, so I’m calling the shop/OEM tech line with that.', 'Called Lippert/Brinkley with findings: front jacks still drift when other circuits pressurize after FL cartridge snug/bleed/resync; coil good. Plumbing check at the front-left hoses (and gray-coil unplug) still pending; no parts replaced.', 'Already called the tech line with the same findings. Plumbing check at the front-left hoses is still pending; no parts replaced.', 'Plumbing check at the front-left hoses is still pending; I already called the shop/OEM line with the drift after snug/bleed/resync. No parts replaced.', 'Already called Lippert/Brinkley with those findings. Plumbing check at the front-left hoses is still pending; no parts replaced.', 'Plumbing check at the front-left hoses is still pending. Already called the shop/OEM line with the drift after snug/bleed/resync; no parts replaced.', 'Plumbing check at the front-left hoses is still pending. Already called the shop/OEM line with both fronts still drifting after FL cartridge snug/bleed/resync; no parts replaced.', 'Plumbing check at the front-left hoses is still pending. Already called Lippert/Brinkley with both fronts still drifting after FL cartridge snug/bleed/resync; no parts replaced.']
RC20_854_GD_T9 = 'Hold all part replacement: an isolation test is still pending ("Plumbing check at the front-left jack hoses is pending.") and it covers the complaint path (cartridge, coil, cylinder, fitting, hose, hpu, jack, manifold). No part on that path is replaced or repaired until its result is recorded. [General trade knowledge]\nThat test has been asked twice and will not be asked again. No result is recorded for it yet: do it once and send the reading, or call the shop/OEM tech line with the findings so far. [General trade knowledge]\nIf you cannot do that test, call the shop/OEM tech line with the findings so far. [General trade knowledge]\n'

RC18_A4_TECH = ['Customer says the front stabilizer jack will not operate when cranking manually with the tool; it works on the power switch.', 'Works under power on the FRONT switch. Manual crank with the customer’s tool does not operate the jack (override input shaft roll pin broken and seized). LCD looks normal/OK, no fault recorded.', 'Controller ID looks normal/OK. Connectors look seated/OK. Override input shaft roll pin is broken and seized (cannot extract); which override port the tool was in isn’t in the notes.', 'Which override port, rubber plugs, and unused-port crank aren’t in the notes; those look normal/OK. Override input shaft roll pin is still broken and seized, cannot extract.', 'Before I replace that - anything else to check?']
RC18_A4_T5_GD = 'Before condemning the jack motor, record its isolation reading (the meter value or jumper/bypass result at the jack motor itself) and send it. [General trade knowledge]\nSupport the 5th Wheel at front and rear with jack stands; keep clear of pinch points. [Manufacturer site: https://lci-support-doc.s3.amazonaws.com/manuals/leveling-and-stabilization/ground%20control/ccd-0001745.pdf p.9]\nDisconnect that front jack motor’s cables from the system harness. [Manufacturer site: https://lci-support-doc.s3.amazonaws.com/manuals/leveling-and-stabilization/ground%20control/ccd-0001745.pdf p.22]\nWith a 1/2" socket or wrench, remove the two motor retention bolts (Fig. 31A) and lift the motor off (Fig. 32). [Manufacturer site: https://lci-support-doc.s3.amazonaws.com/manuals/leveling-and-stabilization/ground%20control/ccd-0001745.pdf p.22]\nEngage the new motor’s drive coupler on the jack-leg drive shaft, reinstall/tighten the two bolts, reconnect the harness, zip-tie it tight to the motor. [Manufacturer site: https://lci-support-doc.s3.amazonaws.com/manuals/leveling-and-stabilization/ground%20control/ccd-0001745.pdf p.22]\nReport when the new motor is bolted on and plugged in (or if the coupler will not engage).\n'

SUBURBAN_DOC = {"id": 124, "title": "Suburban Water Heater Master Service and Training Manual", "brand": "Suburban", "models": "SW6DE",
                "category": "Water Heaters", "doc_number": "S1"}


def _walk_rc22(tech, reply):
    hist = []
    for t, g in RC22_854_HIST:
        hist += [{"role": "user", "content": t}, {"role": "assistant", "content": g}]
    store = {}
    out = go.official_turn(tech, "Water Heaters", "Suburban SW6DE", hist, library=Lib([SUBURBAN_DOC], {124: SUBURBAN_P17}),
                           chat_fn=lambda m, t, e, r=reply: r, pin_store=store)
    return out["reply"], store.get("gd_pin", {})


def _board_lines(text):
    return [ln for ln in text.splitlines() if go._replace_targets(ln) and "board" in ln.lower() and not go.GUARD_LINE_RE.match(ln)]


class TestLockedRC22(unittest.TestCase):
    """854ef47 RC22: every 'decisive' test GD relied on was recorded as normal/OK (or read AT the board, not OF it), then GD condemned
    the DSI module board at T8 and again at T9. No pending scope covered the path at T8, so this is condition (1) on its own."""

    def test_no_pending_scope_at_t8(self):
        hist = [m for t, g in RC22_854_HIST for m in ({"role": "user", "content": t}, {"role": "assistant", "content": g})]
        pairs = go.session_tests(hist, RC22_854_T8_TECH)
        path = go.complaint_path([a for _, a in pairs], SUBURBAN_DOC["title"])
        self.assertFalse([p for p in go.pending_tests(pairs, SUBURBAN_P17) if p.scope & path])

    def test_t8_board_condemn_is_held(self):
        out, pin = _walk_rc22(RC22_854_T8_TECH, RC22_854_T8_GD)
        self.assertEqual(_board_lines(out), [], out)
        self.assertIn("Hold all part replacement for the DSI module board", out)
        self.assertIn("never condemns", out)
        self.assertTrue(pin.get("condemn_basis_held"), pin)

    def test_t8_hold_asks_the_manuals_own_board_test(self):
        out, _ = _walk_rc22(RC22_854_T8_TECH, RC22_854_T8_GD)
        self.assertRegex(out, r"(?i)test module board with field tester")

    def test_t9_nothing_else_board_condemn_is_held(self):
        tech = [t for t, _ in RC22_854_HIST] + [RC22_854_T8_TECH, RC22_854_T9_TECH]
        out, held = go.condemn_gate(RC22_854_T9_GD, tech, "[PAGE 17]\n" + SUBURBAN_P17)
        self.assertEqual(_board_lines(out), [], out)
        self.assertTrue(held)

    def test_board_has_no_own_failing_result(self):
        tech = [t for t, _ in RC22_854_HIST] + [RC22_854_T8_TECH]
        self.assertEqual(go.own_failing_result({"board", "pcb"}, tech), "")
        # 'yellow at the board is -1.2 V' was read AT the board: it belongs to no component
        self.assertEqual(go.result_owners("yellow at the board is 0 V idle / ~-1.2 V during try"), set())

    def test_p17_is_not_an_elimination_path_for_the_board(self):
        """p.17 says 'replace module board if found to be defective' and 'test module board with field tester': it asks for the
        board's OWN test, so it is not an elimination path."""
        line = "Replace the DSI module board (SW6DE part 520814). [Library: Suburban Water Heater Master Service and Training Manual p.17]"
        self.assertEqual(go.manual_elimination_cite(line, {"board", "pcb"}, "[PAGE 17]\n" + SUBURBAN_P17), "")

    def test_board_own_failing_result_releases(self):
        tech = [t for t, _ in RC22_854_HIST] + ["Module board tested with the field tester: board failed (no valve output on the tester)."]
        out, held = go.condemn_gate(RC22_854_T8_GD, tech, "[PAGE 17]\n" + SUBURBAN_P17)
        self.assertTrue(_board_lines(out), out)
        self.assertFalse(held)


class TestLockedInstallProcedureIsACondemn(unittest.TestCase):
    """a4aef6c RC18 run 3, T5: no replace verb, but a full install procedure for a 'new motor' (lift the motor off, engage the new
    motor's coupler) with only a normal/OK isolation and a broken roll pin (no component of its own) recorded. The tech swapped the
    motor (complaint stayed). An install procedure is a condemn of the part it calls new."""

    def test_rc18_new_motor_procedure_is_held(self):
        out, held = go.condemn_gate(RC18_A4_T5_GD, RC18_A4_TECH, "")
        self.assertNotRegex(out, r"(?i)engage the new motor|lift the motor off|new motor is bolted")
        self.assertIn("Hold all part replacement for the motor", out)
        self.assertTrue(held)

    def test_new_part_with_own_failing_result_keeps_its_procedure(self):
        reply = "Pull the old fuse out of the holder.\nPush the new 15A ATC fuse fully into the holder. [General trade knowledge]"
        out, held = go.condemn_gate(reply, ["No power.", "15A fuse is in the holder; continuity is OPEN (blown)."], "")
        self.assertIn("Push the new 15A ATC fuse", out)
        self.assertFalse(held)


RC02_A4_TECH = ['Customer reports both slide-outs won’t extend or retract. [no findings yet]', 'Wheels chocked, area clear, 12V on with ignition off. Slide icons on the OneControl home screen look normal/OK. No movement on either slide, no panel message of note, and relays click audibly at the Unity board on extend and retract for both.', 'Connectors re-seated, pins look normal/OK. Board is Unity X270D, IDS Part# 30606H3162401279. ~14.4 VDC at the X270D power inputs, resting.', 'X270 30A and 15A fuses in the 12V panel are good. Stamp ratings and dedicated-feed details look normal/OK.', 'Resting on the slide REV pairs looks normal/OK. At the X270D slide output terminals, no voltage during EXTEND or RETRACT—outputs stay open/floating and collapse under command instead of switching polarity; both slide circuits identical.']


class TestOutputFailureWithGoodInput(unittest.TestCase):
    def test_rc02_output_fails_with_good_input_is_own(self):
        """a4aef6c RC02: inputs ~14.4 VDC (good), outputs no voltage/open-floating on command: the board's own failure."""
        self.assertTrue(go.output_failure({"x270d", "unity"}, RC02_A4_TECH))

    def test_rc22_output_with_collapsing_feed_is_not_own(self):
        tech = [t for t, _ in RC22_854_HIST] + [RC22_854_T8_TECH, "Board output to the valve is 0 V during the try."]
        self.assertEqual(go.output_failure({"dsi", "board"}, tech), "")


class TestBasisPathsStillWork(unittest.TestCase):
    def test_rc29_normal_ok_lock_is_kept(self):
        """Normal/OK still counts as A's recorded result (RC29 lock) - it rules A out; it never becomes B's failing result."""
        msgs = ["Compressor amp draw and winding check look normal/OK."]
        self.assertTrue(go.isolation_recorded("compressor", msgs))
        self.assertEqual(go.own_failing_result({"compressor"}, ["Customer says it is noisy."] + msgs), "")

    def test_oem_authorization_path(self):
        reply = ("Compressor is not a field-replaceable part on this unit. Document the findings and submit them to the OEM for authorization.\n"
                 "OEM AUTHORIZATION FINDINGS\nComplaint verified: loud knock.\nRequested authorization: replace complete rooftop A/C unit. "
                 "[Library: Chill Low Profile Air Conditioner Troubleshooting and Service Manual p.4]")
        out, held = go.condemn_gate(reply, ["Customer says loud knock.", "Fans look normal/OK; knock is from the compressor area."], "")
        self.assertIn("Requested authorization: replace complete rooftop A/C unit", out)
        self.assertFalse(held)

    def test_manual_elimination_path_rc12_p27(self):
        line = "Replace the inverter PCB and fan. [Library: Furrion Arctic 8 & 10 cu.ft. Refrigerator Troubleshooting and Service Manual p.27]"
        tech = ["Customer says it freezes contents with E2.", "F+/F- at the inverter PCB looks normal/OK.", "E2 returned after the power reset."]
        out, held = go.condemn_gate(line, tech, "[PAGE 27]\n" + FURRION_P27)
        self.assertIn("Replace the inverter PCB and fan", out)
        self.assertFalse(held)

    def test_own_failing_results(self):
        cases = [({"breaker"}, "Drop is across the 30A breaker between isolator and batteries (not near zero)."),
                 ({"fuse"}, "15A fuse is present at the front underneath the fridge; continuity is OPEN (blown)."),
                 ({"thermostat"}, "Bypassing the thermostat at the furnace, the furnace operates."),
                 ({"motor"}, "Indoor fan does not rotate high or low, and the fan motor shaft is locked (~1.91 A).")]
        for comps, sent in cases:
            self.assertTrue(go.own_failing_result(comps, ["Customer complaint.", sent]), sent)

    def test_direct_power_to_a_part_is_its_pass_not_a_bypass(self):
        self.assertEqual(go.own_failing_result({"motor"}, ["Complaint.", "Tongue motor runs on direct 12V both ways."]), "")

    def test_conditionals(self):
        own = "If no continuity on HIGH COOL, replace the selector switch. [General trade knowledge]"
        other = "If valve and supply are both good and yellow still never drives, replace the module board. [General trade knowledge]"
        in_range = "If 30-50 ohm: replace module board 520814. [General trade knowledge]"
        self.assertIn("selector", go.condemn_gate(own, ["Complaint."], "")[0])
        self.assertEqual(_board_lines(go.condemn_gate(other, ["Complaint."], "")[0]), [])
        self.assertEqual(_board_lines(go.condemn_gate(in_range, ["Complaint."], "")[0]), [])


PARTS = ["board", "valve", "motor", "fuse", "thermostat", "relay", "breaker", "compressor", "selector", "capacitor", "switch", "igniter"]
PASS_TEMPL = ["{p} looks normal/OK.", "{p} checked good.", "{p} reading is in spec.", "{p} unplugged made no change.",
              "Voltage at the {p} looks normal/OK.", "{p} reads 12.6 V, normal."]
AT_TEMPL = ["Yellow at the {p} is 0 V idle.", "Signal at the {p} drops to 5 V during the try.", "Got 0 V at the {p} output channel."]
FAIL_TEMPL = ["The {p} reads open.", "{p} is shorted to ground.", "The {p} looks blown, continuity OPEN.", "{p} is seized and will not turn."]
REPLY_TEMPL = ["Replace the {p}. [General trade knowledge]",
               "Lift the old {p} off its mount.\nEngage the new {p} and tighten the two bolts. [Library: Service Manual p.3]",
               "Nothing else to check: {o} already OK, replace the {p}. [Library: Service Manual p.3]",
               "Condemn the {p} and order a new one. [General trade knowledge]",
               "Install a new {p}. [Library: Service Manual p.3]"]
OWN_STATE_PAGE = "[PAGE 3]\nTest the {p} with a meter. Replace the {p} if found to be defective."


class TestPropertyNoCondemnWithoutBasis(unittest.TestCase):
    """Random sessions: no replace line for B survives unless B has its own failing result, a cited elimination path, or an OEM path.
    Normal/OK results on any part (B included) and readings taken AT B never condemn B."""

    def _session(self, rnd, b, own_fail):
        others = [p for p in PARTS if p != b]
        msgs = ["Customer says it does not work."]
        for _ in range(rnd.randint(2, 6)):
            k = rnd.random()
            p = rnd.choice(others + [b])
            if k < 0.45:
                msgs.append(rnd.choice(PASS_TEMPL).format(p=p).capitalize())
            elif k < 0.7:
                msgs.append(rnd.choice(AT_TEMPL).format(p=b))
            else:
                msgs.append(rnd.choice(FAIL_TEMPL).format(p=rnd.choice(others)).capitalize())
        if own_fail:
            msgs.insert(rnd.randint(1, len(msgs)), rnd.choice(FAIL_TEMPL).format(p=b).capitalize())
        return msgs

    def test_property(self):
        rnd = random.Random(20261017)
        n_held = n_kept = 0
        for i in range(600):
            b = rnd.choice(PARTS)
            own_fail = rnd.random() < 0.35
            msgs = self._session(rnd, b, own_fail)
            o = rnd.choice([p for p in PARTS if p != b])
            reply = rnd.choice(REPLY_TEMPL).format(p=b, o=o) + "\nVERIFY: run it 2-3 cycles. [General trade knowledge]"
            sec = OWN_STATE_PAGE.format(p=b) if rnd.random() < 0.5 else ""
            out, held = go.condemn_gate(reply, msgs, sec)
            survived = [ln for ln in out.splitlines() if (go._replace_targets(ln) or re.search(r"\bnew\s+" + b, ln))
                        and not go.GUARD_LINE_RE.match(ln) and re.search(r"\b" + b + r"\b", ln)]
            has_own = bool(go.own_failing_result(go.target_heads(b), msgs))
            if own_fail:
                self.assertTrue(has_own, msgs)
            if has_own:
                self.assertTrue(survived, (msgs, reply, out))
                n_kept += 1
            else:
                self.assertEqual(survived, [], (msgs, reply, out))
                self.assertIn(f"Hold all part replacement for the {b}", out)
                n_held += 1
        self.assertGreater(n_held, 150)
        self.assertGreater(n_kept, 100)

    def test_property_oem_and_elimination_paths_survive(self):
        rnd = random.Random(7)
        for i in range(200):
            b = rnd.choice(PARTS)
            msgs = ["Customer says it does not work.", f"{rnd.choice([p for p in PARTS if p != b]).capitalize()} looks normal/OK."]
            if i % 2:
                reply = (f"OEM AUTHORIZATION FINDINGS\nComplaint verified.\nRequested authorization: replace the {b}. "
                         f"[Library: Service Manual p.3]")
                sec = ""
            else:
                reply = f"Replace the {b}. [Library: Service Manual p.3]"
                sec = f"[PAGE 3]\nIs the voltage 12V? Yes No Check connections. Replace the {b}."
            out, held = go.condemn_gate(reply, msgs, sec)
            self.assertFalse(held, (reply, out))


def _walk_rc20(n):
    doc, text = DOCS["rc20"]
    cat, model = CATS["rc20"]
    hist, store, outs = [], {}, []
    for tech in RC20_854_TECH[:n]:
        out = go.official_turn(tech, cat, model, hist, library=Lib([doc], {doc["id"]: text}),
                               chat_fn=lambda m, t, e: RC20_854_GD_T9, pin_store=store)["reply"]
        outs.append(out)
        hist += [{"role": "user", "content": tech}, {"role": "assistant", "content": out}]
    return outs, store.get("gd_pin", {})


class TestTerminalEscalationSummary(unittest.TestCase):
    """854ef47 RC20 T10-T14 repeated the same hold five times (a loop) even after the tech reported the tech-line call. A session
    that ends with pending tests and no fix must end on the ESCALATION SUMMARY: pending tests named + shop/OEM step."""

    def test_rc20_ends_on_escalation_summary(self):
        outs, pin = _walk_rc20(len(RC20_854_TECH))
        summ = [i for i, o in enumerate(outs) if go.ESCALATION_HEAD in o]
        self.assertTrue(summ, outs[-1])
        s = outs[summ[0]]
        self.assertRegex(s, r"Blocking pending test\(s\): \"[^\"]*(?:[Pp]lumbing|gray-coil)")
        self.assertIn("shop/OEM tech line", s)
        self.assertIn("Hold all part replacement", s)
        self.assertEqual([ln for ln in s.splitlines() if go._replace_targets(ln) and not go.GUARD_LINE_RE.match(ln)], [])

    def test_summary_once_the_tech_reports_the_call(self):
        covering = [go.PendingTest("Plumbing check at the front-left hoses is still pending.", [], {"hose", "jack"}, set())]
        pin = {}
        out = go.structural_reply("Run the plumbing check.", covering, pin,
                                  ["Front jacks drift.", "Already called the shop/OEM line; plumbing check still pending."])
        self.assertIn(go.ESCALATION_HEAD, out)
        self.assertIn("Plumbing check", out)

    def test_property_any_pending_session_ends_named(self):
        rnd = random.Random(31)
        for i in range(100):
            comps = set(rnd.sample(sorted(go.COMPONENT_WORDS), 3))
            text = f"{rnd.choice(['Leak-down', 'Unplug', 'Voltage', 'Continuity'])} test on the {sorted(comps)[0]} is still pending."
            covering = [go.PendingTest(text, [f"Do the {sorted(comps)[0]} test."], comps, set())]
            pin, outs = {}, []
            for k in range(go.REPEAT_MAX_ASKS + 2):
                outs.append(go.structural_reply("Replace the " + sorted(comps)[1] + ".", covering, pin, ["Complaint.", text]))
            self.assertNotIn(go.ESCALATION_HEAD, outs[0])
            self.assertIn(go.ESCALATION_HEAD, outs[go.REPEAT_MAX_ASKS])
            self.assertIn(text[:60], outs[go.REPEAT_MAX_ASKS])
            self.assertIn("shop/OEM tech line", outs[go.REPEAT_MAX_ASKS])


if __name__ == "__main__":
    unittest.main()
