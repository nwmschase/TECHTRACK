"""ROOT RULE locked tests (Leader 2026-10-17 1:45 AM, PR #92 @174d094): each pending test is a structured object with a component
scope taken from GD's own request plus the pinned section; a replace/repair line for X survives only if X has its own decisive result
AND no pending scope contains X; while a pending scope covers the complaint path the reply is structural (pending test, tech line,
safety). Sessions below are verbatim from the sim transcripts (RC04 4aff2a6 + 0c4a291 turn-7 reply, RC20 174d094, RC22 215fce8).
No case keys: GD code never sees an RC id, brand or doc id."""
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go  # noqa: E402
from tests.test_selector_root_fix import Lib  # noqa: E402

RC04_HIST = [('Customer reports leveling operates intermittently, the touchpad is occasionally unresponsive during operation, and auto-level doesn’t consistently complete.', 'Safety first: chock the wheels, keep everyone clear of jacks/slides, and disconnect power before touching wiring.\nChock the wheels, keep everyone clear of the jacks, and confirm coach 12-volt power is on so the BAL touchscreen is live. [General trade knowledge]\nFrom the touchscreen, start Auto Level the same way the customer would and let it run until it finishes, stops, or the screen freezes. [General trade knowledge]\nWhile it runs, watch the touchscreen and the jacks: note whether Auto Level starts, whether the screen stays responsive, whether Auto Level completes, and any message, freeze, or stop. [General trade knowledge]\nReport exactly what you saw (start / screen response / complete or not / any message). [General trade knowledge]'), ('System worked during diag: Auto Level started from the touchscreen, the screen stayed responsive, and it completed with no freeze or comm message.', 'With 12-volt power still on, inspect seating of the BAL controller harness, the touchscreen/panel connector, and each jack motor connector on this circuit: push fully home, check lock tabs, look for bent pins or corrosion. [General trade knowledge]\nReport whether every connector was fully seated and locked, or which one was loose/damaged. [General trade knowledge]'), ('No loose connections — harness, touchscreen/panel, and jack motor connectors were fully seated and locked with no bent pins or corrosion.', 'On the BAL touchscreen, press Settings. [Manufacturer site: https://balrvproducts.com/wp-content/uploads/downloads/tech/20300635_USER-MANUAL.pdf p.12]\nPress SET LEVEL. [Manufacturer site: https://balrvproducts.com/wp-content/uploads/downloads/tech/20300635_USER-MANUAL.pdf p.12]\nPress CALIBRATE LEVEL. [Manufacturer site: https://balrvproducts.com/wp-content/uploads/downloads/tech/20300635_USER-MANUAL.pdf p.12]\nConfirm the display shows the control sensors are now calibrated to the RV’s current position. [Manufacturer site: https://balrvproducts.com/wp-content/uploads/downloads/tech/20300635_USER-MANUAL.pdf p.12]\nReport exactly what the screen showed after you pressed CALIBRATE LEVEL. [Manufacturer site: https://balrvproducts.com/wp-content/uploads/downloads/tech/20300635_USER-MANUAL.pdf p.12]\nVERIFY: run the function again (full cycle, 2-3 times) and confirm it completes and the complaint is gone. [General trade knowledge]'), ('After CALIBRATE LEVEL the screen looked normal/OK. Ran Auto Level again during diag: it started, the touchscreen stayed responsive, and it completed with no freeze or message.', 'With coach 12V on, set the meter to DC volts. Probe battery positive and negative at the coach battery (or converter output) and report the voltage. [General trade knowledge]\nStart Auto Level from the touchscreen and, while jacks are moving, probe the same battery points again and report running voltage. [General trade knowledge]\nIf battery stays above 12.0 V running, probe 12V and ground at the BAL controller harness (backprobe the power and ground pins, connectors still locked) with Auto Level running and report that voltage. [General trade knowledge]\nReport those three readings (battery static, battery running, controller running). If Auto Level fails or the screen freezes on any cycle, stop and report that instead. [General trade knowledge]'), ('Converter output is correct at rest. Battery voltage dropped heavily under load while Auto Level was running. BAL still powered and communicated; I didn’t get a separate controller-harness voltage in the notes.', 'Map the 12V charging path from converter/charger to the battery: converter/charger, fuses and breakers, battery isolator/disconnect, busbars, battery BMS if lithium, and cable runs. [General trade knowledge]\nList each device in order from converter output to battery posts (include wire size/condition if you can see it). [General trade knowledge]\nDo not start voltage-drop tests until that map is reported. [General trade knowledge]\nReport the map. [General trade knowledge]'), ('Charge path as mapped: converter/charger → isolator/disconnect → 30A breaker between isolator and the lithium batteries → battery posts (BMS on the lithiums). Converter output was correct; drop is downstream so the batteries never reach full charge.', 'With shore power on so the converter is charging, set the meter to DC volts. [General trade knowledge]\nPlace one lead on the converter output (input side of the isolator/disconnect) and the other lead on the isolator/disconnect output (same current path). [General trade knowledge]\nReport the voltage drop across the isolator/disconnect. [General trade knowledge]')]
RC04_TECH = 'Voltage-drop test from battery toward the isolator didn’t show the drop across the isolator itself — it was across the 30A breaker between isolator and batteries.'
RC04_REPLY = 'Replace the 30A breaker between the isolator/disconnect and the lithium batteries (and clean/repair its lugs if burned or loose). [General trade knowledge]\nAfter the repair, with shore power on, recheck voltage at the batteries under charge. [General trade knowledge]\nLet the batteries charge, then rerun Auto Level as the customer would and confirm it completes with a responsive pad and no errors. [General trade knowledge]\nBefore release, run a battery capacity / BMS state-of-health (Ah load) test; that was not done. [General trade knowledge]\nVERIFY: run the function again (full cycle, 2-3 times) and confirm it completes and the complaint is gone. [General trade knowledge]'
RC20_HIST = [('Customer says the front jacks drift/move on their own when other circuits pressurize, including the slides; it started after the front-left jack was replaced (old one clanked, internal failure).', 'Safety first: chock the wheels, keep everyone clear of jacks/slides, and disconnect power before touching wiring.\nChock the wheels and stay clear of the jacks and underbody while hydraulics run. [General trade knowledge]\nWith coach power on as the customer uses it, operate a slide (or another circuit that pressurizes the system) and watch both front jacks for any extend, retract, or drift; report which jack moves, which way, and how far. [General trade knowledge]\nPower the Level Up LCD and read any fault or warning on the pad (Low Voltage, Excess Angle, External Sensor, or other text) and on the Firefly Leveling screen Warnings; report the exact message or “none.” [Library: Level Up Advantage 807662 Manual Mode Flash Home — Shop Writeup p.2]\n\nReport those results.'), ('With power on I ran a slide/other circuit: front jacks still drift on their own like the complaint (same as arrival). Level Up LCD and Firefly Warnings showed none. Plumbing check and gray-coil unplug still pending.', 'Confirm the Remote Sensor and all Level Up controller, LCD/panel, and hydraulic power-unit/valve (gray-coil) connectors are fully seated and locked; report any loose, backed-out, or corroded plug. [Library: Level Up Advantage 807662 Manual Mode Flash Home — Shop Writeup p.2]\nHold all part replacement: an isolation test is still pending ("Plumbing check and gray-coil unplug still pending."). No part is replaced or submitted for replacement until that result is recorded. Do that test, or call the shop/OEM tech line with the findings so far. [General trade knowledge]\nUnplug the gray coil on the front-jack valve circuit, then run the same slide/other circuit that pressurizes the system and watch both front jacks; report whether either jack still drifts. [Library: Level Up Advantage 807662 Manual Mode Flash Home — Shop Writeup p.2]\n\nReport those results.\nVERIFY: run the function again (full cycle, 2-3 times) and confirm it completes and the complaint is gone. [General trade knowledge]')]
RC20_TECH = 'Connectors at the remote sensor, controller, LCD, and HPU/valve look seated and OK. Gray-coil unplug and plumbing check are still pending, so I have not isolated whether the jacks still drift with the gray coil unplugged.'
RC20_REPLY = ("Repair both front jacks as a matched pair at cylinder/assembly level (or the HPU/valve if it is not seating), then "
              "re-bleed/resync; do not replace only one side when both drift. [General trade knowledge]\n"
              "Replace both front holding-valve cartridges as a matched pair. [General trade knowledge]\n"
              "If the front jacks still move with no voltage on the coils: replace both front jack hoses. [General trade knowledge]")
