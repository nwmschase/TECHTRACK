"""Air Conditioning library retrieval: prefer Furrion/Dometic rooftop AC over Unity."""
import unittest

from gd_library_coach import (
    AC_PRODUCT_LOCK,
    AC_SEARCH_BOOST,
    ac_search_symptom,
    claims_ac_library_empty,
    drop_unity_chunks_for_ac,
    figure_library_search_boost,
    figure_render_honesty_note,
    format_ac_library_honesty,
    is_ac_library_title,
    is_air_conditioning_context,
    is_unity_board_manual,
    rank_chunks_for_ac,
    score_ac_product,
    skip_unity_for_ac,
    tech_asks_unity_for_ac_controls,
)

CHASE_MODEL = "Furrion FACT12SA2 rooftop air conditioner"
CHASE_CONCERN = "No cool. Interior fan runs. Looking for the FACT / rooftop AC procedure."
CHASE_QUERY = f"{CHASE_MODEL} {CHASE_CONCERN}"

UNITY = {
    "title": "Lippert OneControl M Series Unity Board SM",
    "category": "Electrical",
    "excerpt": (
        "OneControl Unity M-Series reversing output for awning and slide. "
        "BAT1 BAT2 X270 hold EXTEND RETRACT polarity reverse."
    ),
    "page": 4,
}
FACT = {
    "title": "Furrion FACT12SA2 Rooftop Air Conditioner SM",
    "category": "Air Conditioning",
    "excerpt": (
        "Furrion FACT rooftop air conditioner no cool diagnostics. "
        "ADB air distribution box. Compressor and indoor fan."
    ),
    "page": 8,
}
BRISK = {
    "title": "Dometic Brisk B57915 Rooftop AC SM",
    "category": "Air Conditioning",
    "excerpt": "Dometic Brisk II B57915 rooftop AC. E2 E3 fault codes. ADB wiring.",
    "page": 3,
}
ADB = {
    "title": "Dometic ADB air distribution box",
    "category": "Air Conditioning",
    "excerpt": "Air distribution box for rooftop air conditioner. Ceiling assembly.",
    "page": 1,
}
FRIDGE = {
    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
    "category": "Refrigerators",
    "excerpt": "12V refrigerator not cooling. Inoperable compressor section.",
    "page": 34,
}

LIBRARY = [UNITY, FACT, BRISK, ADB, FRIDGE]


class TestAcDetect(unittest.TestCase):
    def test_chase_furrion_fact_job(self):
        self.assertTrue(
            is_air_conditioning_context("Air Conditioning", CHASE_MODEL, CHASE_CONCERN)
        )
        self.assertTrue(skip_unity_for_ac("Air Conditioning", CHASE_MODEL, CHASE_CONCERN))
        self.assertTrue(skip_unity_for_ac("Air Conditioning", CHASE_MODEL, CHASE_CONCERN, "Not sure"))

    def test_dometic_brisk_and_adb(self):
        self.assertTrue(is_air_conditioning_context("", "Dometic B57915", "no cool"))
        self.assertTrue(is_air_conditioning_context("Air Conditioning", "Brisk II", "E3"))
        self.assertTrue(is_air_conditioning_context("", "Dometic ADB", "rooftop AC no cool"))
        self.assertTrue(skip_unity_for_ac("Air Conditioning", "Dometic B57915", "won't cool"))

    def test_e2_e3_ac_codes(self):
        self.assertTrue(is_air_conditioning_context("Air Conditioning", "", "E2 on the CCC"))
        self.assertTrue(is_air_conditioning_context("", "Dometic rooftop AC", "E3 code"))

    def test_rooftop_no_cool(self):
        self.assertTrue(is_air_conditioning_context("", "", "rooftop AC not cooling"))
        self.assertTrue(skip_unity_for_ac("", "", "roof AC no cool"))

    def test_explicit_unity_for_ac_is_allowed(self):
        self.assertTrue(
            tech_asks_unity_for_ac_controls(
                "Air Conditioning", CHASE_MODEL, "OneControl thermostat for the AC"
            )
        )
        self.assertFalse(
            skip_unity_for_ac(
                "Air Conditioning", CHASE_MODEL, "Unity / CAN multiplex running the AC"
            )
        )
        self.assertFalse(
            skip_unity_for_ac("Air Conditioning", CHASE_MODEL, CHASE_CONCERN, "Yes")
        )
        self.assertFalse(
            tech_asks_unity_for_ac_controls("Air Conditioning", CHASE_MODEL, "can I check the fan")
        )

    def test_fridge_is_not_ac(self):
        self.assertFalse(
            is_air_conditioning_context("Refrigerators", "Furrion FCR10", "not cooling")
        )
        self.assertFalse(skip_unity_for_ac("Refrigerators", "Furrion FCR10", "not cooling"))

    def test_level_up_is_not_ac(self):
        self.assertFalse(
            is_air_conditioning_context(
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes",
            )
        )


