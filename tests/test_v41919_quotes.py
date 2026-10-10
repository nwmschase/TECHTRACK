"""v4.19.19: a printed quote is chunk text, and a shop reply does not invent facts."""
import re
import unittest

from bay_procedure import compile_bay_procedure, procedure_plain_text
from gd_library_coach import (
    BAL_TONGUE_PROVE_SHOP_LINE,
    COOKTOP_TIP_LOW_REPAIR,
    FACT12_FREEZE_RESECURE_LINE,
    avoid_duplicate_reply,
    extract_bal_tongue_facts,
    facr_reported_assembly_rr_line,
    polish_shop_reply,
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower().rstrip(".")


class TestChunkQuotes(unittest.TestCase):
    def test_a_printed_quote_is_a_substring_of_its_chunk(self):
        chunks = [
            {
                "title": "Suburban Furnace Service and Training Manual",
                "page": 28,
                "excerpt": (
                    "The wall thermostat controls the operation of the dual stage furnace "
                    "by reacting to room temperature. Count the flashes and use the table below."
                ),
            },
            {
                "title": "Suburban Furnace Service and Training Manual",
                "page": 26,
                "excerpt": "Time line description. Start time.",
            },
        ]
        proc = compile_bay_procedure(
            "Will not blow warm; fan turns on then shuts off.",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
            chunks=chunks,
        )
        by_page = {}
        for chunk in chunks:
            by_page.setdefault(chunk["page"], []).append(chunk["excerpt"])
        printed = 0
        for src in proc.sources:
            quote = (src.get("excerpt") or "").strip()
            if not quote:
                continue
            printed += 1
            raws = by_page.get(src.get("page")) or []
            self.assertTrue(raws, quote)
            hay = " ".join(_collapse(raw) for raw in raws)
            self.assertIn(_collapse(quote), hay, quote)
            self.assertNotIn("table below", quote.lower())
        self.assertGreaterEqual(printed, 1)

    def test_a_locked_sentence_does_not_print_without_a_chunk(self):
        proc = compile_bay_procedure(
            "FACR08HESA2-PS freeze up interior leak condensate",
            "Furrion",
            "FACR08HESA2-PS",
            "Air Conditioning",
            chunks=[],
        )
        quotes = " ".join(src.get("excerpt") or "" for src in proc.sources)
        self.assertNotIn("freeze sensor sits on the evaporator", quotes.lower())
        self.assertNotIn("clean the drainage openings", quotes.lower())
        self.assertTrue(any(src.get("page") == 7 for src in proc.sources))
        self.assertTrue(any(src.get("page") == 10 for src in proc.sources))

    def test_expected_cites_stay_when_the_quote_is_blank(self):
        tongue = compile_bay_procedure(
            "BAL Soft-Touch SS 5.1 electric tongue jack dead. Other stabilizers and panel lights work.",
            "BAL",
            "Soft-Touch SS 5.1",
            "Leveling",
        )
        titles = " ".join(src.get("title") or "" for src in tongue.sources)
        self.assertIn("INS.STA.001", titles)
        self.assertTrue(any(src.get("page") for src in tongue.sources))

        e2 = compile_bay_procedure(
            "FCR10 E2 fan fault current on the freezer evaporator fan",
            "Furrion",
            "FCR10",
            "Refrigerators",
            chunks=[
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 29,
                    "excerpt": "Proceed to the next section.",
                }
            ],
        )
        self.assertIn("page 27", e2.primary_cite.lower())
        self.assertTrue(any(src.get("page") == 27 for src in e2.sources))
        self.assertNotIn("see doc", procedure_plain_text(e2).lower())

        ground = compile_bay_procedure(
            "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
            "tires off the ground even though the coach was nearly level.",
            "Lippert",
            "Ground Control 343633",
            "Leveling",
        )
        self.assertTrue(ground.sources)
        self.assertIn("page 1", ground.primary_cite.lower())
        self.assertNotIn("see doc", ground.primary_cite.lower())
        self.assertFalse(any((src.get("excerpt") or "").strip() for src in ground.sources))

        girard = compile_bay_procedure(
            "Girard GSWH-2 tankless water heater shows E8.",
            "Girard",
            "GSWH-2",
            "Water Heaters",
        )
        self.assertIn("page 23", girard.primary_cite.lower())
        self.assertIn("ccd-0009390", girard.primary_cite.lower())
        self.assertTrue(any(src.get("page") == 23 for src in girard.sources))
        self.assertNotIn("see doc", procedure_plain_text(girard).lower())

    def test_fact12_source_line_is_the_closest_reference(self):
        proc = compile_bay_procedure(
            "Furrion FACT12SA2 rooftop shows E3",
            "Furrion",
            "FACT12SA2",
            "Air Conditioning",
        )
        self.assertEqual(len(proc.sources), 1)
        self.assertEqual(
            proc.sources[0]["title"],
            "Furrion CCD-0008666 (FACR08 manual, closest reference)",
        )
        self.assertEqual(proc.sources[0]["page"], 5)
        self.assertFalse((proc.sources[0].get("excerpt") or "").strip())
        plain = procedure_plain_text(proc)
        self.assertIn("Furrion CCD-0008666 (FACR08 manual, closest reference) p.5", plain)
        self.assertNotIn("not in the library", plain.lower())
        self.assertNotIn("see doc", plain.lower())

    def test_dial_off_master_keeps_the_full_model(self):
        proc = compile_bay_procedure(
            "temperature dial OFF but compressor still running, freezer frozen solid",
            "Furrion",
            "FCR10",
            "Refrigerators",
        )
        self.assertIn("FCR10DCGTA-BL", proc.model_line)
        self.assertNotIn("see doc", procedure_plain_text(proc).lower())
        for src in proc.sources:
            if src.get("page") in (31, 43, 45):
                self.assertFalse((src.get("excerpt") or "").strip(), src)


