"""BAL Soft-Touch SS 5.1 tongue-only dead: panel 20300427, not coupler or fuse first."""
import unittest

from bay_procedure import (
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
    rewrite_bay_search_symptom,
)
from gd_library_coach import (
    BAL_TONGUE_SEARCH_BOOST,
    is_bal_soft_touch_tongue_only_context,
    is_stabilizer_override_pin_context,
    rank_chunks_for_bal_tongue,
)

WO = (
    "BAL Soft-Touch SS 5.1 electric tongue jack dead. "
    "Other stabilizers and panel lights work. Motor OK on direct 12V. Coupler OK."
)

PANEL_PAGE = {
    "title": "BAL SS 5.1 Stabilizing System INS.STA.001",
    "category": "Leveling",
    "page": 4,
    "excerpt": (
        "Tongue jack will not extend. If the motor operates on direct 12V and the coupler "
        "is engaged, the issue is the user panel 20300427 or the wiring between the panel and jack."
    ),
}
COUPLER_PAGE = {
    "title": "BAL tongue jack coupler",
    "category": "Leveling",
    "page": 2,
    "excerpt": "Replace the coupler 21700072. Shear pin. Coupler replacement is the repair.",
}
FUSE_PAGE = {
    "title": "BAL power supply",
    "category": "Leveling",
    "page": 1,
    "excerpt": "Check the 30A fuse and the remote stabilizer harness before any jack.",
}
COUPLER_FIRST = (
    "Replace the coupler 21700072 and the shear pin. "
    "Then check the 30A fuse and the remote stab harness."
)
FUSE_FIRST = (
    "Start with the 30A fuse and the remote stabilizer harness. "
    "The tongue jack fuse is open."
)


def _pdf_text(pdf: bytes) -> str:
    try:
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


class TestBalTongueContext(unittest.TestCase):

    def test_psx1_and_all_jacks_dead_are_not_this_path(self):
        psx1 = (
            "Lippert PSX1 front stabilizer. Power works. Manual override will not engage. "
            "Roll pin seized at the override coupler."
        )
        self.assertFalse(is_bal_soft_touch_tongue_only_context("Leveling", "PSX1", psx1))
        self.assertTrue(is_stabilizer_override_pin_context("Leveling", "PSX1", psx1))
        all_dead = (
            "BAL Soft-Touch SS 5.1 all jacks dead. Panel lights are out. Tongue jack dead."
        )
        self.assertFalse(is_bal_soft_touch_tongue_only_context("Leveling", "BAL", all_dead))


class TestBalTongueBayAndRank(unittest.TestCase):
    def test_panel_page_outranks_coupler_and_fuse(self):
        q = rewrite_bay_search_symptom("Leveling", "BAL SS 5.1", WO)
        self.assertIn("20300427", q)
        self.assertIn("ins.sta.001", q.lower())
        self.assertIn("20300427", BAL_TONGUE_SEARCH_BOOST)
        ranked = rank_chunks_for_bal_tongue([FUSE_PAGE, COUPLER_PAGE, PANEL_PAGE], q, limit=3)
        self.assertEqual(ranked[0]["title"], PANEL_PAGE["title"])
        titles = [row["title"] for row in ranked]
        self.assertNotIn(COUPLER_PAGE["title"], titles)
        self.assertNotIn(FUSE_PAGE["title"], titles)


if __name__ == "__main__":
    unittest.main()
