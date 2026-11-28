"""Simple open library coach: no gate cage, never re-ask stated facts, working vision."""
import unittest
from pathlib import Path

from gd_library_coach import (
    DEFAULT_GROQ_VISION_MODELS,
    HARD_TREE_EXCLUSIVE_CHAT,
    groq_vision_model_candidates,
    is_fcr_e2_fan_fault_context,
    xai_vision_model_candidates,
)

WO_155578 = (
    "Furrion FCR10DCGTA-BG-PWH freezes contents, intermittent blinking 2 / E2, "
    "temp control intermittent"
)

ROOT = Path(__file__).resolve().parents[1]

CHASE_BAY = (
    "found fuse blown and replaced, fridge light comes on inside, fridge is not cooling"
)
BAD_REASK = (
    "After the fuse check/replace and power reapplied: does the refrigerator cavity "
    "light come on when opening the door? Also say if it is cooling or not cooling.\n\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 19"
)


class TestFigureAsks(unittest.TestCase):
    pass




class TestVisionModels(unittest.TestCase):

    def test_shop_override_is_tried_first(self):
        models = groq_vision_model_candidates("shop/custom-vision")
        self.assertEqual(models[0], "shop/custom-vision")
        self.assertIn("qwen/qwen3.6-27b", models)

    def test_xai_prefers_explicit_vision_then_chat(self):
        models = xai_vision_model_candidates("grok-vision-shop", "grok-4.6")
        self.assertEqual(models[0], "grok-vision-shop")
        self.assertIn("grok-4.6", models)
        self.assertIn("grok-2-vision-1212", models)


class TestProductSource(unittest.TestCase):
    def test_rv_techtrack_retired_scout_and_cage(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertNotIn(
            'or "meta-llama/llama-4-scout-17b-16e-instruct"',
            src,
        )
        self.assertNotIn(
            "This path is complete. Start a new chat for another symptom branch.",
            src,
        )
        self.assertIn("_load_gd_library_coach", src)
        self.assertIn("gd_library_coach.py", src)
        self.assertIn("HARD_TREE_EXCLUSIVE_CHAT", src)

    def test_figure_honesty_is_wired(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        code = src.split('"""', 2)[2]   # past the changelog docstring
        self.assertNotIn("wants_library_page_shown", code)   # v4.20.7: gd_picture.is_picture_request is the one check
        self.assertNotIn("pick_diagram_page_numbers", code)   # v4.20.7: old figure path retired
        self.assertIn("is_fcr_e2_fan_fault_context", src)
        self.assertIn("is_cooktop_pan_on_flameout_context", src)
        self.assertIn("is_stabilizer_override_pin_context", src)
        self.assertIn("complete_chat_with_payload_retry", src)
        self.assertIn("2021128850", src)
        self.assertIn("is_facr_rooftop_freeze_context", src)
        self.assertIn("CCD-0007990", src)
        self.assertIn("CCD-0008666", src)
        self.assertIn("is_bal_soft_touch_tongue_only_context", src)
        self.assertIn("20300427", src)
        self.assertIn("is_coleman_2111_context", src)
        self.assertIn("1976-536", src)

    def test_no_tree_dump_hint_in_coach_module(self):
        coach = (ROOT / "gd_library_coach.py").read_text()
        self.assertNotIn("format_procedure_library_hint", coach)
        self.assertNotIn("fan_replacement", coach)


if __name__ == "__main__":
    unittest.main()
