"""Air Conditioning library retrieval: prefer Furrion/Dometic rooftop AC over Unity."""
import unittest

from gd_library_coach import (
    AC_PRODUCT_LOCK,
    AC_SEARCH_BOOST,
    FACR_FREEZE_SEARCH_BOOST,
    ac_search_symptom,
    drop_unity_chunks_for_ac,
    figure_library_search_boost,
    figure_render_honesty_note,
    is_ac_library_title,
    is_air_conditioning_context,
    is_dometic_only_rooftop_ac,
    is_facr_freeze_library_title,
    is_facr_rooftop_freeze_context,
    is_unity_board_manual,
    rank_chunks_for_ac,
    score_ac_product,
)

CHASE_MODEL = "Furrion FACT12SA2 rooftop air conditioner"
CHASE_CONCERN = "No cool. Interior fan runs. Looking for the FACT / rooftop AC procedure."
CHASE_QUERY = f"{CHASE_MODEL} {CHASE_CONCERN}"
FACR_MODEL = "Furrion FACR08HESA2-PS"
FACR_CONCERN = "rooftop freeze / condensate leak from the base pan, ice and frost on the coil"
FACR_QUERY = f"{FACR_MODEL} {FACR_CONCERN}"

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
CCD_7990 = {
    "title": "Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990",
    "category": "Air Conditioning",
    "excerpt": (
        "Furrion rooftop HVAC troubleshooting and service. "
        "Freeze, frost, condensate, base pan, suction icing."
    ),
    "page": 12,
}
CCD_8666 = {
    "title": "Furrion Chill 8K Rooftop Air Conditioner FACR08HESA2 CCD-0008666",
    "category": "Air Conditioning",
    "excerpt": (
        "Furrion Chill FACR08HESA2-PS rooftop air conditioner. "
        "Freeze sensor tripped. Condensate drain and base pan."
    ),
    "page": 18,
}

LIBRARY = [UNITY, FACT, BRISK, ADB, FRIDGE]
FACR_FREEZE_LIBRARY = [UNITY, BRISK, FACT, CCD_8666, CCD_7990, FRIDGE]


class TestAcDetect(unittest.TestCase):


    def test_e2_e3_ac_codes(self):
        self.assertTrue(is_air_conditioning_context("Air Conditioning", "", "E2 on the CCC"))
        self.assertTrue(is_air_conditioning_context("", "Dometic rooftop AC", "E3 code"))


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


    def test_figure_render_fail_names_ac_not_missing_library(self):
        note = figure_render_honesty_note(FACT["title"], True)
        self.assertIn("FACT12SA2", note)
        self.assertIn("could not render", note.lower())
        self.assertNotIn("lacks the procedure", note.lower())
        unity_note = figure_render_honesty_note(UNITY["title"], True)
        self.assertIn("wrong book", unity_note.lower())
        self.assertIn("air condition", unity_note.lower())


class TestFacrFreezeRetrieval(unittest.TestCase):
    def test_facr_freeze_context(self):
        self.assertTrue(
            is_facr_rooftop_freeze_context("Air Conditioning", FACR_MODEL, FACR_CONCERN)
        )
        self.assertTrue(
            is_facr_rooftop_freeze_context("", FACR_MODEL, "base pan ice / melt leak")
        )
        self.assertTrue(
            is_facr_rooftop_freeze_context("", "FACR08HESA2-PS", "suction icing")
        )
        self.assertFalse(
            is_facr_rooftop_freeze_context("Air Conditioning", CHASE_MODEL, CHASE_CONCERN)
        )
        self.assertFalse(
            is_facr_rooftop_freeze_context(
                "Refrigerators", "Furrion FCR10DCGTA", "icing up on rear wall"
            )
        )
        self.assertFalse(
            is_facr_rooftop_freeze_context("Air Conditioning", "Dometic B57915", "no cool")
        )

    def test_boost_prefers_7990_and_8666_titles(self):
        q = ac_search_symptom("Air Conditioning", FACR_MODEL, FACR_CONCERN)
        low = q.lower()
        self.assertIn("ccd-0007990", low)
        self.assertIn("ccd-0008666", low)
        self.assertIn("rooftop hvac troubleshooting", low)
        self.assertIn("furrion chill", low)
        self.assertIn("condensate", low)
        self.assertIn("base pan", FACR_FREEZE_SEARCH_BOOST.lower())
        self.assertNotIn("unity", low)

    def test_facr_freeze_ranks_7990_and_allows_8666(self):
        ranked = rank_chunks_for_ac(FACR_FREEZE_LIBRARY, FACR_QUERY, limit=4)
        titles = [r["title"] for r in ranked]
        self.assertIn(CCD_7990["title"], titles)
        self.assertIn(CCD_8666["title"], titles)
        self.assertNotIn(UNITY["title"], titles)
        self.assertNotIn(BRISK["title"], titles)
        self.assertGreater(
            score_ac_product(CCD_7990, FACR_QUERY),
            score_ac_product(BRISK, FACR_QUERY),
        )
        self.assertGreater(
            score_ac_product(CCD_8666, FACR_QUERY),
            score_ac_product(BRISK, FACR_QUERY),
        )

    def test_title_helpers_know_7990_and_8666(self):
        self.assertTrue(is_facr_freeze_library_title(CCD_7990["title"]))
        self.assertTrue(is_facr_freeze_library_title(CCD_8666["title"]))
        self.assertTrue(is_ac_library_title(CCD_7990["title"]))
        self.assertTrue(is_ac_library_title(CCD_8666["title"]))
        self.assertTrue(is_dometic_only_rooftop_ac(BRISK["title"]))
        self.assertFalse(is_dometic_only_rooftop_ac(CCD_7990["title"]))
        self.assertFalse(is_facr_freeze_library_title(BRISK["title"]))
        self.assertFalse(is_facr_freeze_library_title(FRIDGE["title"]))


if __name__ == "__main__":
    unittest.main()
