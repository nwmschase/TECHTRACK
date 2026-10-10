"""Page-check quotes from the v4.19.16 live sheets must not print.

A Sources line is a complete sentence about this procedure. Table cells,
headings, catalog lines, scan text, and off-topic pages stay off the sheet.
"""
import re
import unittest

from bay_procedure import clean_source_excerpt, compile_bay_procedure


def _excerpts(proc) -> str:
    return " ".join((src.get("excerpt") or "") for src in proc.sources)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


class TestPagecheckQuotes(unittest.TestCase):
    def _sheet(self, concern, brand, model, category, chunks):
        return compile_bay_procedure(
            concern=concern,
            brand=brand,
            model=model,
            category=category,
            chunks=chunks,
        )

    def test_bad_quotes_never_print(self):
        cases = [
            (
                "FACR08HESA2-PS freeze up interior leak condensate",
                "Furrion",
                "FACR08HESA2-PS",
                "Air Conditioning",
                [
                    {
                        "title": "Furrion Chill FACR08 CCD-0007990",
                        "page": 8,
                        "excerpt": (
                            "The nozzles are closed. Rooftop air conditioner Abnormal shutdown "
                            "Freeze sensor has tripped."
                        ),
                    },
                    {
                        "title": "Furrion Chill FACR08 CCD-0007990",
                        "page": 9,
                        "excerpt": "The drain is closed. Not cool enough Refrigerant leakage Contact the dealer.",
                    },
                    {
                        "title": "Furrion Chill FACR08 CCD-0007990",
                        "page": 7,
                        "excerpt": "Furrion Chill drain, base-pan, and freeze-sensor layout.",
                    },
                ],
                [
                    "abnormal shutdown freeze sensor",
                    "not cool enough refrigerant leakage",
                    "freeze-sensor layout",
                ],
            ),
            (
                "Coleman-Mach 2111-0001 ran then went dead. Fan High is dead.",
                "Coleman-Mach",
                "2111-0001",
                "Air Conditioning",
                [
                    {
                        "title": "Coleman-Mach 1976-536",
                        "page": 7,
                        "excerpt": (
                            "Page -7- Figure 3 The following charts show the wiring. "
                            "6799-720 is the board."
                        ),
                    },
                    {
                        "title": "Coleman-Mach catalog",
                        "page": 1,
                        "excerpt": "TITLE: Coleman-Mach 2111 Category: Air Conditioning",
                    },
                ],
                ["page -7- figure", "title: coleman-mach", "category: air"],
            ),
            (
                "temperature dial OFF but compressor still running, freezer frozen solid",
                "Furrion",
                "FCR10",
                "Refrigerators",
                [
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 24,
                        "excerpt": (
                            "Rotate temperature dial to off for 5 minutes "
                            "Ensure refrigerator gets to temperature."
                        ),
                    },
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 44,
                        "excerpt": "Knob removal: remove the knob from the shaft before the thermostat test.",
                    },
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 31,
                        "excerpt": "Open C and T with no jumper. This is the second cite of page 31.",
                    },
                ],
                [
                    "rotate temperature dial to off",
                    "ensure refrigerator gets to temperature",
                    "knob removal",
                    "remove the knob",
                    "second cite of page 31",
                ],
            ),
            (
                "icing up on rear wall — only about half from the top down",
                "Furrion",
                "FCR10",
                "Refrigerators",
                [
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 36,
                        "excerpt": "Ice or Moisture in the Fridge.",
                    },
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 51,
                        "excerpt": "Dollar-bill test around the full perimeter.",
                    },
                ],
                [],
            ),
            (
                "Level Up Advantage 807662 Manual Mode flashes then dumps home. Auto Level still works.",
                "",
                "Level Up Advantage 807662",
                "Leveling",
                [
                    {
                        "title": "Electronic leveling troubleshooting guide",
                        "page": 3,
                        "excerpt": (
                            "ELECTRONIC LEVELING TROUBLESHOOTING GUIDE. The Retract light stays on. "
                            "Set parking break."
                        ),
                    },
                    {
                        "title": "Level Up Advantage",
                        "page": 9,
                        "excerpt": "Leave the terminator plugged and unplug one at a ti",
                    },
                ],
                [
                    "electronic leveling troubleshooting guide",
                    "retract light",
                    "set parking break",
                    "one at a ti",
                ],
            ),
            (
                "FCR10 E2 fan fault current on the freezer evaporator fan",
                "Furrion",
                "FCR10",
                "Refrigerators",
                [
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 18,
                        "excerpt": "Fan quick connection to harness.",
                    },
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 19,
                        "excerpt": "See further information Cycle power to the unit.",
                    },
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 20,
                        "excerpt": "Check the ambient temperature before the fan test.",
                    },
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 33,
                        "excerpt": "Hold a piece of paper at the vent to prove suction.",
                    },
                    {
                        "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                        "page": 40,
                        "excerpt": "Finally, attach the refrigerator to its power source.",
                    },
                ],
                [
                    "fan quick connection to harness",
                    "further information cycle power",
                    "ambient temperature",
                    "piece of paper",
                    "attach the refrigerator to its power source",
                ],
            ),
            (
                "Suburban NT-20SEQT furnace fan comes on then shuts off, no heat",
                "Suburban",
                "NT-20SEQT",
                "Furnaces",
                [
                    {
                        "title": "Suburban furnace service manual",
                        "page": 32,
                        "excerpt": "Check the gas valve and the electrode before the thermostat.",
                    },
                    {
                        "title": "Suburban furnace service manual",
                        "page": 27,
                        "excerpt": "The gas-valve relay closes after pre-purge.",
                    },
                ],
                ["gas valve", "electrode", "pre-purge", "gas-valve relay"],
            ),
            (
                "Dometic B57915 rooftop air conditioner is not cooling.",
                "Dometic",
                "B57915",
                "Air Conditioning",
                [
                    {
                        "title": "Dometic Brisk II",
                        "page": 11,
                        "excerpt": "Select the proper for the specific control system.",
                    },
                    {
                        "title": "Dometic Brisk II",
                        "page": 12,
                        "excerpt": "Check the air box seal before the fan.",
                    },
                    {
                        "title": "Dometic Brisk II",
                        "page": 14,
                        "excerpt": "The heat-pump defrost cycle is running.",
                    },
                    {
                        "title": "Dometic Comfort Control",
                        "page": 2,
                        "excerpt": "Comfort Control 2 shows the setpoint.",
                    },
                ],
                [
                    "the proper for the specific",
                    "air box seal",
                    "heat-pump defrost",
                    "comfort control 2",
                ],
            ),
            (
                "Lippert Ground Control 5th-wheel leveling: auto-level lifts the driver-side "
                "tires off the ground even though the coach was nearly level.",
                "Lippert",
                "Ground Control 343633",
                "Leveling",
                [
                    {
                        "title": "Lippert Ground Control",
                        "page": 8,
                        "excerpt": "Measure voltage at the sensor port before leveling.",
                    },
                    {
                        "title": "Lippert Ground Control",
                        "page": 9,
                        "excerpt": "Remove solar contribution and re-test.",
                    },
                    {
                        "title": "Lippert Ground Control",
                        "page": 10,
                        "excerpt": "The crossed harness swaps the jacks.",
                    },
                ],
                [
                    "voltage at the sensor",
                    "sensor port",
                    "remove solar contribution",
                    "crossed harness",
                ],
            ),
            (
                "Girard GSWH-2 tankless water heater shows E8.",
                "Girard",
                "GSWH-2",
                "Water Heaters",
                [
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 14,
                        "excerpt": "Check the wire CN1 wire at the board.",
                    },
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 16,
                        "excerpt": "E0 means the outlet probe is open.",
                    },
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 18,
                        "excerpt": "The blower PWM signal is missing.",
                    },
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 4,
                        "excerpt": "Do NOT try to adjust or repair the unit yourself.",
                    },
                    {
                        "title": "Girard GSWH-2 CCD-0009390",
                        "page": 5,
                        "excerpt": "This could occur for a number of reasons.",
                    },
                ],
                [
                    "check the wire cn1 wire",
                    "outlet probe",
                    "blower pwm",
                    "repair the unit yourself",
                    "number of reasons",
                ],
            ),
            (
                "Front stabilizer jack. Power extend works. Manual override will not engage. The roll pin is broken.",
                "",
                "",
                "Leveling",
                [
                    {
                        "title": "Lippert rear stabilizer",
                        "page": 11,
                        "excerpt": (
                            "Lippert PSX1 override-usage pages (including p.7) are for using the override, "
                            "not the end fix for a destroyed pin."
                        ),
                    }
                ],
                [
                    "override-usage",
                    "not the end fix for a destroyed pin",
                ],
            ),
        ]
        for concern, brand, model, category, chunks, banned in cases:
            proc = self._sheet(concern, brand, model, category, chunks)
            blob = _norm(_excerpts(proc))
            for phrase in banned:
                self.assertNotIn(phrase, blob, (concern[:40], phrase, blob[:240]))

    def test_s04_cites_page_31_once(self):
        proc = self._sheet(
            "temperature dial OFF but compressor still running, freezer frozen solid",
            "Furrion",
            "FCR10",
            "Refrigerators",
            [
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 31,
                    "excerpt": "Leave the dial fully OFF and open C and T with no jumper.",
                },
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 31,
                    "excerpt": "A second title for the same thermostat page must not print again.",
                },
            ],
        )
        pages = [src.get("page") for src in proc.sources]
        self.assertEqual(pages.count(31), 1)

    def test_s05_heading_and_verbless_line_are_not_quotes(self):
        proc = self._sheet(
            "icing up on rear wall — only about half from the top down",
            "Furrion",
            "FCR10",
            "Refrigerators",
            [
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 12,
                    "excerpt": "Ice or Moisture in the Fridge.",
                },
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 13,
                    "excerpt": "Dollar-bill test around the full perimeter.",
                },
            ],
        )
        excerpts = [(src.get("excerpt") or "").strip() for src in proc.sources]
        for excerpt in excerpts:
            self.assertNotEqual(excerpt.lower(), "ice or moisture in the fridge.")
            self.assertNotEqual(excerpt.lower(), "dollar-bill test around the full perimeter.")
            self.assertNotIn("ice or moisture in the fridge.", excerpt.lower())
        joined = " ".join(excerpts).lower()
        self.assertNotIn("dollar-bill", joined)
        self.assertIn("dollar-bill", " ".join(proc.bay_order).lower())
        self.assertIn("check the door gasket", " ".join(proc.bay_order).lower())

    def test_scanned_range_collapses_to_a_hyphen(self):
        cleaned = clean_source_excerpt("Set the dial to about 4 -5 and dry the cavity overnight.")
        self.assertIn("4-5", cleaned)
        self.assertNotIn("4 -5", cleaned)

    def test_s01_model_uses_the_named_facr_token(self):
        named = self._sheet(
            "FACR08HESA2-PS freeze up interior leak condensate",
            "Furrion",
            "Furrion Chill rooftop unit",
            "Air Conditioning",
            [],
        )
        self.assertEqual(named.model_line, "FACR08HESA2-PS")
        plain = self._sheet(
            "FACR08 freeze up interior leak condensate",
            "Furrion",
            "FACR08",
            "Air Conditioning",
            [],
        )
        self.assertEqual(plain.model_line, "Furrion Chill rooftop unit")

    def test_s08_yes_branch_ends(self):
        proc = self._sheet(
            "Suburban NT-20SEQT furnace fan comes on then shuts off, no heat",
            "Suburban",
            "NT-20SEQT",
            "Furnaces",
            [
                {
                    "title": "Suburban furnace service manual",
                    "page": 32,
                    "excerpt": "Check the gas valve and the electrode before the thermostat.",
                }
            ],
        )
        ends = [node.text for node in proc.flowchart.nodes if node.kind == "end"]
        self.assertTrue(any("end of this prove" in text.lower() for text in ends))
        self.assertNotIn("gas valve", _norm(_excerpts(proc)))
        self.assertNotIn("32", proc.primary_cite)

    def test_s04_do_not_is_a_sentence(self):
        proc = self._sheet(
            "temperature dial OFF but compressor still running, freezer frozen solid",
            "Furrion",
            "FCR10",
            "Refrigerators",
            [],
        )
        joined = " ".join(proc.do_not)
        self.assertIn("do not run a 12V continuity check", joined)
        self.assertNotIn("fuse or a 12V continuity check", joined)

    def test_s14_cites_lippert_page_11_without_the_override_note(self):
        proc = self._sheet(
            "Front stabilizer jack. Power extend works. Manual override will not engage. The roll pin is broken.",
            "",
            "",
            "Leveling",
            [
                {
                    "title": "Lippert rear stabilizer manual",
                    "page": 11,
                    "excerpt": "Replace the rear stabilizer when the pin is sheared.",
                }
            ],
        )
        blob = _norm(" ".join([proc.pattern_means, _excerpts(proc)] + [s.get("title") or "" for s in proc.sources]))
        self.assertNotIn("override-usage", blob)
        self.assertIn("11", " ".join(str(s.get("page")) for s in proc.sources))
        self.assertIn("rear stabilizer", blob)

    def test_s15_cites_page_4_and_figs_3_4(self):
        proc = self._sheet(
            "Suburban SDN2U cooktop. Burner goes out with a pan on. The thermocouple tip sits low and gets pushed.",
            "Suburban",
            "SDN2U",
            "Cooktops",
            [],
        )
        blob = _norm(proc.primary_cite + " " + _excerpts(proc) + " " + proc.pattern_means)
        self.assertIn("page 4", blob)
        self.assertIn("figs. 3-4", blob)
        self.assertIn("thermocouple", blob)
        self.assertNotIn("reposition the thermocouple tip", _excerpts(proc).lower())
