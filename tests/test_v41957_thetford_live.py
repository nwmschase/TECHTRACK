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


    def test_a_bare_valve_start_fails_and_a_tall_crop_fails(self):
        bare = (
            "USER: No leak while flushing. The water valve weeps at the pedal.\n"
            "ASSISTANT:\nTurn off the water to the RV.\nWhat do you see?\n"
            "📖 Source: Thetford Water Valve Kit 42109, page 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(bare)}
        self.assertEqual(named["score-2"].status, "FAIL")
        named_place = (
            "USER: No leak while flushing. The water valve weeps at the pedal.\n"
            "ASSISTANT:\nGo to the water valve.\nUse a 1/2-inch wrench and pliers.\n"
            "Turn off the water to the RV.\nA bad result is water still comes out.\n"
            "What do you see?\n"
            "📖 Source: Thetford Water Valve Kit 42109, page 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(named_place)}
        self.assertNotEqual(named["score-2"].status, "FAIL")