RC22_HIST = [('Customer said they ran gas and electric together, got gurgling/steam and water out the PRV. They say electric never worked after that; gas clicks but never lights, and now it only tries for a shorter time.', 'Safety first: chock the wheels, keep everyone clear of jacks/slides, and disconnect power before touching wiring.\nConfirm no LP odor at floor level around the heater; if you smell gas, stop and do not operate. Report smell or none. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nConfirm the tank is full: open a hot faucet until a steady stream flows, then close it. Report whether water flowed. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nElectric element switch OFF (lower left in control housing), DSI ON/OFF switch OFF, LP on. Turn the DSI switch ON. Watch the reset light, listen for valve click/spark, watch the burner, and time how long it tries. Report reset-light behavior, spark yes/no, flame yes/no, and attempt time. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nTurn DSI switch OFF. Turn the electric element switch ON. Wait several minutes, then check tank warmth or hot-water temp at a faucet (avoid scald). Report whether it heats. [Library: Suburban Water Heater Master Service and Training Manual p.18]\nReport those results.'), ('No LP odor at floor level. Tank is full—steady stream at the hot faucet. DSI ON: it tries (valve click), no flame, shorter attempt; electric switch ON and it does heat (element ~90 VAC).', 'With DSI switch OFF and 12 V DC still on the coach, reseat the module-board plug, the DSI ON/OFF switch/lamp connector, and the gas-valve brown-wire connector until they click fully home. Report if any pin was loose, burned, or not fully seated. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nMeter on DC volts, 20 V range. Probe the DSI ON/OFF switch input (coach 12 V feed vs chassis ground) with the switch still OFF. Report voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf that voltage is 10.5–13.5 VDC, turn the DSI switch ON and probe the same switch output (load side) vs ground. Report voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nReport those results.'), ('Connectors seated fully, pins look OK. ~14.2 V idle on the 12 V feed. With DSI ON it still collapses during the try (~5–10 V).', 'Meter on DC volts, 20 V range. Leave DSI switch OFF. Unplug the brown wire at the gas valve. Turn DSI switch ON for one try and probe the brown wire (board/harness side) vs chassis ground during the try. Report voltage (does it still drop to 5–10 V?). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf that voltage stays 10.5–13.5 VDC with the valve unplugged, turn DSI OFF, reconnect the brown wire, then probe brown at the valve vs ground during the next try. Report voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf voltage still collapses with the valve unplugged, probe the red wire at the module board vs ground during a try (DSI ON). Report voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nReport those readings.'), ('Didn’t get a separate reading with the brown unplugged at the valve. What we have is ~14.2 V idle, collapsing to ~5–10 V during a try.', 'Leave DSI switch OFF. Unplug the brown wire at the gas valve so the valve is out of the circuit. Meter on DC volts, 20 V range. Turn DSI switch ON for one try and probe the brown wire on the board/harness side vs chassis ground during that try. Report the voltage (does it still drop to 5–10 V, or hold 10.5–13.5?). [Library: Suburban Water Heater Master Service and Training Manual p.17]\n\nReport that reading.')]
RC22_TECH = 'That brown-unplugged-at-the-valve reading isn’t in the notes. Battery-jump test and tech-line call are still pending.'
RC22_REPLY = 'DSI and coach 12 V OFF. Meter on ohms. Probe the two gas-valve solenoid terminals (brown circuit). Report ohms. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf 30–50 Ω: supply is collapsing under load—correct coach 12 V feed (min 10.5 VDC during TFI) or replace module board 520814. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf near 0 Ω or far outside 30–50 Ω: replace gas valve (LP) 161109. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf you cannot get ohms: jump a known-good 12 V battery at the heater 12 V feed vs chassis ground, then retry DSI; if voltage still drops, replace module board; if it holds and lights, repair coach wiring. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nShop/OEM tech-line: 423-775-2131 EXT. 7102 with these readings. [Library: Suburban Water Heater Master Service and Training Manual p.3]\nAfter any repair: DSI ON, confirm full try, flame, and hot water; electric still heats. Report result. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nVERIFY: run the function again (full cycle, 2-3 times) and confirm it completes and the complaint is gone. [General trade knowledge]' + "\nReplace module board 520814 and the gas valve 161109. [General trade knowledge]"

