"""Level Up Advantage / 807662 library retrieval: prefer Level-Up/OCTP/TI over Unity."""
import unittest

from gd_library_coach import (
    LEVEL_UP_PRODUCT_LOCK,
    LEVEL_UP_SEARCH_BOOST,
    claims_level_up_library_empty,
    drop_unity_chunks_for_level_up,
    figure_library_search_boost,
    figure_render_honesty_note,
    format_level_up_library_honesty,
    is_ground_control_manual,
    is_level_up_advantage_context,
    is_level_up_library_title,
    is_unity_board_manual,
    level_up_search_symptom,
    rank_chunks_for_level_up,
    score_level_up_product,
    skip_unity_for_level_up,
)

CHASE_MODEL = (
    "Lippert Level Up Advantage Leveling Controller w/ Slide Output, label 807662 / 25499"
)
CHASE_CONCERN = (
    "Manual Mode flashes then returns to home/first screen. "
    "Connectors: Touch Pad, Remote Sensor, Pump, CAN, Slide Output, Power."
)
CHASE_QUERY = f"{CHASE_MODEL} {CHASE_CONCERN} LCD wiring"

UNITY = {
    "title": "Lippert OneControl M Series Unity Board SM",
    "category": "Electrical",
    "excerpt": (
        "OneControl Unity M-Series reversing output for awning and slide. "
        "BAT1 BAT2 X270 hold EXTEND RETRACT polarity reverse."
    ),
    "page": 4,
}
TI005 = {
    "title": "TI-005 Electronic Leveling Troubleshooting Guide",
    "category": "Leveling",
    "excerpt": (
        "Level-Up hydraulic leveling controller Manual Mode. "
        "Touch pad LCD returns to home screen. Pump and slide output."
    ),
    "page": 2,
}
QR092 = {
    "title": "QR-092 Level-Up OCTP wiring",
    "category": "Leveling",
    "excerpt": "Level-Up OCTP touch pad LCD wiring diagram. Controller harness.",
    "page": 1,
}
QR059 = {
    "title": "QR-059 ID guide",
    "category": "ID & Reference",
    "excerpt": "Identify Level-Up leveling controller 807662 vs other Lippert boards.",
    "page": 1,
}
TI170 = {
    "title": "TI-170",
    "category": "Leveling",
    "excerpt": "Level-Up leveling notes and controller identification.",
    "page": 1,
}
GROUND = {
    "title": "Ground Control LCD SM",
    "category": "Leveling",
    "excerpt": "Ground Control electric leveling LCD. Not hydraulic Level Up 807662.",
    "page": 3,
}

LIBRARY = [UNITY, TI005, QR092, QR059, TI170, GROUND]


class TestLevelUpDetect(unittest.TestCase):
    def test_chase_bay_job(self):
        self.assertTrue(
            is_level_up_advantage_context("Leveling", CHASE_MODEL, CHASE_CONCERN)
        )
        self.assertTrue(skip_unity_for_level_up("Leveling", CHASE_MODEL, CHASE_CONCERN))

    def test_part_numbers_and_octp(self):
        self.assertTrue(is_level_up_advantage_context("", "807662", "won't dump"))
        self.assertTrue(is_level_up_advantage_context("", "25499", "Manual Mode"))
        self.assertTrue(is_level_up_advantage_context("Leveling", "", "OCTP wiring"))

    def test_ground_control_alone_is_not_level_up_advantage(self):
        self.assertFalse(
            is_level_up_advantage_context("Leveling", "Ground Control LCD", "no display")
        )
        self.assertTrue(is_ground_control_manual("Ground Control LCD SM"))

    def test_fridge_is_not_level_up(self):
        self.assertFalse(
            is_level_up_advantage_context("Refrigerators", "Furrion FCR10", "not cooling")
        )


class TestLevelUpQueryRewrite(unittest.TestCase):
    def test_boost_prefers_level_up_not_unity(self):
        q = level_up_search_symptom("Leveling", CHASE_MODEL, CHASE_CONCERN)
        low = q.lower()
        self.assertIn("807662", low)
        self.assertIn("ti-005", low)
        self.assertIn("octp", low)
        self.assertIn("qr-092", low)
        self.assertIn("level-up", low)
        self.assertNotIn("unity", low)
        self.assertNotIn("x270", low)
        self.assertNotIn("onecontrol", low)
        self.assertNotIn("awning", low)
        self.assertIn("level up", LEVEL_UP_SEARCH_BOOST.lower())

    def test_non_level_up_unchanged(self):
        raw = "fridge not cooling cavity light on"
        self.assertEqual(level_up_search_symptom("Refrigerators", "FCR10", raw), raw)

    def test_figure_boost_adds_level_up_terms(self):
        boost = figure_library_search_boost(
            "show the Level Up Advantage 807662 LCD wiring diagram"
        )
        low = boost.lower()
        self.assertIn("ti-005", low)
        self.assertIn("octp", low)
        self.assertNotIn("unity", low)


