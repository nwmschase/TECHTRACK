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
    ensure_coleman_motor_board_auth,
    ensure_cooktop_tip_pan_check,
    ensure_dometic_ceiling_thermostat,
    ensure_facr_freeze_assembly_rr,
    ensure_fact12_freeze_resecure,
    ensure_furnace_wall_thermostat,
    ensure_girard_petit_align,
    facr_reported_path_supports_rr,
    facts_from_chat,
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
    def test_fact12_line_does_not_fire_on_coleman_or_dometic(self):
        boosted = f"ran about 2 minutes then dead {AC_SEARCH_BOOST}"
        for model in ("Coleman-Mach 2111-0001", "B57915E711J0EMX"):
            self.assertFalse(
                is_fact12_freeze_code_context("Air Conditioning", model, boosted)
            )
            fixed = ensure_fact12_freeze_resecure(
                "Check the supply voltage.",
                [],
                boosted,
                "Air Conditioning",
                model,
                boosted,
            )
            self.assertNotEqual(fixed, FACT12_FREEZE_RESECURE_LINE)
            self.assertNotIn("resecure the freeze sensor", fixed.lower())

    def test_fact12_model_with_e2_still_reseats(self):
        self.assertTrue(
            is_fact12_freeze_code_context(
                "Air Conditioning", "FACT12SA2-PS", "E2 error code; sometimes normal."
            )
        )
        fixed = ensure_fact12_freeze_resecure(
            "The excerpts do not list or define an E2 code.",
            [],
            "E2 error code; sometimes normal.",
            "Air Conditioning",
            "FACT12SA2-PS",
            "E2 error code; sometimes normal.",
        )
        self.assertEqual(fixed, FACT12_FREEZE_RESECURE_LINE)

    def test_coleman_transcript_authorizes_motor_and_board(self):
        history = []
        facts = {}
        for line in S02:
            facts = coleman_facts_from_chat(
                history, line, "Air Conditioning Coleman-Mach 2111-0001"
            )
            history.append({"role": "user", "content": line})
            history.append({"role": "assistant", "content": "Next check."})
        self.assertTrue(coleman_motor_board_evidence_complete(facts), facts)
        card = ensure_coleman_motor_board_auth("Check continuity of the windings.", facts)
        self.assertEqual(card, COLEMAN_MOTOR_BOARD_AUTH_LINE)

    def test_ceiling_controls_bypass_replaces_the_selector(self):
        facts = dometic_bypass_facts(
            [{"role": "user", "content": "Peacemaker bypass at the rooftop unit cools."}],
            "Bypassing the ceiling controls also cools.",
        )
        self.assertEqual(facts.get("dometic_unit_bypass"), "cools")
        self.assertEqual(facts.get("dometic_ceiling_bypass"), "cools")
        card = ensure_dometic_ceiling_thermostat("Check the filter.", facts, [])
        self.assertEqual(card, DOMETIC_CEILING_LINE)

    def test_s01_words_authorize_rr_without_nozzles(self):
        turns = [
            ("user", "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside."),
            ("assistant", "Check the drain and the filter."),
            ("user", "Drain is clear, pan is clean and draining, base-pan slope is fine."),
            ("assistant", "Pull and inspect the return-air filter."),
            ("user", "Filter is clean."),
            ("assistant", "Verify the evaporator fan is running."),
            ("user", "Evaporator fan spins freely with good airflow."),
            ("assistant", "Measure the freeze sensor."),
            ("user", "Freeze sensor reads 2 kΩ at 25°C."),
        ]
        history = [{"role": role, "content": text} for role, text in turns[:-1]]
        facts = facts_from_chat(history, turns[-1][1])
        self.assertTrue(facr_reported_path_supports_rr(facts), facts)
        self.assertIsNone(facts.get("facr_nozzle"))
        card = ensure_facr_freeze_assembly_rr("Read the refrigerant pressures.", facts)
        self.assertEqual(card, FACR_REPORTED_ASSEMBLY_RR_LINE)

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

    def test_pan_on_flameout_repair_ask_states_the_reposition(self):
        complaint = (
            "When using stove, it will shut off as soon as a pan is put on it — either burner. "
            "What is the repair?"
        )
        fixed = ensure_cooktop_tip_pan_check("What should I check next?", complaint)
        self.assertEqual(fixed, COOKTOP_TIP_LOW_REPAIR)
        self.assertIn("page 4", fixed.lower())
        self.assertNotIn("does not cover", fixed.lower())