CATS = {"rc04": ("Leveling", "BAL LS5.3"), "rc20": ("Leveling", "HWH 807662"), "rc22": ("Water Heaters", "Suburban SW6DE")}
DOCS = {
    "rc04": ({"id": 41, "title": "BAL Electric Leveling System User Manual", "brand": "BAL", "models": "LS5.3", "doc_number": "B1"},
             "Auto Level. If the touchpad is unresponsive check 12V at the controller harness. Low battery voltage stops Auto Level."),
    "rc20": ({"id": 42, "title": "Level Up Advantage Manual Mode Shop Writeup", "brand": "HWH", "models": "807662", "doc_number": "L1"},
             "Jacks drift when other circuits pressurize. Unplug the gray coil on the front-jack valve circuit and watch the front jacks. "
             "Check plumbing at the manifold, hoses and fittings for crossover."),
    "rc22": ({"id": 43, "title": "Suburban Water Heater Master Service and Training Manual", "brand": "Suburban", "models": "SW6DE", "category": "Water Heaters",
              "doc_number": "S1"},
             "Voltage at the heater must stay 10.5-13.5 VDC during TFI. Unplug the brown wire at the gas valve and probe the brown wire "
             "at the board during the try. Gas valve solenoid 30-50 ohms. Replace module board 520814 or gas valve 161109."),
}


