"""Simple open library coach: no gate cage, never re-ask stated facts, working vision."""
import unittest
from pathlib import Path

from gd_library_coach import (
    DEAD_GROQ_SCOUT_MODEL,
    DEFAULT_GROQ_VISION_MODELS,
    HARD_TREE_EXCLUSIVE_CHAT,
    OPEN_LIBRARY_COACH_RULE,
    coach_library_search_boost,
    extract_stated_facts,
    facts_from_chat,
    format_stated_facts_rule,
    groq_vision_model_candidates,
    hard_tree_yields_to_coach,
    is_path_complete_trap,
    pick_working_vision_model,
    powered_not_cooling,
    reply_reasks_stated_facts,
    strip_path_complete_trap,
    tech_wants_open_coach,
    wants_library_figures,
    xai_vision_model_candidates,
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


class TestProductPath(unittest.TestCase):
    def test_hard_tree_not_exclusive(self):
        self.assertFalse(HARD_TREE_EXCLUSIVE_CHAT)
        self.assertTrue(hard_tree_yields_to_coach("anything", {"type": "binary", "edges": {"yes": "x"}}))

    def test_coach_rule_forbids_trap_and_reask(self):
        self.assertIn("NEVER say", OPEN_LIBRARY_COACH_RULE)
        self.assertIn("start a new chat", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("NEVER re-ask", OPEN_LIBRARY_COACH_RULE)
        self.assertFalse(is_path_complete_trap(OPEN_LIBRARY_COACH_RULE))
        self.assertTrue(
            is_path_complete_trap(
                "This path is complete. Start a new chat for another symptom branch."
            )
        )

    def test_strip_path_complete_trap(self):
        cleaned = strip_path_complete_trap(
            "Check amps.\nThis path is complete. Start a new chat for another symptom branch."
        )
        self.assertNotIn("path is complete", cleaned.lower())
        self.assertIn("Check amps", cleaned)


class TestChaseBayFacts(unittest.TestCase):
    def test_extracts_fuse_light_not_cooling(self):
        facts = extract_stated_facts(CHASE_BAY)
        self.assertEqual(facts.get("fuse"), "replaced")
        self.assertEqual(facts.get("light"), "on")
        self.assertEqual(facts.get("cooling"), "not_cooling")
        self.assertTrue(powered_not_cooling(facts))

    def test_facts_from_chat_merge_latest(self):
        hist = [{"role": "user", "content": "customer states not cooling, fuse already replaced, cavity light on"}]
        facts = facts_from_chat(hist, "go to compressor section")
        self.assertEqual(facts.get("fuse"), "replaced")
        self.assertEqual(facts.get("light"), "on")
        self.assertEqual(facts.get("cooling"), "not_cooling")
        self.assertEqual(facts.get("pivot"), "compressor")

    def test_stated_facts_rule_forbids_reask(self):
        rule = format_stated_facts_rule(extract_stated_facts(CHASE_BAY))
        self.assertIn("never re-ask", rule.lower())
        self.assertIn("light is ON", rule)
        self.assertIn("NOT cooling", rule)
        self.assertIn("Do NOT restart at fuse", rule)

    def test_chase_reask_reply_is_detected(self):
        facts = extract_stated_facts(CHASE_BAY)
        hits = reply_reasks_stated_facts(BAD_REASK, facts)
        self.assertIn("light", hits)
        self.assertIn("cooling", hits)

    def test_good_next_check_is_not_a_reask(self):
        facts = extract_stated_facts(CHASE_BAY)
        good = (
            "Fuse replaced and cavity light is on — unit has power and is not cooling. "
            "Next from the service manual: confirm the compressor is running (or measure "
            "current) on the inoperable-compressor / not-cooling section.\n"
            "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 34"
        )
        self.assertEqual(reply_reasks_stated_facts(good, facts), [])

    def test_search_boost_is_not_the_wrong_tree(self):
        facts = extract_stated_facts(CHASE_BAY)
        boost = coach_library_search_boost(facts)
        self.assertIn("inoperable compressor", boost)
        self.assertNotIn("fan replacement", boost.lower())
        self.assertNotIn("no power", boost.lower())


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

    def test_pivot_is_coach_request(self):
        self.assertTrue(tech_wants_open_coach("go back, need to test compressor"))
        self.assertTrue(tech_wants_open_coach("go to compressor section"))


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
        self.assertIn("OPEN LIBRARY COACH", src)
        self.assertIn("from gd_library_coach import", src)
        self.assertIn("HARD_TREE_EXCLUSIVE_CHAT", src)

    def test_jobs_plan_function_still_present(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("def run_guided_diagnostics(", src)
        self.assertIn("Write the guided diagnostic plan now.", src)
        self.assertIn("Start Job + Build Test Plan", src)

    def test_no_tree_dump_hint_in_coach_module(self):
        coach = (ROOT / "gd_library_coach.py").read_text()
        self.assertNotIn("format_procedure_library_hint", coach)
        self.assertNotIn("fan_replacement", coach)


if __name__ == "__main__":
    unittest.main()
