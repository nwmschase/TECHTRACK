"""Bay procedure PDF v2: drawn flowchart, ice/FACR/Firefly path locks."""
import unittest

from bay_procedure import (
    BAY_PROCEDURE_LABEL,
    compile_bay_procedure,
    count_pdf_draw_ops,
    firefly_has_forbidden_module_hunt,
    pdf_content_operators,
    procedure_plain_text,
    render_bay_procedure_pdf,
    rewrite_bay_search_symptom,
    suggested_pdf_filename,
)
from gd_library_coach import (
    FIREFLY_CAN_SEARCH_BOOST,
    ICE_MOISTURE_SEARCH_BOOST,
    is_facr_rooftop_freeze_context,
    is_firefly_can_path_context,
    is_fridge_ice_moisture_context,
)

FURRION = "Furrion FCR08/FCR10 SM CCD-0008122"
WO_MODEL = "Furrion FCR10DCGTA-BG-PWH"
WO_COMPLAINT = "icing up on rear wall — only about half from the top down"

ICE_MOISTURE_P36 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 36,
    "excerpt": (
        "Ice and Moisture\n"
        "Ice or Moisture in the Fridge\n"
        "Fig. 36 rear wall frost pattern. Check whether the dial is at max, "
        "then the door gasket, then verify cooling. Watch/replace from this section."
    ),
}
FUSE_P19 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 19,
    "excerpt": (
        "Section 1 Fuse. Locate the fuse in the front vent cavity. "
        "15A ATC blade / cartridge. Fuse location. No Ice and Moisture on this page."
    ),
}

MANUAL_MODE_DUMP_AUTO = (
    "Manual Mode dump works. Auto works. "
    "Touch pad flashes then returns to the home screen."
)

FORBIDDEN_MODULE_HUNT = "unplug Firefly/CAN modules one at a time"


def _sheet_text(proc) -> str:
    return procedure_plain_text(proc)


def _pdf_text(pdf: bytes) -> str:
    try:
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return pdf_content_operators(pdf)