def _turn(key, hist_pairs, tech, reply):
    doc, text = DOCS[key]
    hist = []
    for t, g in hist_pairs:
        hist += [{"role": "user", "content": t}, {"role": "assistant", "content": g}]
    store = {}
    cat, model = CATS[key]
    out = go.official_turn(tech, cat, model, hist, library=Lib([doc], {doc["id"]: text}),
                           chat_fn=lambda m, t, e, r=reply: r, pin_store=store)
    return out["reply"], store.get("gd_pin", store)


def replace_lines(reply):
    """Every surviving replace/repair directive (conditionals included); guard/hold lines and quoted tech words excluded."""
    reply = re.sub(r'"[^"\n]*"', '""', reply)
    return [ln for ln in reply.splitlines() if go._replace_targets(ln)]


class TestLockedRealSessions(unittest.TestCase):
    def test_rc04_breaker_outside_scope_reaches_its_fix(self):
        out, pin = _turn("rc04", RC04_HIST, RC04_TECH, RC04_REPLY)
        self.assertTrue(re.search(r"Replace the 30A breaker", out), out)
        self.assertNotIn("isolation test is still pending", out)
        self.assertFalse(pin.get("scope_held"), pin.get("scope_held"))

    def test_rc04_scope_is_the_controller_harness_circuit(self):
        pairs = go.session_tests([m for t, g in RC04_HIST for m in ({"role": "user", "content": t},
                                  {"role": "assistant", "content": g})], RC04_TECH)
        pt = go.pending_tests(pairs, "")
        self.assertEqual(len(pt), 1, pt)
        self.assertIn("controller", pt[0].scope)
        self.assertIn("harness", pt[0].scope)
        self.assertNotIn("breaker", pt[0].scope)
        self.assertFalse(pt[0].scope & go.complaint_path([p[1] for p in pairs], DOCS["rc04"][0]["title"]))
        self.assertTrue(go.decisive_result("30A breaker", [p[1] for p in pairs]))

    def test_rc20_front_jacks_inside_scope_are_blocked_structurally(self):
        out, pin = _turn("rc20", RC20_HIST, RC20_TECH, RC20_REPLY)
        self.assertEqual(replace_lines(out), [], out)
        self.assertIn("isolation test is still pending", out)
        self.assertTrue(pin.get("structural_held"), pin)
        self.assertIn("Unplug the gray coil", out)  # the pending test itself is what goes out

    def test_rc20_scope_covers_jacks_hoses_and_valves(self):
        pairs = go.session_tests([m for t, g in RC20_HIST for m in ({"role": "user", "content": t},
                                  {"role": "assistant", "content": g})], RC20_TECH)
        pt = go.pending_tests(pairs, DOCS["rc20"][1])
        scope = set().union(*(p.scope for p in pt))
        self.assertTrue({"jack", "hose", "cartridge", "solenoid", "valve", "coil", "manifold"} <= scope, scope)

    def test_rc22_board_and_valve_inside_scope_are_blocked_structurally(self):
        out, pin = _turn("rc22", RC22_HIST, RC22_TECH, RC22_REPLY)
        self.assertEqual(replace_lines(out), [], out)
        self.assertIn("isolation test is still pending", out)
        self.assertTrue(pin.get("structural_held"), pin)
        self.assertIn("423-775-2131", out)  # the tech line survives

    def test_structural_reply_repeats_the_test_at_most_twice(self):
        pin, outs = {}, []
        hist = []
        for t, g in RC20_HIST:
            hist += [{"role": "user", "content": t}, {"role": "assistant", "content": g}]
        doc, text = DOCS["rc20"]
        for _ in range(4):
            out = go.official_turn(RC20_TECH, *CATS["rc20"], hist, library=Lib([doc], {doc["id"]: text}),
                                   chat_fn=lambda m, t, e: RC20_REPLY, pin_store=pin)["reply"]
            outs.append(out)
            hist += [{"role": "user", "content": RC20_TECH}, {"role": "assistant", "content": out}]
        self.assertIn("Unplug the gray coil", outs[0])
        self.assertIn("asked twice", outs[3]); self.assertIn(go.ESCALATION_HEAD, outs[3])
        self.assertTrue(all(replace_lines(o) == [] for o in outs), outs)


