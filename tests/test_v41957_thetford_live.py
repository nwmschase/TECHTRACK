"""v4.19.57: the live library path, not the direct kit compile, keeps the Thetford sheet.

Live R2 is not on this machine. tests/fixtures/thetford_live_retrieval.json is the
900/120 chunk windows and figure labels the indexer stores for 42088, 42109, and
34123/34122. PNG bytes are read back from those same PDFs, which is what
attach_pngs does when the object is local.
"""
import json
import unittest
from pathlib import Path

import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import apply_chunk_figures, compile_bay_procedure, render_bay_procedure_pdf
from gd_library_coach import ensure_thetford_flush_reply

import scripts.profile_check as profile_check

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "thetford_live_retrieval.json"
ROOT = FIXTURE.parent
CONCERN = "Thetford 42070 leaks under the flush lever"
OM = "Thetford Style II OM Permanent RV Toilet 42088"


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _png_index():
    found = {}
    for name in (
        "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf",
        "34123-34122-VacBrkr-1.pdf",
    ):
        indexed = mf.index_pdf_bytes((ROOT / name).read_bytes())
        for fig in indexed["figures"]:
            found[(fig.get("page"), fig.get("label") or "")] = fig.get("png") or b""
    return found


def _live_procedure():
    payload = _load()
    pngs = _png_index()
    chunks = list(payload["chunks"])
    rows = []
    for fig in payload["figures"]:
        row = dict(fig)
        row["png"] = pngs.get((fig.get("page"), fig.get("label") or ""), b"")
        row["category_name"] = "Plumbing / Toilets"
        rows.append(row)
    proc = compile_bay_procedure(
        concern=CONCERN,
        brand="Thetford",
        model="42070",
        category="Plumbing / Toilets",
        chunks=chunks,
    )
    job = f"{proc.category} {proc.brand} {proc.model} {proc.concern}"
    packets = fb.figure_packets(rows, chunks, job)
    for packet in packets:
        packet["figures"] = [fig for fig in packet.get("figures") or [] if fig.get("png")]
    packets = [packet for packet in packets if packet.get("figures")]
    return apply_chunk_figures(proc, packets)


class TestLiveRetrievalFixture(unittest.TestCase):
    def test_fixture_is_the_indexer_window_shape(self):
        payload = _load()
        self.assertIn("42088", payload["note"])
        self.assertGreaterEqual(len(payload["chunks"]), 10)
        self.assertTrue(any(len(chunk["excerpt"]) <= 900 for chunk in payload["chunks"]))
        titles = {chunk["title"] for chunk in payload["chunks"]}
        self.assertTrue(any("42088" in title for title in titles))
        self.assertTrue(any("42109" in title for title in titles))
        self.assertTrue(any("3412" in title for title in titles))
        labels = " ".join(fig["label"] for fig in payload["figures"])
        self.assertIn("Fig. 1", labels)


class TestLiveFigureAttachKeepsEveryBranch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = _live_procedure()
        cls.pdf = render_bay_procedure_pdf(cls.proc)

    def test_every_flowchart_outcome_keeps_a_branch(self):
        titles = " ".join(item.get("title") or "" for item in self.proc.procedures)
        self.assertIn("Supply", titles)
        self.assertRegex(titles, r"3412")
        self.assertIn("42109", titles)
        self.assertIn("Flange", titles)
        self.assertGreaterEqual(len(self.proc.procedures), 4)
        for procedure in self.proc.procedures:
            sections = {step.get("section") for step in procedure.get("steps") or []}
            self.assertIn("removal", sections, procedure.get("title"))
            self.assertIn("installation", sections, procedure.get("title"))
            for number, step in enumerate(procedure.get("steps") or [], 1):
                lines = mf.step_body_lines(step, show_figure=False)
                self.assertTrue(
                    any(line.startswith("Next:") for line in lines),
                    mf.step_heading(step, number),
                )
                heading = mf.step_heading(step, number)
                self.assertNotIn("Put the vot", heading)
                self.assertNotRegex(heading, r"\bwl\b")

    def test_tools_bad_do_not_and_flush_line(self):
        valve = next(item for item in self.proc.procedures if "42109" in (item.get("title") or ""))
        tool_blob = " ".join(
            [(step.get("fields") or {}).get("TOOLS / METER SETTING") or "" for step in valve.get("steps") or []]
            + list(valve.get("before") or [])
        )
        self.assertIn("wrench", tool_blob.lower())
        self.assertIn("plier", tool_blob.lower())
        self.assertNotRegex(tool_blob, r"(?i)^Tools: a towel\.?$")
        sheet = []
        for procedure in self.proc.procedures:
            for number, step in enumerate(procedure.get("steps") or [], 1):
                sheet.append(mf.step_heading(step, number))
                sheet.extend(mf.step_body_lines(step, show_figure=False))
        blob = "\n".join(sheet)
        self.assertNotIn("Flush 3 times. dry", blob)
        self.assertNotIn("Put the vot", blob)
        for line in blob.splitlines():
            if not line.startswith("Bad looks like:"):
                continue
            self.assertTrue(mf._bad_worth_printing(line.split(":", 1)[1]), line)
        do_not = " ".join(self.proc.do_not).lower()
        self.assertNotIn("antifreeze", do_not)
        self.assertNotIn("ice", do_not)
        self.assertNotIn("scouring", do_not)
        self.assertFalse(any("How (" in line for line in self.proc.bay_order))

    def test_profile_check_has_no_fail(self):
        rules = profile_check.check_pdf_bytes(self.pdf)
        failed = [rule for rule in rules if rule.status == "FAIL"]
        self.assertEqual(failed, [], failed)
        named = {rule.name: rule for rule in rules}
        self.assertEqual(named["PF-10"].status, "PASS")
        self.assertEqual(named["PF-15"].status, "PASS")
        self.assertIn("Result: 10/10.", profile_check.gate_summary(rules))
        manual = [rule.name for rule in rules if rule.name.startswith("PF-") and rule.status == "MANUAL"]
        self.assertEqual(manual, ["PF-32"])


