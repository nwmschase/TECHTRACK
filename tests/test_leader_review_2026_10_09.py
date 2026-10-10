"""Leader review 2026-10-09: source hygiene, sheet layout, and GD chat bugs."""
import unittest
from io import BytesIO

from PIL import Image

from bay_procedure import (
    compose_sheet,
    compile_bay_procedure,
    layout_problems,
    load_oem_figure_png,
    render_bay_procedure_pdf,
    sheet_has_internal_note,
)
from gd_library_coach import (
    BAL_TONGUE_PANEL_SHOP_LINE,
    DIAL_OFF_RUN_SHOP_LINE,
    GROUND_CONTROL_LEVEL_LINE,
    ICE_MOISTURE_SHOP_LINE,
    strip_leaked_prompt,
)


def _blob(proc) -> str:
    parts = [proc.primary_cite, proc.pattern_means, proc.model_line]
    parts.extend(proc.bay_order)
    parts.extend(proc.do_not)
    for src in proc.sources:
        parts.append(src.get("title") or "")
        parts.append(src.get("excerpt") or "")
    return " ".join(parts).lower()


class TestStrictSources(unittest.TestCase):
    def test_scanned_and_off_topic_snippets_stay_off_the_sheet(self):
        cases = [
            (
                "FACR08 freeze up interior leak condensate",
                "Furrion",
                "FACR08",
                "Air Conditioning",
                [
                    {
                        "title": "CCD-0008666",
                        "page": 18,
                        "excerpt": "18 CCD-0008666 Troubleshooting Problem Cause Remedy the filter is dirty.",
                    },
                    {
                        "title": "CCD-0007990",
                        "page": 4,
                        "excerpt": "CCD-0007990 Cleaning and Maintenance A blocked filter stops airflow.",
                    },
                ],
                ["problem cause remedy", "cleaning and maintenance", "blocked filter"],
            ),
            (
                "temperature dial OFF but compressor still running, freezer frozen solid",
                "Furrion",
                "FCR10",
                "Refrigerators",
                [
                    {
                        "title": "CCD-0008122",
                        "page": 24,
                        "excerpt": "CCD-0008122 Lockout/Hard Reset Diagnostics Make sure power is applied to the board.",
                    },
                    {
                        "title": "CCD-0008122",
                        "page": 44,
                        "excerpt": "Knob removal: pull the knob straight off the shaft.",
                    },
                ],
                ["hard reset", "knob removal"],
            ),
            (
                "icing up on rear wall — only about half from the top down",
                "Furrion",
                "FCR10",
                "Refrigerators",
                [
                    {
                        "title": "CCD-0008122",
                        "page": 12,
                        "excerpt": "CCD-0008122 Open the refrigerator and note any ice.",
                    }
                ],
                ["open the refrigerator and note"],
            ),
            (
                "Level Up Advantage 807662 Manual Mode flashes then dumps home. Auto Level still works.",
                "",
                "Level Up Advantage 807662",
                "Leveling",
                [
                    {
                        "title": "CCD-0001749",
                        "page": 6,
                        "excerpt": "CCD-0001749 Touch Pad Error Codes NOTE the fifth-wheel LCD shows a code.",
                    }
                ],
                ["touch pad error", "ccd-0001749"],
            ),
            (
                "FCR10 E2 fan fault current on the freezer evaporator fan",
                "Furrion",
                "FCR10",
                "Refrigerators",
                [
                    {
                        "title": "CCD-0008122",
                        "page": 33,
                        "excerpt": "Hold a sheet of paper over the cavity to prove the fan.",
                    },
                    {
                        "title": "CCD-0008122",
                        "page": 18,
                        "excerpt": "The diagnostic LED is blinking when power is applied.",
                    },
                ],
                ["sheet of paper", "blinking"],
            ),
            (
                "Dometic B57915 rooftop air conditioner is not cooling.",
                "Dometic",
                "B57915",
                "Air Conditioning",
                [
                    {
                        "title": "Dometic operating instructions",
                        "page": 10,
                        "excerpt": "10 SECTION 1 The operating instructions start with the LCD on and off.",
                    },
                    {
                        "title": "Dometic ADB",
                        "page": 47,
                        "excerpt": "5.4 Air Distribution Box (ADB) sits above the ceiling.",
                    },
                    {
                        "title": "Dometic",
                        "page": 14,
                        "excerpt": "Select HEAT PUMP at the same time. 1.4 CCC 2 This type of thermostat is common.",
                    },
                ],
                ["operating instructions", "air distribution", "lcd", "this type of thermostat", "heat pump"],
            ),
            (
                "Girard GSWH-2 tankless water heater shows E8.",
                "Girard",
                "GSWH-2",
                "Water Heaters",
                [
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 35,
                        "excerpt": "The blower motor is the next part after the flame starts.",
                    },
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 19,
                        "excerpt": "Remove and replace the water flow sensor.",
                    },
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 12,
                        "excerpt": "General troubleshooting starts with the control board.",
                    },
                ],
                ["water flow", "general troubleshooting"],
            ),
        ]
        for concern, brand, model, category, chunks, banned in cases:
            proc = compile_bay_procedure(
                concern=concern, brand=brand, model=model, category=category, chunks=chunks
            )
            blob = _blob(proc)
            for phrase in banned:
                self.assertNotIn(phrase, blob, (concern, phrase))

    def test_sensor_snippet_cannot_contradict_the_sheet(self):
        proc = compile_bay_procedure(
            concern=(
                "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
                "tires off the ground even though the coach was nearly level."
            ),
            brand="Lippert",
            model="Ground Control 343633",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert Ground Control",
                    "page": 4,
                    "excerpt": "If the fault follows the sensor, replace the sensor.",
                },
                {
                    "title": "Lippert Ground Control",
                    "page": 3,
                    "excerpt": "A communication failure means the controller cannot see the jacks.",
                },
                {
                    "title": "Lippert Ground Control",
                    "page": 2,
                    "excerpt": "Jack Faults Ground Control TT and Ground Control 3.0 1. Follow the chart.",
                },
            ],
        )
        blob = _blob(proc)
        self.assertNotIn("replace the sensor", blob)
        self.assertNotIn("communication failure", blob)
        self.assertNotIn("jack faults", blob)
        self.assertIn("do not swap a level sensor", blob)


