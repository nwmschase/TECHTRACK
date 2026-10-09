"""Bay sheets stay short: cropped figures, no placeholder page, no raw OCR steps."""
import unittest

from bay_procedure import (
    FACT12_MISLABEL_CITE,
    clean_ocr_prose,
    clean_source_excerpt,
    compile_bay_procedure,
    compose_sheet,
    human_source_title,
    layout_problems,
    render_bay_procedure_pdf,
)

GROUNDED = (
    "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
    "tires off the ground even though the coach was nearly level."
)

LOCKED = (
    (
        "icing up on rear wall — only about half from the top down",
        "Furrion",
        "FCR10DCGTA-BL",
        "Refrigerators",
        [],
    ),
    (
        "FACR08 freeze up interior leak condensate",
        "Furrion",
        "FACR08",
        "Air Conditioning",
        [],
    ),
    (
        "temperature dial OFF but compressor still running, freezer frozen solid, overcooling",
        "Furrion",
        "FCR10DCGTA-BL",
        "Refrigerators",
        [],
    ),
    (
        "BAL Soft-Touch SS 5.1 electric tongue jack dead. Other stabilizers and panel lights work.",
        "BAL",
        "Soft-Touch SS 5.1",
        "Leveling",
        [],
    ),
    (
        "Manual Mode dump works. Auto works. Touch pad flashes then returns to the home screen.",
        "",
        "Level Up Advantage 807662",
        "Leveling",
        [],
    ),
)


def _pdf_doc(pdf: bytes):
    import pymupdf

    return pymupdf.open(stream=pdf, filetype="pdf")


def _pdf_text(pdf: bytes) -> str:
    doc = _pdf_doc(pdf)
    return "\n".join(page.get_text() for page in doc)


class TestSnippetCleanup(unittest.TestCase):
    def test_repeated_phrase_and_ocr_splits_are_repaired(self):
        pcb = clean_source_excerpt("Then locate the inverter PCB.the inverter PCB.")
        self.assertEqual(pcb.lower().count("inverter pcb"), 1)
        self.assertNotIn("PCB.the", pcb)
        terminals = clean_source_excerpt("Check the termina ls before the swap.")
        self.assertIn("terminals", terminals.lower())
        self.assertNotIn("termina ls", terminals.lower())
        black = clean_source_excerpt("The wire is b lack at the plug.")
        self.assertIn("black", black.lower())
        self.assertNotIn("b lack", black.lower())
        fumes = clean_ocr_prose(
            "Watch for gasfumes and anexplosion near the burner. Check ail connections."
        )
        self.assertIn("gas fumes", fumes.lower())
        self.assertIn("an explosion", fumes.lower())
        self.assertIn("all connections", fumes.lower())
        self.assertNotIn("gasfumes", fumes.lower())
        doubled = clean_source_excerpt(
            "Read the section for further troubleshooting.further troubleshooting."
        )
        self.assertEqual(doubled.lower().count("further troubleshooting"), 1)

    def test_parts_list_transcription_and_pdf_names_drop(self):
        self.assertEqual(
            clean_source_excerpt(
                "NOTE: Refer to the Replaceable Parts List for 2021128850 2021128851 2021128852 2021128853."
            ),
            "",
        )
        cleaned = clean_source_excerpt(
            "TRANSCRIPTION for TechTrack search (OCR companion) If the fan is dead, replace it."
        )
        self.assertNotIn("transcription", cleaned.lower())
        self.assertIn("fan is dead", cleaned.lower())
        # A single cited part number is not a parts-list dump.
        kept = clean_source_excerpt("Replace the Spark-Free Thermostat part G 2021128850.")
        self.assertIn("2021128850", kept)
        self.assertNotIn(".pdf", human_source_title("Coleman 1976-603.pdf"))
        self.assertNotIn(".pdf", human_source_title("1976-603.pdf"))