# ---- property test over random sessions -------------------------------------------------------------------------------------------
HYD = ["jack", "cylinder", "hose", "fitting", "manifold", "solenoid", "coil", "pump", "cartridge"]
GAS = ["igniter", "electrode", "burner", "regulator", "module board", "thermocouple"]
AREA_A = ["touchpad", "display", "touchscreen", "lcd"]          # complaint area for gate-mode sessions
AREA_B = ["controller", "harness", "connector", "sensor", "relay"]  # pending-test area for gate-mode sessions
UNRELATED = ["breaker", "fuse", "inverter", "capacitor", "thermostat", "fan", "isolator"]
VERBS = ["Replace the {x}. [General trade knowledge]",
         "Repair the {x} at assembly level, then retest. [General trade knowledge]",
         "If it still fails, replace the {x}. [General trade knowledge]",
         "Rebuild the {x} as a matched pair. [General trade knowledge]",
         "Swap in a new {x} and verify. [General trade knowledge]",
         "Recommended repair: replace {x}. [General trade knowledge]"]


def _session(rng, structural):
    if structural:
        pool, complaint = (HYD, "Customer says the front jacks drift on their own when the slides run.") if rng.random() < .5 else \
            (GAS, "Customer says the water heater gas clicks but never lights.")
        a, b = rng.sample(pool, 2)
        req = f"Unplug the {a} and the {b} circuit, run one cycle, and report the reading at the {a}. [General trade knowledge]"
        pend = f"I didn't get the {a} unplug reading yet; that test is still pending."
        inscope = list(pool)
    else:
        a0, = rng.sample(AREA_A, 1)
        a, b = rng.sample(AREA_B, 2)
        complaint = f"Customer says the {a0} is unresponsive and the function does not complete."
        req = f"Backprobe 12V and ground at the {a} {b} and report that voltage. [General trade knowledge]"
        pend = f"I didn't get a separate {a}-{b} voltage in the notes."
        inscope = [a, b]
    u = rng.choice(UNRELATED)
    decisive = f"Voltage-drop test: the drop was across the {u} (1.8 V)."
    return complaint, req, pend, inscope, u, decisive


class TestPropertyRandomSessions(unittest.TestCase):
    N = 400

    def test_in_scope_part_never_replaced_unrelated_never_blocked(self):
        rng = random.Random(20261017)
        doc = {"id": 9, "title": "Service Manual", "brand": "Generic", "models": "HL1", "doc_number": "G1"}
        for i in range(self.N):
            structural = rng.random() < .5
            complaint, req, pend, inscope, u, decisive = _session(rng, structural)
            hist = [{"role": "user", "content": complaint}, {"role": "assistant", "content": req},
                    {"role": "user", "content": pend}, {"role": "assistant", "content": req}]
            x = rng.choice(inscope)
            reply = "\n".join([rng.choice(VERBS).format(x=x), rng.choice(VERBS).format(x=u)])
            # a reading on another in-scope part (never the pending test's own target: that reading would answer the test)
            tech = decisive + (f" Also the {x} reads 0.4 ohms." if rng.random() < .5 and x not in pend else "")
            out = go.official_turn(tech, "Leveling", "Generic HL1", hist, library=Lib([doc], {9: "Troubleshooting."}),
                                   chat_fn=lambda m, t, e, r=reply: r, pin_store={})["reply"]
            kept = " ".join(replace_lines(out)).lower()
            self.assertNotIn(x.split()[-1], kept, f"session {i}: in-scope {x} replaced\n{reply}\n---\n{out}")
            if structural:
                self.assertIn("isolation test is still pending", out, f"session {i}")
            else:
                self.assertIn(u, kept, f"session {i}: unrelated {u} with its own decisive result was blocked\n{reply}\n---\n{out}")

    def test_answering_the_pending_test_releases_its_part(self):
        complaint = "Customer says the water heater gas clicks but never lights."
        req = "Unplug the igniter and the burner circuit, run one cycle, and report the reading at the igniter. [General trade knowledge]"
        pend = "I didn't get the igniter unplug reading yet; that test is still pending."
        pt = go.pending_tests([("", complaint), (req, pend), (req, "Igniter unplug reading: igniter reads 0.4 ohms, open circuit.")], "")
        self.assertFalse([p for p in pt if "igniter" in p.scope], pt)
        self.assertTrue(go.decisive_result("igniter", ["Igniter unplug reading: igniter reads 0.4 ohms, open circuit."]))

    def test_unit_level_gate_property(self):
        rng = random.Random(7)
        for i in range(self.N):
            complaint, req, pend, inscope, u, decisive = _session(rng, False)
            pt = go.pending_tests([("", complaint), (req, pend)], "")
            self.assertEqual(len(pt), 1)
            x = rng.choice(inscope)
            reply = rng.choice(VERBS).format(x=x) + "\n" + rng.choice(VERBS).format(x=u)
            out, held = go.scope_gate(reply, pt, [complaint, pend, decisive + f" The {x} reads 0.4 ohms."])
            self.assertEqual([h for h in held if u in h[0]], [], (i, reply, held))
            self.assertTrue(any(x in h[0] for h in held), (i, reply, held))