class TestInternalNotesStayOffTheSheet(unittest.TestCase):
    def test_firefly_and_fact12_notes_do_not_print(self):
        firefly = compile_bay_procedure(
            concern="Level Up Advantage 807662 Manual Mode flashes then dumps home. Auto Level still works.",
            brand="",
            model="Level Up Advantage 807662",
            category="Leveling",
        )
        fact = compile_bay_procedure(
            concern="Furrion FACT12SA2 rooftop shows E3",
            brand="Furrion",
            model="FACT12SA2",
            category="Air Conditioning",
            chunks=[
                {
                    "title": "Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666",
                    "page": 5,
                    "excerpt": "FACR08HESA2 8K rooftop. Fig. 1 roof opening and base pan.",
                }
            ],
        )
        for proc in (firefly, fact):
            blob = _blob(proc)
            self.assertNotIn("listed in sources only", blob)
            self.assertNotIn("not the model headline", blob)
            self.assertNotIn("only the facr08 book", blob)
            self.assertNotIn("not the fact12", blob)
            self.assertFalse(any(sheet_has_internal_note(src.get("excerpt") or "") for src in proc.sources))
            self.assertFalse(sheet_has_internal_note(proc.primary_cite))
        self.assertIn("ccd-0008666", fact.primary_cite.lower())
        self.assertIn("15", fact.primary_cite)
        self.assertIn("18", fact.primary_cite)
        self.assertNotIn("closest reference", fact.primary_cite.lower())
        self.assertNotIn("resecure", fact.primary_cite.lower())
        self.assertIn("ccd-0008666", _blob(fact))


