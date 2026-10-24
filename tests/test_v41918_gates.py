"""v4.19.18: canned repairs stay on their model, and a Sources quote is the page text."""
import re
import unittest

from bay_procedure import compile_bay_procedure
from gd_library_coach import (
    AC_SEARCH_BOOST,
    COLEMAN_MOTOR_BOARD_AUTH_LINE,
    COOKTOP_TIP_LOW_REPAIR,
    DOMETIC_CEILING_LINE,
    FACR_REPORTED_ASSEMBLY_RR_LINE,
    FACT12_FREEZE_RESECURE_LINE,
    FURNACE_WALL_TSTAT_LINE,
    GIRARD_PETIT_ALIGN_LINE,
    avoid_duplicate_reply,
    coleman_facts_from_chat,
    coleman_motor_board_evidence_complete,
    dometic_bypass_facts,
    facr_reported_path_supports_rr,
    is_fact12_freeze_code_context,
)


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


S02 = [
    "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead / no response.",
    "Not checked yet — what do you recommend next?",
    "122 VAC at the control box. Board output tester no illuminate on Fan High. "
    "0.000-0.048 VAC on black/white at the 9-pin under Fan High.",
    "Peacemaker bypass: compressor runs, fan does not rotate on high or low. "
    "About 1.91 A at 122 V, shaft locked.",
    "Fan run capacitor 15.11 µF FAN-C, rated 15 µF ±5%.",
]


class TestCannedRepairsStayOnTheirModel(unittest.TestCase):


    def test_three_proves_without_the_pan_still_withhold_rr(self):
        facts = {
            "facr_drain": "clear",
            "facr_fan_filter": "ok",
            "facr_freeze_sensor": "good",
        }
        self.assertFalse(facr_reported_path_supports_rr(facts))

    def test_iced_suction_still_withholds_rr(self):
        facts = {
            "facr_drain": "clear",
            "facr_pan_slope": "ok",
            "facr_filter": "ok",
            "facr_fan": "ok",
            "facr_sensor_reading": "reported",
            "facr_suction": "iced",
        }
        self.assertFalse(facr_reported_path_supports_rr(facts))


class TestNoRepeat(unittest.TestCase):
    def test_the_same_canned_line_is_not_returned_twice(self):
        first = FURNACE_WALL_TSTAT_LINE
        history = [
            {"role": "user", "content": "Thermostat bypassed at the furnace: the furnace operates."},
            {"role": "assistant", "content": first},
        ]
        again = avoid_duplicate_reply(
            first, history, "What is the repair?", "Furnaces", "Suburban NT-20SEQT"
        )
        self.assertNotEqual(_norm(again), _norm(first))
        self.assertIn("wall thermostat", again.lower())
        self.assertNotIn("sail switch", again.lower())
        self.assertNotIn("what is the repair", again.lower())
        self.assertNotIn("repair stands", again.lower())
        self.assertNotIn("unchanged", again.lower())
        self.assertNotIn("that check was already asked", again.lower())
        third = avoid_duplicate_reply(first, history + [
            {"role": "user", "content": "What is the repair?"},
            {"role": "assistant", "content": again},
        ], "Not checked yet — what do you recommend next?", "Furnaces", "Suburban NT-20SEQT")
        self.assertIn("wall thermostat", third.lower())
        self.assertNotIn("sail switch", third.lower())

    def test_a_repeated_filter_ask_moves_forward(self):
        history = [{"role": "assistant", "content": "Pull and inspect the return-air filter."}]
        moved = avoid_duplicate_reply("Check the filter again.", history, "Drain is clear.")
        self.assertNotIn("check the filter", moved.lower())
        self.assertNotIn("noted:", moved.lower())
        self.assertTrue(re.search(r"\b(?:write|dry|replace|check|repair)\b", moved, re.I))


