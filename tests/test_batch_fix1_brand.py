"""Batch fix 1 (Leader 2026-10-14 8:57 PM): a sheet never cites another maker's manual."""
import unittest

from scripts.brand_cite_check import check_titles
from bay_procedure import _spec_off_brand

DOCS = [
    (1, "Level Up® Towable OCTP Owner's Manual", "Lippert", "documents/x.pdf"),
    (2, "Kwikee® Operation Guide Level Best 2000 (Discontinued)", "Kwikee", "documents/y.pdf"),
    (3, "Power Gear T.I.P. - Hydraulic Pump Motor Diagnosis", "Power Gear", "documents/z.pdf"),
]


class TestBrandCiteCheckCatchesBatch1(unittest.TestCase):
    def test_b05_kwikee_case_citing_level_up_fails(self):
        probs = check_titles(["Level Up® Towable OCTP Owner's Manual"], "Kwikee", DOCS)
        self.assertTrue(any(p.startswith("BR-1") for p in probs), probs)

    def test_b06_power_gear_case_citing_title_not_in_db_fails(self):
        probs = check_titles(["Lippert Level Up FW Owner's Manual"], "Power Gear", DOCS)
        self.assertTrue(any(p.startswith("BR-2") for p in probs), probs)
        self.assertTrue(any(p.startswith("BR-1") for p in probs), probs)

    def test_own_brand_passes(self):
        self.assertEqual(check_titles(["Kwikee® Operation Guide Level Best 2000 (Discontinued)"], "Kwikee", DOCS), [])
        self.assertEqual(check_titles(["Power Gear T.I.P. - Hydraulic Pump Motor Diagnosis"], "Power Gear", DOCS), [])


class TestAuthoredSheetOffBrand(unittest.TestCase):
    def test_level_up_sheet_is_off_brand_for_power_gear(self):
        spec = {"sources": [{"title": "Lippert Level Up FW Owner's Manual"}]}
        self.assertTrue(_spec_off_brand(spec, {"power gear"}))
        self.assertFalse(_spec_off_brand(spec, {"lippert"}))


if __name__ == "__main__":
    unittest.main()
