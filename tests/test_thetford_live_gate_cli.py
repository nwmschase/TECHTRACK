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
            t2 = transcript.split("T2 Tech:", 1)[1].split("T3 Tech:", 1)[0]
            self.assertIn("no picture", t2.lower())
            self.assertIn("back of the toilet", t2.lower())
            self.assertIn("water supply line", t2.lower())
            self.assertIn("then do that check and tell me what you see", t2.lower())
            self.assertNotIn("good result", t2.lower())
            self.assertNotIn("bad result", t2.lower())
            self.assertIn("photo", t2.lower())
            self.assertNotIn("Figure:", t2)
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
        self.assertIn("T1 guard:", report)
        self.assertNotIn("T1 guard: none", report)
        self.assertIn("T3 guard:", report)
        self.assertNotIn("T3 guard: none", report)
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
            cite = fields.get("cite") or "the manual"
            picture = (fields.get("picture") or "").lower()
            if picture:
                if "no picture" in picture:
                    return "\n".join([
                        "The manual has no picture of this spot.",
                        "The water supply line connection is at the back of the toilet, on the water valve.",
                        "Send a photo of that connection.",
                        "Then do that check and tell me what you see.",
                        "",
                        f"📖 Source: {cite}",
                    ])
                return "\n".join([
                    "On this page, look at the back of the toilet, "
                    "at the water supply line connection on the water valve.",
                    "Then do that check and tell me what you see.",
                    "",
                    f"📖 Source: {cite}",
                ])
            if "42109" in cite:
                tool = fields.get("tool") or "a 1/2-inch wrench"
                action = (fields.get("look") or "Take the toilet off the closet bolts").rstrip(".")
                parts = [
                    "This is the water valve kit 42109 job. The valve is at the pedal.",
                    "Turn the RV water off.",
                    "The closet bolts are at the floor, on the closet flange.",
                    f"{action[0].upper()}{action[1:]}.",
                    f"Use {tool}.",
                    f"A good result is {fields.get('good') or 'the toilet is off the bolts and the water is off'}.",
                    f"A bad result is {fields.get('bad') or 'the toilet is still on the bolts, or water still comes out'}.",
                    "I can walk the rest with you, one step at a time.",
                    "The Bay PDF has the full list.",
                    "Tell me what you see.",
                    "",
                    f"📖 Source: {cite}",
                ]
                return "\n".join(parts)
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
            parts.append("Tell me what you see.")
            parts.append("")
            parts.append(f"📖 Source: {cite}")
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
                transcript = (out / "transcript.txt").read_text(encoding="utf-8")
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
        self.assertIn("Tell me what you see.", raw)
        self.assertNotIn("Report what you see?", raw)
        self.assertIn("stays dry", raw.lower())
        self.assertIn("42109", raw)
        self.assertIn("closet bolts", raw.lower())
        self.assertIn("closet flange", raw.lower())
        self.assertIn("bay pdf", raw.lower())
        self.assertIn("one step at a time", raw.lower())
        self.assertNotIn("cartridge for a weep", raw.lower())
        self.assertNotIn("Figure:", transcript)
        vacuum = raw.split("The supply connection is dry.", 1)[1].split("USER:", 1)[0].lower()
        self.assertNotIn("plier", vacuum)
        self.assertIn("Do not name pliers", systems[2])
        self.assertIn("do not check for that weep", systems[3].lower())
        self.assertIn("water supply line", systems[1].lower())
        self.assertIn("do not invent a side", systems[1].lower())
        self.assertIn("never reference a figure", systems[1].lower())
        self.assertIn("no picture", systems[1].lower())
        self.assertIn("do not name a tool", systems[1].lower())
        self.assertIn("then do that check and tell me what you see", systems[1].lower())
        self.assertNotIn("the good result is the connection stays dry", systems[1].lower())
        self.assertIn("take the toilet off the closet bolts", systems[3].lower())
        self.assertNotIn("coming off", systems[3].lower())
        self.assertIn("closet flange", systems[3].lower())
        self.assertIn("said once", systems[3].lower())
        self.assertIn("do not name pliers", systems[3].lower())
        self.assertIn("do not seat the cartridge", systems[3].lower())
        self.assertNotIn("wrench and pliers", systems[3].lower())
        self.assertEqual(raw.lower().count("turn the rv water off"), 1)
        self.assertNotIn("plier", raw.lower())
        self.assertNotIn("seat the", raw.lower())
        self.assertIn("water supply line", raw.lower())
        self.assertIn("back of the toilet", raw.lower())
        self.assertIn("no picture", raw.lower())
        self.assertNotIn("inlet side", raw.lower())
        self.assertNotIn("small collar", raw.lower())
        self.assertIn("then do that check and tell me what you see", raw.lower())
        self.assertIn("take the toilet off the closet bolts", raw.lower())
        self.assertNotIn("coming off", raw.lower())
        show = raw.split("ASSISTANT:", 2)[2].split("USER:", 1)[0].lower()
        self.assertNotIn("good result", show)
        self.assertNotIn("bad result", show)
        self.assertNotRegex(show, r"\b(wrench|pliers?|flashlight)\b")
        for label in ("T1", "T2", "T3", "T4"):
            self.assertIn(f"{label} guard: none", report)
        import scripts.profile_check as profile_check

        bodies = [
            profile_check._assistant_body(part)
            for part in raw.split("ASSISTANT:")[1:]
        ]
        self.assertFalse(profile_check._near_duplicate(bodies[:2]))

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
        errored = [
            Rule("PF-07", True, "checker error", status="ERROR"),
            Rule("PF-32", True, "expert review", status="MANUAL"),
        ]
        gap = _score_gap(errored, "PF")
        self.assertEqual(len(gap), 1)
        self.assertIn("ERROR", gap[0])
        self.assertEqual(
            len(_score_gap([Rule("PF-03", True, "unknown", status="UNKNOWN")], "PF")),
            1,
        )

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
            "Tell me what you see.\n\n"
            "📖 Source: 34123, page 1"
        )
        chunks = [
            {"title": "Thetford Style II OM Permanent RV Toilet 42088", "brand": "Thetford"},
            {"title": "Thetford Vacuum Breaker Kit 34123/34122", "brand": "Thetford"},
            {"title": "Thetford Water Valve Kit 42109", "brand": "Thetford"},
        ]
        from gd_library_coach import _unmatched_unit_line

        bare = _unmatched_unit_line(
            history,
            "The supply connection is dry.",
            "Plumbing / Toilets",
            "Thetford 42070",
            current=passing,
        )
        self.assertEqual(bare, library_miss_shop_line("Thetford"))
        held = _unmatched_unit_line(
            history,
            "The supply connection is dry.",
            "Plumbing / Toilets",
            "Thetford 42070",
            current=passing,
            chunks=chunks,
        )
        self.assertEqual(held, "")
        reply = avoid_duplicate_reply(
            passing,
            history,
            "The supply connection is dry.",
            "Plumbing / Toilets",
            "Thetford 42070",
            chunks=chunks,
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
            chunks=chunks,
        )
        self.assertNotIn("no thetford document", guarded.lower())
        self.assertIn("vacuum breaker", guarded.lower())

    def test_a_number_only_cite_of_a_retrieved_doc_is_not_a_library_miss(self):
        """S01, S09, and S20: a document number with no brand word is still a cite.

        The model does not lock a job, so the miss path actually runs. The
        Thetford number list would not recognize these documents.
        """
        from gd_library_coach import (
            _job_key,
            _unmatched_unit_line,
            avoid_duplicate_reply,
            library_miss_shop_line,
        )

        cases = (
            (
                "Furrion",
                "Air Conditioning",
                "Furrion",
                "The fan is noisy.",
                (
                    "Check the connector and confirm the reading holds.\n"
                    "What do you see?\n"
                    "📖 Source: CCD-0008666, page 19"
                ),
                "CCD-0008666",
                [{"title": "Furrion Chill FACR CCD-0008666", "brand": "Furrion"}],
            ),
            (
                "Dometic",
                "Air Conditioning",
                "Dometic",
                "The fan is noisy.",
                (
                    "Check the connector and confirm the reading holds.\n"
                    "What do you see?\n"
                    "📖 Source: 3311071, page 4"
                ),
                "3311071",
                [{"title": "Dometic Brisk II diagnostic 3311071", "brand": "Dometic"}],
            ),
            (
                "Lippert",
                "Leveling",
                "Lippert",
                "The panel light is dim.",
                (
                    "Check the connector and confirm the reading holds.\n"
                    "What do you see?\n"
                    "📖 Source: 177094, page 12"
                ),
                "177094",
                [{"title": "Lippert Level Up cartridge valve 177094", "brand": "Lippert"}],
            ),
        )
        for brand, category, model, symptom, reply, number, chunks in cases:
            with self.subTest(brand=brand):
                self.assertEqual(_job_key([], symptom, category, model), "")
                missed = _unmatched_unit_line([], symptom, category, model, current=reply)
                self.assertEqual(missed, library_miss_shop_line(brand))
                held = _unmatched_unit_line(
                    [], symptom, category, model, current=reply, chunks=chunks
                )
                self.assertEqual(held, "")
                kept = avoid_duplicate_reply(
                    reply, [], symptom, category, model, chunks=chunks
                )
                self.assertNotIn(f"no {brand.lower()} document", kept.lower())
                self.assertIn(number, kept)
                self.assertIn("confirm the reading holds", kept.lower())

    def test_an_unasked_figure_line_fails(self):
        import scripts.profile_check as profile_check

        unasked = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\nGo to the vacuum breaker. Tell me what you see.\n"
            "Figure: Fig. 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(unasked)}
        self.assertFalse(named["figures_only_when_asked"].ok)
        asked = (
            "USER: Show me where that connection is\n"
            "ASSISTANT:\nGo to the water valve.\nFigure: Fig. 1\n"
            "Tell me what you see.\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(asked)}
        self.assertTrue(named["figures_only_when_asked"].ok)
        loose = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\nFlush and watch the vacuum breaker as shown in Figure 1.\n"
            "Tell me what you see.\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(loose)}
        self.assertFalse(named["figure_named_only_when_attached"].ok)
        word = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\nLook at Figure 1 on the vacuum breaker.\n"
            "Tell me what you see.\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(word)}
        self.assertFalse(named["figure_named_only_when_attached"].ok)
        cited = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\nThe manual shows Fig. 1. Kit 34123, page 1.\n"
            "Tell me what you see.\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(cited)}
        self.assertTrue(named["figure_named_only_when_attached"].ok)

    def test_a_show_me_near_copy_is_exempt_only_with_a_picture_or_a_plain_statement(self):
        import scripts.profile_check as profile_check

        supply = (
            "Go to the water valve for the supply connection.\n"
            "Use a flashlight.\n"
            "A good result is the supply connection stays dry.\n"
            "A bad result is water comes out of the supply connection.\n"
            "Tell me what you see.\n"
        )
        copied = (
            "Go to the water valve for the supply connection.\n"
            "Use a flashlight.\n"
            "Check the supply connection at the water valve.\n"
            "A good result is the supply connection stays dry.\n"
            "A bad result is water comes out of the supply connection.\n"
            "Tell me what you see.\n"
        )
        self.assertTrue(
            profile_check._near_duplicate([
                profile_check._assistant_body(supply),
                profile_check._assistant_body(copied),
            ])
        )

        def transcript(second: str) -> str:
            return (
                "USER: Thetford 42070 leaks under the flush lever\n"
                f"ASSISTANT:\n{supply}\n"
                "USER: Show me where that connection is\n"
                f"ASSISTANT:\n{second}\n"
            )

        bare = {rule.name: rule for rule in profile_check.check_transcript(transcript(copied))}
        self.assertFalse(bare["no_repeats"].ok)
        stated = copied + "The manual has no picture of this spot.\n"
        named = {rule.name: rule for rule in profile_check.check_transcript(transcript(stated))}
        self.assertTrue(named["no_repeats"].ok, named["no_repeats"].detail)
        attached = copied + "Figure: Thetford Style II OM Permanent RV Toilet 42088, page 3\n"
        named = {rule.name: rule for rule in profile_check.check_transcript(transcript(attached))}
        self.assertTrue(named["no_repeats"].ok, named["no_repeats"].detail)

    def test_a_complete_flush_and_watch_is_not_rewritten(self):
        """rev6 live1 T3. The review pack was not in this checkout.

        The quoted raw reply started 'Flush and watch that vacuum breaker' and
        ended 'Tell me what you see.', citing 34123. The review abbreviated the
        middle. The where, good, and bad lines are that complete observation.
        It correctly names no tool.
        """
        from gd_library_coach import avoid_duplicate_reply, last_guard_name
        import scripts.profile_check as profile_check

        history = [
            {"role": "user", "content": "Thetford 42070 leaks under the flush lever"},
            {
                "role": "assistant",
                "content": (
                    "Go to the water valve for the supply connection.\n"
                    "Use a flashlight.\n"
                    "A good result is the supply connection stays dry.\n"
                    "A bad result is water comes out of the supply connection.\n"
                    "Tell me what you see.\n"
                    "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"
                ),
            },
            {"role": "user", "content": "Show me where that connection is"},
            {
                "role": "assistant",
                "content": (
                    "Go to the back of the toilet, on the inlet side, "
                    "where the supply hose connects to the water valve.\n"
                    "The fitting is a small collar.\n"
                    "Use a flashlight.\n"
                    "Tell me what you see.\n"
                    "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"
                ),
            },
        ]
        chunks = [
            {"title": "Thetford Style II OM Permanent RV Toilet 42088", "brand": "Thetford"},
            {"title": "Thetford Vacuum Breaker Kit 34123/34122", "brand": "Thetford"},
        ]
        raw = (
            "Flush and watch that vacuum breaker on the flush hose.\n"
            "A good result is no leak while flushing.\n"
            "A bad result is it leaks only while flushing.\n"
            "Tell me what you see.\n\n"
            "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 1"
        )
        reply = avoid_duplicate_reply(
            raw,
            history,
            "The supply connection is dry.",
            "Plumbing / Toilets",
            "Thetford 42070",
            chunks=chunks,
        )
        self.assertIn("Flush and watch that vacuum breaker", reply)
        self.assertIn("Tell me what you see.", reply)
        self.assertIn("34123", reply)
        self.assertNotIn("What do you see?", reply)
        self.assertNotIn("Send a photo of what you see.", reply)
        self.assertEqual(last_guard_name(), "")
        named = avoid_duplicate_reply(
            raw.replace(
                "Flush and watch that vacuum breaker",
                "Flush and watch that vacuum breaker with pliers",
            ),
            history,
            "The supply connection is dry.",
            "Plumbing / Toilets",
            "Thetford 42070",
            chunks=chunks,
        )
        self.assertNotIn("pliers", named.lower())
        self.assertNotEqual(last_guard_name(), "")
        copied = (
            "Go to the water valve for the supply connection.\n"
            "Use a flashlight.\n"
            "Check the supply connection at the water valve.\n"
            "A good result is the supply connection stays dry.\n"
            "A bad result is water comes out of the supply connection.\n"
            "Tell me what you see.\n"
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"
        )
        detailed = (
            "The water supply line connection is at the back of the toilet, on the water valve.\n"
            "Check that water supply line connection.\n"
            "Use a flashlight.\n"
            "A good result is the connection stays dry.\n"
            "A bad result is the leak persists from the water valve.\n"
            "Tell me what you see.\n"
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"
        )
        self.assertTrue(
            profile_check._near_duplicate([
                profile_check._assistant_body(history[1]["content"]),
                profile_check._assistant_body(copied),
            ])
        )
        self.assertFalse(
            profile_check._near_duplicate([
                profile_check._assistant_body(history[1]["content"]),
                profile_check._assistant_body(detailed),
            ])
        )
        shown = avoid_duplicate_reply(
            detailed,
            history[:2],
            "Show me where that connection is",
            "Plumbing / Toilets",
            "Thetford 42070",
            chunks=chunks,
        )
        self.assertIn("water supply line", shown.lower())
        self.assertIn("back of the toilet", shown.lower())
        self.assertNotIn("inlet side", shown.lower())
        self.assertNotIn("small collar", shown.lower())
        invented = detailed.replace(
            "The water supply line connection is at the back of the toilet, on the water valve.",
            "That fitting is at the back of the toilet, on the inlet side. It looks like a small collar.",
        )
        rejected = avoid_duplicate_reply(
            invented,
            history[:2],
            "Show me where that connection is",
            "Plumbing / Toilets",
            "Thetford 42070",
            chunks=chunks,
        )
        self.assertNotIn("inlet side", rejected.lower())
        self.assertNotIn("small collar", rejected.lower())
        self.assertIn("water supply line", rejected.lower())
        doubled = (
            "This is the water valve kit 42109 job at the pedal.\n"
            "Turn the RV water off.\n"
            "Turn the RV water off.\n"
            "Take the toilet off the bolts.\n"
            "Use a 1/2-inch wrench.\n"
            "A good result is the toilet is off the bolts and the water is off.\n"
            "A bad result is the toilet is still on the bolts, or water still comes out.\n"
            "I can walk the rest with you, one step at a time.\n"
            "The Bay PDF has the full list.\n"
            "Tell me what you see.\n\n"
            "📖 Source: Thetford Water Valve Kit 42109, page 1"
        )
        valve_history = history + [
            {"role": "user", "content": "The supply connection is dry."},
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "No leak while flushing. The water valve weeps at the pedal."},
        ]
        collapsed = avoid_duplicate_reply(
            doubled,
            valve_history,
            "No leak while flushing. The water valve weeps at the pedal.",
            "Plumbing / Toilets",
            "Thetford 42070",
            chunks=chunks + [{"title": "Thetford Water Valve Kit 42109", "brand": "Thetford"}],
        )
        self.assertEqual(collapsed.lower().count("turn the rv water off"), 1)
        self.assertIn("1/2-inch wrench", collapsed.lower())
        self.assertNotIn("plier", collapsed.lower())
        self.assertNotIn("seat the", collapsed.lower())
        self.assertEqual(last_guard_name(), "repeated water off")

    def test_fallback_cards_follow_the_model_reply_rules(self):
        """The card a tech sees when the model is down matches a model reply.

        One water-off sentence, the wrench only, and 'Tell me what you see.'
        """
        from gd_library_coach import ensure_thetford_flush_reply
        import manual_figures as mf

        history = []
        messages = [
            "Thetford 42070 leaks under the flush lever",
            "Show me where that connection is",
            "The supply connection is dry.",
            "No leak while flushing. The water valve weeps at the pedal.",
        ]
        cards = []
        for message in messages:
            reply = ensure_thetford_flush_reply(
                "", history, message, "Plumbing / Toilets", "Thetford 42070"
            )
            cards.append(reply)
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
        for key in ("supply", "vacuum", "valve", "flange"):
            cards.append(mf.thetford_proving_line(key))
        for card in cards:
            self.assertIn("tell me what you see.", card.lower())
            self.assertNotIn("What do you see?", card)
            low = card.lower()
            water_off = low.count("turn the rv water off") + low.count("turn off the water")
            self.assertLessEqual(water_off, 1, card)
            self.assertNotIn("wrench and pliers", low)
            if "bolt" in low:
                self.assertNotIn("plier", low)
        valve = cards[3]
        self.assertEqual(
            valve.lower().count("turn the rv water off") + valve.lower().count("turn off the water"),
            1,
        )
        self.assertIn("1/2-inch wrench", valve.lower())
        self.assertNotIn("plier", valve.lower())
        show = cards[1]
        self.assertIn("Send a photo if it helps.", show)
        self.assertNotIn("Send a photo of that connection.", show)
        self.assertIn("then do that check and tell me what you see.", show.lower())
        self.assertNotIn("good result", show.lower())
        self.assertNotIn("bad result", show.lower())
        self.assertNotRegex(show.lower(), r"\b(wrench|pliers?|flashlight)\b")

    def test_a_fake_page_image_is_attached_and_pointed_at(self):
        """Live 42088 page 3 has a page image. The fixture does not, so this adds one."""
        from scripts.thetford_live_gate import (
            _asset_rows,
            _connect,
            _page_has_art,
            _play,
            _rank_chunks,
            _thetford_chunks,
        )
        import library_figure_backfill as fb
        import scripts.profile_check as profile_check

        session = _connect(DB)
        try:
            found = _thetford_chunks(session)
            chunks = _rank_chunks(found, 12)
            doc_ids = {int(chunk["document_id"]) for chunk in chunks if chunk.get("document_id")}
            rows = _asset_rows(session, doc_ids)
        finally:
            session.close()
        fb.attach_pngs(None, rows, read_local=False, download=None, cache_root=CACHE)
        self.assertFalse(_page_has_art(rows, "42088", 3))
        _transcript, plain, plain_problems, _raw, _rewrites, _guards = _play(
            rows, chunks, live=False, library=found
        )
        self.assertEqual(plain_problems, [], plain_problems)
        plain_t2 = plain.split("Show me where that connection is", 1)[1].split("USER:", 1)[0]
        self.assertIn("no picture", plain_t2.lower())
        self.assertNotIn("Figure:", plain_t2)
        rows.append({
            "id": 99,
            "document_id": 3,
            "kind": "page",
            "title": "Thetford Style II OM Permanent RV Toilet 42088",
            "brand": "Thetford",
            "page": 3,
            "label": "page",
            "caption": "Thetford Style II OM Permanent RV Toilet 42088, page 3",
            "png": b"\x89PNG\r\n\x1a\nfake-page",
            "image_path": "library/doc3-p3-page.png",
            "category_name": "Plumbing / Toilets",
        })
        self.assertTrue(_page_has_art(rows, "42088", 3))
        transcript, profile, problems, _raw, _rewrites, _guards = _play(
            rows, chunks, live=False, library=found
        )
        self.assertEqual(problems, [], problems)
        t2 = transcript.split("T2 Tech:", 1)[1].split("T3 Tech:", 1)[0]
        self.assertIn("Figure:", t2)
        self.assertIn("page 3", t2.lower())
        self.assertIn("on this page", t2.lower())
        self.assertIn("water supply line", t2.lower())
        self.assertIn("back of the toilet", t2.lower())
        self.assertIn("then do that check and tell me what you see", t2.lower())
        self.assertNotIn("good result", t2.lower())
        self.assertNotIn("bad result", t2.lower())
        self.assertNotIn("dry", t2.lower())
        self.assertNotIn("no picture", t2.lower())
        self.assertNotIn("page 7", t2.lower())
        self.assertNotRegex(t2, r"Step 1")
        named = {rule.name: rule for rule in profile_check.check_transcript(profile)}
        self.assertTrue(named["no_repeats"].ok, named["no_repeats"].detail)
        self.assertTrue(named["figures_only_when_asked"].ok)

    def test_a_show_me_is_exempt_from_the_tool_and_result_rules(self):
        """A show-me answers where it is. The tool and good/bad rules stay on the checks."""
        from scripts.thetford_live_gate import _raw_manual_problems
        import scripts.profile_check as profile_check

        raw = (
            "USER: Thetford 42070 leaks under the flush lever\n"
            "ASSISTANT:\n"
            "Go to the water valve. You use a flashlight. Check the supply connection.\n"
            "A good result is the supply connection stays dry.\n"
            "A bad result is water comes out.\n"
            "Tell me what you see.\n"
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3\n\n"
            "USER: Show me where that connection is\n"
            "ASSISTANT:\n"
            "The manual has no picture of this spot.\n"
            "The water supply line connection is at the back of the toilet, on the water valve.\n"
            "Send a photo of that connection.\n"
            "Then do that check and tell me what you see.\n"
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3\n\n"
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\n"
            "Go to the vacuum breaker. You flush and watch it.\n"
            "A good result is no leak while flushing.\n"
            "A bad result is it leaks only while flushing.\n"
            "Tell me what you see.\n"
            "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 1\n\n"
            "USER: No leak while flushing. The water valve weeps at the pedal.\n"
            "ASSISTANT:\n"
            "This is the water valve kit 42109 job. The valve is at the pedal.\n"
            "Turn the RV water off.\n"
            "The closet bolts are at the floor, on the closet flange.\n"
            "Take the toilet off the closet bolts.\n"
            "Use a 1/2-inch wrench.\n"
            "A good result is the toilet is off the closet bolts and the water is off.\n"
            "A bad result is the toilet is still on the closet bolts, or water still comes out.\n"
            "I can walk the rest with you, one step at a time.\n"
            "The Bay PDF has the full list.\n"
            "Tell me what you see.\n"
            "📖 Source: Thetford Water Valve Kit 42109, page 1\n"
        )
        self.assertEqual(_raw_manual_problems(raw), [])
        named = {rule.name: rule for rule in profile_check.check_transcript(raw)}
        self.assertTrue(named["labeled_good_bad"].ok, named["labeled_good_bad"].detail)
        self.assertEqual(named["score-2"].status, "PASS")
        no_tool = raw.replace("You use a flashlight. ", "")
        self.assertIn("RAW T1 names no tool", _raw_manual_problems(no_tool))
        repeated = raw.replace(
            "Then do that check and tell me what you see.",
            "A good result is the connection stays dry.\n"
            "A bad result is the leak persists from the water valve.\n"
            "Tell me what you see.",
        )
        problems = _raw_manual_problems(repeated)
        self.assertIn("RAW T2 repeats a good or bad result", problems)
        self.assertIn("RAW T2 does not point back to the pending check", problems)
        self.assertNotIn("RAW T2 names no tool", problems)
        awkward = raw.replace(
            "Take the toilet off the closet bolts.",
            "Check the toilet coming off the closet bolts.",
        )
        problems = _raw_manual_problems(awkward)
        self.assertIn("RAW T4 does not say take the toilet off the closet bolts", problems)
        self.assertIn("RAW T4 checks the toilet coming off instead of taking it off", problems)
        unlabeled = (
            "USER: Thetford 42070 leaks under the flush lever\n"
            "ASSISTANT:\n"
            "Go to the water valve. You check the supply connection. Tell me what you see.\n"
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(unlabeled)}
        self.assertFalse(named["labeled_good_bad"].ok)

    def test_a_how_detail_is_not_appended(self):
        leaked = "How (Thetford, page 3): Tools: not stated. Meter setting: not stated."
        self.assertEqual(_keep_figure_detail(leaked, "Check the valve."), "")
        self.assertEqual(_keep_figure_detail("Use a 1/2-inch wrench.", "Check the valve."), "Use a 1/2-inch wrench.")
