"""v4.19.31 live misses: FACR chart geometry, and the S01-S15 closes.

The 15-case replay stays the proving walk. This file adds the pressure close,
the overnight ice repair, confirmed Girard seating, the cooktop firm line,
the Coleman stop-line strip, and the ask-turn budget.
"""
import unittest
from pathlib import Path

import gd_llm
from bay_procedure import (
    MARGIN,
    _CONTENT_W,
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    layout_flowchart,
    layout_problems,
    render_bay_procedure_pdf,
)
from gd_library_coach import (
    COACH_CONTEXT_CHAR_CAP,
    COACH_EXCERPT_CHAR_CAP,
    COACH_HISTORY_ASSISTANT_CAP,
    COACH_HISTORY_MAX_MESSAGES,
    COOKTOP_TIP_LOW_REPAIR,
    COOKTOP_TIP_PAN_SHOP_LINE,
    DEFAULT_LIBRARY_CATEGORIES,
    WATER_HEATERS_CATEGORY,
    ensure_cooktop_tip_pan_check,
)

FRAME = (MARGIN, 48.0, _CONTENT_W, 640.0)
POISON = "Read the refrigerant pressures again. Connect gauges."


def _segments(pts):
    return list(zip(pts, pts[1:]))


def _overlap(a0, a1, b0, b1):
    lo1, hi1 = min(a0, a1), max(a0, a1)
    lo2, hi2 = min(b0, b1), max(b0, b1)
    return min(hi1, hi2) - max(lo1, lo2) > 1.0


def _shares_segment(pts_a, pts_b):
    for (ax, ay), (bx, by) in _segments(pts_a):
        for (cx, cy), (dx, dy) in _segments(pts_b):
            if (
                abs(ay - by) < 0.8
                and abs(cy - dy) < 0.8
                and abs(((ay + by) / 2.0) - ((cy + dy) / 2.0)) < 1.5
                and _overlap(ax, bx, cx, dx)
            ):
                return True
            if (
                abs(ax - bx) < 0.8
                and abs(cx - dx) < 0.8
                and abs(((ax + bx) / 2.0) - ((cx + dx) / 2.0)) < 1.5
                and _overlap(ay, by, cy, dy)
            ):
                return True
    return False


def _load_send_path():
    src = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
    cut = src.split("# ---------------- LOGIN ----------------", 1)[0]
    ns = {
        "__name__": "rv_techtrack_v41931",
        "__file__": str(Path(__file__).resolve().parents[1] / "rv_techtrack.py"),
    }
    exec(compile(cut, "rv_techtrack.py", "exec"), ns)
    ns["ai_available"] = lambda: True
    holder = {"text": POISON}
    ns["ai_chat"] = lambda *args, **kwargs: holder["text"]
    ns["_draft"] = holder
    return ns


class TestFacrRetestArrow(unittest.TestCase):
    def test_retest_no_leaves_the_diamond_on_its_own_line(self):
        proc = compile_bay_procedure(
            concern="FACR08 freeze up interior leak condensate",
            brand="Furrion",
            model="FACR08HESA2-PS",
            category="Air Conditioning",
        )
        dest = {(e.from_id, e.label.upper()): e.to_id for e in proc.flowchart.edges}
        self.assertEqual(dest[("d_retest", "NO")], "e_ok")
        self.assertEqual(dest[("p_clear", "")], "d_retest")
        self.assertEqual(dest[("d_drain", "NO")], "d_retest")
        fx, fy, fw, fh = FRAME
        rects = flowchart_node_rects(proc.flowchart, fx, fy, fw, fh)
        self.assertEqual(flowchart_boxes_overlap(rects), [])
        shapes, texts = layout_flowchart(proc.flowchart, fx, fy, fw, fh)
        arrows = [shape for shape in shapes if shape.kind == "arrow"]
        routes = {
            (edge.from_id, edge.label): arrow.points
            for edge, arrow in zip(proc.flowchart.edges, arrows)
        }
        no = routes[("d_retest", "NO")]
        clear = routes[("p_clear", "")]
        self.assertGreater(no[-1][0], no[-2][0])
        end_box = rects["e_ok"]
        diamond = rects["d_retest"]
        end_x = (end_box[0] + end_box[2]) / 2.0
        diamond_x = (diamond[0] + diamond[2]) / 2.0
        self.assertLess(abs(no[-1][0] - end_x), abs(no[-1][0] - diamond_x))
        self.assertFalse(_shares_segment(no, clear))
        self.assertFalse(_shares_segment(no, routes[("d_drain", "NO")]))
        top = ((diamond[0] + diamond[2]) / 2.0, max(diamond[1], diamond[3]))
        drain_start = routes[("d_drain", "NO")][0]
        labels = [text for text in texts if text.role == "label" and text.text == "NO"]
        self.assertTrue(labels)
        drain_label = min(
            labels,
            key=lambda text: (text.x - drain_start[0]) ** 2 + (text.y - drain_start[1]) ** 2,
        )
        gap = ((drain_label.x - top[0]) ** 2 + (drain_label.y - top[1]) ** 2) ** 0.5
        self.assertGreater(gap, 16.0)
        self.assertGreater(drain_label.y, top[1])
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])


