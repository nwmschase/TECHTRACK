"""Engine + Furrion CCD-0008122 tree. Run: python3 -m unittest tests.test_guided_flow_engine"""
from __future__ import annotations

import unittest

from guided_flow_engine import (
    PROCEDURE_TREES,
    binary_button_labels,
    engine_turn,
    find_matching_procedure,
    get_procedure,
    get_procedure_node,
    job_pin_caption,
    select_start_node_id,
    validate_procedure,
)

FURRION_ID = "furrion_fcr_ccd_0008122"
SM = "Furrion FCR08/FCR10 SM CCD-0008122"


class TestTreeLoad(unittest.TestCase):
    def test_furrion_is_the_only_loaded_tree(self):
        self.assertEqual(list(PROCEDURE_TREES), [FURRION_ID])

    def test_furrion_validates(self):
        proc = get_procedure(FURRION_ID)
        self.assertTrue(proc)
        self.assertEqual(validate_procedure(proc), [])
        self.assertEqual(proc["brand"], "Furrion")
        self.assertEqual(proc["manual"]["document_code"], "CCD-0008122")
        self.assertEqual(len(proc["nodes"]), 23)

    def test_every_node_cites_a_page(self):
        proc = get_procedure(FURRION_ID)
        for nid, node in proc["nodes"].items():
            self.assertTrue(node.get("source_title"), nid)
            self.assertIsInstance(node.get("source_page"), int, nid)


class TestMatchAndPin(unittest.TestCase):
    def test_matches_model_and_category(self):
        self.assertIsNotNone(find_matching_procedure("Refrigerator", "FCR10DCGTA"))
        self.assertIsNotNone(find_matching_procedure("Refrigerator", "Furrion FCR08"))
        self.assertIsNotNone(find_matching_procedure("", "CCD-0008122"))

    def test_matches_concern_text_when_model_field_empty(self):
        hit = find_matching_procedure("Refrigerator", "", "Furrion FCR10 not cooling")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["id"], FURRION_ID)

    def test_does_not_match_unrelated_fridge(self):
        self.assertIsNone(find_matching_procedure("Refrigerator", "RM2652", "not cooling"))
        self.assertIsNone(find_matching_procedure("Furnaces", "DFMD25111", "fan runs no heat"))
        self.assertIsNone(find_matching_procedure("Slides", "Schwintek", "won't retract"))

    def test_pin_holds_when_ui_model_changes(self):
        first = engine_turn(None, "FCR10 dead, no power", "Refrigerator", "FCR10")
        self.assertTrue(first["used_engine"])
        self.assertEqual(first["ask_flow"]["procedure_id"], FURRION_ID)
        self.assertEqual(first["ask_flow"]["brand"], "Furrion")
        # Widget now says a different brand — pin must not drop the tree or invent another.
        nxt = engine_turn(
            first["ask_flow"],
            "fuse good",
            "Furnaces",
            "Dometic DFMD",
        )
        self.assertTrue(nxt["used_engine"])
        self.assertEqual(nxt["ask_flow"]["procedure_id"], FURRION_ID)
        self.assertEqual(nxt["ask_flow"]["brand"], "Furrion")
        self.assertIn("Pinned job: Furrion", job_pin_caption(nxt["ask_flow"]))


class TestStartGates(unittest.TestCase):
    def setUp(self):
        self.proc = get_procedure(FURRION_ID)

    def test_no_power_starts_at_fuse(self):
        self.assertEqual(
            select_start_node_id(self.proc, "completely dead, no power"),
            "fuse_front_vent",
        )

    def test_fuse_replaced_not_cooling_starts_at_dial(self):
        self.assertEqual(
            select_start_node_id(
                self.proc,
                "replaced the fuse, light on, not cooling",
            ),
            "dial_on_4_5",
        )

    def test_fan_fault_starts_on_p27_not_paper(self):
        self.assertEqual(
            select_start_node_id(self.proc, "2 flash fan fault"),
            "fan_fault_f_terminal_volts",
        )


