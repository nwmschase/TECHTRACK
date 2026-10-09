"""Each live bay case must print the same correction Guided Diagnostics uses."""
import unittest
from io import BytesIO

from bay_procedure import (
    ICE_MONTH_CLOSE,
    clean_ocr_prose,
    clean_source_excerpt,
    compile_bay_procedure,
    compose_sheet,
    layout_problems,
    render_bay_procedure_pdf,
)
from gd_library_coach import (
    DOMETIC_CEILING_LINE,
    FACT12_FREEZE_RESECURE_LINE,
    GIRARD_PETIT_ALIGN_LINE,
    GROUND_CONTROL_LEVEL_LINE,
    PSX1_ASSEMBLY_RR_SHOP_LINE,
    COOKTOP_TIP_LOW_REPAIR,
)

GROUNDED = (
    "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
    "tires off the ground even though the coach was nearly level."
)


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def _sheet(concern, brand="", model="", category="", chunks=None):
    proc = compile_bay_procedure(
        concern=concern,
        brand=brand,
        model=model,
        category=category,
        chunks=chunks or [],
    )
    pdf = render_bay_procedure_pdf(proc)
    return proc, _pdf_text(pdf)


def _no_generic_chart(text: str):
    low = text.lower()
    assert "did the first check pass" not in low
    assert "no matching library excerpt" not in low


class TestSnippetCleanupPatterns(unittest.TestCase):
    def test_ocr_joins_and_cut_snippets_are_repaired(self):
        joined = clean_ocr_prose(
            "Open Cand Topen with no jumper. The fan sits in the cavityso. "
            "Keep pushingup on the latch. The lead is hookedup."
        )
        low = joined.lower()
        self.assertIn("c and t open", low)
        self.assertIn("cavity so", low)
        self.assertIn("pushing up", low)
        self.assertIn("hooked up", low)
        self.assertNotIn("cavityso", low)
        self.assertNotIn("pushingup", low)
        self.assertNotIn("hookedup", low)
        ice = clean_source_excerpt("Open the refrigerator and note any ice (Fig.")
        self.assertNotIn("(Fig.", ice)
        self.assertIn("note any ice", ice.lower())
        cut = clean_source_excerpt("Pin 9 WHITE (WHT) -> Fa.")
        self.assertNotIn("Fa.", cut)
        self.assertEqual(
            clean_source_excerpt("? Boltx 4 ? Mounting Framex 1 ? Screwx 2"),
            "",
        )
        self.assertEqual(
            clean_source_excerpt("Tools required: nut driver, multimeter, sealant."),
            "",
        )


