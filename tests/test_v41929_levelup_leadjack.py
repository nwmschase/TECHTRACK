"""S20: Level Up front jacks drift. Coil and plumbing before the cartridge."""
import re
import unittest
from pathlib import Path

from bay_procedure import (
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    layout_problems,
    render_bay_procedure_pdf,
)

FRAME = (36.0, 50.0, 540.0, 612.0)
CONCERN = (
    "After replacing the front-left jack, the front jacks drift and move on their own "
    "when other circuits pressurize, including when the slides run."
)
POISON = (
    "If the sail switch has power in and power out while the blower runs, replace the wall thermostat.\n"
    "Leave the rubber-boot terminator in. Unplug only the Firefly cable.\n"
    "If the pin or coupler or seized, replace the complete front stabilizer jack assembly.\n"
    "Press FRONT five times, then REAR five times, then ENTER for zero-point calibration."
)
_CARTRIDGE_PAGE_CITE_RE = re.compile(
    r"towable owner'?s manual.{0,60}(?:page|p\.)\s*15"
    r"|fw owner'?s manual.{0,60}(?:page|p\.)\s*18",
    re.I | re.S,
)


def _assert_177094_is_cited(case: unittest.TestCase, text: str) -> None:
    """Part 177094 never prints without the owner's-manual parts-list page."""
    if "177094" not in (text or ""):
        return
    case.assertRegex(text, _CARTRIDGE_PAGE_CITE_RE)


BANNED = (
    "sail switch",
    "wall thermostat",
    "firefly",
    "rubber-boot",
    "front stabilizer",
    "zero-point",
    "zero point",
    "thermocouple",
    "sensing tube",
    "rooftop assembly",
)


def _load_send_path():
    src = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
    cut = src.split("# ---------------- LOGIN ----------------", 1)[0]
    ns = {
        "__name__": "rv_techtrack_s20_replay",
        "__file__": str(Path(__file__).resolve().parents[1] / "rv_techtrack.py"),
    }
    exec(compile(cut, "rv_techtrack.py", "exec"), ns)
    ns["ai_available"] = lambda: True
    ns["ai_chat"] = lambda *args, **kwargs: POISON
    return ns


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


class TestLeadJackReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = _load_send_path()

    def _turn(self, latest, history):
        text, flow = self.ns["guided_diagnostics_reply"](
            latest, "Leveling", "Lippert Level Up", history, unity_gate="Not sure"
        )
        self.assertIsNone(flow)
        text = (text or "").strip()
        self.assertTrue(text)
        low = text.lower()
        self.assertIn("📖", text)
        for phrase in BANNED:
            self.assertNotIn(phrase, low, phrase)
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": text})
        return text

    def test_s20_asks_coil_and_plumbing_before_the_cartridge(self):
        history = []
        first = self._turn(CONCERN, history)
        self.assertIn("gray wire", first.lower())
        self.assertNotIn("177094", first)

        early = self.ns["guided_diagnostics_reply"](
            "What is the repair?",
            "Leveling",
            "Lippert Level Up",
            list(history),
            unity_gate="Not sure",
        )[0]
        self.assertIn("gray wire", (early or "").lower())
        self.assertNotIn("177094", early or "")

        coil = self._turn(
            "The lead-jack valve coil on the gray wire tests good.",
            history,
        )
        self.assertIn("notched", coil.lower())
        self.assertNotIn("177094", coil)

        plumbing = self._turn(
            "Manifold hose is in the notched port. Follow-leg hose is in the non-notched port. "
            "Unused ports are plugged. Orange extend and black retract hoses are not reversed.",
            history,
        )
        self.assertIn("override screw", plumbing.lower())
        self.assertNotIn("177094", plumbing)

        repair = self._turn(
            "The manual override screw is backed out. What is the repair?",
            history,
        )
        low = repair.lower()
        self.assertIn("177094", repair)
        self.assertIn("cartridge", low)
        self.assertIn("ti-005", low)
        _assert_177094_is_cited(self, repair)

    def test_plumbing_yes_advances_to_the_override_screw(self):
        history = []
        self._turn(CONCERN, history)
        self._turn("The lead-jack valve coil on the gray wire tests good.", history)
        yes = self._turn("Yes. The swap plumbing looks good.", history)
        self.assertIn("override screw", yes.lower())
        self.assertNotIn("notched port", yes.lower())

        bare = []
        self._turn(CONCERN, bare)
        self._turn("The lead-jack valve coil on the gray wire tests good.", bare)
        answered = self._turn("Yes", bare)
        self.assertIn("override screw", answered.lower())
        self.assertNotIn("notched port", answered.lower())

    def test_s20_does_not_call_the_model(self):
        calls = {"n": 0}
        original = self.ns["ai_chat"]

        def _count(*args, **kwargs):
            calls["n"] += 1
            return original(*args, **kwargs)

        self.ns["ai_chat"] = _count
        try:
            text, flow = self.ns["guided_diagnostics_reply"](
                CONCERN, "Leveling", "Lippert Level Up", [], unity_gate="Not sure"
            )
        finally:
            self.ns["ai_chat"] = original
        self.assertIsNone(flow)
        self.assertEqual(calls["n"], 0)
        self.assertIn("gray wire", (text or "").lower())

    def test_plumbing_is_not_asked_again_after_the_cartridge_fact(self):
        history = []
        self._turn(CONCERN, history)
        self._turn("The lead-jack valve coil on the gray wire tests good.", history)
        skipped = self._turn("Not checked yet", history)
        self.assertIn("override screw", skipped.lower())
        self.assertNotIn("swap plumbing", skipped.lower())
        self.assertNotIn("notched", skipped.lower())
        repair = self._turn("The manual override screw is backed out.", history)
        self.assertIn("177094", repair)
        follow = self._turn("What is the repair?", history)
        self.assertIn("177094", follow)
        self.assertNotIn("swap plumbing", follow.lower())
        self.assertNotIn("notched", follow.lower())
        again = self._turn("Not checked yet", history)
        self.assertIn("177094", again)
        self.assertNotIn("swap plumbing", again.lower())
        self.assertNotIn("notched", again.lower())

        named = []
        self._turn(CONCERN, named)
        self._turn("The lead-jack valve coil on the gray wire tests good.", named)
        after = self._turn("The cartridge valve is 177094.", named)
        self.assertNotIn("swap plumbing", after.lower())
        self.assertNotIn("notched port", after.lower())
        self.assertTrue("override" in after.lower() or "177094" in after)

    def test_answered_plumbing_is_not_asked_again(self):
        history = []
        self._turn(CONCERN, history)
        self._turn("The lead-jack valve coil on the gray wire tests good.", history)
        self._turn("Yes", history)
        follow = self._turn("What is the repair?", history)
        low = follow.lower()
        self.assertNotIn("notched", low)
        self.assertNotIn("swap plumbing", low)
        self.assertIn("override screw", low)

        stated = []
        self._turn(CONCERN, stated)
        self._turn("The lead-jack valve coil on the gray wire tests good.", stated)
        self._turn(
            "Manifold hose is in the notched port. Follow-leg hose is in the non-notched port. "
            "Unused ports are plugged. Orange extend and black retract hoses are not reversed.",
            stated,
        )
        later = self._turn("What next?", stated)
        self.assertNotIn("notched port", later.lower())
        self.assertIn("override", later.lower())

    def test_177094_never_prints_without_the_owners_manual_page(self):
        from gd_library_coach import LEADJACK_CARTRIDGE_LINE

        _assert_177094_is_cited(self, LEADJACK_CARTRIDGE_LINE)
        history = []
        self._turn(CONCERN, history)
        self._turn("The lead-jack valve coil on the gray wire tests good.", history)
        self._turn("Yes. The swap plumbing looks good.", history)
        repair = self._turn("The manual override screw is backed out.", history)
        _assert_177094_is_cited(self, repair)
        self.assertIn("177094", repair)
        self.assertIn("cartridge valve", repair.lower())

    def test_s20_does_not_borrow_a_furnace_chat(self):
        history = [
            {"role": "user", "content": "Suburban furnace. Will not blow warm; fan turns on then shuts off."},
            {
                "role": "assistant",
                "content": "Replace the wall thermostat.\n📖 Source: Suburban Furnace Service and Training Manual",
            },
        ]
        text = self._turn(CONCERN, history)
        self.assertIn("gray wire", text.lower())
        self.assertNotIn("177094", text)


class TestLeadJackBaySheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = compile_bay_procedure(
            concern=CONCERN,
            brand="Lippert",
            model="Level Up",
            category="Leveling",
            chunks=[],
        )

    def test_sheet_ends_on_the_cartridge(self):
        titles = " ".join((src.get("title") or "") for src in self.proc.sources).lower()
        for token in ("ccd-0001750", "qr-109", "ti-143", "ti-324", "ti-170", "ti-005"):
            self.assertIn(token, titles, token)
        self.assertIn("177094", self.proc.pattern_means + " " + self.proc.bay_order[-1])
        _assert_177094_is_cited(self, self.proc.pattern_means)
        _assert_177094_is_cited(self, self.proc.bay_order[-1])
        source_text = "\n".join(
            f"{src.get('title') or ''} page {src.get('page')} {src.get('excerpt') or ''}"
            for src in self.proc.sources
        )
        self.assertIn("177094", source_text)
        _assert_177094_is_cited(self, source_text)
        self.assertIn("page 3", self.proc.primary_cite.lower())
        self.assertIn("page 15", self.proc.primary_cite.lower())
        self.assertIn("towable", self.proc.primary_cite.lower())
        titles = [(src.get("title") or "").lower() for src in self.proc.sources]
        self.assertFalse(any("hose diagram" in title for title in titles))
        self.assertTrue(
            any(
                "fw owner" in (src.get("title") or "").lower() and src.get("page") == 13
                for src in self.proc.sources
            )
        )
        order = " ".join(self.proc.bay_order).lower()
        self.assertLess(order.index("gray wire"), order.index("notched"))
        self.assertLess(order.index("notched"), order.index("override screw"))
        self.assertLess(order.index("override screw"), order.index("177094"))
        labels = " ".join(node.text for node in self.proc.flowchart.nodes).lower()
        self.assertIn("gray wire", labels)
        self.assertIn("plumbing", labels)
        self.assertIn("override screw", labels)
        self.assertIn("177094", labels)
        self.assertNotIn("firefly", labels)
        self.assertNotIn("did the first", labels)

    def test_pdf_keeps_the_cartridge_and_the_boxes_apart(self):
        trace = []
        pdf = render_bay_procedure_pdf(self.proc, trace=trace)
        problems = layout_problems(trace)
        self.assertEqual(problems, [], problems[:8])
        rects = flowchart_node_rects(self.proc.flowchart, *FRAME)
        self.assertEqual(flowchart_boxes_overlap(rects, gap=6.0), [])
        pdf_text = _pdf_text(pdf)
        low = pdf_text.lower()
        self.assertIn("177094", low)
        _assert_177094_is_cited(self, pdf_text)
        self.assertIn("gray wire", low)
        self.assertIn("notched", low)
        self.assertIn("override", low)
        self.assertIn("ti-005", low)
        self.assertNotIn("hose diagram", low)
        self.assertNotIn("firefly", low)
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        page1 = doc[0].get_text()
        self.assertIn("177094", page1)
        self.assertRegex(page1, r"(?i)towable owner\W{0,3}s manual[\s\S]{0,80}page\s*15")
        self.assertRegex(pdf_text, r"(?i)fw owner\W{0,3}s manual[\s\S]{0,80}page\s*13")
        self.assertNotIn("sail switch", low)


if __name__ == "__main__":
    unittest.main()
