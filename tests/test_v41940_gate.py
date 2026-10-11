"""v4.19.40 live gate misses that stay on the draft.

S03 and S13 keep the library sentence that the sheet had dropped. S15 does not
ship a prompt line about library excerpts. S20 does not repeat one reply.
S09 does not glue an imperative onto the previous clause. S10 names
zero-point calibration as the repair, and its NO label clears the nodes.
"""
import unittest

from bay_procedure import (
    compile_bay_procedure,
    layout_problems,
    render_bay_procedure_pdf,
)
from gd_library_coach import (
    avoid_duplicate_reply,
    dometic_bypass_facts,
    ensure_cooktop_tip_pan_check,
    ensure_dometic_ceiling_thermostat,
    ensure_ground_control_level_path,
    ensure_level_up_lead_jack_reply,
    polish_shop_reply,
    repair_glued_sentence,
)

BAL_CHUNKS = [
    {
        "title": "BAL SS 5.1 Troubleshooting",
        "page": 1,
        "excerpt": (
            "Remove the 4 screws from the cover to ensure a good connection. "
            "If the tongue jack will not run, check the coupler and the 30A fuse."
        ),
    }
]
GIRARD_CHUNKS = [
    {
        "title": "Girard Tankless Water Heater GSWH-2 Troubleshooting and Service Manual CCD-0009390",
        "page": 23,
        "excerpt": (
            "E8 Air Pressure Switch. The sensing tube is at the blower. "
            "Check for integrity and connections of the pressure switch hose."
        ),
    }
]
S20 = (
    "After replacing the front-left jack, the front jacks drift and move on their own "
    "when other circuits pressurize, including when the slides run."
)


def _rect_gap(a, b) -> float:
    ix = min(a.x1, b.x1) - max(a.x0, b.x0)
    iy = min(a.y1, b.y1) - max(a.y0, b.y0)
    if ix > 0 and iy > 0:
        return -min(ix, iy)
    if ix > 0:
        return max(a.y0, b.y0) - min(a.y1, b.y1)
    if iy > 0:
        return max(a.x0, b.x0) - min(a.x1, b.x1)
    return 99.0


class TestGateQuotes(unittest.TestCase):
    def test_s03_keeps_the_bal_troubleshooting_quote(self):
        proc = compile_bay_procedure(
            "BAL Soft-Touch SS 5.1 electric tongue jack dead. Other stabilizers and panel lights work.",
            "BAL",
            "Soft-Touch SS 5.1",
            "Leveling",
            chunks=BAL_CHUNKS,
        )
        hay = " ".join(
            f"{src.get('title') or ''} {src.get('excerpt') or ''}" for src in proc.sources
        )
        self.assertIn("BAL SS 5.1 Troubleshooting", hay)
        self.assertIn("Remove the 4 screws", hay)
        self.assertIn("ensure a good connection", hay.lower())

    def test_s13_keeps_the_pressure_switch_hose_quote(self):
        proc = compile_bay_procedure(
            "Girard GSWH-2 gives E8 error code.",
            "Girard",
            "GSWH-2",
            "Water Heaters",
            chunks=GIRARD_CHUNKS,
        )
        hay = " ".join(src.get("excerpt") or "" for src in proc.sources).lower()
        self.assertIn("pressure switch hose", hay)
        self.assertIn("integrity", hay)


class TestGateReplies(unittest.TestCase):
    def test_s15_drops_the_excerpt_guard(self):
        leak = (
            "The shop Document Library excerpts for this cooktop do not include the thermocouple tip. "
            "With a pan on the burner, check the thermocouple tip position in the flame."
        )
        complaint = "When using stove, it will shut off as soon as a pan is put on it — either burner."
        ensured = ensure_cooktop_tip_pan_check(leak, complaint, [])
        polished = polish_shop_reply(ensured, [], complaint, "Range & Cooktops", "Suburban SDN2U")
        for reply in (ensured, polished):
            low = reply.lower()
            self.assertNotIn("do not include", low)
            self.assertNotIn("document library excerpts", low)
            self.assertIn("thermocouple", low)

    def test_s09_does_not_glue_check_onto_the_rooftop_unit(self):
        draft = (
            "Do the Peacemaker bypass at the rooftop unit Check the ceiling selector "
            "and report whether it cools."
        )
        self.assertNotIn("unit Check", repair_glued_sentence(draft))
        history = [
            {"role": "user", "content": "AC turns on but will not blow cold."},
            {
                "role": "assistant",
                "content": (
                    "Confirm the fan runs, then do the Peacemaker bypass at the rooftop unit "
                    "and report whether it cools."
                ),
            },
        ]
        latest = "Peacemaker bypass at the rooftop unit cools."
        ensured = ensure_dometic_ceiling_thermostat(
            draft, dometic_bypass_facts(history, latest), history
        )
        reply = avoid_duplicate_reply(
            ensured, history, latest, "Air Conditioning", "B57915E711J0EMX"
        )
        self.assertNotIn("unit Check", reply)
        self.assertIn("ceiling", reply.lower())

    def test_s10_states_zero_point_calibration_is_the_repair(self):
        history = []
        turns = [
            "Auto-level lifts driver-side tires though nearly level.",
            "Not checked yet — what do you recommend next?",
            "What is the repair?",
        ]
        replies = []
        for latest in turns:
            guarded = ensure_ground_control_level_path("Check the harness.", history)
            reply = avoid_duplicate_reply(
                guarded, history, latest, "Leveling", "Lippert Ground Control 343633"
            )
            replies.append(reply)
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
        self.assertIn("zero-point calibration is the repair", replies[-1].lower())

    def test_s20_replies_do_not_repeat(self):
        history = []
        turns = [
            S20,
            "The lead-jack valve coil on the gray wire tests good.",
            "What is the repair?",
            "What is the repair?",
            "Yes",
        ]
        replies = []
        for latest in turns:
            reply = ensure_level_up_lead_jack_reply(
                "", history, latest, "Leveling", "Lippert Level Up"
            )
            replies.append(reply.strip())
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
        self.assertEqual(len(replies), 5)
        for earlier, later in zip(replies, replies[1:]):
            self.assertNotEqual(earlier.lower(), later.lower())
        self.assertNotEqual(replies[2].lower(), replies[3].lower())
        self.assertNotEqual(replies[3].lower(), replies[4].lower())


class TestGroundControlNoLabel(unittest.TestCase):
    def test_s10_no_label_clears_every_node(self):
        proc = compile_bay_procedure(
            "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
            "tires off the ground even though the coach was nearly level.",
            "Lippert",
            "Ground Control 343633",
            "Leveling",
        )
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        labels = [mark for mark in trace if mark.role == "label" and mark.text == "NO"]
        nodes = [mark for mark in trace if mark.role == "node" and mark.kind != "text"]
        self.assertTrue(labels)
        self.assertTrue(nodes)
        for label in labels:
            for node in nodes:
                if label.page != node.page:
                    continue
                self.assertGreaterEqual(_rect_gap(label, node), 4.0, node.id)