class TestBayCaseFixes(unittest.TestCase):
    def test_s01_facr_caption_matches_and_arrows_stay_inside(self):
        proc, text = _sheet(
            "FACR08 freeze up interior leak condensate",
            "Furrion",
            "FACR08",
            "Air Conditioning",
            chunks=[
                {
                    "title": "Furrion rooftop precautions",
                    "page": 3,
                    "excerpt": "? Do not install in an unventilated space? . Keep the area clear.",
                }
            ],
        )
        self.assertIn("drainage openings", text.lower())
        self.assertNotIn("?", " ".join(proc.bay_order))
        from PIL import Image

        image = Image.open(BytesIO(proc.figures[0].image_png))
        self.assertLess(image.size[1], 200)
        self.assertGreater(image.size[0], 800)
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        frame = next(mark for mark in trace if mark.role == "frame")
        for mark in trace:
            if mark.role != "connector" or not mark.points:
                continue
            for x, y in mark.points:
                self.assertGreater(x, frame.x0 + 2.0, mark.points)
                self.assertLess(x, frame.x1 - 2.0, mark.points)
                self.assertGreater(y, frame.y0 + 2.0)
                self.assertLess(y, frame.y1 - 2.0)

    def test_s02_coleman_drops_brochure_and_cut_snippets(self):
        proc, text = _sheet(
            "Coleman-Mach 2111-0001 fan high is dead",
            "Coleman-Mach",
            "2111-0001",
            "Air Conditioning",
            chunks=[
                {
                    "title": "Coleman-Mach Brochure - TEXT",
                    "page": 1,
                    "excerpt": "Pin 9 WHITE (WHT) -> Fa. The wire nut then the black.",
                }
            ],
        )
        low = text.lower()
        self.assertIn("control board", low)
        self.assertIn("fan", low)
        self.assertNotIn("brochure", low)
        self.assertNotIn("fa.", low)
        self.assertNotIn("(fig.", low)
        _no_generic_chart(text)
        self.assertLessEqual(len(compose_sheet(proc)), 3)

    def test_s03_bal_stays_on_the_tongue_output_wire(self):
        _proc, text = _sheet(
            "BAL Soft-Touch SS 5.1 electric tongue jack dead. Other stabilizers and panel lights work.",
            "BAL",
            "Soft-Touch SS 5.1",
            "Leveling",
        )
        low = text.lower()
        self.assertIn("20300427", low)
        self.assertIn("output wire", low)
        self.assertNotIn("channel", low)
        _no_generic_chart(text)

    def test_s04_keeps_typed_fcr10_and_repairs_c_and_t(self):
        proc, text = _sheet(
            "temperature dial OFF but compressor still running, freezer frozen solid",
            "Furrion",
            "FCR10",
            "Refrigerators",
            chunks=[
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 45,
                    "excerpt": "Cand Topen with no jumper on the thermostat (Fig.",
                }
            ],
        )
        self.assertEqual(proc.model_line, "Furrion FCR10")
        self.assertNotIn("DCGTA", proc.model_line)
        self.assertIn("FCR10", text)
        self.assertNotIn("Cand Topen", text)
        self.assertIn("c and t open", text.lower())
        self.assertNotIn("(Fig.", text)
        self.assertIn("2021128850", text)
        _no_generic_chart(text)

    def test_s05_replaces_the_cooling_unit_only_after_one_month(self):
        proc, text = _sheet(
            "icing up on rear wall — only about half from the top down",
            "Furrion",
            "FCR10",
            "Refrigerators",
        )
        order = " ".join(proc.bay_order)
        self.assertIn(ICE_MONTH_CLOSE, order)
        self.assertIn("1 month", order.lower())
        self.assertIn("replace the cooling unit", order.lower())
        for step in proc.bay_order:
            if "24 to 48" in step.lower():
                self.assertNotIn("replace the cooling unit", step.lower())
        nodes = " ".join(node.text for node in proc.flowchart.nodes).lower()
        self.assertIn("1 month", nodes)
        self.assertNotIn("after 24 to 48 hours", nodes)
        _no_generic_chart(text)
        self.assertLessEqual(len(compose_sheet(proc)), 3)

    def test_s06_does_not_caption_a_sketch_as_an_oem_page(self):
        proc, text = _sheet(
            "Manual Mode dump works. Auto works. Touch pad flashes then returns to the home screen.",
            "",
            "Level Up Advantage 807662",
            "Leveling",
            chunks=[
                {
                    "title": "Lippert QR-092 Level Up Wiring Diagram",
                    "page": 1,
                    "excerpt": "Fig. 1 Wiring Diagram for the controller plug.",
                }
            ],
        )
        self.assertIn("firefly", text.lower())
        images = [image for page in compose_sheet(proc) for image in page.images]
        self.assertEqual(images, [])
        self.assertNotRegex(text, r"(?i)cited library figure(?!s)")
        _no_generic_chart(text)

    def test_s07_e2_repairs_cavity_and_keeps_the_fan_fix(self):
        _proc, text = _sheet(
            "FCR10 E2 fan fault current on the freezer evaporator fan",
            "Furrion",
            "FCR10",
            "Refrigerators",
            chunks=[
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 33,
                    "excerpt": "The fan sits in the cavityso the inverter PCB can see it (Fig.",
                }
            ],
        )
        low = text.lower()
        self.assertIn("inverter pcb", low)
        self.assertNotIn("cavityso", low)
        self.assertNotIn("(fig.", low)
        _no_generic_chart(text)

    def test_s08_furnace_still_replaces_the_wall_thermostat(self):
        _proc, text = _sheet(
            "Suburban NT-20SEQT furnace fan comes on then shuts off, no heat",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
        )
        low = text.lower()
        self.assertIn("wall thermostat", low)
        self.assertIn("sail", low)
        _no_generic_chart(text)

    def test_s09_replaces_the_ceiling_thermostat(self):
        proc, text = _sheet(
            "Dometic B57915 rooftop air conditioner is not cooling.",
            "Dometic",
            "B57915",
            "Air Conditioning",
            chunks=[
                {
                    "title": "Dometic B57915 Installation Manual",
                    "page": 9,
                    "excerpt": "Minor adjustments while pushingup the housing. Installationwe q r 23.",
                }
            ],
        )
        low = text.lower()
        self.assertIn("replace the ceiling thermostat/selector", low)
        self.assertIn("3311071", text)
        self.assertIn(DOMETIC_CEILING_LINE.split(".")[0].lower(), low)
        self.assertNotIn("pushingup", low)
        self.assertNotIn("did the first", low)
        self.assertNotIn("installation", low)
        _no_generic_chart(text)
        self.assertLessEqual(len(compose_sheet(proc)), 3)

    def test_s10_runs_manual_level_then_zero_point(self):
        proc, text = _sheet(
            GROUNDED,
            "Lippert",
            "Ground Control 343633",
            "Leveling",
            chunks=[
                {
                    "title": "Lippert Ground Control notes",
                    "page": 2,
                    "excerpt": "-> If the fault reverses when the harness is swapped, replace the sensor.",
                }
            ],
        )
        low = text.lower()
        self.assertIn("manual level", low)
        self.assertIn("zero-point", low)
        self.assertIn("front", low)
        self.assertIn("five", low)
        self.assertIn("rear", low)
        self.assertIn("enter", low)
        self.assertIn("tires off the ground", low)
        self.assertNotIn("->", " ".join(proc.bay_order))
        self.assertIn("manual level", GROUND_CONTROL_LEVEL_LINE.lower())
        _no_generic_chart(text)
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        self.assertLessEqual(len(compose_sheet(proc)), 3)

    def test_s11_and_s12_resecure_the_freeze_sensor(self):
        bad = {
            "title": "Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666",
            "page": 5,
            "excerpt": (
                "FACR08HESA2 8K rooftop. ? Do not install in an unventilated space. "
                "? Boltx 4 ? Mounting Framex 1 ? Screwx 2"
            ),
        }
        for concern in (
            "Furrion FACT12SA2 rooftop shows E3",
            "Furrion FACT12SA2 rooftop shows E2",
        ):
            proc, text = _sheet(concern, "Furrion", "FACT12SA2", "Air Conditioning", chunks=[bad])
            low = text.lower()
            self.assertIn("resecure the freeze sensor", low, concern)
            self.assertIn(FACT12_FREEZE_RESECURE_LINE.split(".")[0].lower(), low)
            self.assertIn("not the fact12", low)
            self.assertNotIn("boltx", low)
            self.assertNotIn("?", " ".join(proc.bay_order))
            self.assertNotIn("did the first", low)
            _no_generic_chart(text)

    def test_s13_aligns_the_petit_tube_before_the_control_board(self):
        proc, text = _sheet(
            "Girard GSWH-2 E8 lockout after flame",
            "Girard",
            "GSWH-2",
            "Water Heaters",
            chunks=[
                {
                    "title": "Girard tool list",
                    "page": 14,
                    "excerpt": "Tools required: wrenches. Replace the control board (Fig. Efault (i.",
                }
            ],
        )
        order = " ".join(proc.bay_order).lower()
        self.assertIn("align the petit tube", order)
        self.assertIn(GIRARD_PETIT_ALIGN_LINE.split(".")[0].lower(), order)
        self.assertLess(order.index("petit tube"), order.index("control board"))
        self.assertFalse(any(step.lower().startswith("replace the control board") for step in proc.bay_order))
        low = text.lower()
        self.assertNotIn("(fig.", low)
        self.assertNotIn("efault", low)
        self.assertNotIn("tools required", low)
        _no_generic_chart(text)

    def test_s14_replaces_the_complete_jack_and_leaves_model_blank(self):
        proc, text = _sheet(
            "Front stabilizer jack. Power extend works. Manual override will not engage. The roll pin is broken.",
            "",
            "",
            "Leveling",
            chunks=[
                {
                    "title": "Lippert PSX1 CCD-0007345",
                    "page": 7,
                    "excerpt": "Notes Fig. 5 Troubleshooting What's Happening? The lead is hookedup to lippert.",
                }
            ],
        )
        low = text.lower()
        self.assertEqual(proc.model_line, "")
        self.assertIn("complete front stabilizer jack", low)
        self.assertIn("do not replace the coupler only", low)
        self.assertIn(PSX1_ASSEMBLY_RR_SHOP_LINE.split(".")[0][:40].lower(), low)
        self.assertNotIn("hookedup", low)
        self.assertNotIn("(fig.", low)
        self.assertNotIn("lippert.", low)
        _no_generic_chart(text)
        pages = compose_sheet(proc)
        header = [t.text.strip() for t in pages[0].texts if t.role == "header"]
        self.assertIn("MODEL", header)
        self.assertNotIn("MODEL\n-", "\n".join(header))

    def test_s15_repositions_the_thermocouple_tip(self):
        proc, text = _sheet(
            "Suburban SDN2U cooktop. Burner goes out with a pan on. The thermocouple tip sits low and gets pushed.",
            "Suburban",
            "SDN2U",
            "Cooktops",
            chunks=[
                {
                    "title": "Suburban range (OCR)",
                    "page": 1,
                    "excerpt": "",
                }
            ],
        )
        low = text.lower()
        self.assertIn("reposition the thermocouple tip", low)
        self.assertIn(COOKTOP_TIP_LOW_REPAIR.split(".")[1].strip().lower()[:40], low)
        self.assertNotIn("no matching library excerpt", low)
        self.assertNotIn("(ocr)", low)
        _no_generic_chart(text)
        self.assertGreaterEqual(len(proc.bay_order), 6)
        self.assertLessEqual(len(compose_sheet(proc)), 3)