class TestSheetLengthAndGenericPath(unittest.TestCase):
    def test_locked_sheets_stay_within_three_pages_without_a_placeholder(self):
        for concern, brand, model, category, chunks in LOCKED:
            proc = compile_bay_procedure(
                concern=concern, brand=brand, model=model, category=category, chunks=chunks
            )
            pdf = render_bay_procedure_pdf(proc)
            doc = _pdf_doc(pdf)
            self.assertLessEqual(doc.page_count, 3, concern)
            text = "\n".join(page.get_text() for page in doc)
            self.assertNotRegex(text, r"(?i)cited library figure(?!s)", concern)
            self.assertNotIn("DISCONTINUED", text, concern)
            for page in doc:
                body = page.get_text().strip()
                orphan = (
                    "SOURCES" in body
                    and "BAY ORDER" not in body
                    and "WHAT THIS PATTERN" not in body
                    and len(body) < 400
                )
                self.assertFalse(orphan, (concern, body[:240]))

    def test_typed_model_is_kept_and_a_blank_model_is_blank(self):
        proc = compile_bay_procedure(
            concern=(
                "temperature dial OFF but compressor still running, "
                "freezer frozen solid, overcooling"
            ),
            brand="Furrion",
            model="FCR10DCGTA-BL",
            category="Refrigerators",
        )
        self.assertIn("FCR10DCGTA-BL", proc.model_line)
        self.assertIn("FCR10DCGTA-BL", _pdf_text(render_bay_procedure_pdf(proc)))
        blank = compile_bay_procedure(
            concern="Customer states the marker light is dim.",
            brand="",
            model="",
            category="Electrical",
        )
        self.assertEqual(blank.model_line, "")
        pages = compose_sheet(blank)
        header = [t.text.strip() for t in pages[0].texts if t.role == "header"]
        self.assertIn("MODEL", header)
        self.assertEqual(sum(1 for text in header if text == "-"), 1)

    def test_opening_oval_fits_the_whole_concern(self):
        proc = compile_bay_procedure(
            concern=GROUNDED,
            brand="Lippert",
            model="Ground Control 343633",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert Ground Control service manual",
                    "page": 4,
                    "excerpt": (
                        "-> If the fault reverses when the sensor harness is swapped, replace the sensor."
                    ),
                }
            ],
        )
        start = next(node.text for node in proc.flowchart.nodes if node.kind == "start")
        self.assertIn("tires off the ground", start)
        self.assertNotIn("...", start)
        trace = []
        pdf = render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        text = _pdf_text(pdf)
        self.assertIn("tires off the ground", text)
        self.assertNotIn("tires off...", text)
        self.assertNotIn("->", " ".join(proc.bay_order))
        self.assertLessEqual(_pdf_doc(pdf).page_count, 3)

    def test_generic_path_does_not_paste_raw_ocr_or_an_install_manual(self):
        proc = compile_bay_procedure(
            concern="Dometic B57915 rooftop air conditioner is not cooling.",
            brand="Dometic",
            model="B57915",
            category="Air Conditioning",
            chunks=[
                {
                    "title": "Dometic B57915 Installation Manual",
                    "page": 9,
                    "excerpt": (
                        "9 .2 Cleaning the ADB Housing. 23 EN Rooftop air conditioner. "
                        "Duct size ? Duct layout."
                    ),
                },
                {
                    "title": "Dometic B57915 Troubleshooting and Service Manual",
                    "page": 12,
                    "excerpt": (
                        "If the unit does not cool, check the condenser. "
                        "If the filter is blocked, clean it and retest cooling."
                    ),
                },
                {
                    "title": "Lippert TI-005",
                    "page": 1,
                    "excerpt": "DISCONTINUED. If the jacks drift, stop.",
                },
            ],
        )
        body = " ".join(proc.bay_order)
        self.assertNotIn("?", body)
        self.assertNotIn("Duct size", body)
        self.assertNotIn("Cleaning the ADB", body)
        self.assertNotIn("23 EN", body)
        self.assertIn("condenser", body.lower())
        titles = " ".join(src.get("title") or "" for src in proc.sources).lower()
        self.assertIn("troubleshooting", titles)
        self.assertNotIn("installation", titles)
        self.assertNotIn("ti-005", titles)
        self.assertNotIn("discontinued", titles)
        pdf = _pdf_text(render_bay_procedure_pdf(proc))
        self.assertNotRegex(pdf, r"(?i)cited library figure(?!s)")
        self.assertNotIn(".pdf", pdf.lower())
        self.assertLessEqual(_pdf_doc(render_bay_procedure_pdf(proc)).page_count, 3)

    def test_question_mark_bullet_is_not_a_step(self):
        proc = compile_bay_procedure(
            concern="Girard GSWH-2 tankless water heater shows E8.",
            brand="Girard",
            model="GSWH-2",
            category="Water Heaters",
            chunks=[
                {
                    "title": "Girard Tankless Water Heater GSWH-2 Troubleshooting and Service Manual",
                    "page": 35,
                    "excerpt": (
                        "? Duct size ? Duct layout. "
                        "If the CN1 wire is loose, reseat it and retest the heater."
                    ),
                }
            ],
        )
        blob = " ".join(proc.bay_order)
        self.assertNotIn("Duct size", blob)
        self.assertNotIn("?", blob)
        self.assertIn("CN1", blob)
        box = next(node.text for node in proc.flowchart.nodes if node.kind == "process")
        self.assertFalse(box.strip().startswith("?"))

    def test_fact12_file_that_is_facr08_is_not_the_model_manual(self):
        bad = {
            "title": "Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666",
            "page": 10,
            "excerpt": "FACR08HESA2 8K rooftop. Fig. 1 roof opening and base pan.",
        }
        good = {
            "title": "Furrion FACT12SA2 Rooftop Air Conditioner Service Manual",
            "page": 4,
            "excerpt": "If the FACT12 will not cool, check the capacitor and retest.",
        }
        mixed = compile_bay_procedure(
            concern="Rooftop air conditioner will not cool.",
            brand="Furrion",
            model="FACT12SA2",
            category="Air Conditioning",
            chunks=[bad, good],
        )
        self.assertIn("fact12", mixed.primary_cite.lower())
        self.assertNotIn("facr08", mixed.primary_cite.lower())
        self.assertNotIn("ccd-0008666", mixed.primary_cite.lower())
        only = compile_bay_procedure(
            concern="Rooftop air conditioner will not cool.",
            brand="Furrion",
            model="FACT12SA2",
            category="Air Conditioning",
            chunks=[bad],
        )
        self.assertEqual(only.primary_cite, FACT12_MISLABEL_CITE)
        self.assertNotIn("fact12sa2-ps", only.primary_cite.lower())
        titles = " ".join(src.get("title") or "" for src in only.sources).lower()
        self.assertIn("facr08", titles)
        self.assertIn("not the fact12", titles)


if __name__ == "__main__":
    unittest.main()