class TestLiveCloses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = _load_send_path()

    def _send(self, turns, category, model, draft=POISON):
        self.ns["_draft"]["text"] = draft
        reply_fn = self.ns["guided_diagnostics_reply"]
        history = []
        replies = []
        for latest in turns:
            reply, flow = reply_fn(latest, category, model, history, unity_gate="Not sure")
            self.assertIsNone(flow)
            text = (reply or "").strip()
            self.assertTrue(text)
            replies.append(text)
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": text})
        return replies

    def test_water_heaters_category_is_present_once(self):
        self.assertEqual(WATER_HEATERS_CATEGORY, "Water Heaters")
        self.assertEqual(DEFAULT_LIBRARY_CATEGORIES.count("Water Heaters"), 1)

    def test_s01_pressures_authorize_rooftop_rr_and_do_not_ask_again(self):
        turns = [
            "Furrion FACR08HESA2-PS rooftop AC. Water leaking from the forward AC inside while running, not raining. Frost on the evaporator.",
            "Drain is clear, pan is clean and draining, base-pan slope is fine.",
            "Filter is clean. Evaporator fan spins freely with good airflow.",
            "Suction line is not iced.",
            "Freeze sensor reads 2 kΩ at 25°C.",
            "Cool setpoint is 68°F.",
            "Open nozzles. 72°F ambient.",
            "68/235 psi. Frost and the interior leak are still there.",
            "What is the repair?",
        ]
        replies = self._send(turns, "Air Conditioning", "FACR08HESA2-PS")
        for reply in replies[-2:]:
            low = reply.lower()
            self.assertIn("ccd-0007990", low)
            self.assertIn("authorize rooftop assembly", low)
            self.assertIn("replace the rooftop assembly", low)
            self.assertNotIn("read the refrigerant pressures", low)
            self.assertNotIn("connect gauges", low)
            self.assertNotIn("cooling unit", low)
            self.assertNotIn("thermocouple", low)
            self.assertNotIn("seating is the repair", low)
            self.assertNotIn("stay on the facr", low)
            self.assertNotIn("do not leave this prove", low)

    def test_s01_pressures_authorize_without_asking_the_setpoint(self):
        replies = self._send(
            [
                "Furrion FACR08HESA2-PS rooftop AC. Water leaking from the forward AC inside while running, not raining. Frost on the evaporator.",
                "Drain is clear, pan is clean and draining, base-pan slope is fine.",
                "Filter is clean. Evaporator fan spins freely with good airflow.",
                "Suction line is not iced.",
                "Freeze sensor reads 2 kΩ at 25°C.",
                "Open nozzles. 72°F ambient.",
                "68/235 psi. Frost and the interior leak are still there.",
                "What is the repair?",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
            draft=(
                "Stay on the FACR condensate and freeze prove. "
                "Do not leave this prove for a no-start tree or a high-voltage bus measurement. "
                "Next check: What is the cool setpoint on the thermostat?"
            ),
        )
        for reply in replies[-2:]:
            low = reply.lower()
            self.assertIn("ccd-0007990", low)
            self.assertIn("authorize rooftop assembly", low)
            self.assertIn("replace the rooftop assembly", low)
            self.assertNotIn("stay on the facr", low)
            self.assertNotIn("do not leave this prove", low)
            self.assertNotIn("cool setpoint", low)
            self.assertNotIn("supply a procedure excerpt", low)

    def test_s01_without_pressures_does_not_authorize(self):
        replies = self._send(
            [
                "Furrion FACR08HESA2-PS rooftop AC. Water leaking from the forward AC inside while running.",
                "Drain is clear.",
                "What is the repair?",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        low = replies[-1].lower()
        self.assertNotIn("authorize rooftop assembly", low)
        self.assertTrue(low.startswith("if ") or "pressure" in low)
        self.assertIn("pressure", low)

    def test_pressures_alone_do_not_authorize_or_ask_again(self):
        replies = self._send(
            [
                "Furrion FACR08HESA2-PS rooftop AC. Water leaking inside while running.",
                "68/235 psi.",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
            draft="Read the refrigerant pressures.",
        )
        low = replies[-1].lower()
        self.assertNotIn("authorize rooftop assembly", low)
        self.assertNotIn("read the refrigerant pressures", low)
        self.assertNotIn("stay on the facr", low)
        self.assertNotIn("do not leave this prove", low)

    def test_s05_overnight_dry_and_frost_back_is_the_cooling_unit(self):
        early = self._send(
            [
                "Furrion FCR10 fridge; icing up on the rear wall about halfway from the top.",
                "Door gasket is sealing properly.",
                "What is the repair?",
            ],
            "Refrigerators",
            "FCR10DCGTA-BL",
        )
        self.assertNotEqual(early[-1].split("\n")[0].strip(), "Replace the cooling unit.")
        self.assertRegex(early[-1].lower(), r"\b(?:if|gasket|overnight|dial)\b")
        closed = self._send(
            [
                "Furrion FCR10 fridge; icing up on the rear wall about halfway from the top.",
                "Door gasket is sealing properly.",
                "Dried the cabinet with a towel and waited overnight. Heavy frost came back.",
            ],
            "Refrigerators",
            "FCR10DCGTA-BL",
            draft="If heavy frost returns after the overnight wait, replace the cooling unit.",
        )
        low = closed[-1].lower()
        self.assertIn("replace the cooling unit", low)
        self.assertFalse(low.startswith("if "))
        self.assertNotIn("authorize rooftop", low)
        self.assertNotIn("thermocouple", low)

    def test_s05_dried_and_waited_is_the_firm_cooling_unit(self):
        replies = self._send(
            [
                "Furrion FCR10 fridge; icing up on the rear wall about halfway from the top.",
                "Door gasket is sealing properly.",
                "Dried the cabinet and waited. Heavy frost came back.",
            ],
            "Refrigerators",
            "FCR10DCGTA-BL",
            draft="If heavy frost returns after the overnight wait, replace the cooling unit.",
        )
        low = replies[-1].lower()
        self.assertTrue(low.startswith("replace the cooling unit"))
        self.assertNotIn("only if", low)
        self.assertFalse(low.startswith("if "))
        self.assertNotIn("authorize rooftop", low)

    def test_s13_seating_is_the_repair_once_under_water_heaters(self):
        replies = self._send(
            [
                "Girard GSWH-2 gives E8 error code.",
                "Tubing is clear.",
                "I seated the sensing tube at the blower. Seating confirmed.",
                "What is the repair?",
            ],
            "Water Heaters",
            "Girard GSWH-2",
            draft="Confirm suction at the tube and report the result.",
        )
        self.assertIn("suction", replies[1].lower())
        self.assertNotIn("that seating is the repair", replies[1].lower())
        for reply in replies[2:]:
            low = reply.lower()
            self.assertIn("that seating is the repair", low)
            self.assertNotIn("?", reply)
            self.assertNotIn("confirm suction", low)
            self.assertNotIn("report the result", low)
            self.assertIn("ccd-0009390", low)
            self.assertNotIn("cooling unit", low)
            self.assertNotIn("rooftop assembly", low)

    def test_s15_runon_is_the_prove_and_the_repair_is_firm(self):
        garbled = "The flame lifts off the tip under load Adjust the tip height."
        first = ensure_cooktop_tip_pan_check(
            garbled,
            "When using stove, it will shut off as soon as a pan is put on it.",
        )
        self.assertNotRegex(first, r"under load\s+[A-Z]")
        self.assertIn(COOKTOP_TIP_PAN_SHOP_LINE.split("\n")[0], first)
        replies = self._send(
            [
                "When using stove, it will shut off as soon as a pan is put on it — either burner.",
                "What is the repair?",
            ],
            "Range & Cooktops",
            "Suburban SDN2U",
            draft=garbled,
        )
        self.assertNotRegex(replies[0], r"under load\s+[A-Z]")
        self.assertNotIn("under load adjust", replies[0].lower())
        self.assertIn("check the thermocouple tip", replies[0].lower())
        low = replies[1].lower()
        self.assertIn("reposition the thermocouple tip in the flame", low)
        self.assertIn("page 4", low)
        self.assertFalse(low.startswith("if "))
        self.assertIn(COOKTOP_TIP_LOW_REPAIR.split("\n")[0], replies[1])
        self.assertNotIn("seating is the repair", low)
        self.assertNotIn("cooling unit", low)

    def test_s02_authorization_drops_the_stop_line(self):
        replies = self._send(
            [
                "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead.",
                "122 VAC at the control box. Fan High is dead. Tester dark. 0 VAC on the 9-pin.",
                "Peacemaker bypass: compressor runs, fan does not rotate. About 1.91 A, shaft locked.",
                "Fan run capacitor 15 µF, rated 15 µF.",
            ],
            "Air Conditioning",
            "Coleman-Mach 2111-0001",
            draft="Stop. No further tests. Check continuity of the windings.",
        )
        low = replies[-1].lower()
        self.assertIn("authorization", low)
        self.assertIn("fan motor", low)
        self.assertIn("control board", low)
        self.assertNotIn("stop. no further tests", low)
        self.assertNotIn("no further tests", low)
        self.assertNotIn("rooftop assembly r&r", low)

    def test_a_closed_case_does_not_lend_its_repair(self):
        ice = self._send(
            [
                "Furrion FCR10 fridge; icing up on the rear wall about halfway from the top.",
                "Dried the cabinet with a towel and waited overnight. Heavy frost came back.",
            ],
            "Refrigerators",
            "FCR10DCGTA-BL",
        )
        self.assertIn("replace the cooling unit", ice[-1].lower())
        facr = self._send(
            [
                "Furrion FACR08HESA2-PS rooftop AC. Water leaking from the forward AC inside.",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        self.assertNotIn("cooling unit", facr[-1].lower())
        self.assertNotIn("that seating is the repair", facr[-1].lower())


class TestAskTurnBudget(unittest.TestCase):
    def test_context_caps_and_low_reasoning_are_ask_path_only(self):
        self.assertLessEqual(COACH_HISTORY_MAX_MESSAGES, 6)
        self.assertLessEqual(COACH_HISTORY_ASSISTANT_CAP, 480)
        self.assertLessEqual(COACH_EXCERPT_CHAR_CAP, 700)
        self.assertLessEqual(COACH_CONTEXT_CHAR_CAP, 4200)
        self.assertLessEqual(gd_llm.GD_ASK_MAX_TOKENS, 420)
        self.assertEqual(gd_llm.GD_ASK_REASONING_EFFORT, "low")
        src = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
        ask = src.split("def ask_techtrack_reply", 1)[1].split("def ask_chat_to_warranty_story", 1)[0]
        self.assertIn("GD_ASK_MAX_TOKENS", ask)
        self.assertIn("GD_ASK_REASONING_EFFORT", ask)
        self.assertIn("limit=5", ask)
        plate = src.split("def read_data_plate_from_image", 1)[1].split("def ", 1)[0]
        self.assertNotIn("reasoning_effort", plate)

    def test_low_reasoning_is_sent_to_xai_and_not_groq(self):
        record = []

        def factory(provider, *, api_key, base_url):
            class Completions:
                def create(self, **kwargs):
                    record.append({"provider": provider, "kwargs": kwargs})
                    message = type("M", (), {"content": "next check"})()
                    choice = type("C", (), {"message": message})()
                    return type("R", (), {"choices": [choice]})()

            class Chat:
                completions = Completions()

            class Client:
                chat = Chat()

            return Client()

        messages = [{"role": "user", "content": "Fan voltage cycles on E2."}]
        text = gd_llm.complete_chat(
            messages,
            max_tokens=420,
            secret_fn=lambda name: {"XAI_API_KEY": "xai-test", "GROQ_API_KEY": "groq-test"}.get(name, ""),
            client_factory=factory,
            reasoning_effort="low",
        )
        self.assertEqual(text, "next check")
        self.assertEqual(record[0]["provider"], "xai")
        self.assertEqual(record[0]["kwargs"]["extra_body"], {"reasoning_effort": "low"})
        self.assertEqual(record[0]["kwargs"]["max_tokens"], 420)
        groq = gd_llm.complete_chat(
            messages,
            secret_fn=lambda name: {"GROQ_API_KEY": "groq-test"}.get(name, ""),
            client_factory=factory,
            reasoning_effort="low",
        )
        self.assertEqual(groq, "next check")
        self.assertEqual(record[-1]["provider"], "groq")
        self.assertNotIn("extra_body", record[-1]["kwargs"])


if __name__ == "__main__":
    unittest.main()
