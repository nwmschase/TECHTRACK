"""Leader v4.19.34 GD misses, replayed on the figure rebuild.

Each case walks the same post-model guards the Send path uses.
"""
import unittest

from gd_library_coach import (
    DIAL_OFF_RUN_SHOP_LINE,
    avoid_duplicate_reply,
    ensure_bal_tongue_only_path,
    ensure_coleman_motor_board_auth,
    ensure_facr_freeze_assembly_rr,
    ensure_fcr_dial_off_compressor_run_path,
    ensure_fridge_ice_moisture_path,
    ensure_ground_control_level_path,
    facr_proves_from_chat,
    facts_from_chat,
)

POISON = (
    "If the sail switch has power in and power out while the blower runs, replace the wall thermostat.\n"
    "Take the next check on this job and write the reading down. "
    "If that check fails, replace the part that check names.\n"
    "If the pin or coupler or seized, replace the complete front stabilizer jack assembly.\n"
    "1. 2. Turn touch pad off. 3. 4. Press ENTER.\n"
    "If those pressures are in range and the interior leak , replace the rooftop assembly."
)
VACUUM = (
    "Check whether the vacuum breaker leaks while flushing. "
    "If it leaks, replace the vacuum breaker.\n"
    "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2"
)
DIAL_DOUBLED = (
    f"{DIAL_OFF_RUN_SHOP_LINE}\n\n"
    "Confirm the dial is fully OFF, past the detent. "
    "Disconnect flag terminals C (blue) and T (black) and leave them open, with no jumper. "
    "Report whether the compressor stops."
)


def _guard(kind, draft, history, latest):
    if kind == "facr":
        return ensure_facr_freeze_assembly_rr(draft, facr_proves_from_chat(history, latest))
    if kind == "coleman":
        return ensure_coleman_motor_board_auth(draft, facts_from_chat(history, latest))
    if kind == "bal":
        return ensure_bal_tongue_only_path(draft, facts_from_chat(history, latest))
    if kind == "dial":
        return ensure_fcr_dial_off_compressor_run_path(draft, facts_from_chat(history, latest))
    if kind == "ice":
        return ensure_fridge_ice_moisture_path(draft)
    if kind == "ground":
        return ensure_ground_control_level_path(draft, history)
    return draft


def _walk(turns, category, model, kind="", draft=POISON):
    history = []
    replies = []
    for latest in turns:
        guarded = _guard(kind, draft, history, latest)
        reply = avoid_duplicate_reply(guarded, history, latest, category, model)
        replies.append((reply or "").strip())
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": reply})
    return replies


