"""v4.19.19: a printed quote is chunk text, and a shop reply does not invent facts."""
import re
import unittest

from gd_library_coach import (
    category_conflicts_with_model,
    facr_reported_assembly_rr_line,
    is_air_conditioning_context,
    is_water_heater_context,
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower().rstrip(".")


class TestShopReplyPolish(unittest.TestCase):


    def test_category_does_not_override_a_named_model(self):
        self.assertFalse(
            is_air_conditioning_context("Air Conditioning", "Girard GSWH-2", "E8 code")
        )
        self.assertTrue(
            is_water_heater_context("Air Conditioning", "Girard GSWH-2", "E8 code")
        )
        self.assertTrue(category_conflicts_with_model("Air Conditioning", "Girard GSWH-2", "E8"))
        self.assertTrue(
            is_air_conditioning_context("Air Conditioning", "Furrion FACT12SA2", "E2")
        )


if __name__ == "__main__":
    unittest.main()
