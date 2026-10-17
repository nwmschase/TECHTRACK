"""S20: Level Up front jacks drift. Coil and plumbing before the cartridge.

UPDATED 2026-10-16 for the GD official method. Edit authorized by Leader (1:51 PM PT,
cursor/gd-official-method). The lead-jack card no longer answers by itself; it rides into the
official walk as a shop hint. These replays still assert that the job reaches the correct fix
(cartridge valve 177094 with its owner's-manual page) and that the safety line comes first.
"""
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
    ns["_gd_official_web"] = lambda unit: {}
    ns["_gd_official_chat"] = _scripted_model
    return ns


SENT = []


def _scripted_model(messages, max_tokens, effort):
    """Offline stand-in for grok: follows the shop hint it was given, one action per line."""
    SENT.append(messages)
    system = messages[0]["content"]
    hint = system.split("SHOP HINT (not a source, do not cite):", 1)[-1].split("\n=====", 1)[0] if "SHOP HINT" in system else ""
    lines = [ln.strip() for ln in hint.splitlines() if ln.strip()][:8]
    return "\n".join(f"{i}. {ln}" for i, ln in enumerate(lines, 1)) or "1. Verify the complaint."


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


class TestLeadJackReplay(unittest.TestCase):
    MODEL = "Lippert Level Up 807662"

    @classmethod
    def setUpClass(cls):
        cls.ns = _load_send_path()

    def _turn(self, latest, history, store):
        text, flow = self.ns["guided_diagnostics_reply"](
            latest, "Leveling", self.MODEL, history, unity_gate="No", pin_store=store
        )
        self.assertIsNone(flow)
        text = (text or "").strip()
        self.assertTrue(text)
        for phrase in BANNED:
            self.assertNotIn(phrase, text.lower(), phrase)
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": text})
        return text

    def _walk(self, turns):
        history, store, out = [], {}, []
        for t in turns:
            out.append(self._turn(t, history, store))
        self._last_turns = list(turns)
        return out, store

    HELD_RE = r"before condemning the front lead-jack cartridge valve, record its isolation reading"

    def _assert_reaches_cartridge_fix(self, replies, turns=None):
        """Leader 2026-10-16 8:23 PM: the cartridge call (177094 with its owner's-manual page) is required once the isolation step
        (the coil test) is on record, and only AFTER it; before that step the call must be HELD and 177094 must not print."""
        self.assertIn("Safety first", replies[0])
        joined = "\n".join(replies)
        self.assertIn("cartridge", joined.lower())
        _assert_177094_is_cited(self, joined)
        turns = turns or []
        iso = next((i for i, t in enumerate(turns) if re.search(r"coil.*tests good", t, re.I)), None)
        if iso is None:
            self.assertNotIn("177094", joined)
            self.assertRegex(joined.lower(), self.HELD_RE)
        else:
            self.assertIn("177094", joined)
            first = next(i for i, r in enumerate(replies) if "177094" in r)
            self.assertGreaterEqual(first, iso, "177094 printed before the isolation step")
            for r in replies[:iso]:
                self.assertNotIn("177094", r)

    def test_s20_asks_coil_and_plumbing_before_the_cartridge(self):
        replies, _ = self._walk([CONCERN, "The lead-jack valve coil on the gray wire tests good.",
                                 "The manual override screw is backed out. What is the repair?"])
        self._assert_reaches_cartridge_fix(replies, self._last_turns)
        self.assertIn("VERIFY THE CUSTOMER COMPLAINT", SENT[-3][0]["content"])

    def test_plumbing_yes_advances_to_the_override_screw(self):
        replies, store = self._walk([CONCERN, "The lead-jack valve coil on the gray wire tests good.", "Yes. The swap plumbing looks good."])
        self._assert_reaches_cartridge_fix(replies, self._last_turns)
        self.assertIn("swap plumbing looks good", SENT[-1][0]["content"])

    def test_s20_does_not_call_the_model(self):
        """New method: exactly one primary-model call per turn; the legacy ai_chat is never called."""
        calls = {"legacy": 0}
        original = self.ns["ai_chat"]
        self.ns["ai_chat"] = lambda *a, **k: calls.__setitem__("legacy", calls["legacy"] + 1) or original(*a, **k)
        try:
            before = len(SENT)
            replies, _ = self._walk([CONCERN])
        finally:
            self.ns["ai_chat"] = original
        self.assertEqual(calls["legacy"], 0)
        self.assertEqual(len(SENT) - before, 1)
        self._assert_reaches_cartridge_fix(replies, self._last_turns)

    def test_plumbing_is_not_asked_again_after_the_cartridge_fact(self):
        replies, store = self._walk([CONCERN, "The lead-jack valve coil on the gray wire tests good.",
                                     "Not checked yet", "The manual override screw is backed out."])
        self._assert_reaches_cartridge_fix(replies, self._last_turns)
        self.assertIn("HELD STEP", SENT[-2][0]["content"])

    def test_answered_plumbing_is_not_asked_again(self):
        replies, store = self._walk([CONCERN, "The lead-jack valve coil on the gray wire tests good.",
                                     "Manifold hose is in the notched port. Follow-leg hose is in the non-notched port. "
                                     "Unused ports are plugged. Orange extend and black retract hoses are not reversed.",
                                     "What next?"])
        self._assert_reaches_cartridge_fix(replies, self._last_turns)
        self.assertIn("TECH HAS REPORTED", SENT[-1][0]["content"])
        self.assertIn("notched port", SENT[-1][0]["content"])

    def test_177094_never_prints_without_the_owners_manual_page(self):
        from gd_library_coach import LEADJACK_CARTRIDGE_LINE

        _assert_177094_is_cited(self, LEADJACK_CARTRIDGE_LINE)
        replies, _ = self._walk([CONCERN, "The manual override screw is backed out."])
        self._assert_reaches_cartridge_fix(replies, self._last_turns)

    def test_s20_does_not_borrow_a_furnace_chat(self):
        furnace = [{"role": "user", "content": "Furnace fan runs, no heat."},
                   {"role": "assistant", "content": "Check the sail switch."}]
        text, _ = self.ns["guided_diagnostics_reply"](CONCERN, "Leveling", self.MODEL, furnace, unity_gate="No", pin_store={})
        self.assertNotIn("sail switch", text.lower())
        self.assertIn("Safety first", text)

    def test_s20_live_turns_move_past_the_repair_call(self):
        replies, _ = self._walk(["Cartridge was loose; snugged, bled and resynced; still drifts.",
                                 "Plumbing checked: manifold hose in notched port, follow-leg in non-notched, "
                                 "orange/black correct, no needed port plugged.",
                                 "Override screw is backed out."])
        self._assert_reaches_cartridge_fix(replies, self._last_turns)
        self.assertIn("Plumbing checked", SENT[-1][0]["content"])
