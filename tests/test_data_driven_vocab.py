"""3d/3e: category -> product types come from the library's own rows, not only from curated lists.
v4.20.9: the type maps live in library_category_audit (legacy_selector.py and its brand detection were deleted)."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import library_category_audit as g  # noqa: E402

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
        g.learn_categories(ROWS)

    def tearDown(self):
        g.learn_categories([])

    def test_vent_fans_and_tv_audio_are_typed(self):
        self.assertIn("vent_fan", g.category_types("Vent Fans"))
        self.assertIn("tv_audio", g.category_types("TV & Audio"))
        self.assertIn("leveling", g.category_types("Leveling"))

    def test_kind_category_has_no_product_gate(self):
        self.assertEqual(g.category_types("Recalls & Bulletins"), set())

    def test_category_types_learned_from_its_documents(self):
        g.learn_categories(ROWS + [{"brand": "Acme", "title": "Acme roof air conditioner service manual", "category": "Coach Climate"},
                                {"brand": "Acme", "title": "Acme heat pump air conditioner manual", "category": "Coach Climate"}])
        self.assertIn("ac", g.category_types("Coach Climate"))

    def test_unmapped_category_does_not_block(self):
        self.assertIsNone(g.category_types("Something Entirely New"))


if __name__ == "__main__":
    unittest.main()
