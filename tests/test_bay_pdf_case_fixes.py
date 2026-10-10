"""Each live bay case must print the same correction Guided Diagnostics uses."""
import re
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
    def test_hyphen_splits_runons_and_flowchart_scraps_drop(self):
        joined = clean_ocr_prose(
            "The air con- ditioner lost refriger - ant. This will pre - vent heat. "
            "Check the FUR - NACE next."
        )
        low = joined.lower()
        self.assertIn("conditioner", low)
        self.assertIn("refrigerant", low)
        self.assertIn("prevent", low)
        self.assertIn("furnace", low)
        self.assertNotIn("con- ditioner", low)
        self.assertNotIn("refriger - ant", low)
        run_on = clean_ocr_prose("There is damage to the knob Loosen the lock nut.")
        self.assertIn("knob.", run_on)
        self.assertIn("Loosen", run_on)
        self.assertNotIn("knob Loosen", run_on)
        self.assertEqual(
            clean_source_excerpt(
                "Yes No Proceed to the Voltage Drop-out Troubleshooting section."
            ),
            "",
        )
        self.assertEqual(
            clean_source_excerpt("Yes No Replace the inverter PCB and fan."),
            "",
        )
        ice = clean_source_excerpt(
            "Open the refrigerator and note any ice 36B) build-up in the cavity."
        )
        self.assertNotIn("36B)", ice)
        self.assertIn("build-up", ice.lower())
        self.assertEqual(clean_source_excerpt("4A) engaged the coupler and stopped."), "")
        self.assertEqual(
            clean_source_excerpt("Parts 5012486 and 2025012487 are listed here."),
            "",
        )
        self.assertEqual(
            clean_source_excerpt("Pin 5 is Green High Fan relay Gray (."),
            "",
        )
        self.assertEqual(clean_source_excerpt("Handling the Device ?."), "")
        self.assertEqual(clean_source_excerpt("1 ? CSA Z240 and a caution note."), "")
        self.assertNotIn(
            "grease",
            clean_source_excerpt("A grease fire can start if the pan is left.").lower(),
        )
        self.assertNotIn("piezo", clean_source_excerpt('Use the piezo lighting open "flame').lower())

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
        self.assertGreater(image.size[1], 70)
        self.assertLess(image.size[1], 120)
        self.assertGreater(image.size[0], 1000)
        pages = compose_sheet(proc)
        self.assertTrue(
            any("drainage openings" in (t.text or "").lower() for page in pages for t in page.texts)
        )
        for page in pages:
            if not page.images:
                continue
            has_body = any((t.text or "").strip() and t.role != "header" for t in page.texts if len(t.text or "") > 24)
            for image_box in page.images:
                if image_box.h < 240:
                    self.assertTrue(has_body)
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        frame = next(mark for mark in trace if mark.role == "frame")
        for mark in trace:
            if mark.role != "connector" or not mark.points:
                continue
            for x, y in mark.points:
                self.assertGreater(x, frame.x0 + 2.0, mark.points)
                self.assertLess(x, frame.x1 - 44.0, mark.points)
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

    def test_s02_figure_is_the_fan_or_board_not_the_plenum(self):
        from PIL import Image

        def _png(label):
            image = Image.new("RGB", (640, 480), (255, 255, 255))
            image.putpixel((10, 10), (0, 0, 0))
            buf = BytesIO()
            image.save(buf, format="PNG")
            return buf.getvalue()

        fan = _png("fan")
        plenum = _png("plenum")
        # Distinct bytes so the sheet can be checked for which art was painted.
        plenum = plenum + b"\x00plenum"
        proc, text = _sheet(
            "Coleman-Mach 2111-0001 fan high is dead",
            "Coleman-Mach",
            "2111-0001",
            "Air Conditioning",
            chunks=[
                {
                    "title": "Coleman-Mach ceiling plenum 6799-730",
                    "page": 2,
                    "excerpt": "Fig. 2 6799-730 ceiling plenum.",
                    "image_png": plenum,
                },
                {
                    "title": "Coleman-Mach 12VDC wall-thermostat rooftop service manual",
                    "page": 8,
                    "excerpt": "Fig. 8 fan and control board at the 9-pin.",
                    "image_png": fan,
                },
            ],
        )
        painted = [image.png for page in compose_sheet(proc) for image in page.images]
        self.assertTrue(painted)
        self.assertTrue(all(png == fan for png in painted))
        self.assertNotIn("6799-730", text)
        self.assertNotIn("plenum", text.lower())
        _no_generic_chart(text)

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
        pages = compose_sheet(proc)
        header = " ".join(t.text for t in pages[0].texts if t.role == "header")
        self.assertIn("Furrion FCR10", header)
        self.assertNotIn("FCR10DCGTA", header)
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
        proc, text = _sheet(
            "Suburban NT-20SEQT furnace fan comes on then shuts off, no heat",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
        )
        low = text.lower()
        self.assertIn("wall thermostat", low)
        self.assertIn("sail", low)
        nodes = " ".join(node.text for node in proc.flowchart.nodes).lower()
        self.assertIn("limit switch", nodes)
        self.assertIn("module board", nodes)
        self.assertNotIn("sail passed", nodes)
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
        self.assertNotIn("con- ditioner", low)
        self.assertNotIn("refriger - ant", low)
        bypass = next(node for node in proc.flowchart.nodes if "peacemaker" in node.text.lower())
        decision = next(node for node in proc.flowchart.nodes if "both bypasses" in node.text.lower())
        self.assertLess(bypass.y, decision.y)
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
        self.assertEqual(len(proc.bay_order), len({step.strip() for step in proc.bay_order}))
        self.assertEqual(proc.bay_order[2].lower().count("confirm the controller"), 0)
        ordered = sorted(
            (node.y, node.text.lower())
            for node in proc.flowchart.nodes
            if node.kind in ("process", "start")
        )
        texts = [text for _y, text in ordered]
        self.assertLess(texts.index(next(t for t in texts if "manual level" in t)), texts.index(next(t for t in texts if "zero point" in t)))
        self.assertLess(texts.index(next(t for t in texts if "zero point" in t)), texts.index(next(t for t in texts if "front five" in t)))
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
            nodes = " ".join(node.text for node in proc.flowchart.nodes).lower()
            self.assertNotIn("reseat", nodes)
            self.assertIn("resecure", nodes)
            _no_generic_chart(text)
        titled = {
            "title": "Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666",
            "page": 3,
            "excerpt": "Check the evaporator coil and the sensor clip.",
        }
        proc, text = _sheet(
            "Furrion FACT12SA2 rooftop shows E3",
            "Furrion",
            "FACT12SA2",
            "Air Conditioning",
            chunks=[titled],
        )
        low = text.lower()
        self.assertNotIn("fact12sa2-ps", low)
        self.assertIn("facr08", low)
        self.assertIn("ccd-0008666", low)

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
        self.assertEqual(len(proc.bay_order), len({step.strip() for step in proc.bay_order}))
        yes = next(node.text.lower() for node in proc.flowchart.nodes if "already in the flame" in node.text.lower())
        no = next(node.text.lower() for node in proc.flowchart.nodes if node.text.lower().startswith("align the petit"))
        self.assertNotEqual(yes, no)
        self.assertNotIn("align", yes)
        self.assertIn("align", no)
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
                },
                {
                    "title": "Electric Rear Stabilizer",
                    "page": 1,
                    "excerpt": "4A) engaged the rear stabilizer. Parts 5012486 and 2025012487.",
                },
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
        self.assertNotIn("4a)", low)
        self.assertNotIn("5012486", text)
        self.assertNotIn("rear stabilizer", low)
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
                    "excerpt": 'A grease fire can start. Use the piezo lighting. open "flame and damage,personal injury.',
                }
            ],
        )
        low = text.lower()
        self.assertIn("reposition the thermocouple tip", low)
        self.assertIn(COOKTOP_TIP_LOW_REPAIR.split(".")[1].strip().lower()[:40], low)
        self.assertNotIn("no matching library excerpt", low)
        self.assertNotIn("(ocr)", low)
        self.assertNotIn("reseat", low)
        self.assertNotIn("grease", low)
        self.assertNotIn("piezo", low)
        self.assertEqual(len(proc.bay_order), len({step.strip() for step in proc.bay_order}))
        _no_generic_chart(text)
        self.assertGreaterEqual(len(proc.bay_order), 6)
        self.assertLessEqual(len(compose_sheet(proc)), 3)
        self.assertIn("reposition", proc.bay_order[1].lower())
        self.assertNotEqual(proc.bay_order[2].strip().lower(), proc.bay_order[5].strip().lower())