# ---- target extraction (c249638 RC04 last turn: the gate held GD's own statement of the proven breaker fix) ---------------------
RC04B_HIST = [("Customer reports leveling operates intermittently, the touchpad is occasionally unresponsive during operation, and auto-level doesn't consistently complete.", 'Safety first: chock the wheels, keep everyone clear of jacks/slides, and disconnect power before touching wiring.\nChock the wheels and keep the trailer unhitched on firm, stable ground before running the jacks. [General trade knowledge]\nPower the BAL touchscreen on and operate Auto Level exactly as the customer would; let the full cycle try to finish. [General trade knowledge]\nWatch the screen the entire time and report: whether Auto Level completes, whether the touchpad goes unresponsive, and the exact error text if shown (AUTO LEVEL FAILED, LOW VOLTAGE, HIGH VOLTAGE, EXCESS ANGLE DETECTED, MANUAL ADJUST ANGLE LIMIT, OUT OF STROKE, FEATURE DISABLED, JACK TIMEOUT, or other). [General trade knowledge]\nWhat did you observe?'), ('BAL powered up and communicated with no comm faults. System worked during diagnosis; Auto Level ran without the touchpad going unresponsive and no error text was shown. Battery voltage dropped heavily under load.', 'Map the 12V charging path from converter/charger to the house battery: converter/charger, fuses and breakers, battery isolator/disconnect, busbars, lithium BMS if present, and cable runs. List what is actually installed. [General trade knowledge]\nWith power off, reseat the BAL controller, touchscreen/panel, and jack motor connectors for this circuit; confirm each is fully seated and locked. [General trade knowledge]\nReport the map and whether any connector was loose or unseated. [General trade knowledge]'), ('Charge path: converter output is good, then isolator/disconnect, a 30A breaker between isolator and the lithium batteries, and the batteries. No connectors were loose or unseated.', 'Put the converter on shore power so it is charging, or apply a known DC load so current is flowing through the charge path. [General trade knowledge]\nSet the meter to DC volts. [General trade knowledge]\nPlace one lead on the converter output terminal and the other on the isolator/disconnect input (same conductor, across that run only). Report the voltage drop. [General trade knowledge]\nWhat drop did you read?'), ('I measured voltage drop on the charge path under load; the drop was across the 30A breaker between the isolator and the batteries (not on the converter-to-isolator run).', 'Put the converter on shore power so it is charging. [General trade knowledge]\nSet the meter to DC volts; measure battery voltage at the battery posts under charge and report the reading. [General trade knowledge]\nIf Auto Level completes, flag a battery capacity / BMS state-of-health (Ah load) test before release if that has not been done. [General trade knowledge]\nWhat did you measure and did Auto Level complete?')]
RC04B_TECH = 'Under charge the lithiums never reach full charge because of the drop across that 30A breaker. Auto Level completed during diagnosis with no screen errors. Battery amp-draw/Ah (capacity) test is still pending.'