class TestFiguresAndArrows(unittest.TestCase):
    def test_fig36_is_large_and_the_border_is_not_on_the_last_row(self):
        png = load_oem_figure_png("ccd8122-fig36.png")
        image = Image.open(BytesIO(png)).convert("L")
        width, height = image.size
        self.assertLess(max(image.size), 900)
        bottom = sum(1 for x in range(0, width, 2) if image.getpixel((x, height - 1)) < 80)
        self.assertEqual(bottom, 0)
        # The outer grey frame closes above the padding. A cut crop has no wide bar there.
        grey_rows = [
            y
            for y in range(height)
            if sum(
                1
                for x in range(0, width, 2)
                if 140 <= image.getpixel((x, y)) <= 230
            )
            > width / 8
        ]
        self.assertTrue(grey_rows)
        self.assertLess(grey_rows[-1], height - 8)
        self.assertGreater(grey_rows[-1], height * 0.7)
        proc = compile_bay_procedure(
            concern="icing up on rear wall — only about half from the top down",
            brand="Furrion",
            model="FCR10",
            category="Refrigerators",
        )
        pages = compose_sheet(proc)
        heights = [im.h for page in pages for im in page.images]
        self.assertTrue(heights)
        self.assertGreaterEqual(max(heights), 140.0)
        self.assertLessEqual(len(pages), 3)

    def test_drainage_row_keeps_space_under_the_rule(self):
        proc = compile_bay_procedure(
            concern="FACR08 freeze up interior leak condensate",
            brand="Furrion",
            model="FACR08",
            category="Air Conditioning",
        )
        image = Image.open(BytesIO(proc.figures[0].image_png)).convert("L")
        width, height = image.size
        self.assertGreater(height, 120)
        self.assertLess(height, 180)
        dark_rows = [
            y
            for y in range(height)
            if sum(1 for x in range(0, width, 3) if image.getpixel((x, y)) < 80) > width / 6
        ]
        self.assertTrue(dark_rows)
        self.assertLess(max(dark_rows), height - 3)

    def test_s01_arrowheads_clear_yes_and_no(self):
        proc = compile_bay_procedure(
            concern="FACR08 freeze up interior leak condensate",
            brand="Furrion",
            model="FACR08",
            category="Air Conditioning",
        )
        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        problems = layout_problems(trace)
        self.assertEqual(problems, [])
        labels = [mark.text.strip().upper() for mark in trace if mark.role == "label"]
        self.assertIn("YES", labels)
        self.assertIn("NO", labels)


