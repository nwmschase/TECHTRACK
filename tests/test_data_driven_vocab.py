"""3d/3e: brands and category -> product types come from the library's own rows, not only from curated lists."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import legacy_selector as g  # noqa: E402

ROWS = [
    {"brand": "Greystone", "title": "Greystone Electric Fireplace Owner's Manual", "category": "Fireplaces"},
    {"brand": "Reese", "title": "Reese Hitch Installation Instructions", "category": "Hitches"},
    {"brand": "Bigfoot", "title": "Bigfoot Leveling System Service Manual", "category": "Leveling"},
    {"brand": "DeWald", "title": "DeWald Hydraulic Leveling Parts and Service Manual", "category": "Leveling"},
    {"brand": "MaxxAir", "title": "MaxxFan Deluxe Vent Fan Installation", "category": "Vent Fans"},
    {"brand": "Winegard", "title": "Winegard TV antenna and audio installation", "category": "TV & Audio"},
    {"brand": "Lippert", "title": "Recall bulletin 22-01", "category": "Recalls & Bulletins"},
]


class TestLearnedVocab(unittest.TestCase):
    def setUp(self):
        g.learn_library(ROWS)

    def tearDown(self):
        g.learn_library([])

    def test_unknown_brands_are_detected_from_data(self):
        for text, want in (("greystone fireplace no heat", "greystone"), ("Reese 5th wheel hitch", "reese"),
                           ("bigfoot jacks won't retract", "bigfoot"), ("DeWald leveling", "dewald")):
            self.assertEqual(g.detect_brand(text), g.BRAND_ALIASES.get(want, want), text)

    def test_brand_forgotten_when_no_longer_in_library(self):
        g.learn_library([])
        self.assertNotEqual(g.detect_brand("greystone fireplace"), "greystone")

    def test_vent_fans_and_tv_audio_are_typed(self):
        self.assertIn("vent_fan", g.category_types("Vent Fans"))
        self.assertIn("tv_audio", g.category_types("TV & Audio"))
        self.assertIn("leveling", g.category_types("Leveling"))

    def test_kind_category_has_no_product_gate(self):
        self.assertEqual(g.category_types("Recalls & Bulletins"), set())

    def test_category_types_learned_from_its_documents(self):
        g.learn_library(ROWS + [{"brand": "Acme", "title": "Acme roof air conditioner service manual", "category": "Coach Climate"},
                                {"brand": "Acme", "title": "Acme heat pump air conditioner manual", "category": "Coach Climate"}])
        self.assertIn("ac", g.category_types("Coach Climate"))

    def test_unmapped_category_does_not_block(self):
        self.assertIsNone(g.category_types("Something Entirely New"))


if __name__ == "__main__":
    unittest.main()
