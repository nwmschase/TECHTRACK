"""Water Heaters / Girard GSWH-2 library retrieval: prefer CCD-0009390 over Unity."""
import re
import unittest
from pathlib import Path

from gd_library_coach import (
    WATER_HEATER_PRODUCT_LOCK,
    WATER_HEATER_SEARCH_BOOST,
    claims_water_heater_library_empty,
    drop_unity_chunks_for_water_heater,
    error_code_query_terms,
    figure_library_search_boost,
    figure_render_honesty_note,
    format_water_heater_library_honesty,
    is_air_conditioning_context,
    is_fcr_e2_fan_fault_context,
    is_unity_board_manual,
    is_water_heater_context,
    is_water_heater_library_title,
    rank_chunks_for_water_heater,
    score_water_heater_product,
    skip_unity_for_water_heater,
    water_heater_search_symptom,
)

ROOT = Path(__file__).resolve().parents[1]

CHASE_MODEL = "Girard GSWH-2"
CHASE_CONCERN = "water heater stopped working… E8"
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
GSWH = {
    "title": "Girard GSWH-2 Troubleshooting Manual CCD-0009390",
    "category": "Water Heaters",
    "excerpt": (
        "Girard GSWH-2 tankless water heater. E8 air pressure switch. "
        "Petit Tube restriction / air pressure switch path."
    ),
    "page": 12,
}
FRIDGE = {
    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
    "category": "Refrigerators",
    "excerpt": "E2 Fan Fault Current. Freezer evaporator fan F+ F-.",
    "page": 27,
}
FACT = {
    "title": "Furrion FACT12SA2 Rooftop Air Conditioner SM",
    "category": "Air Conditioning",
    "excerpt": "Furrion FACT rooftop air conditioner. E2 freeze sensor.",
    "page": 8,
}

LIBRARY = [UNITY, GSWH, FRIDGE, FACT]


class TestWaterHeaterDetect(unittest.TestCase):
    def test_chase_gswh2_e8_job(self):
        self.assertTrue(is_water_heater_context("", "", CHASE_CONCERN))
        self.assertTrue(is_water_heater_context("Water Heaters", CHASE_MODEL, CHASE_CONCERN))
        self.assertTrue(skip_unity_for_water_heater("", CHASE_MODEL, CHASE_CONCERN))
        self.assertTrue(skip_unity_for_water_heater("", CHASE_MODEL, CHASE_CONCERN, "Not sure"))

    def test_gswh2_e8_without_category(self):
        self.assertTrue(is_water_heater_context("", "GSWH-2", "E8"))
        self.assertTrue(is_water_heater_context("", "", "GSWH-2 E8"))

    def test_petit_tube_and_air_pressure(self):
        self.assertTrue(is_water_heater_context("", "", "Petit Tube restriction"))
        self.assertTrue(
            is_water_heater_context("Water Heaters", "Girard", "E8 air pressure switch")
        )

    def test_explicit_unity_for_water_heater_is_allowed(self):
        self.assertFalse(
            skip_unity_for_water_heater(
                "Water Heaters", CHASE_MODEL, "OneControl running the water heater"
            )
        )
        self.assertFalse(
            skip_unity_for_water_heater("Water Heaters", CHASE_MODEL, CHASE_CONCERN, "Yes")
        )

    def test_fridge_e2_is_not_water_heater(self):
        self.assertFalse(
            is_water_heater_context("Refrigerators", "Furrion FCR10", "intermittent E2 / 2-flash")
        )
        self.assertTrue(
            is_fcr_e2_fan_fault_context("Refrigerators", "Furrion FCR10", "intermittent E2 / 2-flash")
        )
        self.assertFalse(skip_unity_for_water_heater("Refrigerators", "Furrion FCR10", "E2"))

    def test_rooftop_ac_e2_is_not_water_heater(self):
        self.assertFalse(is_water_heater_context("Air Conditioning", "Furrion FACT12SA2", "E2"))
        self.assertTrue(is_air_conditioning_context("Air Conditioning", "Furrion FACT12SA2", "E2"))

    def test_bare_e8_is_not_enough(self):
        self.assertFalse(is_water_heater_context("", "", "E8"))


