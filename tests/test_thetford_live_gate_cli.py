"""The headless gate reads a SQLite library and an R2 cache, not the Streamlit app."""
import os
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.thetford_live_gate import _keep_figure_detail, main

LIBRARY = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "thetford_live_library"
DB = LIBRARY / "library.sqlite"
CACHE = LIBRARY / "cache"


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    return struct.unpack(">II", data[16:24])


class TestThetfordLiveGateCli(unittest.TestCase):
    def test_the_fixture_library_scores_ten(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            code = main(["--db", str(DB), "--cache", str(CACHE), "--out", str(out)])
            report = (out / "report.txt").read_text(encoding="utf-8")
            transcript = (out / "transcript.txt").read_text(encoding="utf-8")
            self.assertEqual(code, 0, report)
            self.assertEqual(report.count("Result: 10/10."), 2)
            self.assertIn("PF-32 MANUAL", report)
            self.assertNotIn("PF-08 MANUAL", report)
            self.assertTrue((out / "thetford-bay.pdf").stat().st_size > 1000)
            self.assertIn("T2 Tech: Show me where that connection is", transcript)
            self.assertIn("back of the toilet", transcript.lower())
            self.assertIn("water valve", transcript.lower())
            self.assertNotIn("not stated", transcript.lower())
            self.assertNotIn("How (", transcript)
            self.assertNotIn("page 7", transcript.lower())
            self.assertNotRegex(transcript, r"Step 1")
            page = out / "thetford-bay-p01.png"
            self.assertTrue(page.is_file())
            width, height = _png_size(page)
            self.assertEqual((width, height), (765, 990))
            self.assertTrue((out / "transcript-profile.txt").is_file())

    def test_live_llm_without_a_key_exits_2(self):
        saved = os.environ.pop("XAI_API_KEY", None)
        try:
            code = main([
                "--live-llm",
                "--db", str(DB),
                "--cache", str(CACHE),
                "--out", "/tmp/thetford-gate-missing-key",
            ])
        finally:
            if saved is not None:
                os.environ["XAI_API_KEY"] = saved
        self.assertEqual(code, 2)

    def test_live_llm_calls_grok_and_drops_the_how_block(self):
        import tempfile

        calls = []

        def fake_complete(messages, **kwargs):
            calls.append(kwargs)
            return "How (Thetford, page 7): Tools: not stated. Meter setting: not stated."

        saved = os.environ.get("XAI_API_KEY")
        os.environ["XAI_API_KEY"] = "test-key"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                with patch("gd_llm.complete_chat", fake_complete):
                    code = main([
                        "--live-llm",
                        "--db", str(DB),
                        "--cache", str(CACHE),
                        "--out", str(out),
                    ])
                report = (out / "report.txt").read_text(encoding="utf-8")
                transcript = (out / "transcript.txt").read_text(encoding="utf-8")
                raw = (out / "transcript-raw.txt").read_text(encoding="utf-8")
        finally:
            if saved is None:
                os.environ.pop("XAI_API_KEY", None)
            else:
                os.environ["XAI_API_KEY"] = saved
        self.assertEqual(code, 1, report)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0]["providers"], ["xai"])
        self.assertEqual(calls[0]["models"], {"xai": ["grok-4.6"]})
        self.assertNotIn("not stated", transcript.lower())
        self.assertNotIn("How (", transcript)
        self.assertEqual(report.count("Result: 10/10."), 2)
        self.assertIn("How (", raw)
        self.assertIn("guards rewrote 4 of 4 turns", report)
        self.assertIn("RAW model reply", report)
        self.assertRegex(report, r"(?m)^FAIL\b|^\d+\. FAIL\b|^PF-\d+ FAIL\b")

    def test_a_prompt_follower_keeps_the_raw_reply(self):
        import tempfile

        calls = []

        def fake_complete(messages, **kwargs):
            calls.append({"messages": messages, "kwargs": kwargs})
            system = messages[0]["content"]
            fields = {}
            grab = False
            for line in system.splitlines():
                if line.strip() == "THIS TURN":
                    grab = True
                    continue
                if grab and not line.strip():
                    break
                if grab and ":" in line:
                    key, value = line.split(":", 1)
                    fields[key.strip().lower()] = value.strip()
            parts = []
            safety = fields.get("safety") or ""
            if safety:
                parts.append(safety if safety.endswith(".") else safety + ".")
            parts.append(f"Go to {fields.get('where') or 'the part'}.")
            tool = fields.get("tool") or ""
            if tool and not tool.lower().startswith("none"):
                parts.append(f"Use {tool}.")
            parts.append(f"Check {fields.get('look') or 'the part'}.")
            parts.append(f"A good result is {fields.get('good') or 'it is dry'}.")
            parts.append(f"A bad result is {fields.get('bad') or 'it leaks'}.")
            parts.append("Report what you see?")
            parts.append("")
            parts.append(f"📖 Source: {fields.get('cite') or 'the manual'}")
            return "\n".join(parts)

        saved = os.environ.get("XAI_API_KEY")
        os.environ["XAI_API_KEY"] = "test-key"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                with patch("gd_llm.complete_chat", fake_complete):
                    code = main([
                        "--live-llm",
                        "--db", str(DB),
                        "--cache", str(CACHE),
                        "--out", str(out),
                    ])
                report = (out / "report.txt").read_text(encoding="utf-8")
                raw = (out / "transcript-raw.txt").read_text(encoding="utf-8")
        finally:
            if saved is None:
                os.environ.pop("XAI_API_KEY", None)
            else:
                os.environ["XAI_API_KEY"] = saved
        self.assertEqual(code, 0, report)
        self.assertEqual(len(calls), 4)
        systems = [call["messages"][0]["content"] for call in calls]
        self.assertIn("Address the technician as you", systems[0])
        self.assertIn("DIAGNOSIS ORDER", systems[0])
        excerpts = systems[0].split("MANUAL EXCERPTS", 1)[1]
        self.assertLess(excerpts.find("42088"), excerpts.find("42109"))
        self.assertIn("supply connection is dry", systems[2].lower())
        self.assertIn("vacuum breaker", systems[2].lower())
        self.assertIn("water off", systems[3].lower())
        self.assertIn("wrench", systems[3].lower())
        raw_at = report.find("RAW model reply")
        self.assertIn("Result: 10/10.", report[raw_at:])
        self.assertNotRegex(report[raw_at:], r"(?m)^\d+\. FAIL\b")
        self.assertRegex(report, r"guards rewrote [01] of 4 turns")
        self.assertNotIn("the tech", raw.lower())
        self.assertIn("42088", raw.split("ASSISTANT:")[1])
        self.assertNotIn("42109", raw.split("ASSISTANT:")[1].split("USER:")[0])
        self.assertIn("vacuum breaker", raw.lower())
        self.assertIn("34123", raw)
        self.assertIn("flashlight", raw.lower())
        self.assertIn("wrench", raw.lower())
        self.assertIn("water off", raw.lower())
        self.assertIn("Report what you see?", raw)
        self.assertIn("seat", raw.lower())
        self.assertNotIn("cartridge for a weep", raw.lower())
        vacuum = raw.split("The supply connection is dry.", 1)[1].split("USER:", 1)[0].lower()
        self.assertNotIn("plier", vacuum)
        self.assertIn("Do not name pliers", systems[2])
        self.assertIn("do not check for that weep", systems[3].lower())

    def test_manual_lines_do_not_fail_the_exit(self):
        from scripts.profile_check import Rule
        from scripts.thetford_live_gate import _score_gap

        manual = [
            Rule("score-1", True, "human confirms", status="MANUAL", number=1, scorecard=True),
            Rule("score-2", True, "shown", status="PASS", number=2, scorecard=True),
            Rule("PF-32", True, "expert review", status="MANUAL"),
        ]
        self.assertEqual(_score_gap(manual, "GD"), [])
        manual.append(Rule("labeled_good_bad", False, "turn 1 does not label both"))
        self.assertEqual(len(_score_gap(manual, "GD")), 1)

    def test_a_cited_vacuum_reply_is_not_called_a_library_miss(self):
        """rev4 live2: a correct T3 was replaced with a false library-miss line.

        The review pack was not in this checkout, so this uses the described
        path: earlier replies cite 42088 without the word Thetford, and the
        draft names the vacuum breaker and kit 34123.
        """
        from gd_library_coach import avoid_duplicate_reply, library_miss_shop_line

        history = [
            {"role": "user", "content": "Thetford 42070 leaks under the flush lever"},
            {
                "role": "assistant",
                "content": (
                    "Go to the water valve. You use a flashlight. "
                    "A good result is it stays tight. A bad result is water comes out. "
                    "What do you see?\n"
                    "📖 Source: 42088, page 3"
                ),
            },
            {"role": "user", "content": "Show me where that connection is"},
            {
                "role": "assistant",
                "content": (
                    "Go to the back of the toilet, on the water valve. "
                    "What do you see?\n"
                    "📖 Source: 42088, page 3"
                ),
            },
        ]
        passing = (
            "Go to the vacuum breaker on the flush hose.\n"
            "You check it while you flush.\n"
            "A good result is no leak while flushing.\n"
            "A bad result is it leaks only while flushing.\n"
            "Report what you see?\n\n"
            "📖 Source: 34123, page 1"
        )
        reply = avoid_duplicate_reply(
            passing,
            history,
            "The supply connection is dry.",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertNotIn("no thetford document", reply.lower())
        self.assertNotEqual(reply, library_miss_shop_line("Thetford"))
        self.assertIn("vacuum breaker", reply.lower())
        self.assertIn("34123", reply)
        self.assertIn("You check it while you flush.", reply)
        short = (
            "Go to the vacuum breaker. Kit 34123. You should watch it while flushing.\n"
            "📖 Source: 34123, page 1"
        )
        guarded = avoid_duplicate_reply(
            short,
            history,
            "The supply connection is dry.",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertNotIn("no thetford document", guarded.lower())
        self.assertIn("vacuum breaker", guarded.lower())

    def test_a_how_detail_is_not_appended(self):
        leaked = "How (Thetford, page 3): Tools: not stated. Meter setting: not stated."
        self.assertEqual(_keep_figure_detail(leaked, "Check the valve."), "")
        self.assertEqual(_keep_figure_detail("Use a 1/2-inch wrench.", "Check the valve."), "Use a 1/2-inch wrench.")