class TestShopReplyPolish(unittest.TestCase):
    def test_the_model_instruction_never_reaches_the_tech(self):
        history = [
            {"role": "assistant", "content": BAL_TONGUE_PROVE_SHOP_LINE},
        ]
        latest = "I measured 0 V at the soft-touch panel tongue channel while commanding extend."
        facts = extract_bal_tongue_facts(latest)
        self.assertEqual(facts.get("tongue_channel_volts"), "missing")
        reply = avoid_duplicate_reply(
            "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel.",
            history,
            latest,
        )
        low = reply.lower()
        self.assertNotIn("that check was already asked", low)
        self.assertNotIn("use the facts already reported", low)
        self.assertIn("20300427", reply)
        self.assertIn("0 v", low)

    def test_fallback_questions_are_not_noted_as_facts(self):
        history = [
            {"role": "user", "content": "FACT12SA2-PS shows E3."},
            {"role": "assistant", "content": FACT12_FREEZE_RESECURE_LINE},
        ]
        reply = avoid_duplicate_reply(FACT12_FREEZE_RESECURE_LINE, history, "What is the repair?")
        self.assertNotIn("Noted: What is the repair", reply)
        self.assertNotIn("what is the repair", reply.lower())
        self.assertNotEqual(reply.strip(), FACT12_FREEZE_RESECURE_LINE.strip())

    def test_unreported_claims_are_removed(self):
        user = "Drain is clear. Filter is clean. Fan spins. Freeze sensor reads 2 kΩ."
        card = facr_reported_assembly_rr_line()
        self.assertNotIn("nozzle", card.lower())
        with_nozzles = facr_reported_assembly_rr_line({"facr_nozzle": "open"})
        self.assertIn("nozzles", with_nozzles.lower())
        scrubbed = polish_shop_reply(
            "Nozzles are reported good. Dial turned down. Error remains. The tip sits low. "
            "No sticky Low Voltage. E2 returned after reset.",
            [{"role": "user", "content": user}, {"role": "assistant", "content": "Next check."}],
            "The code returned after the thaw.",
        )
        low = scrubbed.lower()
        self.assertNotIn("nozzles are reported good", low)
        self.assertNotIn("dial turned down", low)
        self.assertNotIn("error remains", low)
        self.assertNotIn("sits low", low)
        self.assertNotIn("no sticky", low)
        self.assertNotIn("after reset", low)
        self.assertIn("thaw", low)

    def test_cooktop_repair_does_not_invent_tip_height_or_ask_to_pivot(self):
        self.assertNotIn("sits low", COOKTOP_TIP_LOW_REPAIR.lower())
        reply = polish_shop_reply(
            COOKTOP_TIP_LOW_REPAIR
            + " Does the coach have any other symptoms, or do you want to pivot to a different check?",
            [],
            "It will shut off as soon as a pan is put on it.",
        )
        self.assertNotIn("pivot", reply.lower())
        self.assertNotIn("any other symptoms", reply.lower())
        self.assertIn("reposition", reply.lower())

    def test_the_same_check_is_not_said_twice_in_one_reply(self):
        reply = polish_shop_reply(
            "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel. "
            "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel.",
            [],
            "Tongue jack only is dead.",
        )
        self.assertEqual(reply.lower().count("check for 12v"), 1)

    def test_library_gap_is_one_line_of_shop_advice(self):
        self.assertEqual(FACT12_FREEZE_RESECURE_LINE.lower().count("not in the shop library"), 1)
        self.assertNotIn("closest reference", FACT12_FREEZE_RESECURE_LINE.lower())
        self.assertIn("do not replace the control board first", FACT12_FREEZE_RESECURE_LINE.lower())


if __name__ == "__main__":
    unittest.main()