class TestNoRepeat(unittest.TestCase):
    def test_the_same_canned_line_is_not_returned_twice(self):
        first = FURNACE_WALL_TSTAT_LINE
        history = [
            {"role": "user", "content": "Thermostat bypassed at the furnace: the furnace operates."},
            {"role": "assistant", "content": first},
        ]
        again = avoid_duplicate_reply(first, history, "What is the repair?")
        self.assertNotEqual(_norm(again), _norm(first))
        self.assertIn("wall thermostat", again.lower())
        self.assertNotIn("what is the repair", again.lower())
        self.assertNotIn("that check was already asked", again.lower())
        third = avoid_duplicate_reply(first, history + [
            {"role": "user", "content": "What is the repair?"},
            {"role": "assistant", "content": again},
        ], "Not checked yet — what do you recommend next?")
        self.assertNotEqual(_norm(third), _norm(again))
        self.assertNotEqual(_norm(third), _norm(first))

    def test_a_repeated_filter_ask_moves_forward(self):
        history = [{"role": "assistant", "content": "Pull and inspect the return-air filter."}]
        moved = avoid_duplicate_reply("Check the filter again.", history, "Drain is clear.")
        self.assertNotIn("check the filter", moved.lower())
        self.assertNotIn("noted:", moved.lower())
        self.assertTrue(re.search(r"\b(?:write|dry|replace|check|repair)\b", moved, re.I))

    def test_cross_case_facts_do_not_take_another_cases_card(self):
        cases = [
            ("coleman", "Air Conditioning", "Coleman-Mach 2111-0001", S02[0], COLEMAN_MOTOR_BOARD_AUTH_LINE),
            ("dometic", "Air Conditioning", "B57915E711J0EMX", "AC turns on but will not blow cold.", DOMETIC_CEILING_LINE),
            ("furnace", "Furnaces", "Suburban NT-20SEQT", "Will not blow warm; fan turns on then shuts off.", FURNACE_WALL_TSTAT_LINE),
            ("girard", "(any)", "Girard GSWH-2", "Gives E8 error code. Tubing is clear.", GIRARD_PETIT_ALIGN_LINE),
            ("fact12", "Air Conditioning", "FACT12SA2-PS", "E2 error code; sometimes normal.", FACT12_FREEZE_RESECURE_LINE),
            ("facr", "Air Conditioning", "FACR08HESA2-PS", "Water leaking from the rooftop AC.", FACR_REPORTED_ASSEMBLY_RR_LINE),
            ("cooktop", "Range & Cooktops", "Suburban SDN2U", "It will shut off as soon as a pan is put on it.", COOKTOP_TIP_LOW_REPAIR),
        ]
        neutral = "Check the supply and report the reading."
        for name, category, model, complaint, own in cases:
            foreign = [
                line for other, _c, _m, _p, line in cases if other != name
            ]
            fact12 = ensure_fact12_freeze_resecure(
                neutral, [], complaint, category, model, f"{complaint} {AC_SEARCH_BOOST}"
            )
            furnace = ensure_furnace_wall_thermostat(
                neutral, [], "What is the repair?", category, model
            )
            girard = ensure_girard_petit_align(
                neutral, [], "What is the repair?", category, model, complaint
            )
            produced = [fact12, furnace, girard]
            if name != "fact12":
                self.assertNotIn(FACT12_FREEZE_RESECURE_LINE, produced)
            for line in foreign:
                if line in (FURNACE_WALL_TSTAT_LINE, GIRARD_PETIT_ALIGN_LINE, FACT12_FREEZE_RESECURE_LINE):
                    continue
                self.assertNotIn(line, produced, name)


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
            ["Furrion CCD-0008666 (FACR08 manual, closest reference)"],
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
        self.assertTrue(any(src.get("page") == 11 for src in proc.sources))
        self.assertTrue(any(src.get("page") == 7 for src in proc.sources))
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
