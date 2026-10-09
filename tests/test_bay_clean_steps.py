"""Generic bay sheets are shop steps. OCR headers stay out of the order and SOURCES."""
import unittest

from bay_procedure import (
    clean_ocr_prose,
    clean_source_excerpt,
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    join_brand_model,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
    sheet_standard_violations,
)

FURNACE_CONCERN = "Will not blow warm; fan turns on then shuts off."
FURNACE_P28 = {
    "title": "Suburban Furnace Service and Training Manual",
    "page": 28,
    "excerpt": (
        "28 TIME LINE DESCRIPTION Start Time Thermostat Calls for Heat The wall "
        "thermostat controls the operation of the dual stage furnace by reacting to "
        "room temperature. This allows current to flow through the ON/OFF switch."
    ),
}
FURNACE_P26 = {
    "title": "Suburban Furnace Service and Training Manual",
    "page": 26,
    "excerpt": (
        "26 TIME LINE DESCRIPTION Start Time Thermostat Calls for Heat The wall "
        "thermostat controls the operation of the furnace by reacting to room temperature."
    ),
}
FURNACE_P27 = {
    "title": "Suburban Furnace Service and Training Manual",
    "page": 27,
    "excerpt": (
        "27 SEQUENCE OF OPERATION FOR 24 VAC FAN CONTROL MODULE BOARD PART NUMBER 520947 "
        "TIME LINE DESCRIPTION Start Time Thermostat Calls for Heat The wall thermostat "
        "controls the operation of the furnace by reacting to room temperature."
    ),
}
E2_CONCERN = "Freezes contents; intermittent blinking 2 / E2; temp control intermittent."
E2_P27 = {
    "title": "Furrion FCR08 FCR10 12V Refrigerator Troubleshooting and Service Manual CCD-0008122",
    "page": 27,
    "excerpt": (
        "Rev: 03.30.26 Page 27 Error Code - Fan Fault Diagnostics Connect power to the "
        "Connect power to the appliance and locate the inverter PCB. Is the nominal voltage 12V?"
    ),
}
E2_P29 = {
    "title": "Furrion FCR08 FCR10 12V Refrigerator Troubleshooting and Service Manual CCD-0008122",
    "page": 29,
    "excerpt": (
        "e issue resolved? Yes No Replace the inverter PCB and fan. Proceed to Compressor "
        "Inverter PCB Replacement and Fan Replacement in Repair Section 2."
    ),
}


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


class TestModelLine(unittest.TestCase):
    def test_brand_is_not_repeated_on_the_model_line(self):
        self.assertEqual(
            join_brand_model("Suburban", "Suburban NT-20SEQT"),
            "Suburban NT-20SEQT",
        )
        self.assertEqual(
            join_brand_model("Furrion", "FCR10DCGTA-BG-PWH"),
            "Furrion FCR10DCGTA-BG-PWH",
        )
        proc = compile_bay_procedure(
            concern=FURNACE_CONCERN,
            brand="Suburban",
            model="Suburban NT-20SEQT",
            category="Furnaces",
            chunks=[FURNACE_P28],
        )
        self.assertEqual(proc.model_line, "Suburban NT-20SEQT")
        self.assertNotIn("Suburban Suburban", proc.model_line)


class TestOcrCleanup(unittest.TestCase):
    def test_headers_and_duplicated_phrases_come_out(self):
        cleaned = clean_ocr_prose(E2_P27["excerpt"])
        low = cleaned.lower()
        self.assertNotIn("rev:", low)
        self.assertNotIn("page 27", low)
        self.assertNotIn("connect power to the connect power", low)
        self.assertIn("connect power to the appliance", low)
        source = clean_source_excerpt(FURNACE_P28["excerpt"]).lower()
        self.assertNotIn("time line", source)
        self.assertNotIn("sequence of operation", source)
        self.assertIn("wall thermostat", source)