class TestSourceQuotes(unittest.TestCase):
    def test_s04_brand_is_not_doubled_and_a_long_token_stays(self):
        doubled = compile_bay_procedure(
            "temperature dial OFF but compressor still running",
            "Furrion",
            "Furrion FCR10",
            "Refrigerators",
        )
        self.assertEqual(doubled.model_line, "Furrion FCR10DCGTA-BL")
        self.assertNotIn("Furrion Furrion", doubled.model_line)
        full = compile_bay_procedure(
            "temperature dial OFF but compressor still running",
            "Furrion",
            "FCR10DCGTA-BL",
            "Refrigerators",
        )
        self.assertIn("FCR10DCGTA-BL", full.model_line)
        self.assertNotIn("Furrion Furrion", full.model_line)

    def test_s01_page_7_quote_is_the_manual_sentence(self):
        proc = compile_bay_procedure(
            "FACR08HESA2-PS freeze up interior leak condensate",
            "Furrion",
            "FACR08HESA2-PS",
            "Air Conditioning",
        )
        quotes = " ".join(src.get("excerpt") or "" for src in proc.sources)
        self.assertNotIn("Clean the drainage openings for condensation water.", quotes)
        self.assertTrue(any(src.get("page") == 7 for src in proc.sources))
        self.assertNotIn("so condensate can leave", quotes)
        self.assertNotIn("not set to cooling", quotes.lower())
        self.assertTrue(all(src.get("page") for src in proc.sources))

    def test_s08_falls_back_to_the_page_28_index_sentence(self):
        proc = compile_bay_procedure(
            "Will not blow warm; fan turns on then shuts off.",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
            chunks=[],
        )
        self.assertIn("page 26", proc.primary_cite.lower())
        self.assertTrue(any(src.get("page") == 26 for src in proc.sources))
        blob = " ".join(
            f"{src.get('title') or ''} {src.get('excerpt') or ''}" for src in proc.sources
        ).lower()
        self.assertNotIn("wall thermostat controls the operation", blob)
        self.assertNotIn("no indexed excerpt", blob)

    def test_fact12_library_note_is_only_a_source_line(self):
        proc = compile_bay_procedure(
            "Furrion FACT12SA2 rooftop shows E2",
            "Furrion",
            "FACT12SA2",
            "Air Conditioning",
        )
        body = " ".join([proc.primary_cite, proc.pattern_means, *proc.bay_order]).lower()
        self.assertNotIn("not in the library", body)
        self.assertNotIn("closest reference", body)
        titles = " ".join(src.get("title") or "" for src in proc.sources)
        self.assertEqual(
            [src.get("title") for src in proc.sources],
            ["Furrion Chill FACR08 8K manual CCD-0008666"],
        )
        self.assertNotIn("not in the library", titles.lower())
        self.assertTrue(any(src.get("page") == 5 and "8666" in (src.get("title") or "") for src in proc.sources))
        self.assertFalse(any((src.get("excerpt") or "").strip() for src in proc.sources))

    def test_s14_keeps_the_lippert_page_11_cite(self):
        proc = compile_bay_procedure(
            "Front stabilizer jack. Power extend works. Manual override will not engage. The roll pin is broken.",
            "",
            "",
            "Leveling",
        )
        self.assertFalse(any(src.get("page") == 11 for src in proc.sources))
        self.assertTrue(any(src.get("page") == 7 for src in proc.sources))
        self.assertFalse(any("rear stabilizer" in (src.get("title") or "").lower() for src in proc.sources))
        blob = " ".join(src.get("excerpt") or "" for src in proc.sources).lower()
        self.assertNotIn("override-usage", blob)

    def test_a_quote_is_one_verbatim_sentence_from_the_chunk(self):
        raw = (
            "The wall thermostat controls the operation of the dual stage furnace "
            "by reacting to room temperature. This allows current to flow through the switch. "
            "Count the flashes and use the table below."
        )
        proc = compile_bay_procedure(
            "Will not blow warm; fan turns on then shuts off.",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
            chunks=[
                {
                    "title": "Suburban Furnace Service and Training Manual",
                    "page": 28,
                    "excerpt": raw,
                }
            ],
        )
        for src in proc.sources:
            self.assertTrue(src.get("page"), src)
            excerpt = (src.get("excerpt") or "").strip()
            if not excerpt:
                continue
            self.assertLessEqual(excerpt.count(".") , 1, excerpt)
            self.assertNotIn("->", excerpt)
            self.assertNotIn("table below", excerpt.lower())
            if src.get("page") == 28 and "thermostat" in excerpt.lower():
                self.assertIn(excerpt.rstrip(".").lower(), " ".join(raw.split()).lower())