class TestFurrionPath(unittest.TestCase):
    def _open(self, msg, category="Refrigerator", model="FCR10"):
        return engine_turn(None, msg, category, model)

    def test_no_power_path_cites_page_19(self):
        r = self._open("no power, dead fridge")
        self.assertTrue(r["used_engine"])
        self.assertEqual(r["start_id"], "fuse_front_vent")
        self.assertIn("15A ATC", r["reply"])
        self.assertIn(f"📖 Source: {SM} - page 19", r["reply"])
        self.assertEqual(r["ask_flow"]["source_ledger"][0]["page"], 19)

    def test_fuse_good_then_light_then_dial_then_battery_reading(self):
        r = self._open("no power")
        r = engine_turn(r["ask_flow"], "fuse good", "Refrigerator", "FCR10")
        self.assertFalse(r["reask"])
        self.assertEqual(r["node"]["id"], "cavity_light_check")
        r = engine_turn(r["ask_flow"], "yes", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "dial_on_4_5")
        self.assertIn("page 23", r["reply"])
        r = engine_turn(r["ask_flow"], "yes, dial on 4", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "battery_under_load")
        self.assertIn("page 12", r["reply"])
        r = engine_turn(r["ask_flow"], "12.4V under load", "Refrigerator", "FCR10")
        self.assertEqual(r["answer"], "yes")
        self.assertEqual(r["reading"], 12.4)
        self.assertEqual(r["node"]["id"], "paper_test")
        self.assertIn("page 33", r["reply"])

    def test_low_battery_reading_is_external_power(self):
        r = self._open("replaced fuse, light on, not cooling")
        self.assertEqual(r["start_id"], "dial_on_4_5")
        r = engine_turn(r["ask_flow"], "yes", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "9.8V", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "external_power_issue")
        self.assertIn("page 20", r["reply"])

    def test_paper_fail_operating_no_ends_fan_replacement_not_f_volts(self):
        r = self._open("replaced the fuse, cavity light on, not cooling")
        r = engine_turn(r["ask_flow"], "dial is on 5", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "13.1V under load", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "paper_test")
        r = engine_turn(r["ask_flow"], "paper does not move", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "is_operating_diamond")
        self.assertIn("page 33", r["reply"])
        r = engine_turn(r["ask_flow"], "not operating, compressor silent", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "fan_replacement")
        self.assertIn("Fan Replacement", r["reply"])
        self.assertNotIn("F+", r["reply"])
        self.assertNotIn("F−", r["reply"])
        self.assertNotIn("page 27", r["reply"])

    def test_paper_pass_goes_to_not_cooling_current_not_fan_volts(self):
        r = self._open("not cooling, FCR10 has power")
        r = engine_turn(r["ask_flow"], "yes", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "11.2V", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "left suck right blow", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "not_cooling_current")
        self.assertIn("page 34", r["reply"])
        self.assertNotIn("F+", r["reply"])

    def test_current_reading_gates(self):
        r = self._open("not cooling, has power")
        r = engine_turn(r["ask_flow"], "yes", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "12V", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "pass", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "not_cooling_current")
        low = engine_turn(r["ask_flow"], "2.1A", "Refrigerator", "FCR10")
        self.assertEqual(low["node"]["id"], "oily_substance_check")
        high = engine_turn(r["ask_flow"], "4.2A", "Refrigerator", "FCR10")
        self.assertEqual(high["node"]["id"], "dial_max_one_hour")

    def test_operating_diamond_cold_only_reasks(self):
        r = self._open("replaced fuse, light on, not cooling")
        r = engine_turn(r["ask_flow"], "yes", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "12V", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "fail", "Refrigerator", "FCR10")
        self.assertEqual(r["node"]["id"], "is_operating_diamond")
        again = engine_turn(r["ask_flow"], "still not cooling", "Refrigerator", "FCR10")
        self.assertTrue(again["reask"])
        self.assertEqual(again["ask_flow"]["node_id"], "is_operating_diamond")
        self.assertIn("Cold alone is not this gate", again["reply"])

    def test_unmapped_does_not_advance(self):
        r = self._open("no power")
        again = engine_turn(r["ask_flow"], "maybe later", "Refrigerator", "FCR10")
        self.assertTrue(again["reask"])
        self.assertEqual(again["ask_flow"]["node_id"], "fuse_front_vent")
        self.assertIn("page 19", again["reply"])

    def test_yes_no_buttons_on_binary_gates(self):
        paper = get_procedure_node(get_procedure(FURRION_ID), "paper_test")
        self.assertEqual(binary_button_labels(paper), ("Pass", "pass", "Fail", "fail"))
        light = get_procedure_node(get_procedure(FURRION_ID), "cavity_light_check")
        self.assertEqual(binary_button_labels(light), ("Yes", "yes", "No", "no"))
        end = get_procedure_node(get_procedure(FURRION_ID), "fan_replacement")
        self.assertIsNone(binary_button_labels(end))

    def test_source_ledger_is_silent_and_append_only(self):
        r = self._open("no power")
        r = engine_turn(r["ask_flow"], "fuse good", "Refrigerator", "FCR10")
        r = engine_turn(r["ask_flow"], "yes", "Refrigerator", "FCR10")
        pages = [(s["title"], s["page"]) for s in r["ask_flow"]["source_ledger"]]
        self.assertIn((SM, 19), pages)
        self.assertIn((SM, 23), pages)
        self.assertEqual(len(pages), len(set(pages)))

    def test_history_binds_result_to_cited_page(self):
        r = self._open("no power")
        r = engine_turn(r["ask_flow"], "fuse replaced", "Refrigerator", "FCR10")
        step = r["ask_flow"]["history"][0]
        self.assertEqual(step["node_id"], "fuse_front_vent")
        self.assertEqual(step["result"], "replaced")
        self.assertEqual(step["source_page"], 19)
        self.assertEqual(step["source_title"], SM)


class TestNoInventedSecondTree(unittest.TestCase):
    def test_no_lippert_or_furnace_json_shipped(self):
        banned = ("lippert", "dometic", "suburban", "atwood", "norcold", "level-up", "awning")
        for pid in PROCEDURE_TREES:
            self.assertTrue(pid.startswith("furrion"), pid)
            for token in banned:
                self.assertNotIn(token, pid)


if __name__ == "__main__":
    unittest.main()