class TestAcQueryRewrite(unittest.TestCase):
    def test_boost_prefers_fact_brisk_not_unity(self):
        q = ac_search_symptom("Air Conditioning", CHASE_MODEL, CHASE_CONCERN)
        low = q.lower()
        self.assertIn("fact12", low)
        self.assertIn("brisk", low)
        self.assertIn("b57915", low)
        self.assertIn("rooftop", low)
        self.assertNotIn("unity", low)
        self.assertNotIn("x270", low)
        self.assertNotIn("onecontrol", low)
        self.assertNotIn("awning", low)
        self.assertIn("fact", AC_SEARCH_BOOST.lower())

    def test_non_ac_unchanged(self):
        raw = "fridge not cooling cavity light on"
        self.assertEqual(ac_search_symptom("Refrigerators", "FCR10", raw), raw)

    def test_figure_boost_adds_ac_terms(self):
        boost = figure_library_search_boost(
            "show the Furrion FACT12SA2 rooftop AC wiring diagram"
        )
        low = boost.lower()
        self.assertIn("fact", low)
        self.assertIn("brisk", low)
        self.assertNotIn("unity", low)


class TestAcRanking(unittest.TestCase):
    def test_no_cool_prefers_fact_and_brisk_over_unity(self):
        ranked = rank_chunks_for_ac(LIBRARY, CHASE_QUERY, limit=4)
        titles = [r["title"] for r in ranked]
        self.assertIn(FACT["title"], titles)
        self.assertTrue(any("Brisk" in t or "FACT" in t or "ADB" in t for t in titles))
        self.assertNotIn(UNITY["title"], titles)
        self.assertGreater(
            score_ac_product(FACT, CHASE_QUERY),
            score_ac_product(UNITY, CHASE_QUERY),
        )
        self.assertGreater(
            score_ac_product(BRISK, CHASE_QUERY),
            score_ac_product(UNITY, CHASE_QUERY),
        )

    def test_dometic_b57915_prefers_brisk_over_unity(self):
        ranked = rank_chunks_for_ac(LIBRARY, "Dometic B57915 Brisk no cool E3", limit=3)
        titles = [r["title"] for r in ranked]
        self.assertIn(BRISK["title"], titles)
        self.assertNotIn(UNITY["title"], titles)

    def test_unity_dropped_even_if_only_competitor_when_ac_exists(self):
        kept = drop_unity_chunks_for_ac([UNITY, FACT])
        self.assertEqual([k["title"] for k in kept], [FACT["title"]])

    def test_fridge_loses_to_rooftop_ac(self):
        self.assertGreater(
            score_ac_product(FACT, CHASE_QUERY),
            score_ac_product(FRIDGE, CHASE_QUERY),
        )

    def test_title_helpers(self):
        self.assertTrue(is_ac_library_title(FACT["title"]))
        self.assertTrue(is_ac_library_title(BRISK["title"]))
        self.assertTrue(is_ac_library_title(ADB["title"]))
        self.assertFalse(is_ac_library_title(UNITY["title"]))
        self.assertFalse(is_ac_library_title(FRIDGE["title"]))
        self.assertTrue(is_unity_board_manual(UNITY["title"]))


class TestAcHonesty(unittest.TestCase):
    def test_does_not_claim_empty_when_titles_exist(self):
        catalog = [
            {"title": FACT["title"], "indexed": False, "chunk_count": 0},
            {"title": BRISK["title"], "indexed": True, "chunk_count": 2},
            {"title": UNITY["title"], "indexed": True, "chunk_count": 20},
        ]
        note = format_ac_library_honesty(catalog, chunks=None)
        self.assertIn("DOES include", note)
        self.assertIn("FACT12SA2", note)
        self.assertIn("re-index", note.lower().replace("reindex", "re-index"))
        self.assertIn("Unity", note)
        self.assertNotIn("does not include", note.lower())
        self.assertFalse(claims_ac_library_empty(note))

    def test_empty_claim_detector(self):
        bad = (
            "The shop Document Library does not include Air Conditioning procedures. "
            "I only have the OneControl Unity board manual."
        )
        self.assertTrue(claims_ac_library_empty(bad))
        good = (
            "Furrion FACT12SA2 Rooftop Air Conditioner SM is in the shop library "
            "but is not indexed. Ask a manager to re-index it."
        )
        self.assertFalse(claims_ac_library_empty(good))

    def test_first_turn_hits_block_unity_only_claim(self):
        note = format_ac_library_honesty(
            [{"title": FACT["title"], "indexed": True, "chunk_count": 4}],
            chunks=[FACT],
        )
        self.assertIn("FACT12SA2", note)
        self.assertFalse(claims_ac_library_empty(note))

    def test_product_lock_forbids_unity_substitute(self):
        t = AC_PRODUCT_LOCK.lower()
        self.assertIn("never cite", t)
        self.assertIn("unity", t)
        self.assertIn("re-index", t)
        self.assertIn("fact", t)
        self.assertIn("b57915", t)

    def test_figure_render_fail_names_ac_not_missing_library(self):
        note = figure_render_honesty_note(FACT["title"], True)
        self.assertIn("FACT12SA2", note)
        self.assertIn("could not render", note.lower())
        self.assertNotIn("lacks the procedure", note.lower())
        unity_note = figure_render_honesty_note(UNITY["title"], True)
        self.assertIn("wrong book", unity_note.lower())
        self.assertIn("air condition", unity_note.lower())


if __name__ == "__main__":
    unittest.main()