class TestTargetExtraction(unittest.TestCase):
    def _comps(self, line):
        t = go._replace_targets(line)
        return sorted(set().union(*[go.target_components(x) for x in t])) if t else None

    def test_location_phrase_is_not_a_target(self):
        self.assertEqual(self._comps("Replace the 30A breaker in the isolator-to-battery lead."), ["breaker"])
        self.assertEqual(self._comps("Replace the 30A breaker between the isolator/disconnect and the lithium batteries."), ["breaker"])

    def test_conjunction_targets_all_count(self):
        self.assertEqual(self._comps("Replace module board 520814 and the gas valve 161109."),
                         ["board", "gas", "module", "pcb", "valve"])

    def test_phrasal_and_noun_uses(self):
        self.assertEqual(self._comps("Swap in a new module board and verify."), ["board", "module", "pcb"])
        self.assertIsNone(self._comps("Repair already isolated: the 30A breaker in the isolator-to-battery lead is the fix."))
        self.assertIsNone(self._comps("Panel 20300427 is already the isolated repair: 0 V on the tongue channel."))

    def test_rc04_c249638_last_turn_breaker_not_held_by_battery_test(self):
        pairs = go.session_tests([m for t, g in RC04B_HIST for m in ({"role": "user", "content": t},
                                  {"role": "assistant", "content": g})], RC04B_TECH)
        pt = go.pending_tests(pairs, "")
        self.assertTrue(pt and all("breaker" not in p.scope for p in pt), pt)
        reply = ("Replace the 30A breaker in the isolator-to-battery lead (and clean/repair its lugs if burned or loose). "
                 "[General trade knowledge]")
        out, held = go.scope_gate(reply, pt, [p[1] for p in pairs])
        self.assertEqual(held, [], out)


class TestPropertyLocationAndConjunction(unittest.TestCase):
    def test_unrelated_with_in_scope_location_kept_conjunction_with_in_scope_held(self):
        rng = random.Random(99)
        for i in range(400):
            complaint, req, pend, inscope, u, decisive = _session(rng, False)
            pt = go.pending_tests([("", complaint), (req, pend)], "")
            x = rng.choice(inscope)
            techs = [complaint, pend, decisive]
            loc = rng.choice(["in the {x} lead", "at the {x}", "between the {x} and the frame", "near the {x}"])
            keep = f"Replace the {u} {loc.format(x=x)}. [General trade knowledge]"
            out, held = go.scope_gate(keep, pt, techs)
            self.assertEqual(held, [], (i, keep, held))
            both = rng.choice(["Replace the {u} and the {x}.", "Replace the {x}, {u}.", "Replace the {u} plus the {x}."]).format(u=u, x=x)
            out, held = go.scope_gate(both, pt, techs)
            self.assertTrue(held, (i, both, out))


