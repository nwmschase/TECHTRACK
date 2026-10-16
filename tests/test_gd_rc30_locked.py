"""LOCKED (Chase/Leader 2026-10-16 3:27 PM): RC30 exact repro must pin CCD-0008122, never the vent fan manual.

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


if __name__ == "__main__":
    unittest.main()
