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


if __name__ == "__main__":
    unittest.main()
