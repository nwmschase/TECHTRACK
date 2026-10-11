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
        self.assertEqual(code, 0, report)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0]["providers"], ["xai"])
        self.assertEqual(calls[0]["models"], {"xai": ["grok-4.6"]})
        self.assertNotIn("not stated", transcript.lower())
        self.assertNotIn("How (", transcript)
        self.assertEqual(report.count("Result: 10/10."), 2)
        self.assertIn("How (", raw)
        self.assertIn("guards rewrote 4 of 4 turns", report)
        self.assertIn("RAW model reply", report)

    def test_a_how_detail_is_not_appended(self):
        leaked = "How (Thetford, page 3): Tools: not stated. Meter setting: not stated."
        self.assertEqual(_keep_figure_detail(leaked, "Check the valve."), "")
        self.assertEqual(_keep_figure_detail("Use a 1/2-inch wrench.", "Check the valve."), "Use a 1/2-inch wrench.")