_GLUE_ALLOW = {"onecontrol", "techtrack"}


def _glued_tokens(text: str) -> list[str]:
    """A lowercase letter followed by an uppercase letter inside one token."""
    bad = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9'+.-]*", text or ""):
        if token.lower() in _GLUE_ALLOW:
            continue
        if re.search(r"[a-z][A-Z]", token):
            bad.append(token)
    return bad


class TestSnippetScrubRegressions(unittest.TestCase):
    def test_line_joins_use_a_space_and_keep_ranges(self):
        text = clean_ocr_prose(
            "push ENTER Button - If error remains. Error Code - Fan Fault Diagnostics "
            "Connect power to the. Connect power to the appliance and retest. "
            "The sensor reads a typical 3-9V). The code - water flow is low. "
            "Install the screws top - and the bracket."
        )
        low = text.lower()
        self.assertNotIn("buttonif", low)
        self.assertNotIn("codefan", low)
        self.assertNotIn("codewater", low)
        self.assertNotIn("topand", low)
        self.assertIn("button if", low)
        self.assertIn("code fan", low)
        self.assertIn("code water", low)
        self.assertIn("top and", low)
        self.assertIn("3-9v", low)
        self.assertNotIn("3- .", low)
        self.assertEqual(low.count("connect power to the"), 1)
        self.assertIn("connect power to the appliance", low)
        self.assertEqual(_glued_tokens(text), [])

    def test_duplicate_snippets_boilerplate_and_empty_excerpts_drop(self):
        proc, text = _sheet(
            "FACR08 freeze up interior leak condensate",
            "Furrion",
            "FACR08",
            "Air Conditioning",
            chunks=[
                {
                    "title": "Furrion rooftop CCD-0007990",
                    "page": 7,
                    "excerpt": "Clean the drainage openings so water can leave the pan.",
                },
                {
                    "title": "Furrion rooftop CCD-0007990",
                    "page": 19,
                    "excerpt": "Clean the drainage openings so water can leave the pan.",
                },
            ],
        )
        pages = [src.get("page") for src in proc.sources]
        self.assertIn(7, pages)
        self.assertNotIn(19, pages)
        self.assertNotIn("brochure", text.lower())
        self.assertTrue(all((src.get("excerpt") or "").strip() for src in proc.sources))
        self.assertEqual(_glued_tokens(text), [])

    def test_s02_transcription_companion_and_text_figure_stay_off(self):
        from PIL import Image

        text_block = Image.new("RGB", (420, 180), (255, 255, 255))
        for y in (20, 44, 68, 92, 116, 140):
            for x in range(16, 390):
                text_block.putpixel((x, y), (20, 20, 20))
                text_block.putpixel((x, y + 1), (20, 20, 20))
        buf = BytesIO()
        text_block.save(buf, format="PNG")
        proc, text = _sheet(
            "Coleman-Mach 2111-0001 fan high is dead",
            "Coleman-Mach",
            "2111-0001",
            "Air Conditioning",
            chunks=[
                {
                    "title": "TRANSCRIPTION for TechTrack search (OCR companion)",
                    "page": 7,
                    "excerpt": "The wire nut then the black.",
                    "file_path": "Coleman-Mach-Brochure-TEXT.pdf",
                },
                {
                    "title": "Coleman-Mach service manual",
                    "page": 11,
                    "excerpt": "Figure 7 shows the installation paragraph for the cover.",
                    "image_png": buf.getvalue(),
                },
            ],
        )
        low = text.lower()
        self.assertNotIn("brochure", low)
        self.assertNotIn("ocr companion", low)
        self.assertNotIn("transcription", low)
        self.assertNotIn("figure 7", low)
        images = [image for page in compose_sheet(proc) for image in page.images]
        self.assertEqual(images, [])
        self.assertTrue(all((src.get("excerpt") or "").strip() for src in proc.sources))

    def test_s05_does_not_splice_the_next_passage(self):
        proc, text = _sheet(
            "Ice and moisture on the rear wall of the Furrion fridge",
            "Furrion",
            "FCR10",
            "Refrigerators",
            chunks=[
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 36,
                    "excerpt": "After drying, note any ice Refer to Door Gasket Test on the next page.",
                }
            ],
        )
        joined = " ".join(src.get("excerpt") or "" for src in proc.sources).lower()
        self.assertNotIn("ice refer", joined)
        self.assertNotIn("refer to door", joined)
        self.assertNotRegex(text, r"ice Refer")

    def test_s08_drops_the_duplicate_page_snippet(self):
        same = "With the blower running, power in and power out means the sail switch is closed."
        proc, _text = _sheet(
            "Suburban NT-20SEQT furnace fan comes on then shuts off, no heat",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
            chunks=[
                {"title": "Suburban furnace service manual", "page": 26, "excerpt": same},
                {"title": "Suburban furnace service manual", "page": 27, "excerpt": same},
            ],
        )
        excerpts = [src.get("excerpt") or "" for src in proc.sources]
        self.assertEqual(
            sum(1 for excerpt in excerpts if "sail switch is closed" in excerpt.lower()),
            1,
        )
        self.assertTrue(all(excerpt.strip() for excerpt in excerpts))

    def test_s10_correction_sits_below_the_question_and_keeps_the_range(self):
        proc, text = _sheet(
            GROUNDED,
            "Lippert",
            "Ground Control 343633",
            "Leveling",
            chunks=[
                {
                    "title": "Lippert Ground Control service manual",
                    "page": 4,
                    "excerpt": "Run manual level. The hall sensor reads a typical 3-9V while the jack runs.",
                }
            ],
        )
        decision = next(node for node in proc.flowchart.nodes if node.kind == "decision")
        correction = next(node for node in proc.flowchart.nodes if "confirmed" in node.text.lower())
        self.assertGreater(correction.y, decision.y)
        self.assertIn("3-9v", text.lower())
        self.assertNotIn("3- .", text.lower())
        self.assertEqual(_glued_tokens(text), [])

    def test_no_labels_stay_on_their_arrows(self):
        proc, _text = _sheet(
            "FACR08 freeze up interior leak condensate",
            "Furrion",
            "FACR08",
            "Air Conditioning",
        )
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        labels = [mark for mark in trace if mark.role == "label" and (mark.text or "").strip().upper() == "NO"]
        connectors = [mark for mark in trace if mark.role == "connector" and mark.points]
        self.assertTrue(labels)
        for label in labels:
            near = any(
                abs(x - label.x0) < 40 and abs(y - (label.y0 + label.y1) / 2) < 40
                for connector in connectors
                for x, y in connector.points
            )
            self.assertTrue(near, (label.text, label.x0, label.y0))
        frame = next(mark for mark in trace if mark.role == "frame")
        for mark in connectors:
            for x, _y in mark.points:
                self.assertLess(x, frame.x1 - 44.0)

    def test_s11_says_only_the_facr08_book_and_names_the_next_action(self):
        proc, text = _sheet(
            "Furrion FACT12SA2 rooftop shows E3",
            "Furrion",
            "FACT12SA2",
            "Air Conditioning",
            chunks=[
                {
                    "title": "Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666",
                    "page": 3,
                    "excerpt": "Check the evaporator coil and the sensor clip.",
                }
            ],
        )
        cite = proc.primary_cite.lower()
        self.assertIn("only the facr08 book", cite)
        self.assertIn("ccd-0008666", cite)
        self.assertIn("not the fact12", cite)
        self.assertNotIn("retest once more", text.lower())
        self.assertIn("replace the freeze sensor", proc.bay_order[2].lower())
        self.assertEqual(_glued_tokens(text), [])

    def test_s13_does_not_repeat_the_alignment_and_does_not_glue_codewater(self):
        proc, text = _sheet(
            "Girard GSWH-2 E8 lockout after flame",
            "Girard",
            "GSWH-2",
            "Water Heaters",
            chunks=[
                {
                    "title": "Girard GSWH-2 service manual CCD-0009390",
                    "page": 35,
                    "excerpt": "The error code - water flow sensor is out of the flame path.",
                },
                {
                    "title": "Girard GSWH-2 service manual CCD-0009390",
                    "page": 23,
                    "excerpt": "CCD-0009390 ? Before replacing the control board, align the tube.",
                },
                {
                    "title": "Girard GSWH-2 service manual CCD-0009390",
                    "page": 19,
                    "excerpt": "Remove and Replace Water Flow Sensor before the control board.",
                },
            ],
        )
        self.assertEqual(len(proc.bay_order), 6)
        self.assertEqual(len(proc.bay_order), len({step.strip() for step in proc.bay_order}))
        self.assertNotEqual(proc.bay_order[2].strip().lower(), proc.bay_order[5].strip().lower())
        self.assertNotIn(proc.bay_order[2][:40].lower(), proc.bay_order[5].lower())
        low = text.lower()
        self.assertNotIn("codewater", low)
        self.assertIn("code water", low)
        self.assertIn("remove and replace", low)
        self.assertNotIn("? before", low)
        self.assertEqual(_glued_tokens(text), [])

    def test_s14_drops_boilerplate_and_s15_drops_ocr_junk(self):
        stab, _stab_text = _sheet(
            "Front stabilizer jack. Power extend works. Manual override will not engage. The roll pin is broken.",
            "",
            "",
            "Leveling",
            chunks=[
                {
                    "title": "Lippert PSX1 CCD-0007345",
                    "page": 4,
                    "excerpt": "Welding the jack frame is not a field repair.",
                },
                {
                    "title": "Lippert PSX1 CCD-0007345",
                    "page": 6,
                    "excerpt": "Warning: do not use an extension cord on this motor.",
                },
                {
                    "title": "Lippert PSX1 CCD-0007345",
                    "page": 8,
                    "excerpt": "Specifications are subject to change without notice.",
                },
            ],
        )
        blob = " ".join((src.get("excerpt") or "") for src in stab.sources).lower()
        self.assertNotIn("welding", blob)
        self.assertNotIn("extension cord", blob)
        self.assertNotIn("subject to change", blob)
        self.assertEqual(stab.model_line, "")
        self.assertTrue(all((src.get("excerpt") or "").strip() for src in stab.sources))
        _proc, cook = _sheet(
            "Suburban SDN2U cooktop. Burner goes out with a pan on. The thermocouple tip sits low and gets pushed.",
            "Suburban",
            "SDN2U",
            "Cooktops",
            chunks=[
                {
                    "title": "Suburban range service manual",
                    "page": 4,
                    "excerpt": "A grease fire can start if oil is left on the burner.",
                },
                {
                    "title": "Suburban range service manual",
                    "page": 2,
                    "excerpt": "Tighten the mounting screws on the top - and the side.",
                },
                {
                    "title": "Suburban range service manual",
                    "page": 9,
                    "excerpt": "Tum oven control knob clockwise /* until it stops.",
                },
            ],
        )
        low = cook.lower()
        self.assertNotIn("grease", low)
        self.assertNotIn("topand", low)
        self.assertNotIn("tum ", low)
        self.assertNotIn("/*", low)
        self.assertNotIn("mounting screw", low)
        self.assertEqual(_glued_tokens(cook), [])