class TestIceRearWallBayProcedure(unittest.TestCase):
    def test_ice_rear_wall_biases_ice_moisture_or_ccd_0008122(self):
        self.assertTrue(
            is_fridge_ice_moisture_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        q = rewrite_bay_search_symptom("Refrigerators", WO_MODEL, WO_COMPLAINT)
        low_q = q.lower()
        self.assertIn("ice and moisture", low_q)
        self.assertIn("fig. 36", low_q)
        self.assertIn(ICE_MOISTURE_SEARCH_BOOST.split()[0].lower(), low_q)

        proc = compile_bay_procedure(
            concern=WO_COMPLAINT,
            brand="Furrion",
            model=WO_MODEL,
            category="Refrigerators",
            chunks=[FUSE_P19, ICE_MOISTURE_P36],
        )
        text = _sheet_text(proc).lower()
        self.assertTrue(
            "ice and moisture" in text or "ccd-0008122" in text,
            text[:800],
        )
        self.assertIn("ccd-0008122", text)
        self.assertIn("page 36", text)
        self.assertNotIn("ai report", text)
        self.assertNotIn("written flowchart language", text)
        self.assertIn("what this pattern usually means", text)
        self.assertIn("bay order (do this first)", text)
        titles = [s.get("title") for s in proc.sources]
        self.assertTrue(any("CCD-0008122" in (t or "") for t in titles))
        ice_idx = next(
            i
            for i, s in enumerate(proc.sources)
            if s.get("page") == 36 or "moisture" in (s.get("excerpt") or "").lower()
        )
        fuse_hits = [i for i, s in enumerate(proc.sources) if s.get("page") == 19]
        if fuse_hits:
            self.assertLess(ice_idx, fuse_hits[0])
        # Fuse / 12V is not the path.
        blob = f"{proc.primary_cite} {proc.pattern_means} {' '.join(proc.bay_order)}".lower()
        self.assertIn("ccd-0008122", blob)
        self.assertTrue("p.36" in blob or "page 36" in blob)
        self.assertTrue(any(n.kind == "decision" for n in proc.flowchart.nodes))


class TestManualModeFireflyCan(unittest.TestCase):
    def test_manual_mode_dump_auto_works_includes_can_isolate_terminator(self):
        self.assertTrue(
            is_firefly_can_path_context("Leveling", "Level Up Advantage 807662", MANUAL_MODE_DUMP_AUTO)
        )
        self.assertTrue(is_firefly_can_path_context("", "", MANUAL_MODE_DUMP_AUTO))
        q = rewrite_bay_search_symptom("Leveling", "807662", MANUAL_MODE_DUMP_AUTO)
        self.assertIn("terminator", q.lower())
        self.assertIn("can isolate", FIREFLY_CAN_SEARCH_BOOST.lower())

        proc = compile_bay_procedure(
            concern=MANUAL_MODE_DUMP_AUTO,
            category="Leveling",
            model="Level Up Advantage 807662",
            chunks=[],
        )
        text = _sheet_text(proc)
        low = text.lower()
        self.assertIn("can isolate", low)
        self.assertIn("terminator", low)
        self.assertIn("rubber-boot", low)
        self.assertIn("firefly usb", low)
        self.assertIn("574-825-4600", low)
        self.assertIn("firefly", low)
        self.assertIn("wired coach can", low)
        self.assertTrue(
            "stays plugged" in low or "stays in" in low or "terminator stays" in low,
            text[:1200],
        )
        self.assertNotIn("ai report", low)
        self.assertNotIn("confirm manual dump works", low)
        self.assertNotIn("confirm manual mode dump works", low)
        self.assertFalse(firefly_has_forbidden_module_hunt(text), text[:800])
        self.assertNotIn(FORBIDDEN_MODULE_HUNT.lower(), low)
        self.assertNotIn("one at a time", low)

    def test_seed_facr08_freeze_surfaces_ccd_0007990(self):
        concern = "FACR08 freeze up interior leak condensate"
        self.assertTrue(is_facr_rooftop_freeze_context("", "Furrion", concern))
        proc = compile_bay_procedure(concern=concern, brand="Furrion")
        text = _sheet_text(proc)
        low = text.lower()
        self.assertIn("ccd-0007990", low)
        self.assertIn("condensate", low)
        self.assertIn("assembly", low)
        self.assertTrue("ccd-0008666" in low)
        self.assertNotIn("no matching manual excerpt", low)
        titles = " ".join(s.get("title") or "" for s in proc.sources).lower()
        self.assertIn("ccd-0007990", titles)
        self.assertEqual(proc.checks[0].kind, "check")
        self.assertIn("ccd-0007990", proc.primary_cite.lower())

    def test_seed_807662_flash_home_has_usb_and_terminator(self):
        concern = (
            "Level Up Advantage 807662 Manual Mode flashes then dumps home. "
            "Auto Level still works. Brinkley Firefly."
        )
        self.assertTrue(is_firefly_can_path_context("", "", concern))
        proc = compile_bay_procedure(concern=concern)
        text = _sheet_text(proc)
        low = text.lower()
        self.assertIn("can isolate", low)
        self.assertIn("terminator", low)
        self.assertIn("rubber-boot", low)
        self.assertIn("firefly usb", low)
        self.assertIn("574-825-4600", low)
        self.assertIn("4 gb", low)
        self.assertIn("interim", low)
        self.assertIn("wired coach can", low)
        self.assertTrue("stays plugged" in low or "stays in" in low)
        self.assertNotIn("confirm manual dump works", low)
        self.assertNotIn("no matching manual excerpt", low)
        self.assertNotIn("one at a time", low)
        self.assertFalse(firefly_has_forbidden_module_hunt(text))
        pdf = render_bay_procedure_pdf(proc)
        pdf_low = _pdf_text(pdf).lower()
        self.assertIn("wired coach can", pdf_low)
        self.assertTrue("stays plugged" in pdf_low or "stays in" in pdf_low)
        self.assertIn("574-825-4600", pdf_low)
        self.assertNotIn("one at a time", pdf_low)
        self.assertFalse(firefly_has_forbidden_module_hunt(pdf_low))


class TestBayProcedurePdfBytes(unittest.TestCase):
    def test_pdf_bytes_nonempty_for_sample_concern(self):
        proc = compile_bay_procedure(
            concern="Customer states the air conditioner is not cooling.",
            brand="Furrion",
            model="FACT12SA2",
            category="Air Conditioning",
            wo_number="WO-4521",
            include_3c=True,
        )
        pdf = render_bay_procedure_pdf(proc)
        self.assertTrue(pdf.startswith(b"%PDF"), pdf[:20])
        self.assertGreater(len(pdf), 200)
        self.assertIn(b"%%EOF", pdf[-64:] if len(pdf) > 64 else pdf)
        self.assertEqual(suggested_pdf_filename(proc), "bay_procedure_WO-4521.pdf")
        self.assertEqual(BAY_PROCEDURE_LABEL, "Bay procedure PDF")
        self.assertNotIn("AI report", BAY_PROCEDURE_LABEL)
        fancy = None
        try:
            from bay_procedure import _render_pdf_reportlab, compose_sheet

            fancy = _render_pdf_reportlab(proc, compose_sheet(proc))
        except ImportError:
            try:
                from bay_procedure import _render_pdf_fpdf2, compose_sheet

                fancy = _render_pdf_fpdf2(proc, compose_sheet(proc))
            except ImportError:
                fancy = None
        if fancy is not None:
            self.assertTrue(fancy.startswith(b"%PDF"))
            self.assertGreater(len(fancy), 400)


class TestVisualFlowchartDrawn(unittest.TestCase):
    def test_pdf_contains_multiple_drawn_shapes(self):
        proc = compile_bay_procedure(
            concern=WO_COMPLAINT,
            brand="Furrion",
            model=WO_MODEL,
            category="Refrigerators",
            chunks=[FUSE_P19, ICE_MOISTURE_P36],
        )
        pdf = render_bay_procedure_pdf(proc)
        ops = count_pdf_draw_ops(pdf)
        drawn = ops["rect"] + ops["curve"]
        paths = ops["moveto"] + ops["lineto"] + ops["close"]
        self.assertGreaterEqual(
            drawn,
            3,
            f"expected multiple rect/ellipse operators, got {ops}",
        )
        self.assertGreater(
            paths,
            4,
            f"expected path operators for diamonds/arrows, got {ops}",
        )
        stream = pdf_content_operators(pdf).lower()
        self.assertNotIn("written flowchart language", stream)
        text = _pdf_text(pdf).lower()
        self.assertIn("what this pattern usually means", text)
        self.assertIn("ccd-0008122", text)
        self.assertTrue("p.36" in text or "page 36" in text)
        self.assertIn("visual flowchart", text)

    def test_facr_and_firefly_pdfs_also_draw_shapes(self):
        for concern, brand, model in (
            ("FACR08 freeze up interior leak condensate", "Furrion", "FACR08"),
            (
                "Level Up Advantage 807662 Manual Mode flashes then dumps home. Auto Level still works.",
                "",
                "807662",
            ),
        ):
            proc = compile_bay_procedure(concern=concern, brand=brand, model=model)
            pdf = render_bay_procedure_pdf(proc)
            ops = count_pdf_draw_ops(pdf)
            self.assertGreaterEqual(ops["rect"] + ops["curve"], 3, (concern, ops))
            self.assertTrue(any(n.kind == "decision" for n in proc.flowchart.nodes), concern)


class TestNavAndGdUntouched(unittest.TestCase):
    def test_nav_label_and_gd_chat_untouched(self):
        from pathlib import Path

        src = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
        self.assertIn('"🧾 Bay procedure PDF"', src)
        self.assertIn("BAY_PROCEDURE_LABEL", src)
        self.assertNotIn("AI report", BAY_PROCEDURE_LABEL)
        self.assertIn("OPEN LIBRARY COACH", src)
        self.assertIn("with tab_ask:", src)
        self.assertIn("💬 Guided Diagnostics", src)


if __name__ == "__main__":
    unittest.main()