class TestWaterHeaterQueryRewrite(unittest.TestCase):
    def test_boost_prefers_gswh_not_unity(self):
        q = water_heater_search_symptom("", CHASE_MODEL, CHASE_CONCERN)
        low = q.lower()
        self.assertIn("gswh", low)
        self.assertIn("e8", low)
        self.assertIn("petit", low)
        self.assertIn("ccd-0009390", low)
        self.assertNotIn("unity", low)
        self.assertNotIn("x270", low)
        self.assertNotIn("onecontrol", low)
        self.assertIn("gswh", WATER_HEATER_SEARCH_BOOST.lower())

    def test_non_water_heater_unchanged(self):
        raw = "fridge not cooling cavity light on"
        self.assertEqual(water_heater_search_symptom("Refrigerators", "FCR10", raw), raw)

    def test_error_code_terms_keep_e8(self):
        terms = error_code_query_terms(CHASE_CONCERN)
        self.assertIn("e8", terms)
        self.assertNotIn("e2", terms)

    def test_tokenize_keeps_e8(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("FAULT_CODE_TOKEN_RE", src)
        start = src.index("FAULT_CODE_TOKEN_RE = re.compile")
        end = src.index("def model_search_terms")
        ns = {"re": re}
        exec(compile(src[start:end], "tokenize", "exec"), ns)
        tokens = ns["tokenize"]("water heater stopped working E8 GSWH-2")
        self.assertIn("e8", tokens)
        self.assertIn("water", tokens)
        self.assertIn("heater", tokens)
        self.assertIn("gswh", tokens)

    def test_figure_boost_adds_water_heater_terms(self):
        boost = figure_library_search_boost(
            "show the Girard GSWH-2 water heater wiring diagram"
        )
        low = boost.lower()
        self.assertIn("gswh", low)
        self.assertIn("petit", low)
        self.assertNotIn("unity", low)


class TestWaterHeaterRanking(unittest.TestCase):
    def test_e8_prefers_gswh_over_unity(self):
        ranked = rank_chunks_for_water_heater(LIBRARY, CHASE_QUERY, limit=3)
        titles = [r["title"] for r in ranked]
        self.assertIn(GSWH["title"], titles)
        self.assertNotIn(UNITY["title"], titles)
        self.assertGreater(
            score_water_heater_product(GSWH, CHASE_QUERY),
            score_water_heater_product(UNITY, CHASE_QUERY),
        )

    def test_petit_tube_prefers_ccd_0009390(self):
        ranked = rank_chunks_for_water_heater(
            LIBRARY, "GSWH-2 E8 Petit Tube air pressure switch", limit=2
        )
        self.assertEqual(ranked[0]["title"], GSWH["title"])

    def test_unity_dropped_when_gswh_exists(self):
        kept = drop_unity_chunks_for_water_heater([UNITY, GSWH])
        self.assertEqual([k["title"] for k in kept], [GSWH["title"]])

    def test_fridge_e2_loses_to_gswh(self):
        self.assertGreater(
            score_water_heater_product(GSWH, CHASE_QUERY),
            score_water_heater_product(FRIDGE, CHASE_QUERY),
        )

    def test_title_helpers(self):
        self.assertTrue(is_water_heater_library_title(GSWH["title"]))
        self.assertFalse(is_water_heater_library_title(UNITY["title"]))
        self.assertFalse(is_water_heater_library_title(FRIDGE["title"]))
        self.assertFalse(is_water_heater_library_title(FACT["title"]))
        self.assertTrue(is_unity_board_manual(UNITY["title"]))


class TestWaterHeaterHonesty(unittest.TestCase):
    def test_does_not_claim_empty_when_titles_exist(self):
        catalog = [
            {"title": GSWH["title"], "indexed": False, "chunk_count": 0},
            {"title": UNITY["title"], "indexed": True, "chunk_count": 20},
        ]
        note = format_water_heater_library_honesty(catalog, chunks=None)
        self.assertIn("DOES include", note)
        self.assertIn("CCD-0009390", note)
        self.assertIn("re-index", note.lower().replace("reindex", "re-index"))
        self.assertIn("Unity", note)
        self.assertFalse(claims_water_heater_library_empty(note))

    def test_empty_claim_detector(self):
        bad = (
            "The shop Document Library does not include a Girard GSWH-2 procedure. "
            "I only have the OneControl Unity board manual."
        )
        self.assertTrue(claims_water_heater_library_empty(bad))
        good = (
            "Girard GSWH-2 Troubleshooting Manual CCD-0009390 is in the shop library "
            "but is not indexed. Ask a manager to re-index it."
        )
        self.assertFalse(claims_water_heater_library_empty(good))

    def test_first_turn_hits_block_empty_claim(self):
        note = format_water_heater_library_honesty(
            [{"title": GSWH["title"], "indexed": True, "chunk_count": 109}],
            chunks=[GSWH],
        )
        self.assertIn("CCD-0009390", note)
        self.assertFalse(claims_water_heater_library_empty(note))

    def test_product_lock_forbids_unity_and_invented_leds(self):
        t = WATER_HEATER_PRODUCT_LOCK.lower()
        self.assertIn("never cite", t)
        self.assertIn("unity", t)
        self.assertIn("re-index", t)
        self.assertIn("gswh", t)
        self.assertIn("ccd-0009390", t)
        self.assertIn("never invent blink", t)

    def test_figure_render_fail_names_gswh_not_missing_library(self):
        note = figure_render_honesty_note(GSWH["title"], True)
        self.assertIn("CCD-0009390", note)
        self.assertIn("could not render", note.lower())
        self.assertNotIn("lacks the procedure", note.lower())
        unity_note = figure_render_honesty_note(UNITY["title"], True)
        self.assertIn("wrong book", unity_note.lower())
        self.assertIn("gswh", unity_note.lower())


if __name__ == "__main__":
    unittest.main()