# ---- ea06f7e RC22 T6: "I don't have a separate brown-at-coil number" is a not-done report of the decisive test ------------------
RC22B_HIST = [('Customer said they ran gas and electric together, got gurgling/steam and water out the PRV. They say electric never worked after that; gas clicks but never lights, and now it only tries for a shorter time.', 'Safety first: chock the wheels, keep everyone clear of jacks/slides, and disconnect power before touching wiring.\nConfirm the tank is filled: open a hot faucet until you get a steady water stream with no sputtering air. Report if the tank is full. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nSmell around the water heater and next to the floor for LP gas. Report odor yes or no. Do not proceed if you smell gas. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nElectric element switch (lower left in the control housing) OFF, LP supply ON, DSI ON/OFF switch ON. Watch the reset light, listen/see clicks and spark at the electrode, note if the burner lights, and time how long it tries before lockout. Report what you see and the times. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nDSI switch OFF. Electric element switch ON. Wait 5–10 minutes, then check tank warmth or hot-faucet temperature and watch the PRV for weeping/steam. Report if electric heats and any PRV discharge. [Library: Suburban Water Heater Master Service and Training Manual p.18]\nReport those four results.'), ('Tank looks full/OK, no LP odor around the heater or floor. Gas tries (clicks) but never lights and lockout is shorter than it used to be. Electric does heat (element ~90 VAC); PRV issue was found with discharge.', 'With DSI switch OFF and 12 V coach power on, unplug then fully reseat the module-board connector, the ON/OFF switch/lamp harness, and the gas-valve brown-wire connector until they click/lock. Report if any pin was loose, burned, or not fully seated. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nDSI switch ON, electric element switch OFF. Meter DC volts, 20 V range. Probe ON/OFF switch input (coach 12 V feed) to chassis ground. Report voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nSame meter. Probe ON/OFF switch output (to thermostat/ECO) to chassis ground with switch ON. Report voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf switch output is below 10.5 VDC, stop and report that reading. If 10.5–13.5 VDC, continue. Report those three results.'), ('Connectors reseated fine — no loose, burned, or unseated pins. Idle at the switch is ~14.2 V to chassis ground (input and output both look like that). During a try it still collapses into the 5–10 V range.', 'DSI switch OFF. Press the ECO reset button on the 12 VDC thermostat/hi-limit (under the t-stat cover on the tank). Report if it clicked or was already set. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nDSI switch ON, electric element OFF. Meter DC volts 20 V. Probe the thermostat/ECO output (wire toward the module, red) to chassis ground at idle, then during a try. Report both voltages. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nSame meter. Probe the red wire at the module-board connector to chassis ground at idle and during a try. Report both voltages. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nConfirm module and switch grounds are tight to chassis. Report if any ground was loose. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nReport those four results. If red at the board stays below 10.5 VDC during a try, stop and report that.'), ('ECO reset looks already set/OK. Idle is still ~14.2 V on the red/feed (same at switch and board); during a try it collapses to ~5–10 V (I saw ~10.1, 8.3, ~5.5–9.5). Module and switch grounds are tight; jumpering ground didn’t change it.', 'DSI switch ON, electric element OFF. Meter DC volts, 20 V range. Probe the brown wire at the gas valve to chassis ground during a try (TFI). Report the voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nDSI switch OFF. Unplug the brown wire from the gas valve. Switch ON and try again. Probe red at the module to chassis ground during that try. Report if it still collapses into 5–10 V. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nDSI switch OFF, brown unplugged. Meter ohms. Measure resistance through the gas-valve solenoids (across the valve coil terminals). Report ohms (spec 30–50). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf you have a manometer, LP on, heater off: supply pressure at the valve inlet. Report inches WC (spec 11–14). [Library: Suburban Water Heater Master Service and Training Manual p.10]\nReport those readings. If brown stays below 10.5 VDC during TFI with the valve connected, stop and report that.'), ('Gas-valve coil is ~32 Ohm. Yellow at the board (valve drive) is 0 V idle and ~-1.2 V during a try; spark unplugged didn’t stop the collapse on the 12 V side. LP supply pressure isn’t in the notes — looks normal/OK.', 'DSI switch ON, electric element OFF, brown wire connected at the valve. Meter DC volts, 20 V. Probe the brown wire at the gas-valve coil to chassis ground during a try (TFI). Report that voltage. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nDSI switch OFF. Unplug the module-board connector completely (all pins). Switch ON. Meter DC volts, 20 V. Probe the red/feed in the harness (switch/t-stat side) to chassis ground for 20–30 seconds. Report if it stays ~14 V or still drops into 5–10 V. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nInspect the electrode gap (1/8"), porcelain for cracks, carbon on the tip, and the spark-wire connections. Report what you find. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nReport those three results.')]
RC22B_TECH = 'Yellow at the board (valve drive) is ~-1.2 V during a try; I don’t have a separate brown-at-coil number. Unplugging the module and watching harness red isn’t in the notes — looks normal/OK. Electrode/spark hardware looks normal/OK.'
RC22B_REPLY = 'Replace the DSI module board (valve drive is ~-1.2 V during TFI, not 10.5–13.5 VDC; 12 V feed collapses only under module load; coil ~32 Ω, electrode/spark, connectors, ECO, and grounds already OK). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf brown/yellow harness to the valve is burned, open, or shorted to ground, repair or replace that wire first, then the board. [Library: Suburban Water Heater Master Service and Training Manual p.17]\nIf coach 12 V at the switch still drops below 10.5 VDC with the new board unplugged, correct the vehicle supply (min 10.5 VDC under load). [Library: Suburban Water Heater Master Service and Training Manual p.17]\nVERIFY: tank full, LP on, electric element OFF, DSI ON — burner must light and stay on, lockout time back to normal, no 5–10 V collapse on red, PRV not dumping from overheat. Report result. [Library: Suburban Water Heater Master Service and Training Manual p.14]\nIf it still will not light after the board, document and call Suburban factory service 423-775-2131 ext. 7102 for authorization. [Library: Suburban Water Heater Master Service and Training Manual p.3]'


class TestMissingMeasurementIsPending(unittest.TestCase):
    def test_not_done_shapes(self):
        for s in ["I don't have a separate brown-at-coil number.", "I do not have the brown reading at the valve.",
                  "Didn't have a voltage at the board during the try."]:
            self.assertTrue(go.NOT_DONE_RE.search(s) and go.PENDING_TEST_WORD_RE.search(s), s)
        for s in ["I don't have the part number handy.", "I don't have the model number.", "I have the reading: 12.4 V."]:
            self.assertFalse(go.NOT_DONE_RE.search(s) and go.PENDING_TEST_WORD_RE.search(s), s)

    def test_rc22_ea06f7e_t6_module_board_blocked(self):
        out, pin = _turn("rc22", RC22B_HIST, RC22B_TECH, RC22B_REPLY)
        self.assertEqual(replace_lines(out), [], out)
        self.assertIn("isolation test is still pending", out)
        self.assertNotIn("Replace the DSI module board", out)


if __name__ == "__main__":
    unittest.main()
