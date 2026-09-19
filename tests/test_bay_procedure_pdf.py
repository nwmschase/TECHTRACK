"""Bay procedure PDF v2: drawn flowchart, ice/FACR/Firefly path locks."""
import unittest

from bay_procedure import (
    BAY_PROCEDURE_LABEL,
    body_uses_manual_codes,
    check_text_leads_with_bare_pn,
    compile_bay_procedure,
    count_pdf_draw_ops,
    firefly_has_forbidden_module_hunt,
    firefly_sheet_uses_service_names,
    pdf_content_operators,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
    rewrite_bay_search_symptom,
    suggested_pdf_filename,
    uses_wired_coach_can_jargon,
)
from gd_library_coach import (
    FIREFLY_CAN_SEARCH_BOOST,
    FIREFLY_TWO_PLUG_PROVE,
    ICE_MOISTURE_SEARCH_BOOST,
    LEVEL_UP_CAN_FIREFLY_SHOP_LINE,
    LEVEL_UP_CAN_ISOLATE_SHOP_LINE,
    LEVEL_UP_CAN_NOT_FIREFLY_SHOP_LINE,
    LEVEL_UP_CAN_PRODUCT_LOCK,
    OPEN_LIBRARY_COACH_RULE,
    is_facr_rooftop_freeze_context,
    is_firefly_can_path_context,
    is_fridge_ice_moisture_context,
)

