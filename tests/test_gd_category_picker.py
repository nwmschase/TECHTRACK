"""GD / Document Library category picker list includes Water Heaters and Range & Cooktops."""
import ast
import unittest
from pathlib import Path

from gd_library_coach import (
    AIR_CONDITIONING_CATEGORY,
    DEFAULT_LIBRARY_CATEGORIES,
    RANGE_COOKTOPS_CATEGORY,
    REFRIGERATORS_CATEGORY,
    WATER_HEATERS_CATEGORY,
    gd_category_select_options,
    library_category_picker_names,
)

ROOT = Path(__file__).resolve().parents[1]


class TestGdCategoryPicker(unittest.TestCase):
    def test_exact_strings_on_default_list(self):
        self.assertEqual(WATER_HEATERS_CATEGORY, "Water Heaters")
        self.assertEqual(RANGE_COOKTOPS_CATEGORY, "Range & Cooktops")
        self.assertIn(WATER_HEATERS_CATEGORY, DEFAULT_LIBRARY_CATEGORIES)
        self.assertIn(RANGE_COOKTOPS_CATEGORY, DEFAULT_LIBRARY_CATEGORIES)
        self.assertIn(AIR_CONDITIONING_CATEGORY, DEFAULT_LIBRARY_CATEGORIES)
        self.assertIn(REFRIGERATORS_CATEGORY, DEFAULT_LIBRARY_CATEGORIES)

    def test_gd_select_uses_same_list_plus_any(self):
        opts = gd_category_select_options([])
        self.assertEqual(opts[0], "(any)")
        self.assertIn("Water Heaters", opts)
        self.assertIn("Range & Cooktops", opts)
        self.assertEqual(opts[1:], library_category_picker_names([]))

    def test_picker_keeps_manager_extra_names(self):
        names = library_category_picker_names(["TSB / Recall", "Water Heaters", ""])
        self.assertIn("TSB / Recall", names)
        self.assertIn("Water Heaters", names)
        self.assertIn("Range & Cooktops", names)
        self.assertEqual(names, sorted(names))

    def test_rv_techtrack_gd_select_calls_shared_helper(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("gd_category_select_options", src)
        self.assertIn("library_category_picker_names", src)
        self.assertIn("DEFAULT_LIBRARY_CATEGORIES", src)
        self.assertNotIn(
            'cat_names = ["(any)"] + [c.name for c in cats]',
            src,
        )
        self.assertIn("for name in DEFAULT_LIBRARY_CATEGORIES:", src)

    def test_seed_upserts_missing_categories(self):
        """Existing shop DBs (count != 0) still receive Water Heaters / Range & Cooktops."""
        src = (ROOT / "rv_techtrack.py").read_text()
        tree = ast.parse(src)
        seed_fn = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "seed_data":
                seed_fn = node
                break
        self.assertIsNotNone(seed_fn)
        seed_src = ast.get_source_segment(src, seed_fn)
        self.assertIsNotNone(seed_src)
        self.assertNotIn("if session.query(Category).count() == 0:", seed_src)
        self.assertIn("DEFAULT_LIBRARY_CATEGORIES", seed_src)
        self.assertIn("if name not in existing:", seed_src)

    def test_search_filters_use_category_constants(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        search = src.split("def search_manual_chunks(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("WATER_HEATERS_CATEGORY", search)
        self.assertIn("AIR_CONDITIONING_CATEGORY", search)
        self.assertIn("RANGE_COOKTOPS_CATEGORY", search)
        self.assertNotIn('"Water Heaters"', search)
        self.assertNotIn('"Air Conditioning"', search)


if __name__ == "__main__":
    unittest.main()
