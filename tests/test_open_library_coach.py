"""Simple open library coach: no gate cage, never re-ask stated facts, working vision."""
import unittest
from pathlib import Path

from gd_library_coach import (
    DEAD_GROQ_SCOUT_MODEL,
    DEFAULT_GROQ_VISION_MODELS,
    FCR_E2_FAN_FAULT_PRODUCT_LOCK,
    HARD_TREE_EXCLUSIVE_CHAT,
    OPEN_LIBRARY_COACH_RULE,
    claims_fcr_e2_board_only_cage,
    coach_library_search_boost,
    extract_stated_facts,
    facts_from_chat,
    format_stated_facts_rule,
    groq_vision_model_candidates,
    hard_tree_yields_to_coach,
    is_fcr_e2_fan_fault_context,
    is_path_complete_trap,
    pick_working_vision_model,
    powered_not_cooling,
    reply_reasks_stated_facts,
    strip_path_complete_trap,
    tech_wants_open_coach,
    wants_board_or_terminal_figure,
    wants_library_figures,
    wants_library_page_shown,
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


class TestProductPath(unittest.TestCase):
    def test_hard_tree_not_exclusive(self):
        self.assertFalse(HARD_TREE_EXCLUSIVE_CHAT)
        self.assertTrue(hard_tree_yields_to_coach("anything", {"type": "binary", "edges": {"yes": "x"}}))

    def test_coach_rule_forbids_trap_and_reask(self):
        self.assertIn("NEVER say", OPEN_LIBRARY_COACH_RULE)
        self.assertIn("start a new chat", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("NEVER re-ask", OPEN_LIBRARY_COACH_RULE)
        self.assertIn("Fan Fault Current", OPEN_LIBRARY_COACH_RULE)
        self.assertIn("freezer evaporator fan", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("cookware", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("complete stabilizer jack assembly", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("ice and moisture", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("page 36", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("terminator", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("firefly", OPEN_LIBRARY_COACH_RULE.lower())
        self.assertIn("wired coach can", OPEN_LIBRARY_COACH_RULE.lower())
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


class TestFcrE2FanFaultFacts(unittest.TestCase):
    def test_extracts_e2_and_fan_readings(self):
        facts = extract_stated_facts(
            WO_155578 + ". fan V 14.28-10.37 V; fan amps 0.383-0.442 A; E2 returned after thaw"
        )
        self.assertEqual(facts.get("fan_fault"), "e2")
        self.assertEqual(facts.get("fan_volts"), "reported")
        self.assertEqual(facts.get("fan_amps"), "reported")

    def test_e2_search_boost_is_fan_replacement_not_compressor_only(self):
        facts = extract_stated_facts(WO_155578)
        boost = coach_library_search_boost(facts)
        low = boost.lower()
        self.assertIn("fan fault", low)
        self.assertIn("fan replacement", low)
        self.assertNotIn("inoperable compressor", low)
        self.assertNotIn("no power", low)

    def test_stated_facts_rule_forbids_board_only_cage(self):
        rule = format_stated_facts_rule(extract_stated_facts(WO_155578 + " fan V 12.4 V"))
        low = rule.lower()
        self.assertIn("never re-ask", low)
        self.assertIn("freezer evaporator fan", low)
        self.assertIn("board only", low)

    def test_powered_not_cooling_without_e2_still_not_fan_path(self):
        facts = extract_stated_facts(CHASE_BAY)
        self.assertNotIn("fan_fault", facts)
        self.assertFalse(is_fcr_e2_fan_fault_context("Refrigerators", "Furrion FCR10", CHASE_BAY))


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

    def test_chase_terminal_ask_shows_library_page(self):
        for msg in (
            "show me the page with output terminals labeled",
            "inverter PCB terminals",
        ):
            self.assertTrue(wants_board_or_terminal_figure(msg), msg)
            self.assertTrue(wants_library_page_shown(msg), msg)

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
        self.assertIn("_load_gd_library_coach", src)
        self.assertIn("gd_library_coach.py", src)
        self.assertIn("HARD_TREE_EXCLUSIVE_CHAT", src)
        self.assertIn("FIGURE_PAGE_HONESTY", src)

    def test_jobs_plan_function_still_present(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("def run_guided_diagnostics(", src)
        self.assertIn("Write the guided diagnostic plan now.", src)
        self.assertIn("Bay procedure PDF", src)
        self.assertIn("Generate {BAY_PROCEDURE_LABEL}", src)
        self.assertNotIn("Start Job + Build Test Plan", src)
        self.assertIn("figure_seek: bool = False", src)
        self.assertNotIn("figure_seek=True", src.split("def run_guided_diagnostics")[1][:800])
        self.assertIn("level_up_context: bool = False", src)
        self.assertNotIn("level_up_context=True", src.split("def run_guided_diagnostics")[1][:1200])
        self.assertIn("ac_context: bool = False", src)
        self.assertNotIn("ac_context=True", src.split("def run_guided_diagnostics")[1][:1200])
        self.assertIn("fan_fault_context: bool = False", src)
        self.assertNotIn("fan_fault_context=True", src.split("def run_guided_diagnostics")[1][:1600])
        self.assertIn("water_heater_context: bool = False", src)
        self.assertNotIn("water_heater_context=True", src.split("def run_guided_diagnostics")[1][:1800])
        self.assertIn("cooktop_context: bool = False", src)
        self.assertNotIn("cooktop_context=True", src.split("def run_guided_diagnostics")[1][:2000])
        self.assertIn("stabilizer_context: bool = False", src)
        self.assertNotIn("stabilizer_context=True", src.split("def run_guided_diagnostics")[1][:2200])
        self.assertIn("ice_moisture_context: bool = False", src)
        self.assertNotIn("ice_moisture_context=True", src.split("def run_guided_diagnostics")[1][:2400])
        self.assertNotIn("level_up_can_context=True", src.split("def run_guided_diagnostics")[1][:2600])

    def test_figure_honesty_is_wired(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("FIGURE_PAGE_HONESTY", src)
        self.assertIn("wants_library_page_shown", src)
        self.assertIn("pick_diagram_page_numbers", src)
        self.assertIn("LEVEL_UP_PRODUCT_LOCK", src)
        self.assertIn("level_up_search_symptom", src)
        self.assertIn("skip_unity_for_level_up", src)
        self.assertIn("AC_PRODUCT_LOCK", src)
        self.assertIn("ac_search_symptom", src)
        self.assertIn("skip_unity_for_ac", src)
        self.assertIn("FCR_E2_FAN_FAULT_PRODUCT_LOCK", src)
        self.assertIn("fcr_e2_search_symptom", src)
        self.assertIn("is_fcr_e2_fan_fault_context", src)
        self.assertIn("rank_chunks_for_fcr_fan_fault", src)
        self.assertIn("claims_fcr_e2_board_only_cage", src)
        self.assertIn("ensure_fcr_e2_fan_rr", src)
        self.assertIn("WATER_HEATER_PRODUCT_LOCK", src)
        self.assertIn("water_heater_search_symptom", src)
        self.assertIn("skip_unity_for_water_heater", src)
        self.assertIn("is_water_heater_context", src)
        self.assertIn("COOKTOP_PRODUCT_LOCK", src)
        self.assertIn("cooktop_search_symptom", src)
        self.assertIn("is_cooktop_pan_on_flameout_context", src)
        self.assertIn("ensure_cooktop_tip_pan_check", src)
        self.assertIn("PSX1_PRODUCT_LOCK", src)
        self.assertIn("stabilizer_search_symptom", src)
        self.assertIn("is_stabilizer_override_pin_context", src)
        self.assertIn("ensure_stabilizer_assembly_rr", src)
        self.assertIn("ICE_MOISTURE_PRODUCT_LOCK", src)
        self.assertIn("ice_moisture_search_symptom", src)
        self.assertIn("is_fridge_ice_moisture_context", src)
        self.assertIn("rank_chunks_for_ice_moisture", src)
        self.assertIn("ensure_fridge_ice_moisture_path", src)
        self.assertIn("supplement_ice_moisture_pages", src)
        self.assertIn("is_facr_rooftop_freeze_context", src)
        self.assertIn("is_firefly_can_path_context", src)
        self.assertIn("FACR_FREEZE_SEARCH_BOOST", src)
        self.assertIn("FIREFLY_CAN_SEARCH_BOOST", src)
        self.assertIn("CCD-0007990", src)
        self.assertIn("CCD-0008666", src)
        self.assertIn("LEVEL_UP_CAN_PRODUCT_LOCK", src)
        self.assertIn("is_level_up_manual_can_conflict_context", src)
        self.assertIn("ensure_level_up_manual_can_path", src)
        self.assertIn("rank_chunks_for_level_up_can", src)
        self.assertIn("Fan Replacement", FCR_E2_FAN_FAULT_PRODUCT_LOCK)
        self.assertIn("freezer evaporator fan", FCR_E2_FAN_FAULT_PRODUCT_LOCK.lower())
        self.assertFalse(claims_fcr_e2_board_only_cage(FCR_E2_FAN_FAULT_PRODUCT_LOCK))

    def test_no_tree_dump_hint_in_coach_module(self):
        coach = (ROOT / "gd_library_coach.py").read_text()
        self.assertNotIn("format_procedure_library_hint", coach)
        self.assertNotIn("fan_replacement", coach)


if __name__ == "__main__":
    unittest.main()