EXACT_TWO_PLUG = (
    "The Level Up controller has two network plugs. "
    "One has a rubber boot on it — leave that one alone. "
    "The other has a cable running to the Firefly / OneControl system — unplug that cable only. "
    "Then try Manual Mode again."
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
        # Fuse / 12V is not the path. Manual codes stay in Sources, not body copy.
        blob = f"{proc.primary_cite} {proc.pattern_means} {' '.join(proc.bay_order)}".lower()
        self.assertIn("ice and moisture", blob)
        self.assertIn("furrion fridge service manual", blob)
        self.assertFalse(body_uses_manual_codes(procedure_body_text(proc)))
        src = " ".join(f"{s.get('title')} {s.get('page')}" for s in proc.sources).lower()
        self.assertIn("ccd-0008122", src)
        self.assertTrue("36" in src or "page 36" in text)
        self.assertTrue(any(n.kind == "decision" for n in proc.flowchart.nodes))
        self.assertTrue(any(fig.image_png for fig in proc.figures), "ice sheet must embed a figure")
        self.assertIn("light sheet", " ".join(proc.bay_order).lower())
        self.assertIn("dollar-bill", " ".join(proc.bay_order).lower())
        self.assertIn("rear drain", " ".join(proc.bay_order).lower())
        self.assertIn("24 to 48", " ".join(proc.bay_order).lower())
        self.assertTrue(any("knife" in d.lower() for d in proc.do_not))
        self.assertTrue(any("sealed-system" in d.lower() for d in proc.do_not))
        body = procedure_body_text(proc).lower()
        for banned in ("fuse", "12-volt", "12v", "inverter", "dead-unit", "15a"):
            self.assertNotIn(banned, body)
        self.assertTrue(proc.flowchart.readable)
        self.assertLessEqual(len(proc.flowchart.nodes), 6)
        self.assertTrue(any(n.w >= 170 for n in proc.flowchart.nodes))
        order = " ".join(proc.bay_order).lower()
        self.assertIn("if it is only a light sheet", order)
        self.assertIn("if the bill slides", order)
        self.assertIn("if heavy frost returns", order)
        pdf_low = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        for banned in ("fuse", "12-volt", "12v inverter", "dead-unit", "15a"):
            self.assertNotIn(banned, pdf_low)


class TestManualModeFireflyCan(unittest.TestCase):
    def test_manual_mode_dump_auto_works_includes_can_isolate_terminator(self):
        self.assertTrue(
            is_firefly_can_path_context("Leveling", "Level Up Advantage 807662", MANUAL_MODE_DUMP_AUTO)
        )
        self.assertTrue(is_firefly_can_path_context("", "", MANUAL_MODE_DUMP_AUTO))
        q = rewrite_bay_search_symptom("Leveling", "807662", MANUAL_MODE_DUMP_AUTO)
        self.assertIn("terminator", q.lower())
        self.assertIn("firefly", FIREFLY_CAN_SEARCH_BOOST.lower())
        self.assertIn("rubber-boot", FIREFLY_CAN_SEARCH_BOOST.lower())

        proc = compile_bay_procedure(
            concern=MANUAL_MODE_DUMP_AUTO,
            category="Leveling",
            model="Level Up Advantage 807662",
            chunks=[],
        )
        text = _sheet_text(proc)
        low = text.lower()
        self.assertIn("rubber-boot", low)
        self.assertIn("rubber boot", low)
        self.assertIn("firefly usb", low)
        self.assertIn("574-825-4600", low)
        self.assertIn("firefly", low)
        self.assertIn("level up controller", low)
        self.assertIn("two network plugs", low)
        self.assertIn("unplug that cable only", low)
        self.assertIn("level up advantage controller (brinkley / firefly)", proc.model_line.lower())
        self.assertNotIn("807662", proc.model_line)
        self.assertTrue(firefly_sheet_uses_service_names(text), text[:1200])
        self.assertFalse(body_uses_manual_codes(procedure_body_text(proc)))
        self.assertTrue(any(fig.image_png for fig in proc.figures))
        self.assertFalse(uses_wired_coach_can_jargon(text), text[:800])
        self.assertNotIn("ai report", low)
        self.assertNotIn("confirm manual dump works", low)
        self.assertNotIn("confirm manual mode dump works", low)
        self.assertFalse(firefly_has_forbidden_module_hunt(text), text[:800])
        self.assertNotIn(FORBIDDEN_MODULE_HUNT.lower(), low)
        self.assertNotIn("one at a time", low)
        self.assertFalse(check_text_leads_with_bare_pn("\n".join(proc.bay_order)))
        self.assertFalse(check_text_leads_with_bare_pn("\n".join(proc.do_not)))

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
        self.assertIn("rooftop", proc.primary_cite.lower())
        self.assertFalse(body_uses_manual_codes(procedure_body_text(proc)))
        self.assertTrue(any(fig.image_png for fig in proc.figures))

    def test_seed_807662_flash_home_has_usb_and_terminator(self):
        concern = (
            "Level Up Advantage 807662 Manual Mode flashes then dumps home. "
            "Auto Level still works. Brinkley Firefly."
        )
        self.assertTrue(is_firefly_can_path_context("", "", concern))
        proc = compile_bay_procedure(concern=concern)
        text = _sheet_text(proc)
        low = text.lower()
        self.assertIn("rubber-boot", low)
        self.assertIn("rubber boot", low)
        self.assertIn("firefly usb", low)
        self.assertIn("574-825-4600", low)
        self.assertIn("4 gb", low)
        self.assertIn("interim", low)
        self.assertIn("two network plugs", low)
        self.assertIn("unplug that cable only", low)
        self.assertIn("level up controller", low)
        self.assertIn("level up advantage controller (brinkley / firefly)", proc.model_line.lower())
        self.assertNotIn("807662", proc.model_line)
        self.assertTrue(firefly_sheet_uses_service_names(text))
        self.assertFalse(body_uses_manual_codes(procedure_body_text(proc)))
        self.assertFalse(uses_wired_coach_can_jargon(text))
        self.assertIn(FIREFLY_TWO_PLUG_PROVE.split(".")[0].lower(), low)
        self.assertNotIn("confirm manual dump works", low)
        self.assertNotIn("no matching manual excerpt", low)
        self.assertNotIn("one at a time", low)
        self.assertFalse(firefly_has_forbidden_module_hunt(text))
        self.assertFalse(check_text_leads_with_bare_pn("\n".join(proc.bay_order + proc.do_not)))
        pdf = render_bay_procedure_pdf(proc)
        pdf_low = _pdf_text(pdf).lower()
        self.assertFalse(uses_wired_coach_can_jargon(pdf_low))
        self.assertIn("two network plugs", pdf_low)
        self.assertIn("unplug that cable only", pdf_low)
        self.assertIn("rubber-boot", pdf_low)
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


class TestExactFireflyTwoPlugLock(unittest.TestCase):
    def test_constant_and_sheet_are_character_exact(self):
        self.assertEqual(FIREFLY_TWO_PLUG_PROVE, EXACT_TWO_PLUG)
        self.assertNotIn("Find the connector", FIREFLY_TWO_PLUG_PROVE)
        self.assertNotIn("labeled CAN", FIREFLY_TWO_PLUG_PROVE)
        proc = compile_bay_procedure(
            concern=MANUAL_MODE_DUMP_AUTO,
            category="Leveling",
            model="Level Up Advantage 807662",
        )
        text = procedure_plain_text(proc)
        self.assertIn(EXACT_TWO_PLUG, text)
        self.assertEqual(proc.bay_order[1], EXACT_TWO_PLUG)
        self.assertIn(EXACT_TWO_PLUG, proc.pattern_means)
        self.assertFalse(uses_wired_coach_can_jargon(text))
        self.assertNotIn("wired coach can", text.lower())
        pdf_low = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        self.assertIn("the level up controller has two network plugs", pdf_low)
        self.assertIn("unplug that cable only", pdf_low)
        self.assertIn("then try manual mode again", pdf_low)
        self.assertNotIn("wired coach can", pdf_low)
        self.assertNotIn("find the connector", pdf_low)

    def test_gd_path_strings_use_exact_block_and_ban_jargon(self):
        self.assertIn(EXACT_TWO_PLUG, LEVEL_UP_CAN_ISOLATE_SHOP_LINE)
        self.assertIn(EXACT_TWO_PLUG, LEVEL_UP_CAN_PRODUCT_LOCK)
        self.assertIn(EXACT_TWO_PLUG, OPEN_LIBRARY_COACH_RULE)
        from pathlib import Path

        app = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
        self.assertIn(EXACT_TWO_PLUG, app)
        self.assertNotIn("wired coach can", app.lower().split("18b.")[1].split("19.")[0])
        for blob in (
            LEVEL_UP_CAN_ISOLATE_SHOP_LINE,
            LEVEL_UP_CAN_FIREFLY_SHOP_LINE,
            LEVEL_UP_CAN_NOT_FIREFLY_SHOP_LINE,
            LEVEL_UP_CAN_PRODUCT_LOCK,
            OPEN_LIBRARY_COACH_RULE,
        ):
            self.assertNotIn("wired coach can", blob.lower(), blob[:200])
            self.assertNotIn("find the connector", blob.lower())
        self.assertIn("gui", LEVEL_UP_CAN_FIREFLY_SHOP_LINE.lower())
        self.assertIn("ccm", LEVEL_UP_CAN_FIREFLY_SHOP_LINE.lower())
        self.assertIn("574-825-4600", LEVEL_UP_CAN_FIREFLY_SHOP_LINE)
        self.assertIn("level up controller", LEVEL_UP_CAN_NOT_FIREFLY_SHOP_LINE.lower())
        self.assertIn("do not push", LEVEL_UP_CAN_NOT_FIREFLY_SHOP_LINE.lower())


class TestFireflyServiceNamesNotPartNumbers(unittest.TestCase):
    def test_firefly_checks_use_names_not_bare_pn(self):
        proc = compile_bay_procedure(
            concern=MANUAL_MODE_DUMP_AUTO,
            category="Leveling",
            model="Level Up Advantage 807662",
        )
        body = "\n".join(
            [proc.pattern_means, *proc.bay_order, *proc.do_not]
            + [n.text for n in proc.flowchart.nodes]
        )
        self.assertTrue(firefly_sheet_uses_service_names(procedure_plain_text(proc)))
        self.assertIn("level up controller", body.lower())
        self.assertIn("firefly", body.lower())
        self.assertTrue("rubber boot" in body.lower() or "rubber-boot" in body.lower())
        self.assertFalse(check_text_leads_with_bare_pn(body), body)
        self.assertFalse(uses_wired_coach_can_jargon(body), body)
        self.assertIn("The Level Up controller has two network plugs.", proc.bay_order[1])
        self.assertIn("unplug that cable only", proc.bay_order[1])
        for step in proc.bay_order:
            self.assertTrue(step.strip().endswith("."), step)
            self.assertFalse(step.lstrip().startswith("807662"), step)


class TestServiceBayVoiceEntireSheet(unittest.TestCase):
    """Entire bay sheet stays in complete-sentence service voice — not only Firefly."""

    BANNED_FRAGMENTS = (
        "inverter tree",
        "8666 OK",
        "assembly / condensate",
        "PRODUCT LOCK",
        "board-swap-first",
        "Not this path.",
        "Prove power looks sane",
        "Watch or replace only from",
        "wired coach CAN",
        "wired coach can",
        "Find the connector",
        "labeled CAN",
    )

    def _assert_human_steps(self, steps):
        for step in steps:
            self.assertTrue(step.strip().endswith("."), step)
            self.assertFalse(step.lstrip().startswith("807662"), step)
            self.assertNotIn("→", step)
            for banned in self.BANNED_FRAGMENTS:
                self.assertNotIn(banned, step)

    def _assert_flowchart_voice(self, proc):
        for node in proc.flowchart.nodes:
            blob = node.text.replace("\n", " ").strip()
            if node.kind == "decision":
                self.assertTrue(blob.endswith("?"), node.text)
            else:
                self.assertTrue(blob.endswith("."), node.text)
            self.assertNotIn(" / ", blob.replace("Firefly / OneControl", ""))
            for banned in self.BANNED_FRAGMENTS:
                self.assertNotIn(banned, node.text)

    def test_ice_facr_firefly_entire_sheet_is_service_bay_voice(self):
        cases = (
            (WO_COMPLAINT, "Furrion", WO_MODEL, "Refrigerators"),
            ("FACR08 freeze up interior leak condensate", "Furrion", "FACR08", "Air Conditioning"),
            (MANUAL_MODE_DUMP_AUTO, "", "Level Up Advantage 807662", "Leveling"),
        )
        for concern, brand, model, category in cases:
            proc = compile_bay_procedure(
                concern=concern, brand=brand, model=model, category=category
            )
            text = procedure_plain_text(proc)
            self._assert_human_steps(proc.bay_order)
            self._assert_human_steps(proc.do_not)
            self.assertTrue(proc.pattern_means.strip().endswith("."), proc.pattern_means)
            self.assertTrue(proc.primary_cite.strip().endswith("."), proc.primary_cite)
            self._assert_flowchart_voice(proc)
            for note in proc.notes:
                self.assertTrue(note.strip().endswith("."), note)
                self.assertNotIn("PRODUCT LOCK", note)
            for src in proc.sources:
                excerpt = (src.get("excerpt") or "").strip()
                if excerpt:
                    self.assertTrue(excerpt.endswith("."), excerpt)
            self.assertFalse(uses_wired_coach_can_jargon(text))
            pdf_text = _pdf_text(render_bay_procedure_pdf(proc))
            for banned in self.BANNED_FRAGMENTS:
                self.assertNotIn(banned.lower(), pdf_text.lower(), banned)

    def test_firefly_prove_stays_short_two_plug_not_silkscreen(self):
        proc = compile_bay_procedure(
            concern=MANUAL_MODE_DUMP_AUTO,
            category="Leveling",
            model="Level Up Advantage 807662",
        )
        text = procedure_plain_text(proc)
        self.assertIn(EXACT_TWO_PLUG, text)
        self.assertEqual(proc.bay_order[1], EXACT_TWO_PLUG)
        self.assertIn(EXACT_TWO_PLUG, proc.pattern_means)
        self.assertIn("rubber boot", text.lower())
        self.assertIn("firefly", text.lower())
        self.assertIn("cable", text.lower())
        self.assertIn("then try manual mode again", text.lower())
        self.assertNotIn("Find the connector", text)
        self.assertNotIn("labeled CAN", text)
        self.assertNotIn("Go back to the touchpad", text)
        self.assertNotIn("wired coach CAN", text)


class TestQualityGateNamesAndFigures(unittest.TestCase):
    def test_body_is_names_first_and_figures_are_embedded(self):
        cases = (
            (WO_COMPLAINT, "Furrion", WO_MODEL, "Refrigerators"),
            ("FACR08 freeze up interior leak condensate", "Furrion", "FACR08", "Air Conditioning"),
            (MANUAL_MODE_DUMP_AUTO, "", "Level Up Advantage 807662", "Leveling"),
        )
        for concern, brand, model, category in cases:
            proc = compile_bay_procedure(
                concern=concern, brand=brand, model=model, category=category
            )
            body = procedure_body_text(proc)
            self.assertFalse(body_uses_manual_codes(body), body[:400])
            self.assertTrue(any(fig.image_png for fig in proc.figures), concern)
            pdf = render_bay_procedure_pdf(proc)
            self.assertGreater(len(pdf), 2000)
            if category == "Leveling":
                self.assertEqual(
                    proc.model_line,
                    "Level Up Advantage controller (Brinkley / Firefly)",
                )
                self.assertNotIn("807662", proc.model_line)
                src = " ".join((s.get("excerpt") or "") + (s.get("title") or "") for s in proc.sources)
                self.assertIn("807662", src)
            if category == "Refrigerators":
                self.assertIn("furrion fridge service manual", body.lower())
                self.assertIn("dollar-bill", body.lower())
                src = " ".join(s.get("title") or "" for s in proc.sources)
                self.assertIn("CCD-0008122", src)


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
