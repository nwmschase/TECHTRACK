"""BAL Soft-Touch SS 5.1 tongue-only dead: panel 20300427, not coupler or fuse first."""
import unittest

from bay_procedure import (
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
    rewrite_bay_search_symptom,
    sheet_standard_violations,
)
from gd_library_coach import (
    BAL_TONGUE_PART,
    BAL_TONGUE_PRODUCT_LOCK,
    BAL_TONGUE_SEARCH_BOOST,
    OPEN_LIBRARY_COACH_RULE,
    bal_tongue_stage,
    ensure_bal_tongue_only_path,
    extract_bal_tongue_facts,
    extract_stated_facts,
    is_bal_soft_touch_tongue_only_context,
    is_stabilizer_override_pin_context,
    rank_chunks_for_bal_tongue,
    reply_leads_with_bal_banned_primary,
    reply_leads_with_bal_fuse_harness,
)

WO = (
    "BAL Soft-Touch SS 5.1 electric tongue jack dead. "
    "Other stabilizers and panel lights work. Motor OK on direct 12V. Coupler OK."
)

PANEL_PAGE = {
    "title": "BAL SS 5.1 Stabilizing System INS.STA.001",
    "category": "Leveling",
    "page": 4,
    "excerpt": (
        "Tongue jack will not extend. If the motor operates on direct 12V and the coupler "
        "is engaged, the issue is the user panel 20300427 or the wiring between the panel and jack."
    ),
}
COUPLER_PAGE = {
    "title": "BAL tongue jack coupler",
    "category": "Leveling",
    "page": 2,
    "excerpt": "Replace the coupler 21700072. Shear pin. Coupler replacement is the repair.",
}
FUSE_PAGE = {
    "title": "BAL power supply",
    "category": "Leveling",
    "page": 1,
    "excerpt": "Check the 30A fuse and the remote stabilizer harness before any jack.",
}
COUPLER_FIRST = (
    "Replace the coupler 21700072 and the shear pin. "
    "Then check the 30A fuse and the remote stab harness."
)
FUSE_FIRST = (
    "Start with the 30A fuse and the remote stabilizer harness. "
    "The tongue jack fuse is open."
)


def _pdf_text(pdf: bytes) -> str:
    try:
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


class TestBalTongueContext(unittest.TestCase):
    def test_tongue_only_dead_is_the_panel_path(self):
        self.assertTrue(is_bal_soft_touch_tongue_only_context("Leveling", "BAL SS 5.1", WO))
        self.assertFalse(is_stabilizer_override_pin_context("Leveling", "BAL SS 5.1", WO))
        facts = extract_stated_facts(WO)
        self.assertEqual(facts.get("bal_tongue"), "only_dead")
        self.assertEqual(facts.get("tongue_motor_12v"), "ok")
        self.assertEqual(facts.get("tongue_coupler"), "ok")
        self.assertEqual(bal_tongue_stage(facts), "prove")
        self.assertIn("20300427", OPEN_LIBRARY_COACH_RULE)
        self.assertIn("INS.STA.001", OPEN_LIBRARY_COACH_RULE)
        self.assertIn("20300427", BAL_TONGUE_PRODUCT_LOCK)
        self.assertIn("do not lead", BAL_TONGUE_PRODUCT_LOCK.lower())

    def test_psx1_and_all_jacks_dead_are_not_this_path(self):
        psx1 = (
            "Lippert PSX1 front stabilizer. Power works. Manual override will not engage. "
            "Roll pin seized at the override coupler."
        )
        self.assertFalse(is_bal_soft_touch_tongue_only_context("Leveling", "PSX1", psx1))
        self.assertTrue(is_stabilizer_override_pin_context("Leveling", "PSX1", psx1))
        all_dead = (
            "BAL Soft-Touch SS 5.1 all jacks dead. Panel lights are out. Tongue jack dead."
        )
        self.assertFalse(is_bal_soft_touch_tongue_only_context("Leveling", "BAL", all_dead))

    def test_coupler_exception_is_not_the_panel_primary(self):
        concern = (
            "BAL Soft-Touch SS 5.1 tongue jack dead. Other stabilizers and panel lights work. "
            "Manual override will not turn."
        )
        self.assertTrue(is_bal_soft_touch_tongue_only_context("", "BAL SS 5.1", concern))
        facts = extract_bal_tongue_facts(concern)
        facts["bal_tongue"] = "only_dead"
        self.assertEqual(bal_tongue_stage(facts), "coupler")