class TestLevelUpRanking(unittest.TestCase):
    def test_manual_mode_prefers_ti_and_octp_over_unity(self):
        ranked = rank_chunks_for_level_up(LIBRARY, CHASE_QUERY, limit=4)
        titles = [r["title"] for r in ranked]
        self.assertIn(TI005["title"], titles)
        self.assertTrue(any("OCTP" in t or "TI-005" in t or "TI-170" in t or "QR-059" in t for t in titles))
        self.assertNotIn(UNITY["title"], titles)
        self.assertGreater(
            score_level_up_product(TI005, CHASE_QUERY),
            score_level_up_product(UNITY, CHASE_QUERY),
        )
        self.assertGreater(
            score_level_up_product(QR092, CHASE_QUERY),
            score_level_up_product(UNITY, CHASE_QUERY),
        )

    def test_lcd_wiring_prefers_qr092_over_unity(self):
        ranked = rank_chunks_for_level_up(LIBRARY, "Level Up Advantage 807662 LCD wiring", limit=3)
        titles = [r["title"] for r in ranked]
        self.assertIn(QR092["title"], titles)
        self.assertNotIn(UNITY["title"], titles)

    def test_unity_dropped_even_if_only_competitor_when_level_up_exists(self):
        kept = drop_unity_chunks_for_level_up([UNITY, TI005])
        self.assertEqual([k["title"] for k in kept], [TI005["title"]])

    def test_ground_control_loses_to_hydraulic_level_up(self):
        self.assertGreater(
            score_level_up_product(TI005, CHASE_QUERY),
            score_level_up_product(GROUND, CHASE_QUERY),
        )

    def test_title_helpers(self):
        self.assertTrue(is_level_up_library_title(TI005["title"]))
        self.assertTrue(is_level_up_library_title(QR092["title"]))
        self.assertFalse(is_level_up_library_title(UNITY["title"]))
        self.assertFalse(is_level_up_library_title(GROUND["title"]))
        self.assertTrue(is_unity_board_manual(UNITY["title"]))


class TestLevelUpHonesty(unittest.TestCase):
    def test_does_not_claim_empty_when_titles_exist(self):
        catalog = [
            {"title": TI005["title"], "indexed": False, "chunk_count": 0},
            {"title": QR092["title"], "indexed": True, "chunk_count": 2},
            {"title": UNITY["title"], "indexed": True, "chunk_count": 20},
        ]
        note = format_level_up_library_honesty(catalog, chunks=None)
        self.assertIn("DOES include", note)
        self.assertIn("TI-005", note)
        self.assertIn("re-index", note.lower().replace("reindex", "re-index"))
        self.assertIn("Unity", note)
        self.assertNotIn("does not include Level Up", note)
        self.assertFalse(claims_level_up_library_empty(note))

    def test_empty_claim_detector(self):
        bad = (
            "The shop Document Library does not include Level Up controller diagnostics. "
            "I only have the OneControl Unity board manual."
        )
        self.assertTrue(claims_level_up_library_empty(bad))
        good = (
            "TI-005 Electronic Leveling Troubleshooting Guide is in the shop library "
            "but is not indexed. Ask a manager to re-index it."
        )
        self.assertFalse(claims_level_up_library_empty(good))

    def test_product_lock_forbids_unity_substitute(self):
        t = LEVEL_UP_PRODUCT_LOCK.lower()
        self.assertIn("never cite", t)
        self.assertIn("unity", t)
        self.assertIn("re-index", t)
        self.assertIn("807662", t)

    def test_figure_render_fail_names_level_up_not_missing_library(self):
        note = figure_render_honesty_note(TI005["title"], True)
        self.assertIn("TI-005", note)
        self.assertIn("could not render", note.lower())
        self.assertNotIn("lacks the procedure", note.lower())
        unity_note = figure_render_honesty_note(UNITY["title"], True)
        self.assertIn("wrong book", unity_note.lower())
        self.assertIn("level-up", unity_note.lower())


if __name__ == "__main__":
    unittest.main()
