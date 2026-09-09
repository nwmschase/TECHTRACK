"""Figure / terminal page retrieval: prefer real SM diagrams over Quick Notes p.13."""
import unittest

from gd_library_coach import (
    FIGURE_PAGE_HONESTY,
    FIGURE_SEARCH_BOOST,
    FURRION_FCR_BOARD_FIGURE_PAGES,
    figure_library_search_boost,
    page_has_figure_or_terminal_layout,
    page_is_text_only_notes,
    pick_diagram_page_numbers,
    rank_chunks_for_figure_ask,
    score_figure_page,
    wants_board_or_terminal_figure,
    wants_library_page_shown,
)

FURRION = "Furrion FCR08/FCR10 SM CCD-0008122"

# Shop-typical OCR/index text for CCD-0008122 (Chase live miss was p.13).
FURRION_PAGES = [
    {
        "page": 13,
        "title": FURRION,
        "excerpt": (
            "Troubleshooting Instructions\nQuick Notes\n"
            "Nominal voltage: 12 V DC\n"
            "Check supply voltage at the refrigerator.\n"
            "If voltage is below specification, charge the battery.\n"
            "Output of the compressor circuit should be within spec."
        ),
    },
    {
        "page": 11,
        "title": FURRION,
        "excerpt": (
            "Wiring diagram\nFig. 1 Refrigerator wiring schematic\n"
            "12V DC input, compressor, fan connections."
        ),
    },
    {
        "page": 16,
        "title": FURRION,
        "excerpt": (
            "Fig. 2 Inverter PCB\n"
            "Fig. 3 Diagnostic LED terminals D and +\n"
            "Fig. 4 Board layout showing output terminals"
        ),
    },
    {
        "page": 17,
        "title": FURRION,
        "excerpt": (
            "Fig. 4 Inverter board terminal identification\n"
            "D / + diagnostic LED clip-on points on the inverter PCB"
        ),
    },
    {
        "page": 27,
        "title": FURRION,
        "excerpt": (
            "Error Code — Fan Fault Diagnostics\n"
            "Fig. 21 Locate the inverter PCB. "
            "Measure voltage at the F+ and F− terminals."
        ),
    },
    {
        "page": 45,
        "title": FURRION,
        "excerpt": "Fig. 68 Housing labels\nFig. 69 Terminal identification on the refrigerator housing",
    },
    {
        "page": 46,
        "title": FURRION,
        "excerpt": "Fig. 69 Housing labels continued — terminal callouts on the cabinet.",
    },
]

DIAGRAM_PAGES = {11, 16, 17, 27, 45, 46}


class TestBoardFigureAskDetect(unittest.TestCase):
    def test_chase_live_phrases(self):
        for msg in (
            "show me the page with output terminals labeled",
            "inverter PCB terminals",
            "show me labeled PCB",
            "inverter board layout",
            "where are the F+ F- terminals",
            "pinout on the inverter",
            "housing labels",
        ):
            self.assertTrue(wants_board_or_terminal_figure(msg), msg)
            self.assertTrue(wants_library_page_shown(msg), msg)

    def test_plain_result_is_not_a_board_figure_ask(self):
        self.assertFalse(wants_board_or_terminal_figure("paper moved left suck right blow"))
        self.assertFalse(wants_board_or_terminal_figure("fuse blown and replaced"))


class TestFigureQueryRewrite(unittest.TestCase):
    def test_boost_has_figure_terms_not_quick_notes(self):
        boost = figure_library_search_boost("show me the page with output terminals labeled")
        self.assertEqual(boost, FIGURE_SEARCH_BOOST)
        low = boost.lower()
        self.assertIn("fig", low)
        self.assertIn("inverter", low)
        self.assertIn("pcb", low)
        self.assertIn("wiring", low)
        self.assertNotIn("nominal voltage", low)
        self.assertNotIn("quick notes", low)

    def test_honesty_rule_forbids_invented_pads(self):
        t = FIGURE_PAGE_HONESTY.lower()
        self.assertIn("no diagram", t)
        self.assertIn("do not invent pad locations", t)
        self.assertIn("quick notes", t)


class TestPageLayoutGuard(unittest.TestCase):
    def test_page_13_is_text_only(self):
        p13 = FURRION_PAGES[0]["excerpt"]
        self.assertFalse(page_has_figure_or_terminal_layout(p13))
        self.assertTrue(page_is_text_only_notes(p13))

    def test_inverter_and_housing_pages_are_diagrams(self):
        for row in FURRION_PAGES:
            if row["page"] == 13:
                continue
            self.assertTrue(
                page_has_figure_or_terminal_layout(row["excerpt"]),
                f"page {row['page']} should look like a figure",
            )
            self.assertFalse(page_is_text_only_notes(row["excerpt"]))


class TestFurrionFigureRanking(unittest.TestCase):
    def _top_pages(self, query, limit=3):
        ranked = rank_chunks_for_figure_ask(FURRION_PAGES, query, limit=limit)
        return [int(p["page"]) for p in ranked]

    def test_output_terminals_labeled_prefers_diagram_over_p13(self):
        query = "show me the page with output terminals labeled"
        top = self._top_pages(query)
        self.assertNotIn(13, top)
        self.assertTrue(any(p in DIAGRAM_PAGES for p in top), top)
        self.assertTrue(any(p in (16, 17, 27, 45) for p in top), top)
        self.assertLess(
            score_figure_page(FURRION_PAGES[0], query),
            score_figure_page(next(p for p in FURRION_PAGES if p["page"] == 16), query),
        )

    def test_inverter_pcb_terminals_prefers_board_pages(self):
        query = "inverter PCB terminals"
        top = self._top_pages(query)
        self.assertNotIn(13, top)
        self.assertTrue(any(p in (16, 17, 27) for p in top), top)

    def test_rank_drops_quick_notes_when_figure_exists(self):
        ranked = rank_chunks_for_figure_ask(FURRION_PAGES, "inverter PCB terminals", limit=8)
        pages = [int(p["page"]) for p in ranked]
        self.assertNotIn(13, pages)
        self.assertIn(16, pages)

    def test_pick_diagram_pages_skips_p13(self):
        query = "show me the page with output terminals labeled"
        picked = pick_diagram_page_numbers(FURRION_PAGES, query, FURRION)
        self.assertTrue(picked)
        self.assertNotIn(13, picked)
        self.assertTrue(set(picked) <= DIAGRAM_PAGES | set(FURRION_FCR_BOARD_FIGURE_PAGES))

    def test_furrion_hint_fallback_when_only_quick_notes_retrieved(self):
        only_notes = [FURRION_PAGES[0]]
        picked = pick_diagram_page_numbers(
            only_notes,
            "show me the page with output terminals labeled",
            FURRION,
        )
        self.assertTrue(picked)
        self.assertNotIn(13, picked)
        self.assertTrue(all(p in FURRION_FCR_BOARD_FIGURE_PAGES for p in picked))


if __name__ == "__main__":
    unittest.main()