class TestBalTongueCoach(unittest.TestCase):
    def test_coupler_and_fuse_first_rewrites_to_panel_climax(self):
        self.assertTrue(reply_leads_with_bal_banned_primary(COUPLER_FIRST))
        self.assertTrue(reply_leads_with_bal_fuse_harness(FUSE_FIRST))
        facts = extract_stated_facts(WO)
        for bad in (COUPLER_FIRST, FUSE_FIRST, "Searching the manuals for a tongue procedure."):
            fixed = ensure_bal_tongue_only_path(bad, facts)
            low = fixed.lower()
            self.assertIn(BAL_TONGUE_PART, fixed)
            self.assertIn("tongue channel", low)
            self.assertIn("pigtail", low)
            self.assertIn("ins.sta.001", low)
            self.assertFalse(reply_leads_with_bal_banned_primary(fixed), fixed[:240])
            self.assertFalse(reply_leads_with_bal_fuse_harness(fixed), fixed[:240])
            self.assertLess(low.find("20300427"), low.find("coupler"))

    def test_missing_channel_voltage_climaxes_at_20300427(self):
        facts = extract_stated_facts(
            WO + " No 12V at the soft-touch panel tongue channel."
        )
        self.assertEqual(facts.get("tongue_channel_volts"), "missing")
        self.assertEqual(bal_tongue_stage(facts), "panel")
        fixed = ensure_bal_tongue_only_path(COUPLER_FIRST, facts)
        self.assertIn("20300427", fixed)
        self.assertIn("replace the soft-touch user panel", fixed.lower())
        self.assertFalse(reply_leads_with_bal_banned_primary(fixed))

    def test_panel_voltage_present_climaxes_at_pigtail(self):
        facts = extract_stated_facts(
            WO + " 12V is present at the soft-touch panel tongue channel."
        )
        self.assertEqual(facts.get("tongue_channel_volts"), "present")
        self.assertEqual(bal_tongue_stage(facts), "pigtail")
        fixed = ensure_bal_tongue_only_path("Replace the coupler.", facts)
        low = fixed.lower()
        self.assertIn("pigtail", low)
        self.assertIn("repair", low)
        self.assertIn("tongue channel", low)
        self.assertLess(low.find("pigtail"), low.find("coupler"))

    def test_override_wont_turn_keeps_coupler_and_not_fuse(self):
        facts = extract_stated_facts(
            "BAL Soft-Touch SS 5.1 tongue jack only dead. Stabilizers work. Panel lights work. "
            "Manual override will not turn."
        )
        self.assertEqual(bal_tongue_stage(facts), "coupler")
        fixed = ensure_bal_tongue_only_path(FUSE_FIRST, facts)
        low = fixed.lower()
        self.assertIn("coupler", low)
        self.assertFalse(reply_leads_with_bal_fuse_harness(fixed), fixed[:300])
        self.assertNotIn("20300427", fixed.split("Replace the coupler", 1)[0])


class TestBalTongueBayAndRank(unittest.TestCase):
    def test_panel_page_outranks_coupler_and_fuse(self):
        q = rewrite_bay_search_symptom("Leveling", "BAL SS 5.1", WO)
        self.assertIn("20300427", q)
        self.assertIn("ins.sta.001", q.lower())
        self.assertIn("20300427", BAL_TONGUE_SEARCH_BOOST)
        ranked = rank_chunks_for_bal_tongue([FUSE_PAGE, COUPLER_PAGE, PANEL_PAGE], q, limit=3)
        self.assertEqual(ranked[0]["title"], PANEL_PAGE["title"])
        titles = [row["title"] for row in ranked]
        self.assertNotIn(COUPLER_PAGE["title"], titles)
        self.assertNotIn(FUSE_PAGE["title"], titles)

    def test_bay_sheet_climax_is_panel_then_pigtail(self):
        proc = compile_bay_procedure(
            concern=WO,
            brand="BAL",
            model="Soft-Touch SS 5.1",
            category="Leveling",
            chunks=[FUSE_PAGE, COUPLER_PAGE, PANEL_PAGE],
        )
        text = procedure_plain_text(proc)
        low = text.lower()
        self.assertIn("20300427", text)
        self.assertIn("ins.sta.001", low)
        self.assertIn("tongue channel", low)
        self.assertIn("pigtail", low)
        self.assertIn("12v", low)
        order = " ".join(proc.bay_order)
        self.assertNotIn("coupler", proc.bay_order[0].lower())
        self.assertNotIn("fuse", proc.bay_order[0].lower())
        self.assertNotIn("30a", proc.bay_order[0].lower())
        self.assertNotIn("shear", proc.bay_order[0].lower())
        self.assertNotIn("harness", proc.bay_order[0].lower())
        self.assertLess(order.lower().find("20300427"), order.lower().find("coupler"))
        self.assertLess(order.lower().find("tongue channel"), order.lower().find("coupler"))
        flow = " ".join(node.text for node in proc.flowchart.nodes).lower()
        self.assertIn("20300427", flow)
        self.assertIn("tongue channel", flow)
        self.assertIn("pigtail", flow)
        self.assertNotIn("coupler", flow)
        self.assertNotIn("fuse", flow)
        self.assertNotIn("shear", flow)
        donot = " ".join(proc.do_not).lower()
        self.assertIn("coupler", donot)
        self.assertIn("30a", donot)
        self.assertIn("harness", donot)
        self.assertFalse(sheet_standard_violations(procedure_body_text(proc)))
        rects = flowchart_node_rects(proc.flowchart, 36.0, 50.0, 540.0, 612.0)
        self.assertEqual(flowchart_boxes_overlap(rects, gap=14.0), [])
        pdf_low = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        if pdf_low:
            self.assertIn("20300427", pdf_low)
            self.assertIn("tongue channel", pdf_low)
            self.assertLess(pdf_low.find("20300427"), pdf_low.find("coupler"))


if __name__ == "__main__":
    unittest.main()