class TestLeaderReplay(unittest.TestCase):
    def test_s01_does_not_leak_internal_text_or_condemn_early(self):
        replies = _walk(
            [
                "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside while running, not raining.",
                "Drain is clear, pan is clean and draining, base-pan slope is fine.",
                "Filter is clean.",
                "Evaporator fan spins freely with good airflow.",
                "Freeze sensor reads 2 kΩ at 25°C.",
                "What is the repair?",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
            kind="facr",
        )
        for reply in replies:
            low = reply.lower()
            self.assertTrue(reply)
            self.assertIn("📖", reply)
            self.assertNotIn("replace the rooftop assembly", low)
            self.assertNotIn("authorize rooftop assembly", low)
            self.assertNotIn("next check on the", low)
            self.assertNotIn("stay on the facr", low)
            self.assertNotIn("do not leave this prove", low)
            self.assertNotIn("interior leak remains", low)
            self.assertNotIn("report the prove that is still open", low)
            self.assertNotIn("sail switch", low)

    def test_s02_does_not_repeat_the_peacemaker_ask(self):
        replies = _walk(
            [
                "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead.",
                "122 VAC at the control box. Fan High is dead.",
                "Peacemaker bypass: compressor runs, fan does not rotate. About 1.91 A, shaft locked.",
                "What is the repair?",
            ],
            "Air Conditioning",
            "Coleman-Mach 2111-0001",
            kind="coleman",
        )
        self.assertIn("peacemaker", replies[0].lower())
        self.assertNotIn(replies[0].split(".")[0].lower(), replies[1].lower())
        for left, right in zip(replies, replies[1:]):
            self.assertNotEqual(left.strip().lower(), right.strip().lower())
        self.assertNotIn("sail switch", replies[-1].lower())

    def test_s05_does_not_repeat_the_overnight_line(self):
        replies = _walk(
            [
                "Furrion FCR10 fridge; icing up on the rear wall about halfway from the top.",
                "Door gasket is sealing properly.",
                "What is the repair?",
            ],
            "Refrigerators",
            "FCR10DCGTA-BL",
            kind="ice",
        )
        self.assertNotEqual(replies[1].strip().lower(), replies[2].strip().lower())
        self.assertNotIn(replies[1].split(".")[0].lower(), replies[2].lower())
        self.assertIn("overnight", replies[1].lower())
        self.assertIn("overnight", replies[2].lower())
        self.assertNotIn("sail switch", replies[-1].lower())

    def test_s03_asks_for_12v_before_the_part(self):
        replies = _walk(
            [
                "BAL Soft-Touch SS 5.1 electric tongue jack dead only; other stabilizers and panel lights work.",
                "I measured 0 V at the soft-touch panel tongue channel while commanding extend.",
                "What is the repair?",
            ],
            "Electrical",
            "BAL Soft-Touch SS 5.1",
            kind="bal",
        )
        first = replies[0].lower()
        self.assertIn("12v", first)
        self.assertIn("tongue", first)
        self.assertNotIn("20300427", replies[0])
        self.assertIn("20300427", replies[1])
        self.assertIn("20300427", replies[2])

    def test_s04_prompt_is_not_pasted_twice(self):
        replies = _walk(
            [
                "Temperature dial is OFF and the compressor is still running. Freezer is frozen solid.",
                "Not checked yet — what do you recommend next?",
            ],
            "Refrigerators",
            "FCR10DCGTA-BL",
            kind="dial",
            draft=DIAL_DOUBLED,
        )
        first = replies[0].lower()
        self.assertEqual(first.count("disconnect flag terminals"), 1)
        self.assertEqual(first.count("leave them open"), 1)
        self.assertNotEqual(replies[0].strip().lower(), replies[1].strip().lower())

    def test_s10_reaches_the_manual_level_step(self):
        replies = _walk(
            [
                "Auto-level lifts driver-side tires though nearly level.",
                "Not checked yet — what do you recommend next?",
                "What is the repair?",
            ],
            "Leveling",
            "Lippert Ground Control 343633",
            kind="ground",
        )
        self.assertIn("plugs", replies[0].lower())
        self.assertNotIn("manual level", replies[0].lower())
        self.assertIn("manual level", replies[1].lower())
        self.assertIn("front", replies[1].lower())
        self.assertIn("rear", replies[1].lower())
        self.assertIn("enter", replies[1].lower())

    def test_s20_uses_the_loose_cartridge_fact(self):
        replies = _walk(
            [
                "After replacing the front-left jack, the front jacks drift and move on their own.",
                "The cartridge is loose.",
                "What is the repair?",
            ],
            "Leveling",
            "Lippert Level Up",
            kind="leadjack",
        )
        self.assertIn("gray wire", replies[0].lower())
        self.assertNotIn("177094", replies[0])
        for reply in replies[1:]:
            low = reply.lower()
            self.assertIn("177094", reply)
            self.assertIn("cartridge", low)
            self.assertNotEqual(reply.strip().lower(), replies[0].strip().lower())
            self.assertNotIn("gray wire", low)
            self.assertNotIn("swap plumbing", low)
            self.assertTrue(
                "towable owner's manual" in low or "fw owner's manual" in low,
                reply,
            )

    def test_thetford_starts_at_supply_then_reaches_the_water_valve(self):
        replies = _walk(
            [
                "toilet leaks under the flush lever when flushing",
                "Not checked yet",
                "Not checked yet",
                "Not checked yet",
            ],
            "Plumbing / Toilets",
            "Style II 42070",
            kind="thetford",
            draft=VACUUM,
        )
        self.assertIn("supply", replies[0].lower())
        self.assertNotIn("vacuum breaker", replies[0].lower())
        self.assertIn("vacuum breaker", replies[1].lower())
        self.assertNotIn("42049", replies[1])
        self.assertNotIn("weep", replies[1].lower())
        self.assertIn("42049", replies[2])
        self.assertIn("42109", replies[2])
        self.assertIn("weep", replies[2].lower())
        self.assertNotIn("vacuum breaker", replies[2].lower())
        self.assertIn("flange", replies[3].lower())
        self.assertIn("7/16", replies[3])
        joined = "\n".join(replies).lower()
        self.assertLess(joined.find("supply"), joined.find("vacuum breaker"))
        self.assertLess(joined.find("vacuum breaker"), joined.find("42049"))
        self.assertLess(joined.find("42049"), joined.find("flange"))


if __name__ == "__main__":
    unittest.main()