class TestDashesCitesAndBranches(unittest.TestCase):
    def test_s06_keeps_clause_dashes_and_level_up_cites(self):
        proc = compile_bay_procedure(
            concern="Level Up Advantage 807662 Manual Mode flashes then dumps home. Auto Level still works.",
            brand="",
            model="Level Up Advantage 807662",
            category="Leveling",
        )
        blob = _blob(proc)
        self.assertIn("terminator - leave", blob)
        self.assertIn("onecontrol - unplug", blob)
        self.assertIn("ti-005", blob)
        self.assertIn("qr-092", blob)
        self.assertIn("807662", blob)
        self.assertTrue(proc.sources)
        self.assertTrue(all(src.get("page") == 1 for src in proc.sources))
        self.assertNotIn("1-page tech info", blob)

    def test_expected_pages_are_on_the_sheet(self):
        facr = compile_bay_procedure(
            concern="FACR08 freeze up interior leak condensate",
            brand="Furrion",
            model="FACR08",
            category="Air Conditioning",
        )
        self.assertTrue(any(src.get("page") == 10 and "8666" in (src.get("title") or "") for src in facr.sources))
        coleman = compile_bay_procedure(
            concern="Coleman-Mach 2111-0001 fan high is dead",
            brand="Coleman-Mach",
            model="2111-0001",
            category="Air Conditioning",
            chunks=[
                {
                    "title": "Coleman-Mach Mechanical Controls Service Manual",
                    "page": 8,
                    "excerpt": "On all models, the condenser fan pulls the air through the coil.",
                }
            ],
        )
        titles = " ".join(src.get("title") or "" for src in coleman.sources)
        self.assertIn("1976-536", coleman.primary_cite)
        self.assertIn("1976-603", coleman.primary_cite)
        self.assertIn("1976-695", titles)
        self.assertNotIn("1976-536", titles)
        self.assertNotIn("pulls the air through the coil", _blob(coleman))
        brisk = compile_bay_procedure(
            concern="Dometic B57915 rooftop air conditioner is not cooling.",
            brand="Dometic",
            model="B57915",
            category="Air Conditioning",
        )
        self.assertTrue(
            any("brisk ii" in (src.get("title") or "").lower() and src.get("page") == 23 for src in brisk.sources)
        )
        stab = compile_bay_procedure(
            concern="Front stabilizer jack. Power extend works. Manual override will not engage. The roll pin is broken.",
            brand="",
            model="",
            category="Leveling",
        )
        self.assertEqual(stab.model_line, "Lippert PSX1 front stabilizer")
        self.assertTrue(any(src.get("page") == 7 and "psx1" in (src.get("title") or "").lower() for src in stab.sources))
        self.assertFalse(any(src.get("page") == 11 for src in stab.sources))
        blob = _blob(stab)
        self.assertNotIn("rear stabilizer", blob)
        self.assertNotIn("override-usage pages", blob)
        self.assertNotIn("not the end fix for a destroyed pin", blob)

    def test_s07_no_voltage_branch_replaces_the_board_and_the_fan(self):
        proc = compile_bay_procedure(
            concern="FCR10 E2 fan fault current on the freezer evaporator fan",
            brand="Furrion",
            model="FCR10",
            category="Refrigerators",
        )
        no_node = next(node.text.lower() for node in proc.flowchart.nodes if "pcb and the fan" in node.text.lower())
        self.assertIn("inverter", no_node)
        self.assertIn("fan", no_node)
        self.assertIn("replace the inverter pcb and the fan", proc.pattern_means.lower())
        self.assertIn("replace the inverter pcb and the fan", proc.bay_order[0].lower())


class TestPromptLeak(unittest.TestCase):
    def test_leading_prompt_text_is_stripped(self):
        shop_lines = (
            BAL_TONGUE_PANEL_SHOP_LINE,
            DIAL_OFF_RUN_SHOP_LINE,
            ICE_MOISTURE_SHOP_LINE,
            GROUND_CONTROL_LEVEL_LINE,
        )
        prefixes = (
            "You are an OPEN LIBRARY COACH for Tacoma RV Center techs.\n\n",
            "PRODUCT LOCK\nFollow the card.\n\n",
            "SHOP WORDS: output wire.\n\n",
            "Rules:\n1. Use only the excerpts.\n\n",
            "MANUAL EXCERPTS follow.\n\n",
            "Your previous draft re-asked the fan.\n\n",
            "Category selected: Refrigerators\n\n",
            "Model/system: FCR10\n\n",
            "GROUND CONTROL 343633: zero the jacks.\n\n",
            "DOMETIC B57915 TURNS ON and will not blow cold.\n\n",
        )
        for prefix, shop in zip(prefixes, shop_lines * 3):
            cleaned = strip_leaked_prompt(prefix + shop)
            self.assertFalse(cleaned.lower().startswith(prefix.splitlines()[0].lower()))
            self.assertIn(shop.split(".")[0][:24], cleaned)
        self.assertTrue(strip_leaked_prompt("Do not swap a level sensor.").lower().startswith("do not"))
