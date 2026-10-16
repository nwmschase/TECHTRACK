"""LOCKED manual-selection regressions (Chase/Leader 2026-10-16 3:27/3:29 PM). One selector: gd_official.select_manual.
RC30 exact repro must pin CCD-0008122, never the vent fan manual.

Library rows copied from the live DB (ids, titles, model fields, in live id order: the fan row comes first,
which is what made it win the tie on main ab090e4).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go  # noqa: E402

ROWS = [
    {"id": 186, "title": "Furrion FCR08 FCR10 12V Refrigerator Troubleshooting and Service Manual CCD-0008122", "models": "", "brand": "", "doc_number": ""},
    {"id": 283, "title": 'Furrion 14" 12V Vent Fan (V2.0) with Lid Troubleshooting and Service Manual',
     "models": "FVF14D90A2-GS-OEM;FVF14D90A2-PW-OEM;FVF14D90R6A2-GS-AM;FVF14D90R6A2-PW-AM;FVF14D90A2;FVF14D90A2-GS;FVF14D90A-PS-OEM;FVF14D90R6A-GW-AM",
     "brand": "Furrion", "doc_number": "CCD-0010491"},
    {"id": 298, "title": "Furrion Arctic 8 & 10 cu.ft. Refrigerator Troubleshooting and Service Manual",
     "models": "FCR08DCGTA-BL;FCR08DCGTA-BR;FCR08DCGTA-NL;FCR08DCGTA-NR;FCR08DCGTA-KL;FCR08DCGTA-KR;FCR10DCGTA-BL;FCR10DCGTA-BR;FCR10DCGTA-NL;FCR10DCGTA-NR;FCR10DCGTA-KL;FCR10DCGTA-KR;FCR08DCGTA;FCR10DCGTA",
     "brand": "Furrion", "doc_number": "CCD-0008122"},
]
CCD_0008122 = {186, 298}  # same manual: 186 by title, 298 by file/doc number CCD-0008122


class Lib:
    def __init__(self, rows):
        self.rows = rows

    def documents(self):
        return list(self.rows)


class TestRC30Locked(unittest.TestCase):
    MODEL = "Furrion FCR08DCGTA 12V DC refrigerator (label cut off after GTA)"

    def _pin(self, rows):
        unit = go.identify_unit([], "Customer reports the fridge has no power, interior light won't turn on.", "Refrigerators", self.MODEL)
        return go.pin_document(Lib(rows), unit)

    def test_exact_repro_pins_ccd_0008122(self):
        doc = self._pin(ROWS)
        self.assertIsNotNone(doc)
        self.assertIn(doc["id"], CCD_0008122)
        self.assertNotIn("vent fan", doc["title"].lower())

    def test_any_row_order(self):
        for rows in (ROWS, ROWS[::-1], [ROWS[1], ROWS[0]], [ROWS[1], ROWS[2]]):
            self.assertIn(self._pin(rows)["id"], CCD_0008122)

    def test_fan_alone_is_never_borrowed(self):
        self.assertIsNone(self._pin([ROWS[1]]))


def _sel(rows, model, category, complaint="x"):
    unit = go.identify_unit([], complaint, category, model)
    return go.select_manual(Lib(rows), unit)


class LibC(Lib):
    def chunks(self, doc_id):
        return [{"page": 1, "text": "vent fan safety " * 50}]


class TestWebFallbackFires(unittest.TestCase):
    def test_wrong_type_doc_counts_as_not_found_and_web_runs(self):
        seen = []
        r = go.official_turn("Customer reports the fridge has no power", "Refrigerators", TestRC30Locked.MODEL, [],
                             library=LibC([ROWS[1]]), chat_fn=lambda m, t, e: "1. Verify the complaint [General trade knowledge]",
                             pin_store={}, web_fetch_fn=lambda unit: seen.append(unit) or {})
        self.assertEqual(len(seen), 1)
        self.assertEqual(r["mode"], "no_manual")
        self.assertNotIn("vent fan", r["reply"].lower())
        self.assertIn("No Furrion", r["reply"])


class TestOtherLockedCases(unittest.TestCase):
    def test_rc17_girard_gswh2_not_gswh1_or_fridge(self):
        rows = [{"id": 162, "title": "Girard GSWH-1 Tankless LP Water Heater Service Manual (1GWH / 1GWHAF)"},
                {"id": 99, "title": "Girard 10 cu.ft. 12V Built-in Refrigerator Troubleshooting and Service Manual"},
                {"id": 328, "title": "Girard Tankless Water Heater GSWH-2 Troubleshooting and Service Manual", "brand": "Girard", "models": "GSWH-2", "doc_number": "CCD-0009390"}]
        self.assertEqual(_sel(rows, "Girard GSWH-2 tankless water heater", "Water Heaters")["doc"]["id"], 328)

    def test_thetford_guard_never_another_toilet_brand(self):
        rows = [{"id": 1, "title": "Dometic 310 Toilet Service Manual", "brand": "Dometic"},
                {"id": 247, "title": "Thetford Style II OM Permanent RV Toilet 42088"}]
        self.assertEqual(_sel(rows, "Thetford Style II 42088", "Plumbing / Toilets")["doc"]["id"], 247)
        r = _sel(rows[:1], "Thetford Style II 42088", "Plumbing / Toilets")
        self.assertIsNone(r["doc"])
        self.assertIn("No Thetford", r["miss_line"])

    def test_maxxfan_remote_pins_maxxair_not_furrion_fan(self):
        rows = [{"id": 283, "title": 'Furrion 14" 12V Vent Fan (V2.0) with Lid Troubleshooting and Service Manual', "brand": "Furrion", "models": "FVF14D90A2"},
                {"id": 900, "title": "MaxxAir MaxxFan Deluxe 00-07500K / 11F90000K Remote Installation and Operation", "brand": "MaxxAir", "models": "11F90000K;00-07500K"}]
        self.assertEqual(_sel(rows, "MaxxAir MaxxFan Deluxe 11F90000K", "Electrical", "remote does nothing")["doc"]["id"], 900)
        self.assertIsNone(_sel(rows[:1], "MaxxAir MaxxFan Deluxe 11F90000K", "Electrical")["doc"])

    def test_unknown_brand_never_borrows(self):
        rows = [{"id": 18, "title": "Lippert Power Tongue Jack Troubleshooting and Service Manual", "brand": "Lippert"},
                {"id": 19, "title": "Lippert Front Electric Stabilizer Jack Service Manual 3100", "brand": "Lippert"}]
        r = _sel(rows, "2026 Brinkley Model Z 3100 fifth wheel front jack", "Leveling")
        self.assertIsNone(r["doc"])
        self.assertTrue(r["miss_line"].startswith("No Brinkley"))

    def test_rc30_miss_line_when_no_fridge_manual(self):
        r = _sel([ROWS[1]], TestRC30Locked.MODEL, "Refrigerators")
        self.assertIsNone(r["doc"])
        self.assertEqual(r["miss_line"], "No Furrion FCR08DCGTA fridge manual found")


if __name__ == "__main__":
    unittest.main()