class TestSuburbanFurnaceBay(unittest.TestCase):
    def test_jumper_then_sail_not_the_timeline(self):
        proc = compile_bay_procedure(
            concern=FURNACE_CONCERN,
            brand="Suburban",
            model="Suburban NT-20SEQT",
            category="Furnaces",
            chunks=[FURNACE_P26, FURNACE_P27, FURNACE_P28],
        )
        order = " ".join(proc.bay_order).lower()
        plain = procedure_plain_text(proc).lower()
        self.assertIn("page 28", proc.primary_cite.lower())
        self.assertIn("suburban", proc.primary_cite.lower())
        self.assertIn("jumper", order)
        self.assertIn("r/w", order)
        self.assertIn("wall thermostat", order)
        self.assertIn("sail", order)
        self.assertIn("confirmed correction", order)
        self.assertIn("replace the wall thermostat", order)
        self.assertNotIn("time line", order)
        self.assertNotIn("sequence of operation", order)
        self.assertNotIn("time line", plain)
        excerpts = " ".join((s.get("excerpt") or "") for s in proc.sources).lower()
        self.assertNotIn("time line", excerpts)
        self.assertNotIn("sequence of operation", excerpts)
        self.assertTrue(any(s.get("page") == 28 for s in proc.sources))
        self.assertEqual(sheet_standard_violations(procedure_body_text(proc)), [])
        for node in proc.flowchart.nodes:
            blob = node.text.replace("\n", " ").strip()
            if node.kind == "decision":
                self.assertTrue(blob.endswith("?"))
            else:
                self.assertTrue(blob.endswith("."))
        rects = flowchart_node_rects(proc.flowchart, 36.0, 50.0, 540.0, 612.0)
        self.assertEqual(flowchart_boxes_overlap(rects, gap=14.0), [])
        pdf = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        self.assertIn("suburban nt-20seqt", pdf)
        self.assertNotIn("suburban suburban", pdf)
        self.assertIn("r/w", pdf)
        self.assertIn("sail", pdf)
        self.assertNotIn("time line", pdf)


class TestE2FanFaultBay(unittest.TestCase):
    def test_steps_follow_the_fan_fault_diamond(self):
        proc = compile_bay_procedure(
            concern=E2_CONCERN,
            brand="Furrion",
            model="FCR10DCGTA-BG-PWH",
            category="Refrigerators",
            chunks=[E2_P27, E2_P29],
        )
        order = " ".join(proc.bay_order).lower()
        self.assertEqual(proc.model_line, "Furrion FCR10DCGTA-BG-PWH")
        self.assertIn("page 27", proc.primary_cite.lower())
        self.assertIn("ccd-0008122", proc.primary_cite.lower())
        self.assertIn("12v", order)
        self.assertIn("f+", order)
        self.assertIn("f-", order)
        self.assertIn("inverter pcb and the fan", order)
        self.assertIn("confirmed correction", order)
        self.assertNotIn("rev:", order)
        self.assertNotIn("connect power to the connect power", order)
        excerpts = " ".join((s.get("excerpt") or "") for s in proc.sources).lower()
        self.assertNotIn("rev:", excerpts)
        self.assertNotIn("connect power to the connect power", excerpts)
        self.assertTrue(any("ccd-0008122" in (s.get("title") or "").lower() for s in proc.sources))
        self.assertTrue(any(s.get("page") == 27 for s in proc.sources))
        self.assertEqual(sheet_standard_violations(procedure_body_text(proc)), [])
        pdf = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        self.assertIn("inverter pcb and the fan", pdf)
        self.assertNotIn("rev:", pdf)
        self.assertNotIn("connect power to the connect power", pdf)


class TestGenericDecisionSteps(unittest.TestCase):
    def test_unloaded_job_uses_the_yes_no_sentence_not_the_header(self):
        proc = compile_bay_procedure(
            concern="Rooftop air conditioner will not cool.",
            brand="Dometic",
            model="Penguin II",
            category="Air Conditioning",
            chunks=[
                {
                    "title": "Dometic rooftop service manual",
                    "page": 4,
                    "excerpt": (
                        "Rev: 01.02.26 Page 4 Connect power to the Connect power to the unit. "
                        "If the valve is open, replace the valve. If it is closed, retest the cool air."
                    ),
                }
            ],
        )
        order = " ".join(proc.bay_order).lower()
        self.assertIn("replace the valve", order)
        self.assertIn("if ", order)
        self.assertIn("confirmed correction", order)
        self.assertNotIn("rev:", order)
        self.assertNotIn("connect power to the connect power", order)
        excerpts = " ".join((s.get("excerpt") or "") for s in proc.sources).lower()
        self.assertNotIn("rev:", excerpts)
        self.assertNotIn("connect power to the connect power", excerpts)
        self.assertIn("dometic", proc.model_line.lower())
        self.assertEqual(sheet_standard_violations(procedure_body_text(proc)), [])


if __name__ == "__main__":
    unittest.main()
