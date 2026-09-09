"""Open library coach: no locked-tree cage, working Groq vision ids, figure asks."""
import unittest
from pathlib import Path

from gd_library_coach import (
    DEAD_GROQ_SCOUT_MODEL,
    DEFAULT_GROQ_VISION_MODELS,
    HARD_TREE_EXCLUSIVE_CHAT,
    OPEN_LIBRARY_COACH_RULE,
    format_procedure_library_hint,
    groq_vision_model_candidates,
    hard_tree_yields_to_coach,
    is_path_complete_trap,
    pick_working_vision_model,
    tech_wants_open_coach,
    wants_library_figures,
    xai_vision_model_candidates,
)

ROOT = Path(__file__).resolve().parents[1]


class TestOpenCoachRouting(unittest.TestCase):
    def test_hard_tree_not_exclusive_on_product_path(self):
        self.assertFalse(HARD_TREE_EXCLUSIVE_CHAT)

    def test_coach_rule_forbids_path_complete_trap(self):
        self.assertIn("NEVER say", OPEN_LIBRARY_COACH_RULE)
        self.assertIn("start a new chat", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertFalse(is_path_complete_trap(OPEN_LIBRARY_COACH_RULE))
        self.assertTrue(
            is_path_complete_trap(
                "This path is complete. Start a new chat for another symptom branch."
            )
        )

    def test_pivot_after_paper_is_coach_request(self):
        msg = "go back, need to test compressor"
        self.assertTrue(tech_wants_open_coach(msg))
        self.assertTrue(
            hard_tree_yields_to_coach(
                msg,
                {"id": "fan_replacement", "type": "end", "edges": {}},
            )
        )

    def test_end_leaf_always_yields_even_without_pivot_phrase(self):
        self.assertTrue(
            hard_tree_yields_to_coach(
                "ok what next for the compressor",
                {"type": "end", "edges": {}},
            )
        )

    def test_yes_on_open_gate_is_not_forced_coach(self):
        self.assertFalse(tech_wants_open_coach("yes"))
        self.assertFalse(
            hard_tree_yields_to_coach(
                "yes",
                {"type": "binary", "edges": {"yes": "paper_test", "no": "fan"}},
            )
        )

    def test_question_yields(self):
        self.assertTrue(tech_wants_open_coach("what voltage should I see at the inverter?"))
        self.assertTrue(
            hard_tree_yields_to_coach(
                "what voltage should I see at the inverter?",
                {"type": "binary", "edges": {"yes": "a", "no": "b"}},
            )
        )


class TestFigureAsks(unittest.TestCase):
    def test_common_figure_phrases(self):
        for msg in (
            "show me the figure on that page",
            "can I see the diagram",
            "show the illustration",
            "show Fig. 33",
            "display the page",
            "show that diagram",
        ):
            self.assertTrue(wants_library_figures(msg), msg)
            self.assertTrue(tech_wants_open_coach(msg), msg)

    def test_plain_result_is_not_a_figure_ask(self):
        self.assertFalse(wants_library_figures("paper moved left suck right blow"))


class TestVisionModels(unittest.TestCase):
    def test_default_groq_vision_is_current_qwen(self):
        models = groq_vision_model_candidates("")
        self.assertEqual(models[0], "qwen/qwen3.6-27b")
        self.assertIn("qwen/qwen3.8-27b", models)
        self.assertNotIn(DEAD_GROQ_SCOUT_MODEL, models)
        self.assertNotIn(DEAD_GROQ_SCOUT_MODEL, DEFAULT_GROQ_VISION_MODELS)

    def test_shop_override_is_tried_first(self):
        models = groq_vision_model_candidates("shop/custom-vision")
        self.assertEqual(models[0], "shop/custom-vision")
        self.assertIn("qwen/qwen3.6-27b", models)

    def test_xai_prefers_explicit_vision_then_chat(self):
        models = xai_vision_model_candidates("grok-vision-shop", "grok-4.6")
        self.assertEqual(models[0], "grok-vision-shop")
        self.assertIn("grok-4.6", models)
        self.assertIn("grok-2-vision-1212", models)

    def test_scout_404_falls_through_to_qwen(self):
        tried = []

        def call_model(model):
            tried.append(model)
            if model == DEAD_GROQ_SCOUT_MODEL:
                raise RuntimeError("404 model_not_found")
            if model == "qwen/qwen3.6-27b":
                return '{"brand":"Furrion","model":"FCR10DCGTA","notes":""}'
            return ""

        model, raw, errors = pick_working_vision_model(
            [DEAD_GROQ_SCOUT_MODEL, "qwen/qwen3.6-27b"],
            call_model,
        )
        self.assertEqual(model, "qwen/qwen3.6-27b")
        self.assertIn("FCR10DCGTA", raw)
        self.assertTrue(any("404" in e for e in errors))
        self.assertEqual(tried, [DEAD_GROQ_SCOUT_MODEL, "qwen/qwen3.6-27b"])


class TestLibraryHint(unittest.TestCase):
    def test_hint_lists_cited_pages_and_is_not_a_lock(self):
        procedure = {
            "id": "furrion_fcr_ccd_0008122",
            "title": "Furrion FCR08/FCR10 SM CCD-0008122",
            "nodes": {
                "paper_test": {
                    "id": "paper_test",
                    "source_title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "source_page": 33,
                },
                "fan_replacement": {
                    "id": "fan_replacement",
                    "source_title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "source_page": 33,
                },
                "not_cooling_current": {
                    "id": "not_cooling_current",
                    "source_title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "source_page": 34,
                },
            },
        }
        hint = format_procedure_library_hint(procedure)
        self.assertIn("citation aid only", hint)
        self.assertIn("page 33", hint)
        self.assertIn("page 34", hint)
        self.assertIn("Never say the path is complete", hint)
        self.assertFalse(is_path_complete_trap(hint))


class TestProductSource(unittest.TestCase):
    def test_rv_techtrack_retired_scout_default_and_path_complete_trap(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertNotIn(
            'or "meta-llama/llama-4-scout-17b-16e-instruct"',
            src,
        )
        self.assertNotIn(
            "This path is complete. Start a new chat for another symptom branch.",
            src,
        )
        self.assertIn("OPEN LIBRARY COACH", src)
        self.assertIn("run_guided_diagnostics", src)
        self.assertIn("from gd_library_coach import", src)

    def test_jobs_plan_function_still_present(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("def run_guided_diagnostics(", src)
        self.assertIn("Write the guided diagnostic plan now.", src)


if __name__ == "__main__":
    unittest.main()