class TestShowMeReply(unittest.TestCase):
    def test_supply_show_me_names_the_connection_and_page_3(self):
        supply = mf.thetford_proving_line("supply")
        self.assertIn("back of the toilet, on the water valve", supply)
        self.assertIn("page 3", supply)
        history = [
            {"role": "user", "content": CONCERN},
            {"role": "assistant", "content": supply},
        ]
        reply = ensure_thetford_flush_reply(
            "How (Thetford, page 7): Tools: not stated. Meter setting: not stated.",
            history,
            "show me",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertIn("back of the toilet, on the water valve", reply)
        self.assertNotIn("How (", reply)
        self.assertNotIn("Meter setting: not stated", reply)
        page7 = {
            "id": 7,
            "document_id": 9,
            "kind": "figure",
            "title": OM,
            "brand": "Thetford",
            "page": 7,
            "label": "Step 1",
            "png": b"\x89PNG\r\n\x1a\npage7",
            "category_name": "Plumbing / Toilets",
        }
        page3 = {
            "id": 3,
            "document_id": 9,
            "kind": "page",
            "title": OM,
            "brand": "Thetford",
            "page": 3,
            "label": "page",
            "png": b"\x89PNG\r\n\x1a\npage3",
            "category_name": "Plumbing / Toilets",
        }
        offers = fb.offers_for_turn(
            [page7, page3], supply, "it leaks under the lever", "Plumbing / Toilets", "Thetford 42070"
        )
        self.assertEqual(len(offers), 1)
        self.assertEqual(int(offers[0]["page"]), 3)
        caption = fb.gd_figure_caption(offers[0])
        self.assertIn("page 3", caption)
        self.assertNotIn("page 7", caption)
        self.assertNotIn("Step 1", caption)


class TestBayTabCopy(unittest.TestCase):
    def test_the_form_describes_branches(self):
        source = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn("Repair branches:", source)
        self.assertNotIn("Bay-order steps:", source)
        self.assertIn("one numbered branch", source)


class TestReviewDefectsFail(unittest.TestCase):
    """The pre-merge misses stay failures. A clean sheet is not a weaker check."""

    def test_bare_vacuum_near_copy_marker_and_page_clash_fail(self):
        bare = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\n"
            "Check the vacuum breaker on page 3.\n"
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(bare)}
        self.assertEqual(named["score-2"].status, "FAIL")
        clash = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\n"
            "Bad result: it leaks while flushing. What do you see? Owner manual page 1 shows the kit.\n"
            "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(clash)}
        self.assertEqual(named["score-1"].status, "FAIL")
        copied = (
            "The water supply connection is at the back of the toilet on the water valve "
            "and the fitting should be dry before you open a kit."
        )
        dup = (
            f"USER: one\nASSISTANT:\n{copied}\n\n"
            f"USER: two\nASSISTANT:\n{copied} The cited manual page shows that connection.\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(dup)}
        self.assertEqual(named["no_repeats"].status, "FAIL")
        leaked = "USER: one\nASSISTANT:\nPull the pedal up and off.\n<!--gd-step:1-->\n"
        banned = [rule for rule in profile_check.check_transcript(leaked) if rule.name == "banned_strings"]
        self.assertEqual(banned[0].status, "FAIL")

    def test_duplicate_pod_and_scouring_fail(self):
        pod = (
            "Thetford 42070\n"
            "REPAIR BRANCH\nVacuum breaker 34123\n"
            "REMOVAL\n"
            "Step 12: Take off the pod\nDo this:\n1. Take off the pod.\n"
            "Step 14: Take off the pod\nDo this:\n1. Take off the pod.\n"
        )
        named = {rule.name: rule for rule in profile_check.grade_past_fails(None, pod)}
        self.assertEqual(named["PF-09"].status, "FAIL")
        banned = [
            rule
            for rule in profile_check.check_transcript(
                "USER: x\nASSISTANT:\nDo not use scouring powders.\n"
            )
            if rule.name == "banned_strings"
        ]
        self.assertEqual(banned[0].status, "FAIL")
